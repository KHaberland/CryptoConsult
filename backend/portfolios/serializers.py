from rest_framework import serializers
from .models import Portfolio, PortfolioAsset, PortfolioContribution, DEFAULT_PORTFOLIO_ASSETS
from .services import PriceService


class PortfolioAssetSerializer(serializers.ModelSerializer):
    """Сериализатор для актива портфеля."""
    initial_value = serializers.ReadOnlyField()
    
    class Meta:
        model = PortfolioAsset
        fields = (
            'id',
            'symbol',
            'name',
            'percentage',
            'initial_price',
            'initial_value',
        )
        read_only_fields = ('id', 'initial_value')


class PortfolioSerializer(serializers.ModelSerializer):
    """Сериализатор для портфеля."""
    assets = PortfolioAssetSerializer(many=True, read_only=True)
    target_date = serializers.ReadOnlyField()
    
    class Meta:
        model = Portfolio
        fields = (
            'id',
            'name',
            'initial_amount',
            'start_date',
            'target_years',
            'target_date',
            'is_active',
            'assets',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'start_date', 'target_date', 'created_at', 'updated_at')


class PortfolioCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания портфеля."""
    use_default_assets = serializers.BooleanField(default=True, write_only=True)
    custom_assets = PortfolioAssetSerializer(many=True, required=False, write_only=True)
    experience_level = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Portfolio
        fields = (
            'name',
            'initial_amount',
            'target_years',
            'use_default_assets',
            'custom_assets',
            'experience_level',
        )

    def validate_initial_amount(self, value):
        if value < 1000:
            raise serializers.ValidationError(
                'Минимальная сумма инвестиций — $1,000.'
            )
        return value

    def validate_target_years(self, value):
        if not 1 <= value <= 7:
            raise serializers.ValidationError(
                'Горизонт инвестирования должен быть от 1 до 7 лет.'
            )
        return value

    def validate_custom_assets(self, value):
        if value:
            total_percentage = sum(asset['percentage'] for asset in value)
            if abs(total_percentage - 100) > 0.01:
                raise serializers.ValidationError(
                    f'Сумма долей должна равняться 100%. Текущая сумма: {total_percentage}%'
                )
            for asset in value:
                if not PriceService.is_symbol_supported(asset.get('symbol', '')):
                    raise serializers.ValidationError(
                        f"Символ '{asset.get('symbol')}' не поддерживается. "
                        f"Доступные: {', '.join(PriceService.get_supported_symbols())}"
                    )
        return value

    def create(self, validated_data):
        use_default = validated_data.pop('use_default_assets', True)
        custom_assets = validated_data.pop('custom_assets', None)
        experience_level = (validated_data.pop('experience_level', '') or '').strip().lower()

        session_id = validated_data.get('session_id')
        if not session_id:
            raise ValueError("session_id is required")

        portfolio = Portfolio.objects.create(**validated_data)
        price_service = PriceService()

        if experience_level == 'beginner':
            assets_to_add = price_service.get_beginner_portfolio_assets()
        elif use_default or not custom_assets:
            assets_to_add = DEFAULT_PORTFOLIO_ASSETS
        else:
            assets_to_add = custom_assets

        symbols = [a.get('symbol') or a['symbol'] for a in assets_to_add]
        need_prices = not any(a.get('initial_price') is not None for a in assets_to_add)
        current_prices = price_service.get_prices(symbols) if need_prices else {}

        for asset_data in assets_to_add:
            symbol = asset_data.get('symbol') or asset_data['symbol']
            initial_price = asset_data.get('initial_price')
            if initial_price is None:
                initial_price = current_prices.get(symbol)
            initial_price = initial_price or 0

            # Рассчитываем units для учёта взносов
            pct = float(asset_data['percentage'])
            asset_value = float(validated_data['initial_amount']) * pct / 100
            units = (asset_value / initial_price) if initial_price else 0

            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol=symbol,
                name=asset_data.get('name', symbol),
                percentage=asset_data['percentage'],
                initial_price=initial_price,
                units=units
            )

        return portfolio


class PortfolioValueSerializer(serializers.Serializer):
    """Сериализатор для отображения текущей стоимости портфеля."""
    total_value = serializers.FloatField()
    initial_value = serializers.FloatField()
    profit_loss = serializers.FloatField()
    profit_loss_percent = serializers.FloatField()
    start_date = serializers.DateField()
    target_date = serializers.DateField()
    days_remaining = serializers.IntegerField()
    assets = serializers.ListField()


# ============ Сериализаторы для цен ============

class PriceSerializer(serializers.Serializer):
    """Сериализатор для цены актива."""
    symbol = serializers.CharField()
    price = serializers.FloatField()


class PriceWithChangeSerializer(serializers.Serializer):
    """Сериализатор для цены с изменением за 24ч."""
    symbol = serializers.CharField()
    price = serializers.FloatField()
    change_24h = serializers.FloatField()


class MarketDataSerializer(serializers.Serializer):
    """Сериализатор для рыночных данных."""
    symbol = serializers.CharField()
    price = serializers.FloatField()
    market_cap = serializers.FloatField()
    volume_24h = serializers.FloatField()
    change_24h = serializers.FloatField()
    change_7d = serializers.FloatField()
    change_30d = serializers.FloatField()
    high_24h = serializers.FloatField()
    low_24h = serializers.FloatField()
    ath = serializers.FloatField()
    ath_change_percentage = serializers.FloatField()


class HistoricalPriceSerializer(serializers.Serializer):
    """Сериализатор для исторической цены."""
    date = serializers.IntegerField()  # timestamp
    price = serializers.FloatField()


class SupportedAssetsSerializer(serializers.Serializer):
    """Сериализатор для списка поддерживаемых активов."""
    symbols = serializers.ListField(child=serializers.CharField())
