from django.db import models
from django.conf import settings


class ChatMessage(models.Model):
    """Сообщение в чате с ИИ-консультантом."""
    
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('assistant', 'Консультант'),
    ]
    
    # Опциональная связь с User (для будущей регистрации)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        null=True,
        blank=True
    )
    
    # Session ID для идентификации без авторизации
    session_id = models.CharField(
        max_length=36,
        db_index=True,
        verbose_name='ID сессии'
    )
    
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        verbose_name='Роль'
    )
    
    content = models.TextField(
        verbose_name='Содержание сообщения'
    )
    
    # Опционально: привязка к портфелю
    portfolio = models.ForeignKey(
        'portfolios.Portfolio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Сообщение чата'
        verbose_name_plural = 'Сообщения чата'
        ordering = ['created_at']
    
    def __str__(self):
        return f'{self.role}: {self.content[:50]}...'
