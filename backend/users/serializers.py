from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import InvestorProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации пользователя."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password_confirm')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password': 'Пароли не совпадают.'
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения пользователя."""
    
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'date_joined')
        read_only_fields = ('id', 'date_joined')


class InvestorProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для профиля инвестора."""
    
    class Meta:
        model = InvestorProfile
        fields = (
            'id',
            'name',
            'investment_horizon',
            'investment_amount',
            'max_drawdown',
            'needs_liquidity',
            'experience_level',
            'use_dca',
            'dca_parts',
            'use_default_portfolio',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Имя обязательно.')
        
        # Проверка на уникальность (исключая текущий профиль при обновлении)
        instance = getattr(self, 'instance', None)
        if InvestorProfile.objects.filter(name__iexact=value.strip()).exclude(
            pk=instance.pk if instance else None
        ).exists():
            raise serializers.ValidationError(
                'Пользователь с таким именем уже существует. '
                'Пожалуйста, выберите другое имя или добавьте фамилию.'
            )
        return value.strip()
    
    def validate_investment_horizon(self, value):
        if not 1 <= value <= 7:
            raise serializers.ValidationError(
                'Горизонт инвестирования должен быть от 1 до 7 лет.'
            )
        return value
    
    def validate_investment_amount(self, value):
        if value < 1000:
            raise serializers.ValidationError(
                'Минимальная сумма инвестиций — $1,000.'
            )
        if value > 50000:
            raise serializers.ValidationError(
                'Максимальная сумма инвестиций — $50,000.'
            )
        return value
    
    def validate_max_drawdown(self, value):
        if not 5 <= value <= 50:
            raise serializers.ValidationError(
                'Допустимая просадка должна быть от 5% до 50%.'
            )
        return value
    
    def validate_dca_parts(self, value):
        if value is not None and not 3 <= value <= 6:
            raise serializers.ValidationError(
                'Количество частей DCA должно быть от 3 до 6.'
            )
        return value
    
    def validate(self, attrs):
        # Если используется DCA, должно быть указано количество частей
        if attrs.get('use_dca') and not attrs.get('dca_parts'):
            attrs['dca_parts'] = 3  # По умолчанию 3 части
        return attrs
