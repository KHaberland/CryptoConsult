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


# Ограничения по уровням опыта инвестора
EXPERIENCE_LEVEL_LIMITS = {
    'beginner': {'max_amount': 5000, 'max_horizon': 3, 'dca_parts_min': 3, 'dca_parts_max': 3, 'max_drawdown': 10},
    'some': {'max_amount': 7000, 'max_horizon': 4, 'dca_parts_min': 4, 'dca_parts_max': 4, 'max_drawdown': 30},
    'medium': {'max_amount': 15000, 'max_horizon': 5, 'dca_parts_min': 4, 'dca_parts_max': 5},
    'advanced': {'max_amount': 50000, 'max_horizon': 7, 'dca_parts_min': 5, 'dca_parts_max': 6},
}


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
        experience_level = attrs.get('experience_level')
        if experience_level is None and self.instance:
            experience_level = self.instance.experience_level
        # Если используется DCA, должно быть указано количество частей
        if attrs.get('use_dca') and not attrs.get('dca_parts'):
            if experience_level and experience_level in EXPERIENCE_LEVEL_LIMITS:
                attrs['dca_parts'] = EXPERIENCE_LEVEL_LIMITS[experience_level]['dca_parts_min']
            else:
                attrs['dca_parts'] = 3
        # Уровень «some»: DCA жёстко 4 части, без возможности изменения
        if experience_level == 'some':
            attrs['use_dca'] = True
            attrs['dca_parts'] = 4
        if experience_level and experience_level in EXPERIENCE_LEVEL_LIMITS:
            limits = EXPERIENCE_LEVEL_LIMITS[experience_level]
            horizon = attrs.get('investment_horizon')
            if horizon is None and self.instance:
                horizon = self.instance.investment_horizon
            if horizon is not None and horizon > limits['max_horizon']:
                raise serializers.ValidationError({
                    'investment_horizon': f'Для вашего уровня опыта максимальный горизонт — {limits["max_horizon"]} лет.'
                })
            amount = attrs.get('investment_amount')
            if amount is None and self.instance:
                amount = self.instance.investment_amount
            if amount is not None and amount > limits['max_amount']:
                raise serializers.ValidationError({
                    'investment_amount': f'Для вашего уровня опыта максимальная сумма — ${limits["max_amount"]:,}.'
                })
            dca_parts = attrs.get('dca_parts')
            if dca_parts is None and self.instance:
                dca_parts = self.instance.dca_parts
            if dca_parts is not None and dca_parts not in range(limits['dca_parts_min'], limits['dca_parts_max'] + 1):
                raise serializers.ValidationError({
                    'dca_parts': f'Для вашего уровня опыта допустимо {limits["dca_parts_min"]}–{limits["dca_parts_max"]} частей.'
                })
            max_drawdown_limit = limits.get('max_drawdown')
            if max_drawdown_limit is not None:
                drawdown = attrs.get('max_drawdown')
                if drawdown is None and self.instance:
                    drawdown = self.instance.max_drawdown
                if drawdown is not None and drawdown > max_drawdown_limit:
                    raise serializers.ValidationError({
                        'max_drawdown': f'Для вашего уровня опыта максимальная просадка — {max_drawdown_limit}%.'
                    })
        return attrs
