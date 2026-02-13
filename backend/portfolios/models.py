from django.db import models
from django.conf import settings


class Portfolio(models.Model):
    """Инвестиционный портфель пользователя."""
    
    # Опциональная связь с User (для будущей регистрации)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='portfolios',
        null=True,
        blank=True
    )
    
    # Session ID для идентификации без авторизации
    session_id = models.CharField(
        max_length=36,
        db_index=True,
        verbose_name='ID сессии'
    )
    
    name = models.CharField(
        max_length=100,
        default='Мой портфель',
        verbose_name='Название портфеля'
    )
    
    initial_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Начальная сумма ($)'
    )
    
    start_date = models.DateField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    target_years = models.IntegerField(
        verbose_name='Горизонт инвестирования (лет)'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Портфель'
        verbose_name_plural = 'Портфели'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.user:
            return f'{self.name} ({self.user.email})'
        return f'{self.name} (сессия: {self.session_id[:8]}...)'
    
    @property
    def target_date(self):
        """Целевая дата завершения стратегии."""
        from datetime import timedelta
        return self.start_date + timedelta(days=self.target_years * 365)


class PortfolioAsset(models.Model):
    """Актив в портфеле."""
    
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='assets'
    )
    
    symbol = models.CharField(
        max_length=10,
        verbose_name='Символ актива'
    )
    
    name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Название актива'
    )
    
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Доля в портфеле (%)'
    )
    
    # Цена на момент покупки (для расчёта прибыли/убытка)
    initial_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='Цена при покупке ($)'
    )
    
    # Количество единиц актива (для учёта нескольких взносов по разным ценам)
    units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='Количество единиц'
    )
    
    class Meta:
        verbose_name = 'Актив портфеля'
        verbose_name_plural = 'Активы портфеля'
        unique_together = ['portfolio', 'symbol']
    
    def __str__(self):
        return f'{self.symbol} ({self.percentage}%)'
    
    @property
    def initial_value(self):
        """Начальная стоимость актива в портфеле."""
        return float(self.portfolio.initial_amount) * float(self.percentage) / 100


class PortfolioContribution(models.Model):
    """Взнос в портфель (дополнительная покупка по DCA)."""
    
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма взноса ($)'
    )
    
    contributed_at = models.DateField(
        auto_now_add=True,
        verbose_name='Дата взноса'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Взнос в портфель'
        verbose_name_plural = 'Взносы в портфель'
        ordering = ['contributed_at']
    
    def __str__(self):
        return f'{self.amount} ({self.contributed_at})'


class PortfolioWithdrawal(models.Model):
    """Вывод средств из портфеля (не считается просадкой)."""
    
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='withdrawals'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма вывода ($)'
    )
    
    withdrawn_at = models.DateField(
        auto_now_add=True,
        verbose_name='Дата вывода'
    )
    
    # Стоимость портфеля после вывода — база для расчёта просадки
    value_after = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Стоимость портфеля после вывода ($)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Вывод из портфеля'
        verbose_name_plural = 'Выводы из портфеля'
        ordering = ['-withdrawn_at']
    
    def __str__(self):
        return f'{self.amount} ({self.withdrawn_at})'


# Базовый портфель по умолчанию
DEFAULT_PORTFOLIO_ASSETS = [
    {'symbol': 'BTC', 'name': 'Bitcoin', 'percentage': 50.0},
    {'symbol': 'ETH', 'name': 'Ethereum', 'percentage': 25.0},
    {'symbol': 'BNB', 'name': 'Binance Coin', 'percentage': 7.5},
    {'symbol': 'SOL', 'name': 'Solana', 'percentage': 7.5},
    {'symbol': 'USDT', 'name': 'Tether', 'percentage': 10.0},
]
