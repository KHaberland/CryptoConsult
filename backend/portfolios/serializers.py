from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import serializers
from .models import (
    Portfolio,
    PortfolioAsset,
    PortfolioContribution,
    DEFAULT_PORTFOLIO_ASSETS,
    FiatCashFlow,
    HoldingAdjustment,
    Wallet,
    WalletHolding,
)
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
            'units',
            'is_recommended',
            'purchased_at',
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
            'is_imported',
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
    needs_liquidity = serializers.BooleanField(required=False, default=True, write_only=True)

    class Meta:
        model = Portfolio
        fields = (
            'name',
            'initial_amount',
            'target_years',
            'use_default_assets',
            'custom_assets',
            'experience_level',
            'needs_liquidity',
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
        needs_liquidity = validated_data.pop('needs_liquidity', True)

        session_id = validated_data.get('session_id')
        if not session_id:
            raise ValueError("session_id is required")

        portfolio = Portfolio.objects.create(**validated_data)
        price_service = PriceService()

        if experience_level == 'beginner':
            assets_to_add = price_service.get_beginner_portfolio_assets()
        elif experience_level == 'some':
            assets_to_add = price_service.get_some_experience_portfolio_assets()
        elif experience_level == 'medium':
            if needs_liquidity:
                assets_to_add = price_service.get_medium_portfolio_with_liquidity()
            else:
                assets_to_add = price_service.get_medium_portfolio_no_liquidity()
        elif experience_level == 'advanced':
            if needs_liquidity:
                assets_to_add = price_service.get_advanced_portfolio_with_liquidity()
            else:
                assets_to_add = price_service.get_advanced_portfolio_no_liquidity()
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


class ContributionItemInputSerializer(serializers.Serializer):
    """Одна позиция взноса в режиме «по монетам»."""

    symbol = serializers.CharField(max_length=10)
    units = serializers.FloatField(min_value=0.0)
    purchase_price = serializers.FloatField(
        required=False, allow_null=True, min_value=0.0
    )
    purchased_at = serializers.DateField(required=False, allow_null=True)

    def validate_symbol(self, value):
        sym = (value or '').upper().strip()
        if not sym:
            raise serializers.ValidationError('Не указан символ актива.')
        if not PriceService.is_symbol_supported(sym):
            raise serializers.ValidationError(
                f"Символ '{sym}' не поддерживается."
            )
        return sym

    def validate_units(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Количество должно быть больше нуля.'
            )
        return value


class ContributeByUnitsSerializer(serializers.Serializer):
    """Взнос в портфель в режиме «по монетам»: список позиций.

    Поле ``wallet_id`` — опциональное. Если не задано, используется default
    Wallet портфеля (см. WalletLedger.get_default_wallet).
    """

    items = ContributionItemInputSerializer(many=True)
    wallet_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError(
                'Укажите хотя бы одну позицию.'
            )
        for it in value:
            if it.get('units', 0) <= 0:
                raise serializers.ValidationError(
                    'Количество должно быть больше нуля.'
                )
        return value


class SwapInputSerializer(serializers.Serializer):
    """Вход для исполнения обмена (swap) активов внутри портфеля.

    Поле ``wallet_id`` — опциональное. Если не задано, используется default
    Wallet портфеля (см. WalletLedger.get_default_wallet). Swap всегда
    происходит внутри одного кошелька (см. PLAN06 — Агент 12).
    """

    from_symbol = serializers.CharField(max_length=10)
    from_units = serializers.FloatField(min_value=0.0)
    to_symbol = serializers.CharField(max_length=10)
    to_units = serializers.FloatField(min_value=0.0)
    note = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    wallet_id = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )

    def validate(self, attrs):
        attrs['from_symbol'] = (attrs.get('from_symbol') or '').upper().strip()
        attrs['to_symbol'] = (attrs.get('to_symbol') or '').upper().strip()

        if not attrs['from_symbol'] or not attrs['to_symbol']:
            raise serializers.ValidationError('Не указан один из символов.')

        if attrs['from_symbol'] == attrs['to_symbol']:
            raise serializers.ValidationError(
                'Символы «Из» и «В» не могут совпадать.'
            )

        if attrs['from_units'] <= 0 or attrs['to_units'] <= 0:
            raise serializers.ValidationError(
                'Количество должно быть больше нуля.'
            )

        for sym in (attrs['from_symbol'], attrs['to_symbol']):
            if not PriceService.is_symbol_supported(sym):
                raise serializers.ValidationError(
                    f"Символ '{sym}' не поддерживается."
                )

        return attrs


