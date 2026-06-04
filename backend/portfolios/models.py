from decimal import Decimal

from django.db import models
from django.conf import settings


class Portfolio(models.Model):
    """Инвестиционный портфель пользователя."""

    CURRENCY_USD = 'USD'
    CURRENCY_EUR = 'EUR'
    CURRENCY_CHOICES = [
        (CURRENCY_USD, 'Доллар США (USD)'),
        (CURRENCY_EUR, 'Евро (EUR)'),
    ]

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

    base_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_USD,
        verbose_name='Базовая валюта для P&L по фиату',
    )

    manual_usd_eur_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name='Ручной курс USD→EUR для фиатного P&L',
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

    is_imported = models.BooleanField(
        default=False,
        verbose_name='Импортирован пользователем'
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

    is_recommended = models.BooleanField(
        default=True,
        verbose_name='Входит в рекомендуемый ТОП-10'
    )

    purchased_at = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата покупки'
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


class PortfolioContributionItem(models.Model):
    """Детализация взноса по конкретной монете (для режима «по монетам»)."""

    contribution = models.ForeignKey(
        'PortfolioContribution',
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Взнос'
    )

    symbol = models.CharField(
        max_length=10,
        verbose_name='Символ актива'
    )

    units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Количество единиц'
    )

    purchase_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Цена покупки ($)'
    )

    value_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Сумма позиции ($)'
    )

    class Meta:
        verbose_name = 'Позиция взноса'
        verbose_name_plural = 'Позиции взносов'

    def __str__(self):
        return f'{self.units} {self.symbol} @ ${self.purchase_price}'


class PortfolioSwap(models.Model):
    """Обмен одного актива портфеля на другой (внутренняя операция, без cash-in/out).

    Swap всегда происходит внутри одного кошелька: from_symbol списывается и
    to_symbol зачисляется на один и тот же ``wallet`` (см. PLAN06 — Агент 12).
    Поле ``wallet`` оставлено nullable для исторических записей, созданных до
    появления модели Wallet.
    """

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='swaps',
        verbose_name='Портфель'
    )

    wallet = models.ForeignKey(
        'Wallet',
        on_delete=models.SET_NULL,
        related_name='swaps',
        null=True,
        blank=True,
        verbose_name='Кошелёк'
    )

    from_symbol = models.CharField(
        max_length=10,
        verbose_name='Из (символ)'
    )

    from_units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Из (количество)'
    )

    from_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Из (цена $)'
    )

    to_symbol = models.CharField(
        max_length=10,
        verbose_name='В (символ)'
    )

    to_units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='В (количество)'
    )

    to_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='В (цена $)'
    )

    to_units_expected = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name='Ожидаемое количество по рынку'
    )

    fee_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Комиссия / разница ($)'
    )

    note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Комментарий'
    )

    swapped_at = models.DateField(
        auto_now_add=True,
        verbose_name='Дата обмена'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Обмен активов'
        verbose_name_plural = 'Обмены активов'
        ordering = ['-swapped_at']

    def __str__(self):
        return f'{self.from_units} {self.from_symbol} → {self.to_units} {self.to_symbol}'


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


class Wallet(models.Model):
    """Кошелёк портфеля (биржа, холодный/горячий, банковский счёт и т.д.)."""

    TYPE_EXCHANGE = 'exchange'
    TYPE_HOT = 'hot'
    TYPE_COLD = 'cold'
    TYPE_BANK = 'bank'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_EXCHANGE, 'Биржа'),
        (TYPE_HOT, 'Горячий кошелёк'),
        (TYPE_COLD, 'Холодный кошелёк'),
        (TYPE_BANK, 'Банковский счёт'),
        (TYPE_OTHER, 'Другое'),
    ]

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='wallets',
        verbose_name='Портфель'
    )

    name = models.CharField(
        max_length=100,
        verbose_name='Название кошелька'
    )

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_OTHER,
        verbose_name='Тип кошелька'
    )

    is_default = models.BooleanField(
        default=False,
        verbose_name='Кошелёк по умолчанию'
    )

    note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Комментарий'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Кошелёк'
        verbose_name_plural = 'Кошельки'
        unique_together = ['portfolio', 'name']
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'


class WalletHolding(models.Model):
    """Баланс актива на конкретном кошельке (только units, без цены покупки)."""

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='holdings',
        verbose_name='Кошелёк'
    )

    symbol = models.CharField(
        max_length=10,
        verbose_name='Символ актива'
    )

    units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Количество единиц'
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Баланс на кошельке'
        verbose_name_plural = 'Балансы на кошельках'
        unique_together = ['wallet', 'symbol']

    def __str__(self):
        return f'{self.units} {self.symbol} @ {self.wallet.name}'


