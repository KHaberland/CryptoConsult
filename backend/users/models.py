from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Кастомная модель пользователя."""
    email = models.EmailField(unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
    
    def __str__(self):
        return self.email


class InvestorProfile(models.Model):
    """Профиль инвестора с ответами на анкету."""
    
    EXPERIENCE_CHOICES = [
        ('beginner', 'Новичок'),
        ('some', 'Немного опыта'),
        ('medium', 'Средний опыт'),
        ('advanced', 'Продвинутый'),
    ]
    
    # Опциональная связь с User (для будущей регистрации)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='investor_profile',
        null=True,
        blank=True
    )
    
    # Session ID для идентификации без авторизации
    session_id = models.CharField(
        max_length=36,
        unique=True,
        db_index=True,
        verbose_name='ID сессии'
    )
    
    # Имя пользователя для MVP-идентификации
    name = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Имя пользователя'
    )
    
    # Вопрос 1: Горизонт инвестирования (1-7 лет)
    investment_horizon = models.IntegerField(
        verbose_name='Горизонт инвестирования (лет)',
        help_text='От 1 до 7 лет'
    )
    
    # Вопрос 2: Сумма инвестирования
    investment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма инвестиций ($)',
        help_text='От $1,000 до $50,000'
    )
    
    # Вопрос 3: Допустимая просадка (%)
    max_drawdown = models.IntegerField(
        verbose_name='Допустимая просадка (%)',
        help_text='От 5% до 50%'
    )
    
    # Вопрос 4: Нужна ли ликвидность
    needs_liquidity = models.BooleanField(
        default=False,
        verbose_name='Нужна возможность быстрого вывода'
    )
    
    # Вопрос 5: Уровень опыта
    experience_level = models.CharField(
        max_length=20,
        choices=EXPERIENCE_CHOICES,
        default='beginner',
        verbose_name='Уровень опыта'
    )
    
    # Вопрос 7: Использовать DCA
    use_dca = models.BooleanField(
        default=True,
        verbose_name='Использовать DCA (вход частями)'
    )
    
    # Количество частей для DCA (3-6)
    dca_parts = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Количество частей DCA',
        help_text='От 3 до 6 частей'
    )
    
    # Вопрос 8: Использовать базовый портфель
    use_default_portfolio = models.BooleanField(
        default=True,
        verbose_name='Использовать базовый портфель'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Профиль инвестора'
        verbose_name_plural = 'Профили инвесторов'
    
    def __str__(self):
        if self.user:
            return f'Профиль {self.user.email}'
        return f'Профиль {self.name}'