class WalletTransferInputSerializer(serializers.Serializer):
    """Вход для перевода актива между кошельками внутри портфеля."""

    from_wallet_id = serializers.IntegerField(min_value=1)
    to_wallet_id = serializers.IntegerField(min_value=1)
    symbol = serializers.CharField(max_length=10)
    from_units = serializers.DecimalField(max_digits=20, decimal_places=8)
    to_units = serializers.DecimalField(max_digits=20, decimal_places=8)

    def validate_symbol(self, value):
        sym = (value or '').upper().strip()
        if not sym:
            raise serializers.ValidationError('Не указан символ актива.')
        if not PriceService.is_symbol_supported(sym):
            raise serializers.ValidationError(
                f"Символ '{sym}' не поддерживается."
            )
        return sym

    def validate(self, attrs):
        from_wallet_id = attrs.get('from_wallet_id')
        to_wallet_id = attrs.get('to_wallet_id')
        from_units = attrs.get('from_units')
        to_units = attrs.get('to_units')

        if from_wallet_id == to_wallet_id:
            raise serializers.ValidationError(
                'Кошелёк-источник и кошелёк-получатель не могут совпадать.'
            )

        if from_units is None or to_units is None:
            raise serializers.ValidationError(
                'Не указано количество единиц.'
            )

        if from_units <= 0 or to_units <= 0:
            raise serializers.ValidationError(
                'Количество должно быть больше нуля.'
            )

        if to_units > from_units:
            raise serializers.ValidationError(
                'Количество к получению не может превышать количество к отправке.'
            )

        return attrs


class HoldingAdjustInputSerializer(serializers.Serializer):
    """Вход для ручной коррекции баланса WalletHolding.

    Тело запроса задаёт ЦЕЛЕВОЕ значение баланса (`units_after`).
    Дельта вычисляется во view как `units_after - units_before`.
    Net Invested при коррекции НЕ меняется — мы только пересчитываем
    `PortfolioAsset.units` через `WalletLedger.sync_aggregate`.
    """

    units_after = serializers.DecimalField(
        max_digits=20, decimal_places=8, min_value=0
    )
    reason = serializers.ChoiceField(
        choices=HoldingAdjustment.REASON_CHOICES,
        required=False,
        default=HoldingAdjustment.REASON_OTHER,
    )
    note = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=''
    )
    occurred_on = serializers.DateField(required=False)


def _holding_value_usd(symbol, units, prices):
    """Стоимость holding'а в USD по словарю цен.

    Возвращает float, округлённый до 2 знаков, либо None, если цены нет
    или её невозможно привести к числу.
    """
    if not prices:
        return None
    price = prices.get(symbol)
    if price is None:
        return None
    try:
        value = Decimal(str(price)) * (units or Decimal('0'))
    except (InvalidOperation, TypeError):
        return None
    return float(round(value, 2))


class WalletHoldingSerializer(serializers.ModelSerializer):
    """Сериализатор баланса актива на кошельке (read-only представление)."""

    wallet_id = serializers.IntegerField(source='wallet.id', read_only=True)
    value_usd = serializers.SerializerMethodField()

    class Meta:
        model = WalletHolding
        fields = ('id', 'wallet_id', 'symbol', 'units', 'value_usd', 'updated_at')
        read_only_fields = fields

    def get_value_usd(self, obj):
        prices = self.context.get('prices') or {}
        return _holding_value_usd(obj.symbol, obj.units, prices)


