from rest_framework import serializers
from .models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    """Сериализатор для сообщения чата."""
    
    class Meta:
        model = ChatMessage
        fields = ('id', 'role', 'content', 'created_at')
        read_only_fields = ('id', 'role', 'created_at')


class ChatInputSerializer(serializers.Serializer):
    """Сериализатор для входящего сообщения."""
    message = serializers.CharField(
        max_length=2000,
        help_text='Сообщение для консультанта. Поддерживает быстрые команды: /status, /risk, /market и др.'
    )
    
    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError('Сообщение не может быть пустым.')
        return value.strip()


class ChatResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа консультанта."""
    response = serializers.CharField()
    user_message = ChatMessageSerializer()
    assistant_message = ChatMessageSerializer()


class DrawdownAlertSerializer(serializers.Serializer):
    """Сериализатор для алерта о просадке."""
    alert = serializers.BooleanField()
    level = serializers.ChoiceField(
        choices=['warning', 'critical'],
        required=False
    )
    message = serializers.CharField()
    current_drawdown = serializers.FloatField(required=False)
    max_drawdown = serializers.FloatField(required=False)


class RiskAnalysisSerializer(serializers.Serializer):
    """Сериализатор для анализа рисков."""
    risk_level = serializers.ChoiceField(
        choices=['low', 'medium', 'elevated', 'high']
    )
    risk_label = serializers.CharField()
    risk_emoji = serializers.CharField()
    current_drawdown = serializers.FloatField()
    max_allowed_drawdown = serializers.FloatField()
    drawdown_usage = serializers.FloatField()
    portfolio_value = serializers.FloatField()
    profit_loss_percent = serializers.FloatField()
    days_active = serializers.IntegerField()
    recommendations = serializers.ListField(
        child=serializers.CharField()
    )


class QuickCommandSerializer(serializers.Serializer):
    """Сериализатор для быстрой команды."""
    command = serializers.CharField()
    slash_command = serializers.CharField()
    description = serializers.CharField()