class WalletTransfer(models.Model):
    """Перевод актива между кошельками портфеля (внутреннее перемещение)."""

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='wallet_transfers',
        verbose_name='Портфель'
    )

    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transfers_out',
        verbose_name='Откуда (кошелёк)'
    )

    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transfers_in',
        verbose_name='Куда (кошелёк)'
    )

    symbol = models.CharField(
        max_length=10,
        verbose_name='Символ актива'
    )

    from_units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Списано (количество)'
    )

    to_units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Зачислено (количество)'
    )

    fee_units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='Комиссия (в единицах актива)'
    )

    fee_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Комиссия ($)'
    )

    occurred_on = models.DateField(
        verbose_name='Дата перевода'
    )

    note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Комментарий'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Перевод между кошельками'
        verbose_name_plural = 'Переводы между кошельками'
        ordering = ['-occurred_on', '-created_at']
        indexes = [
            models.Index(fields=['portfolio', 'occurred_on']),
        ]

    def __str__(self):
        return (
            f'{self.from_units} {self.symbol}: '
            f'{self.from_wallet.name} → {self.to_wallet.name} ({self.occurred_on})'
        )


class HoldingAdjustment(models.Model):
    """Ручная корректировка баланса WalletHolding (комиссии сети, сверка, ошибки ввода и т.д.)."""

    REASON_NETWORK_FEE = 'network_fee'
    REASON_EXCHANGE_FEE = 'exchange_fee'
    REASON_RECONCILIATION = 'reconciliation'
    REASON_INPUT_ERROR = 'input_error'
    REASON_OTHER = 'other'

    REASON_CHOICES = [
        (REASON_NETWORK_FEE, 'Комиссия сети'),
        (REASON_EXCHANGE_FEE, 'Комиссия биржи'),
        (REASON_RECONCILIATION, 'Сверка баланса'),
        (REASON_INPUT_ERROR, 'Исправление ошибки ввода'),
        (REASON_OTHER, 'Другое'),
    ]

    holding = models.ForeignKey(
        WalletHolding,
        on_delete=models.CASCADE,
        related_name='adjustments',
        verbose_name='Баланс на кошельке'
    )

    units_before = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Баланс до (количество)'
    )

    units_after = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Баланс после (количество)'
    )

    delta = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name='Изменение (units_after - units_before)'
    )

    value_delta_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name='Изменение стоимости ($)'
    )

    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        default=REASON_OTHER,
        verbose_name='Причина'
    )

    note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Комментарий'
    )

    occurred_on = models.DateField(
        verbose_name='Дата корректировки'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Корректировка баланса'
        verbose_name_plural = 'Корректировки балансов'
        ordering = ['-occurred_on', '-created_at']
        indexes = [
            models.Index(fields=['holding', 'occurred_on']),
        ]

    def __str__(self):
        return (
            f'{self.holding.symbol} @ {self.holding.wallet.name}: '
            f'{self.units_before} → {self.units_after} ({self.get_reason_display()})'
        )


class FiatCashFlow(models.Model):
    """Фиатное движение средств по портфелю (USD/EUR).

    Используется ТОЛЬКО для расчёта прибыли/убытка на dashboard.
    НЕ связано с Portfolio.initial_amount/PortfolioContribution/
    PortfolioWithdrawal — те остаются для DCA/onboarding-механик.
    """

    KIND_DEPOSIT = 'deposit'
    KIND_WITHDRAWAL = 'withdrawal'
    KIND_CHOICES = [
        (KIND_DEPOSIT, 'Внесение фиата'),
        (KIND_WITHDRAWAL, 'Вывод фиата'),
    ]

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='fiat_cash_flows',
        verbose_name='Портфель',
    )
    kind = models.CharField(
        max_length=12,
        choices=KIND_CHOICES,
        verbose_name='Тип операции',
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Сумма',
    )
    currency = models.CharField(
        max_length=3,
        choices=Portfolio.CURRENCY_CHOICES,
        verbose_name='Валюта операции',
    )
    fx_rate_to_base = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name='Курс currency → portfolio.base_currency',
    )
    occurred_on = models.DateField(verbose_name='Дата операции')
    note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Комментарий',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Фиатное движение'
        verbose_name_plural = 'Фиатные движения'
        ordering = ['-occurred_on', '-created_at']
        indexes = [
            models.Index(fields=['portfolio', 'kind', 'occurred_on']),
        ]

    @property
    def amount_in_base(self) -> Decimal:
        return (self.amount or Decimal('0')) * (self.fx_rate_to_base or Decimal('1'))

    def __str__(self):
        return f'{self.get_kind_display()} {self.amount} {self.currency} ({self.occurred_on})'


# Базовый портфель по умолчанию
DEFAULT_PORTFOLIO_ASSETS = [
    {'symbol': 'BTC', 'name': 'Bitcoin', 'percentage': 50.0},
    {'symbol': 'ETH', 'name': 'Ethereum', 'percentage': 25.0},
    {'symbol': 'BNB', 'name': 'Binance Coin', 'percentage': 7.5},
    {'symbol': 'SOL', 'name': 'Solana', 'percentage': 7.5},
    {'symbol': 'USDT', 'name': 'Tether', 'percentage': 10.0},
]