class WalletSerializer(serializers.ModelSerializer):
    """Сериализатор кошелька (для list/retrieve)."""

    portfolio_id = serializers.IntegerField(source='portfolio.id', read_only=True)
    holdings = WalletHoldingSerializer(many=True, read_only=True)
    total_value_usd = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = (
            'id',
            'portfolio_id',
            'name',
            'type',
            'is_default',
            'note',
            'created_at',
            'updated_at',
            'holdings',
            'total_value_usd',
        )
        read_only_fields = (
            'id',
            'portfolio_id',
            'created_at',
            'updated_at',
            'holdings',
            'total_value_usd',
        )

    def get_total_value_usd(self, obj):
        prices = self.context.get('prices') or {}
        total = Decimal('0')
        for holding in obj.holdings.all():
            value = _holding_value_usd(holding.symbol, holding.units, prices)
            if value is not None:
                total += Decimal(str(value))
        return float(round(total, 2))


class WalletCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания кошелька в активном портфеле."""

    class Meta:
        model = Wallet
        fields = ('name', 'type', 'note', 'is_default')
        extra_kwargs = {
            'note': {'required': False, 'allow_blank': True, 'default': ''},
            'is_default': {'required': False, 'default': False},
            'type': {'required': False, 'default': Wallet.TYPE_OTHER},
        }

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Название кошелька не может быть пустым.')
        if len(name) > 100:
            raise serializers.ValidationError('Название слишком длинное (максимум 100 символов).')
        return name


class WalletUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для PATCH кошелька (имя/тип/комментарий/флаг default)."""

    class Meta:
        model = Wallet
        fields = ('name', 'type', 'note', 'is_default')
        extra_kwargs = {
            'name': {'required': False},
            'type': {'required': False},
            'note': {'required': False, 'allow_blank': True},
            'is_default': {'required': False},
        }

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Название кошелька не может быть пустым.')
        if len(name) > 100:
            raise serializers.ValidationError('Название слишком длинное (максимум 100 символов).')
        return name


class FiatCashFlowSerializer(serializers.ModelSerializer):
    """Сериализатор фиатного движения средств по портфелю (PLAN11).

    Создание/чтение/частичное обновление :class:`FiatCashFlow`.

    Read-only поля:
        * ``id``, ``created_at`` — служебные.
        * ``fx_rate_to_base`` — проставляется во view через ``_fx_rate``.
        * ``amount_in_base`` — расчётное поле модели (``amount × fx_rate``).

    Валидация:
        * ``kind`` ∈ {deposit, withdrawal};
        * ``currency`` ∈ {USD, EUR};
        * ``amount > 0``;
        * ``occurred_on`` <= сегодня; если не указана — подставляется ``today``.
    """

    amount_in_base = serializers.FloatField(read_only=True)
    occurred_on = serializers.DateField(required=False)
    note = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=''
    )

    class Meta:
        model = FiatCashFlow
        fields = (
            'id',
            'kind',
            'amount',
            'currency',
            'fx_rate_to_base',
            'amount_in_base',
            'occurred_on',
            'note',
            'created_at',
        )
        read_only_fields = (
            'id',
            'fx_rate_to_base',
            'amount_in_base',
            'created_at',
        )

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('Сумма должна быть больше нуля.')
        return value

    def validate_kind(self, value):
        valid = (FiatCashFlow.KIND_DEPOSIT, FiatCashFlow.KIND_WITHDRAWAL)
        if value not in valid:
            raise serializers.ValidationError(
                f"Допустимые значения kind: {', '.join(valid)}."
            )
        return value

    def validate_currency(self, value):
        valid = (Portfolio.CURRENCY_USD, Portfolio.CURRENCY_EUR)
        if value not in valid:
            raise serializers.ValidationError(
                f"Допустимые значения currency: {', '.join(valid)}."
            )
        return value

    def validate_occurred_on(self, value):
        if value and value > date.today():
            raise serializers.ValidationError(
                'Дата операции не может быть в будущем.'
            )
        return value

    def validate(self, attrs):
        if not attrs.get('occurred_on'):
            attrs['occurred_on'] = date.today()
        return attrs


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
