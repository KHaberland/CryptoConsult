# PLAN06: Несколько кошельков (биржи / холодные / горячие) с ручной коррекцией

## Цель

Расширить систему до **многокошельковой модели**: каждый пользователь
ведёт несколько счетов (биржи, холодные кошельки, банк) и видит
**физическое распределение криптоактивов** по этим кошелькам.

Аналогия — **«один бак с горючим, разделённый на N независимых секций»**:

- Общий объём бака = `Σ units` по всем секциям.
- Перелив бензина из секции в секцию **не меняет** общий объём, но может
  иметь потери на «утечку» (сетевая комиссия / биржевой fee).
- Долив бензина = depo + покупка → секция растёт, общий объём растёт.
- Слив = вывод средств → секция уменьшается, общий объём уменьшается.

**Ключевые архитектурные решения:**

1. **Кошелёк хранит ТОЛЬКО криптоактивы.** Фиатный баланс на кошельке
   мы не считаем. `Net Invested` остаётся **portfolio-level**, как в PLAN05.
2. **Cost basis (`initial_price`) при transfer НЕ переносится.**
   `PnL = Portfolio Value − Net Invested` не зависит от того, на каком
   кошельке лежит каждая единица актива.
3. **Per-wallet PnL не считаем.** На карточке кошелька — только баланс
   и USD-эквивалент по текущему рынку.
4. **Ручная коррекция актива** — отдельная операция, влияет на units и
   стоимость портфеля, но не на Net Invested.
5. **Сетевые комиссии при transfer** — встроены в саму операцию transfer
   (`from_units != to_units` ⇒ есть комиссия).

---

## 1. Терминология и формулы

```
🔋 Wallet              — пользовательский кошелёк (биржа / холодный / банк)
🪙 WalletHolding       — баланс одной монеты на одном кошельке (units)
🔄 WalletTransfer      — перевод между кошельками (with fee)
✏️  HoldingAdjustment  — ручная коррекция баланса монеты на кошельке

Σ WalletHolding.units (по symbol) == PortfolioAsset.units    [инвариант]

Portfolio Value = Σ (PortfolioAsset.units × current_price)
                = Σ (WalletHolding.units × current_price) — то же самое

Net Invested  = (как в PLAN05, без изменений)
PnL           = Portfolio Value − Net Invested
ROI %         = PnL / Net Invested × 100
```

| Сущность | Где живёт | Что хранит |
|---|---|---|
| `Portfolio` | `portfolios.Portfolio` | Старая модель, без изменений в этом плане. |
| `PortfolioAsset` | `portfolios.PortfolioAsset` | **Сводка по символу** на уровне портфеля: `units` (агрегированные), `initial_price` (средневзвешенная), `percentage`. Сохраняется как «view». |
| `Wallet` (новое) | `portfolios.Wallet` | `name`, `type`, `portfolio` — пользовательский счёт. |
| `WalletHolding` (новое) | `portfolios.WalletHolding` | `wallet`, `symbol`, `units` — баланс одной монеты на одном кошельке. **Без `initial_price`.** |
| `WalletTransfer` (новое) | `portfolios.WalletTransfer` | Перевод между кошельками. |
| `HoldingAdjustment` (новое) | `portfolios.HoldingAdjustment` | Лог ручных коррекций. |

**Инвариант:** для каждого `PortfolioAsset(portfolio, symbol)` всегда выполняется

```
PortfolioAsset.units == Σ WalletHolding.units (для тех же portfolio + symbol)
```

Программно поддерживается через сервис `WalletLedger.sync_aggregate(portfolio, symbol)`.

---

## 2. Пользовательские сценарии

### 2.1 Просмотр кошельков на дашборде

```
🔋 Мои кошельки                                    [+ Добавить]
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Binance    │ │  Ledger     │ │  Trust      │ │  Bybit      │
│  биржа      │ │  холодный   │ │  горячий    │ │  биржа      │
├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤
│ 0.25 BTC    │ │ 1.00 BTC    │ │ 2.00 BTC    │ │ 0.50 BTC    │
│ 5.00 ETH    │ │      —      │ │ 1.50 ETH    │ │ 200 USDT    │
│ ≈ $20 000   │ │ ≈ $50 000   │ │ ≈ $105 000  │ │ ≈ $25 200   │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### 2.2 Создание / редактирование кошелька

Модалка `WalletFormModal`:

```
┌───────────────────────────────┐
│ Добавить кошелёк              │
├───────────────────────────────┤
│ Имя:    [Binance       ]      │
│ Тип:    ( ) Биржа             │
│         (•) Холодный кошелёк  │
│         ( ) Горячий кошелёк   │
│         ( ) Банковский счёт   │
│         ( ) Другое            │
│                               │
│         [Отмена] [Сохранить]  │
└───────────────────────────────┘
```

### 2.3 Перевод между кошельками

```
[Дашборд] → кнопка «Перевести между кошельками»
        ▼
┌─────────────────────────────────────────────────┐
│ Перевод                                         │
├─────────────────────────────────────────────────┤
│ Из кошелька:    [Binance ▼]                     │
│ Актив:          [BTC ▼]                         │
│   доступно:     0.5000 BTC                      │
│ Списать:        [0.0400] BTC                    │
│                                                 │
│ В кошелёк:      [Ledger ▼]                      │
│ Получить:       [0.0395] BTC ← редактируется    │
│   (комиссия сети ~0.0005 BTC ≈ $25)             │
│                                                 │
│ Дата:           [29.04.2026]                    │
│ Заметка:        [────────────────────]          │
│                                                 │
│            [Отмена]  [Подтвердить]              │
└─────────────────────────────────────────────────┘
        ▼
POST /api/portfolio/wallets/transfer/
        ▼
[Дашборд: Binance −0.04 BTC, Ledger +0.0395 BTC, Portfolio Value −$25]
```

### 2.4 Ручная коррекция актива

В таблице активов на дашборде у каждого holding-а — иконка ✏:

```
┌──────────────────────────────────────────────────────────────┐
│ Актив | Кошелёк | Кол-во      | Цена | Стоимость | P/L      │
├──────────────────────────────────────────────────────────────┤
│ BTC   | Binance | 0.500 [✏]   | $50k | $25 000   | +5%      │
│ BTC   | Ledger  | 1.000 [✏]   | $50k | $50 000   | +5%      │
│ ETH   | Trust   | 1.500 [✏]   | $3k  | $4 500    | −2%      │
└──────────────────────────────────────────────────────────────┘
```

Клик на ✏:

```
┌────────────────────────────────────────────┐
│ Коррекция баланса BTC на Binance            │
├────────────────────────────────────────────┤
│ Сейчас:   0.5000 BTC  ($25 000.00)         │
│ Стало:    [0.4980]  BTC                    │
│ Дельта:   −0.0020 BTC (≈ −$100)            │
│                                            │
│ Причина (опц.): [Сетевая комиссия ▼]       │
│ Заметка (опц.): [перевод на Ledger     ]   │
│                                            │
│ ⚠ Это изменит стоимость портфеля на −$100  │
│   и PnL на −$100. Net Invested не         │
│   изменится.                               │
│                                            │
│           [Отмена]  [Подтвердить]          │
└────────────────────────────────────────────┘
```

Если пользователь увеличивает баланс (например, нашёл забытые сатоши) —
warning меняется на «увеличит стоимость на +$X».

### 2.5 Что меняется в существующих операциях

| Операция | До (PLAN05) | После (PLAN06) |
|---|---|---|
| Пополнение «по сумме $» (DCA) | `_contribute_by_amount` распределяет $ по существующим активам | то же, но units добавляются в **выбранный кошелёк**. Если у портфеля только один — без выбора. |
| Пополнение «по монетам» | создаёт `PortfolioAsset` | создаёт/обновляет **`WalletHolding(wallet, symbol)`**, агрегат `PortfolioAsset` пересчитывается из суммы Holdings. |
| Swap (обмен) | внутри портфеля | внутри **одного кошелька** (на бирже нельзя обменять монеты с холодного кошелька). |
| Вывод монет (продажа) | пропорционально по всем активам | списывает с **выбранного кошелька** (по умолчанию — кошелька с наибольшим балансом продаваемого актива). |
| Депозит / вывод фиата (PLAN05) | без привязки | без привязки (как было). Фиат в нашей модели — portfolio-level. |
| Импорт портфеля | создаёт `PortfolioAsset` | создаёт default-кошелёк «Импорт» и заполняет его Holdings. |

---

## 3. Backend — изменения

### 3.1 Модели — `backend/portfolios/models.py`

#### Новая модель `Wallet`

```python
class Wallet(models.Model):
    """Пользовательский кошелёк / биржевой счёт."""

    EXCHANGE = 'exchange'
    HOT = 'hot'
    COLD = 'cold'
    BANK = 'bank'
    OTHER = 'other'
    TYPE_CHOICES = [
        (EXCHANGE, 'Биржа'),
        (HOT, 'Горячий кошелёк'),
        (COLD, 'Холодный кошелёк'),
        (BANK, 'Банковский счёт'),
        (OTHER, 'Другое'),
    ]

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='wallets',
        verbose_name='Портфель',
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название',
        help_text='Произвольное имя для удобства пользователя',
    )
    type = models.CharField(
        max_length=12,
        choices=TYPE_CHOICES,
        default=EXCHANGE,
        verbose_name='Тип',
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Кошелёк по умолчанию',
        help_text='Используется, если пользователь не указал кошелёк явно.',
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Заметка',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Кошелёк'
        verbose_name_plural = 'Кошельки'
        ordering = ['-is_default', 'name']
        unique_together = [('portfolio', 'name')]

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'
```

#### Новая модель `WalletHolding`

```python
class WalletHolding(models.Model):
    """Баланс одной монеты на одном кошельке (только units, без cost basis)."""

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='holdings',
        verbose_name='Кошелёк',
    )
    symbol = models.CharField(
        max_length=10,
        verbose_name='Символ актива',
    )
    units = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        verbose_name='Количество единиц',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Холдинг кошелька'
        verbose_name_plural = 'Холдинги кошельков'
        unique_together = [('wallet', 'symbol')]

    def __str__(self):
        return f'{self.wallet.name}: {self.units} {self.symbol}'
```

#### Новая модель `WalletTransfer`

```python
class WalletTransfer(models.Model):
    """Перевод одного актива между кошельками одного портфеля."""

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='wallet_transfers',
        verbose_name='Портфель',
    )
    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='transfers_out',
        verbose_name='Кошелёк-источник',
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='transfers_in',
        verbose_name='Кошелёк-получатель',
    )
    symbol = models.CharField(
        max_length=10,
        verbose_name='Символ актива',
    )
    from_units = models.DecimalField(
        max_digits=20, decimal_places=8,
        verbose_name='Списано (units)',
    )
    to_units = models.DecimalField(
        max_digits=20, decimal_places=8,
        verbose_name='Получено (units)',
    )
    # = from_units - to_units (>= 0 в норме). Сохраняем для аналитики.
    fee_units = models.DecimalField(
        max_digits=20, decimal_places=8, default=0,
        verbose_name='Комиссия (units)',
    )
    # USD-эквивалент комиссии на момент операции (для аналитики)
    fee_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Комиссия ($)',
    )
    occurred_on = models.DateField(verbose_name='Дата операции')
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Перевод между кошельками'
        verbose_name_plural = 'Переводы между кошельками'
        ordering = ['-occurred_on', '-id']
        indexes = [
            models.Index(fields=['portfolio', 'occurred_on']),
        ]

    def __str__(self):
        return (f'{self.from_units} {self.symbol}: '
                f'{self.from_wallet.name} → {self.to_wallet.name}')
```

#### Новая модель `HoldingAdjustment`

```python
class HoldingAdjustment(models.Model):
    """Лог ручных коррекций баланса монеты на кошельке."""

    NETWORK_FEE = 'network_fee'
    EXCHANGE_FEE = 'exchange_fee'
    RECONCILIATION = 'reconciliation'
    INPUT_ERROR = 'input_error'
    OTHER = 'other'
    REASON_CHOICES = [
        (NETWORK_FEE, 'Сетевая комиссия'),
        (EXCHANGE_FEE, 'Биржевая комиссия'),
        (RECONCILIATION, 'Сверка с реальным балансом'),
        (INPUT_ERROR, 'Исправление ошибки ввода'),
        (OTHER, 'Другое'),
    ]

    holding = models.ForeignKey(
        WalletHolding,
        on_delete=models.CASCADE,
        related_name='adjustments',
        verbose_name='Холдинг',
    )
    units_before = models.DecimalField(max_digits=20, decimal_places=8)
    units_after = models.DecimalField(max_digits=20, decimal_places=8)
    delta = models.DecimalField(
        max_digits=20, decimal_places=8,
        verbose_name='Дельта (units)',
        help_text='units_after - units_before (отрицательная = уменьшение)',
    )
    value_delta_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Влияние на стоимость портфеля ($)',
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        blank=True,
        default='',
        verbose_name='Причина (опционально)',
    )
    note = models.CharField(max_length=200, blank=True, default='')
    occurred_on = models.DateField(verbose_name='Дата коррекции')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Коррекция холдинга'
        verbose_name_plural = 'Коррекции холдингов'
        ordering = ['-occurred_on', '-id']

    def __str__(self):
        sign = '+' if self.delta >= 0 else ''
        return f'{self.holding}: {sign}{self.delta}'
```

#### Миграции

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python manage.py makemigrations portfolios -n wallets_holdings_transfers_adjustments
python manage.py makemigrations portfolios -n backfill_default_wallets --empty
# (вписать backfill, см. ниже)
python manage.py migrate
```

#### Дата-миграция `0010_backfill_default_wallets.py`

```python
def backfill_default_wallets(apps, schema_editor):
    Portfolio = apps.get_model('portfolios', 'Portfolio')
    PortfolioAsset = apps.get_model('portfolios', 'PortfolioAsset')
    Wallet = apps.get_model('portfolios', 'Wallet')
    WalletHolding = apps.get_model('portfolios', 'WalletHolding')

    for p in Portfolio.objects.all():
        # 1) Default wallet на портфель
        default = Wallet.objects.filter(portfolio=p, is_default=True).first()
        if not default:
            default = Wallet.objects.create(
                portfolio=p,
                name='Общий кошелёк',
                type='exchange',
                is_default=True,
                note='Создан автоматически при миграции',
            )

        # 2) Holdings из существующих PortfolioAsset
        for a in PortfolioAsset.objects.filter(portfolio=p):
            units = a.units or 0
            holding, created = WalletHolding.objects.get_or_create(
                wallet=default,
                symbol=a.symbol,
                defaults={'units': units},
            )
            if not created and (holding.units or 0) == 0 and units:
                holding.units = units
                holding.save(update_fields=['units'])


class Migration(migrations.Migration):
    dependencies = [('portfolios', '0009_wallets_holdings_transfers_adjustments')]
    operations = [migrations.RunPython(backfill_default_wallets,
                                       migrations.RunPython.noop)]
```

> **Важно:** `PortfolioAsset` НЕ удаляется и НЕ деактивируется. Он остаётся
> «материализованным агрегатом» (`units`, `initial_price`, `percentage`,
> `is_recommended`, `purchased_at`). Просто после PLAN06 источником истины
> для **`units`** становится сумма Holdings; `PortfolioAsset.units`
> поддерживается через сервис `WalletLedger.sync_aggregate(...)`.

### 3.2 Сервис — `WalletLedger` (`backend/portfolios/services.py`)

Единая утилита поддержания инварианта и пересчёта.

```python
class WalletLedger:
    """Согласование Wallet/WalletHolding с PortfolioAsset (агрегат)."""

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio

    def get_default_wallet(self) -> Wallet:
        w = self.portfolio.wallets.filter(is_default=True).first()
        if w:
            return w
        w = self.portfolio.wallets.first()
        if w:
            return w
        # Если кошельков ещё нет — создаём
        return Wallet.objects.create(
            portfolio=self.portfolio,
            name='Общий кошелёк',
            type=Wallet.EXCHANGE,
            is_default=True,
        )

    def get_or_create_holding(self, wallet: Wallet, symbol: str) -> WalletHolding:
        holding, _ = WalletHolding.objects.get_or_create(
            wallet=wallet, symbol=symbol.upper(), defaults={'units': 0}
        )
        return holding

    def add_units(self, wallet: Wallet, symbol: str, delta_units: float) -> WalletHolding:
        """Добавить delta (может быть отрицательным) к Holding."""
        h = self.get_or_create_holding(wallet, symbol)
        h.units = Decimal(str(round(float(h.units or 0) + float(delta_units), 8)))
        h.save(update_fields=['units'])
        return h

    def aggregate_units(self, symbol: str) -> float:
        """Σ units по всем кошелькам портфеля для данного symbol."""
        from django.db.models import Sum
        agg = WalletHolding.objects.filter(
            wallet__portfolio=self.portfolio, symbol=symbol.upper()
        ).aggregate(s=Sum('units'))
        return float(agg['s'] or 0)

    def sync_aggregate(self, symbol: str) -> Optional['PortfolioAsset']:
        """Обновить PortfolioAsset.units по сумме Holdings."""
        total = self.aggregate_units(symbol)
        asset = self.portfolio.assets.filter(symbol=symbol.upper()).first()
        if asset:
            asset.units = Decimal(str(round(total, 8)))
            asset.save(update_fields=['units'])
        return asset

    def sync_all(self) -> None:
        """Пересинхронизировать все PortfolioAsset с Holdings."""
        symbols = set(self.portfolio.assets.values_list('symbol', flat=True))
        symbols |= set(WalletHolding.objects.filter(
            wallet__portfolio=self.portfolio
        ).values_list('symbol', flat=True))
        for sym in symbols:
            self.sync_aggregate(sym)
```

### 3.3 Сериализаторы — `backend/portfolios/serializers.py`

```python
class WalletHoldingSerializer(serializers.ModelSerializer):
    current_price = serializers.SerializerMethodField()
    value_usd = serializers.SerializerMethodField()

    class Meta:
        model = WalletHolding
        fields = ('id', 'symbol', 'units', 'current_price', 'value_usd', 'updated_at')
        read_only_fields = fields

    def get_current_price(self, obj):
        prices = self.context.get('prices') or {}
        return float(prices.get(obj.symbol, 0) or 0)

    def get_value_usd(self, obj):
        prices = self.context.get('prices') or {}
        price = float(prices.get(obj.symbol, 0) or 0)
        return round(float(obj.units or 0) * price, 2)


class WalletSerializer(serializers.ModelSerializer):
    holdings = WalletHoldingSerializer(many=True, read_only=True)
    total_value_usd = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ('id', 'name', 'type', 'is_default', 'note',
                  'holdings', 'total_value_usd',
                  'created_at', 'updated_at')
        read_only_fields = ('id', 'is_default', 'created_at', 'updated_at',
                            'holdings', 'total_value_usd')

    def get_total_value_usd(self, obj):
        prices = self.context.get('prices') or {}
        total = 0.0
        for h in obj.holdings.all():
            total += float(h.units or 0) * float(prices.get(h.symbol, 0) or 0)
        return round(total, 2)


class WalletInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=Wallet.TYPE_CHOICES, default=Wallet.EXCHANGE)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')


class WalletTransferInputSerializer(serializers.Serializer):
    from_wallet_id = serializers.IntegerField()
    to_wallet_id = serializers.IntegerField()
    symbol = serializers.CharField(max_length=10)
    from_units = serializers.FloatField(min_value=0.0)
    to_units = serializers.FloatField(min_value=0.0)
    occurred_on = serializers.DateField(required=False)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs['from_wallet_id'] == attrs['to_wallet_id']:
            raise serializers.ValidationError('Кошельки источника и получателя совпадают.')
        if attrs['from_units'] <= 0:
            raise serializers.ValidationError('from_units должен быть > 0.')
        if attrs['to_units'] <= 0:
            raise serializers.ValidationError('to_units должен быть > 0.')
        if attrs['to_units'] - attrs['from_units'] > 1e-9:
            raise serializers.ValidationError(
                'Получено больше, чем списано — для увеличения баланса используйте '
                'ручную коррекцию.'
            )
        attrs['symbol'] = attrs['symbol'].upper().strip()
        if not PriceService.is_symbol_supported(attrs['symbol']):
            raise serializers.ValidationError(f"Символ '{attrs['symbol']}' не поддерживается.")
        return attrs


class HoldingAdjustmentInputSerializer(serializers.Serializer):
    units_after = serializers.FloatField(min_value=0.0)
    reason = serializers.ChoiceField(
        choices=HoldingAdjustment.REASON_CHOICES,
        required=False, allow_blank=True, default=''
    )
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    occurred_on = serializers.DateField(required=False)


class HoldingAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HoldingAdjustment
        fields = ('id', 'units_before', 'units_after', 'delta',
                  'value_delta_usd', 'reason', 'note', 'occurred_on',
                  'created_at')
        read_only_fields = fields


class WalletTransferSerializer(serializers.ModelSerializer):
    from_wallet_name = serializers.CharField(source='from_wallet.name', read_only=True)
    to_wallet_name = serializers.CharField(source='to_wallet.name', read_only=True)

    class Meta:
        model = WalletTransfer
        fields = ('id', 'from_wallet', 'from_wallet_name',
                  'to_wallet', 'to_wallet_name',
                  'symbol', 'from_units', 'to_units',
                  'fee_units', 'fee_usd',
                  'occurred_on', 'note', 'created_at')
        read_only_fields = fields
```

### 3.4 Views — `backend/portfolios/views.py`

#### `WalletListCreateView`

```python
class WalletListCreateView(APIView):
    """
    GET  /api/portfolio/wallets/         — список кошельков активного портфеля.
    POST /api/portfolio/wallets/         — создать кошелёк.
    """
    permission_classes = (AllowAny,)

    def get(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response({'detail': 'Активный портфель не найден.'}, status=404)
        wallets = portfolio.wallets.all().prefetch_related('holdings')

        symbols = list({h.symbol for w in wallets for h in w.holdings.all()})
        prices = PriceService().get_prices(symbols) if symbols else {}

        ser = WalletSerializer(wallets, many=True, context={'prices': prices})
        return Response({'wallets': ser.data, 'count': len(ser.data)})

    def post(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response({'detail': 'Активный портфель не найден.'}, status=404)

        s = WalletInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        if portfolio.wallets.filter(name=d['name']).exists():
            return Response({'detail': 'Кошелёк с таким именем уже существует.'},
                            status=400)

        wallet = Wallet.objects.create(
            portfolio=portfolio,
            name=d['name'],
            type=d.get('type') or Wallet.EXCHANGE,
            note=d.get('note') or '',
            is_default=not portfolio.wallets.exists(),
        )
        return Response(WalletSerializer(wallet, context={'prices': {}}).data,
                        status=201)
```

#### `WalletDetailView`

```python
class WalletDetailView(APIView):
    """PATCH/DELETE /api/portfolio/wallets/<id>/"""
    permission_classes = (AllowAny,)

    def _get_wallet(self, request, pk):
        return Wallet.objects.filter(
            pk=pk, portfolio__session_id=request.session_id
        ).first()

    def patch(self, request, pk):
        wallet = self._get_wallet(request, pk)
        if not wallet:
            return Response({'detail': 'Не найден.'}, status=404)

        s = WalletInputSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        for k, v in s.validated_data.items():
            setattr(wallet, k, v)
        wallet.save()
        return Response(WalletSerializer(wallet, context={'prices': {}}).data)

    def delete(self, request, pk):
        wallet = self._get_wallet(request, pk)
        if not wallet:
            return Response({'detail': 'Не найден.'}, status=404)

        # Запрещаем удалять, если есть ненулевые holdings
        non_zero = wallet.holdings.filter(units__gt=0).exists()
        if non_zero:
            return Response(
                {'detail': 'На кошельке есть ненулевые балансы. Сначала переведите '
                           'или скорректируйте их в ноль.'},
                status=400
            )
        if wallet.is_default:
            return Response(
                {'detail': 'Нельзя удалить дефолтный кошелёк. Назначьте другой '
                           'дефолтным сначала.'},
                status=400
            )
        wallet.delete()
        return Response(status=204)
```

#### `WalletTransferView`

```python
class WalletTransferView(APIView):
    """POST /api/portfolio/wallets/transfer/ — перевод актива между кошельками."""
    permission_classes = (AllowAny,)

    @transaction.atomic
    def post(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response({'detail': 'Активный портфель не найден.'}, status=404)

        s = WalletTransferInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        from_wallet = portfolio.wallets.filter(pk=d['from_wallet_id']).first()
        to_wallet = portfolio.wallets.filter(pk=d['to_wallet_id']).first()
        if not from_wallet or not to_wallet:
            return Response({'detail': 'Кошелёк не принадлежит портфелю.'}, status=400)

        symbol = d['symbol']
        from_units = float(d['from_units'])
        to_units = float(d['to_units'])

        from_holding = WalletHolding.objects.filter(
            wallet=from_wallet, symbol=symbol
        ).first()
        if not from_holding or float(from_holding.units or 0) < from_units - 1e-9:
            available = float(from_holding.units or 0) if from_holding else 0
            return Response({
                'detail': f'Недостаточно {symbol} на {from_wallet.name}: '
                          f'доступно {available:.8f}, запрошено {from_units:.8f}.',
                'units_available': round(available, 8),
            }, status=400)

        ledger = WalletLedger(portfolio)
        ledger.add_units(from_wallet, symbol, -from_units)
        ledger.add_units(to_wallet, symbol, +to_units)

        # Комиссия — в units и в USD на момент операции
        fee_units = max(0.0, from_units - to_units)
        price_now = float(PriceService().get_price(symbol) or 0)
        fee_usd = round(fee_units * price_now, 2)

        # PortfolioAsset.units пересчитывается: -fee_units (общий бак уменьшился
        # на величину комиссии). Это корректное поведение — Portfolio Value упадёт.
        ledger.sync_aggregate(symbol)
        # Доли пересчитаем после операции
        symbols_for_recalc = list({a.symbol for a in portfolio.assets.all()})
        prices = PriceService().get_prices(symbols_for_recalc)
        recompute_percentages_by_market(portfolio, prices)

        transfer = WalletTransfer.objects.create(
            portfolio=portfolio,
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            symbol=symbol,
            from_units=Decimal(str(round(from_units, 8))),
            to_units=Decimal(str(round(to_units, 8))),
            fee_units=Decimal(str(round(fee_units, 8))),
            fee_usd=Decimal(str(fee_usd)),
            occurred_on=d.get('occurred_on') or date.today(),
            note=d.get('note') or '',
        )

        return Response({
            'success': True,
            'transfer': WalletTransferSerializer(transfer).data,
        }, status=201)
```

#### `HoldingAdjustView`

```python
class HoldingAdjustView(APIView):
    """
    POST /api/portfolio/wallets/<wallet_id>/holdings/<symbol>/adjust/
    Ручная коррекция баланса актива на кошельке.
    """
    permission_classes = (AllowAny,)

    @transaction.atomic
    def post(self, request, wallet_id, symbol):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response({'detail': 'Активный портфель не найден.'}, status=404)

        wallet = portfolio.wallets.filter(pk=wallet_id).first()
        if not wallet:
            return Response({'detail': 'Кошелёк не найден.'}, status=404)

        s = HoldingAdjustmentInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        holding = WalletHolding.objects.filter(
            wallet=wallet, symbol=symbol.upper()
        ).first()
        if not holding:
            holding = WalletHolding.objects.create(
                wallet=wallet, symbol=symbol.upper(), units=0
            )

        units_before = Decimal(str(round(float(holding.units or 0), 8)))
        units_after = Decimal(str(round(float(d['units_after']), 8)))
        delta = units_after - units_before

        price = float(PriceService().get_price(symbol) or 0)
        value_delta_usd = float(delta) * price

        holding.units = units_after
        holding.save(update_fields=['units'])

        # Пересинхронизация агрегата + долей
        WalletLedger(portfolio).sync_aggregate(symbol)
        symbols = list({a.symbol for a in portfolio.assets.all()})
        prices = PriceService().get_prices(symbols)
        recompute_percentages_by_market(portfolio, prices)

        adj = HoldingAdjustment.objects.create(
            holding=holding,
            units_before=units_before,
            units_after=units_after,
            delta=delta,
            value_delta_usd=Decimal(str(round(value_delta_usd, 2))),
            reason=d.get('reason') or '',
            note=d.get('note') or '',
            occurred_on=d.get('occurred_on') or date.today(),
        )

        return Response({
            'success': True,
            'adjustment': HoldingAdjustmentSerializer(adj).data,
        }, status=201)
```

### 3.5 Доработка существующих view-х

#### `ContributePortfolioView._contribute_by_units`

В `ContributionItemInputSerializer` добавить поле:

```python
class ContributionItemInputSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=10)
    units = serializers.FloatField(min_value=0.0)
    purchase_price = serializers.FloatField(required=False, allow_null=True, min_value=0.0)
    purchased_at = serializers.DateField(required=False, allow_null=True)
    wallet_id = serializers.IntegerField(required=False, allow_null=True)  # ← new
```

В `_contribute_by_units` — после определения `asset` добавить:

```python
# Куда зачисляем монеты
ledger = WalletLedger(portfolio)
wallet = (
    portfolio.wallets.filter(pk=item.get('wallet_id')).first()
    if item.get('wallet_id') else ledger.get_default_wallet()
)
ledger.add_units(wallet, symbol, add_units)
# В конце метода
ledger.sync_all()
```

PortfolioAsset.units теперь становится **производной** от Holdings; прямое
присваивание `asset.units = ...` нужно убрать (или оставить, но затем
переопределить через `sync_aggregate`).

#### `_contribute_by_amount`

Аналогично — после расчёта `new_units` для каждого актива, вместо
`asset.units = old_units + new_units` делаем
`ledger.add_units(default_wallet, asset.symbol, new_units)` и затем
`ledger.sync_aggregate(asset.symbol)`. Поскольку DCA-режим не предполагает
выбор кошелька — всегда используется `get_default_wallet()`.

#### `SwapExecuteView`

В `SwapInputSerializer` добавить:

```python
wallet_id = serializers.IntegerField(required=False, allow_null=True)
```

В `post()` — выбираем кошелёк через `wallet_id` (или дефолтный).
**Все операции swap выполняются внутри одного кошелька:**

```python
ledger = WalletLedger(portfolio)
wallet = (
    portfolio.wallets.filter(pk=d.get('wallet_id')).first()
    if d.get('wallet_id') else ledger.get_default_wallet()
)
# Проверяем доступность from_units на ЭТОМ кошельке (не агрегатно)
from_holding = WalletHolding.objects.filter(wallet=wallet, symbol=from_symbol).first()
units_available = float(from_holding.units or 0) if from_holding else 0
if from_units - units_available > 1e-9:
    return Response({
        'detail': f'Недостаточно {from_symbol} на кошельке {wallet.name}: '
                  f'доступно {units_available:.8f}.',
    }, status=400)
ledger.add_units(wallet, from_symbol, -from_units)
ledger.add_units(wallet, to_symbol, +to_units)
ledger.sync_aggregate(from_symbol)
ledger.sync_aggregate(to_symbol)
```

#### `WithdrawPortfolioView`

В body теперь принимается `wallet_id` для каждого актива (опц.). Если не указан —
списываем с кошелька с **наибольшим балансом** этого символа.

```python
for item in assets_data:
    symbol = item.get('symbol', '').upper()
    wallet_id = item.get('wallet_id')

    if wallet_id:
        holding = WalletHolding.objects.filter(
            wallet__portfolio=portfolio, wallet__pk=wallet_id, symbol=symbol
        ).first()
    else:
        holding = WalletHolding.objects.filter(
            wallet__portfolio=portfolio, symbol=symbol
        ).order_by('-units').first()

    if not holding or float(holding.units or 0) <= 0:
        continue

    units_to_sell = min(float(item.get('units_to_sell', 0)),
                        float(holding.units or 0))
    holding.units = Decimal(str(round(float(holding.units) - units_to_sell, 8)))
    holding.save(update_fields=['units'])

    # ... остальное как было ...
    WalletLedger(portfolio).sync_aggregate(symbol)
```

#### `PortfolioImportView`

После создания `PortfolioAsset`-ов:

```python
# Создаём default-кошелёк "Импортированный"
import_wallet = Wallet.objects.create(
    portfolio=portfolio,
    name='Импортированный',
    type=Wallet.EXCHANGE,
    is_default=True,
    note='Создан при импорте портфеля',
)
for p in parsed_list:
    WalletHolding.objects.create(
        wallet=import_wallet,
        symbol=p['symbol'],
        units=Decimal(str(p['units'])),
    )
```

#### `PortfolioCreateSerializer.create`

После `Portfolio.objects.create(...)` и заполнения `PortfolioAsset`-ов:

```python
# Дефолтный кошелёк + Holdings из PortfolioAsset
default_wallet = Wallet.objects.create(
    portfolio=portfolio,
    name='Общий кошелёк',
    type=Wallet.EXCHANGE,
    is_default=True,
)
for asset in portfolio.assets.all():
    WalletHolding.objects.create(
        wallet=default_wallet,
        symbol=asset.symbol,
        units=asset.units or 0,
    )
```

### 3.6 URL-маршруты — `backend/portfolios/urls.py`

```python
# Кошельки
path('wallets/', WalletListCreateView.as_view(), name='wallets'),
path('wallets/<int:pk>/', WalletDetailView.as_view(), name='wallet_detail'),

# Перевод между кошельками
path('wallets/transfer/', WalletTransferView.as_view(), name='wallet_transfer'),

# Ручная коррекция холдинга
path('wallets/<int:wallet_id>/holdings/<str:symbol>/adjust/',
     HoldingAdjustView.as_view(), name='holding_adjust'),
```

### 3.7 Admin — `backend/portfolios/admin.py`

```python
class WalletHoldingInline(admin.TabularInline):
    model = WalletHolding
    extra = 0
    readonly_fields = ('updated_at',)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'portfolio', 'is_default')
    list_filter = ('type', 'is_default')
    search_fields = ('name', 'portfolio__name')
    inlines = [WalletHoldingInline]


@admin.register(WalletTransfer)
class WalletTransferAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'symbol', 'from_wallet', 'to_wallet',
                    'from_units', 'to_units', 'fee_units', 'occurred_on')
    list_filter = ('symbol', 'occurred_on')
    search_fields = ('portfolio__name', 'symbol')


@admin.register(HoldingAdjustment)
class HoldingAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('holding', 'delta', 'value_delta_usd',
                    'reason', 'occurred_on')
    list_filter = ('reason', 'occurred_on')
    search_fields = ('holding__wallet__name', 'note')
```

### 3.8 Дополнения в `PortfolioCapitalSummaryView` (PLAN05)

Расширить ответ `/api/portfolio/summary/` секцией `wallets`:

```python
wallets = portfolio.wallets.prefetch_related('holdings').all()
symbols = list({h.symbol for w in wallets for h in w.holdings.all()})
prices = PriceService().get_prices(symbols) if symbols else {}
ctx = {'prices': prices}
response['wallets'] = WalletSerializer(wallets, many=True, context=ctx).data
```

---

## 4. Frontend — изменения

### 4.1 API-клиент — `frontend/src/services/api.ts`

```ts
export interface WalletHolding {
  id: number
  symbol: string
  units: number
  current_price: number
  value_usd: number
  updated_at: string
}

export interface Wallet {
  id: number
  name: string
  type: 'exchange' | 'hot' | 'cold' | 'bank' | 'other'
  is_default: boolean
  note: string
  holdings: WalletHolding[]
  total_value_usd: number
  created_at: string
  updated_at: string
}

export interface WalletTransfer {
  id: number
  from_wallet: number
  from_wallet_name: string
  to_wallet: number
  to_wallet_name: string
  symbol: string
  from_units: number
  to_units: number
  fee_units: number
  fee_usd: number
  occurred_on: string
  note: string
  created_at: string
}

export const walletsApi = {
  list: async (): Promise<{ wallets: Wallet[]; count: number }> => {
    const r = await api.get('/portfolio/wallets/')
    return r.data
  },

  create: async (data: {
    name: string
    type?: Wallet['type']
    note?: string
  }): Promise<Wallet> => {
    const r = await api.post('/portfolio/wallets/', data)
    return r.data
  },

  update: async (id: number, data: Partial<{
    name: string
    type: Wallet['type']
    note: string
  }>): Promise<Wallet> => {
    const r = await api.patch(`/portfolio/wallets/${id}/`, data)
    return r.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/portfolio/wallets/${id}/`)
  },

  transfer: async (data: {
    from_wallet_id: number
    to_wallet_id: number
    symbol: string
    from_units: number
    to_units: number
    occurred_on?: string
    note?: string
  }): Promise<{ success: true; transfer: WalletTransfer }> => {
    const r = await api.post('/portfolio/wallets/transfer/', data)
    return r.data
  },

  adjustHolding: async (
    walletId: number,
    symbol: string,
    data: {
      units_after: number
      reason?: 'network_fee' | 'exchange_fee' | 'reconciliation' | 'input_error' | 'other' | ''
      note?: string
      occurred_on?: string
    }
  ) => {
    const r = await api.post(
      `/portfolio/wallets/${walletId}/holdings/${symbol}/adjust/`,
      data
    )
    return r.data
  },
}
```

В `portfolioApi.contributeByUnits` и `portfolioApi.executeSwap` — добавить
опциональное `wallet_id` в типы аргументов.

### 4.2 Стор — `frontend/src/store/portfolioStore.ts`

```ts
wallets: Wallet[] | null
fetchWallets: () => Promise<void>
createWallet: (data: { name: string; type?: Wallet['type']; note?: string }) => Promise<void>
updateWallet: (id: number, data: Partial<{...}>) => Promise<void>
deleteWallet: (id: number) => Promise<void>
transferBetweenWallets: (data: {...}) => Promise<void>
adjustHolding: (walletId: number, symbol: string, data: {...}) => Promise<void>
```

После каждой мутации — `fetchWallets()` + `fetchPortfolioValue(true)` +
`fetchCapitalSummary(true)` (последнее из PLAN05).

### 4.3 Дашборд — `frontend/src/app/dashboard/page.tsx`

#### 4.3.1 Новая секция «Мои кошельки»

Над таблицей «Состав портфеля» (или сбоку):

```tsx
<Card>
  <CardHeader className="flex flex-row items-center justify-between">
    <CardTitle>
      <div className="flex items-center gap-2">
        <Wallet className="w-5 h-5" />
        Мои кошельки
      </div>
    </CardTitle>
    <div className="flex gap-2">
      <Button size="sm" variant="secondary" onClick={() => setShowTransferModal(true)}>
        <ArrowLeftRight className="w-4 h-4 mr-1" />
        Перевести
      </Button>
      <Button size="sm" onClick={() => setShowAddWalletModal(true)}>
        <PlusCircle className="w-4 h-4 mr-1" />
        Добавить
      </Button>
    </div>
  </CardHeader>
  <CardContent>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {wallets.map((w) => (
        <WalletCard key={w.id} wallet={w} onEdit={...} onDelete={...} />
      ))}
    </div>
  </CardContent>
</Card>
```

`WalletCard.tsx`:

```tsx
interface Props { wallet: Wallet; onEdit: (w: Wallet) => void; onDelete: (id: number) => void }

export function WalletCard({ wallet, onEdit, onDelete }: Props) {
  const typeLabel = {
    exchange: 'Биржа', hot: 'Горячий', cold: 'Холодный', bank: 'Банк', other: 'Другое'
  }[wallet.type]
  const TypeIcon = {
    exchange: Building2, hot: Flame, cold: Snowflake, bank: Landmark, other: Wallet
  }[wallet.type]

  return (
    <div className="rounded-lg border border-gray-200 p-4 bg-white">
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="font-semibold">{wallet.name}</p>
          <p className="text-xs text-gray-500 flex items-center gap-1">
            <TypeIcon className="w-3 h-3" /> {typeLabel}
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuItem onClick={() => onEdit(wallet)}>Редактировать</DropdownMenuItem>
          <DropdownMenuItem onClick={() => onDelete(wallet.id)} disabled={wallet.is_default}>
            Удалить
          </DropdownMenuItem>
        </DropdownMenu>
      </div>
      <div className="space-y-1 text-sm">
        {wallet.holdings.length === 0 ? (
          <p className="text-gray-500 italic">пусто</p>
        ) : (
          wallet.holdings
            .filter((h) => h.units > 0)
            .map((h) => (
              <div key={h.symbol} className="flex justify-between">
                <span>{formatUnits(h.units)} {h.symbol}</span>
                <span className="text-gray-600">{formatCurrency(h.value_usd)}</span>
              </div>
            ))
        )}
      </div>
      <div className="mt-3 pt-2 border-t text-right">
        <span className="text-xs text-gray-500">Итого: </span>
        <span className="font-semibold">{formatCurrency(wallet.total_value_usd)}</span>
      </div>
    </div>
  )
}
```

#### 4.3.2 Таблица активов с разрезом по кошелькам

Добавить колонку «Кошелёк» и кнопку коррекции:

```tsx
<thead>
  <tr>
    <th>Актив</th>
    <th>Кошелёк</th>
    <th>Доля (общая)</th>
    <th>Кол-во</th>
    <th>Цена</th>
    <th>24ч</th>
    <th>Стоимость</th>
    <th></th>
  </tr>
</thead>
<tbody>
  {wallets.flatMap((w) =>
    w.holdings.filter((h) => h.units > 0).map((h) => (
      <tr key={`${w.id}-${h.symbol}`}>
        <td>{h.symbol}</td>
        <td className="text-sm text-gray-600">{w.name}</td>
        <td>{aggregatePercentBySymbol(h.symbol)}%</td>
        <td>{formatUnits(h.units)}</td>
        <td>{formatCurrency(h.current_price)}</td>
        <td>{/* change_24h из portfolioValue.assets */}</td>
        <td>{formatCurrency(h.value_usd)}</td>
        <td>
          <Button
            size="xs"
            variant="ghost"
            onClick={() => setAdjustTarget({ walletId: w.id, symbol: h.symbol, currentUnits: h.units })}
          >
            <Pencil className="w-3.5 h-3.5" />
          </Button>
        </td>
      </tr>
    ))
  )}
</tbody>
```

> **Альтернатива**: оставить «агрегатную» таблицу как раньше, а ✏ открывает
> сначала выбор кошелька, потом форму коррекции. Решение принять при имплементации.

### 4.4 Новые компоненты

#### `WalletFormModal.tsx`

CRUD-модалка для кошелька:

```tsx
interface Props {
  isOpen: boolean
  onClose: () => void
  wallet?: Wallet // если задан — режим редактирования
}

const TYPE_OPTIONS = [
  { value: 'exchange', label: 'Биржа', icon: Building2 },
  { value: 'cold',     label: 'Холодный кошелёк', icon: Snowflake },
  { value: 'hot',      label: 'Горячий кошелёк',  icon: Flame },
  { value: 'bank',     label: 'Банковский счёт',  icon: Landmark },
  { value: 'other',    label: 'Другое',           icon: Wallet },
]
```

#### `TransferBetweenWalletsModal.tsx`

Шаги: `form` → `success`. Поля:
- селект `from_wallet`
- селект `symbol` (только символы с `units > 0` на `from_wallet`)
- input `from_units` (max = available)
- селект `to_wallet`
- input `to_units` (default = `from_units`, можно уменьшить)
- date-picker `occurred_on` (default = today)
- input `note`

Подсчёт fee:
```ts
const feeUnits = Math.max(0, fromUnits - toUnits)
const feeUsd = feeUnits * currentPrice
```

Сабмит → `walletsApi.transfer(...)`.

#### `AdjustHoldingModal.tsx`

```tsx
interface Props {
  isOpen: boolean
  onClose: () => void
  walletId: number
  walletName: string
  symbol: string
  currentUnits: number
  currentPrice: number
}

// поля: units_after, reason (select, опц.), note (опц.), occurred_on (default today)
// показываем live: delta = units_after - currentUnits, value_delta_usd = delta * currentPrice
// warning: "Это изменит стоимость портфеля на ${formatCurrency(value_delta_usd)} и PnL на ту же сумму. Net Invested не изменится."
```

#### `WalletSelector.tsx` (переиспользуемый)

Используется внутри `ContributeModal` (режим «по монетам»), `SwapModal`,
`WithdrawModal`. Если у портфеля 1 кошелёк — селект скрыт, выбран автоматически.

### 4.5 Обновления существующих модалок

#### `ContributeModal` (режим «По монетам»)

Над списком позиций — `<WalletSelector>` (общий для всех позиций добавления).
Передавать `wallet_id` в `portfolioApi.contributeByUnits`.

#### `SwapModal`

В шаге «form» добавить вверху `<WalletSelector>`. В селекте `from_symbol`
показывать **только активы с `units > 0` на выбранном кошельке**.

#### `WithdrawModal`

Для каждой строки актива добавить селект кошелька (по умолчанию — кошелёк
с наибольшим балансом этого символа).

### 4.6 Иконки

`lucide-react`:
- Кошелёк-биржа: `Building2`
- Холодный: `Snowflake`
- Горячий: `Flame`
- Банк: `Landmark`
- Другое: `Wallet`
- Перевод: `ArrowLeftRight`
- Коррекция: `Pencil` или `SlidersHorizontal`

---

## 5. Тесты — `backend/portfolios/tests/`

### 5.1 `test_wallets.py`

- `test_create_wallet` — успешное создание; первый кошелёк автоматически
  становится `is_default=True`.
- `test_create_wallet_duplicate_name_rejected` — 400.
- `test_update_wallet_name_and_type`.
- `test_delete_wallet_with_zero_holdings_ok`.
- `test_delete_wallet_with_balance_rejected` — 400.
- `test_delete_default_wallet_rejected` — 400.

### 5.2 `test_wallet_transfer.py`

- `test_transfer_basic` — 0.04 BTC из A в B (без fee): from=−0.04, to=+0.04,
  агрегатные `PortfolioAsset.units` не изменились.
- `test_transfer_with_fee` — from=0.04, to=0.0395: разница попадает в
  `fee_units=0.0005`, `fee_usd > 0`, агрегат уменьшился на 0.0005,
  Portfolio Value упал на `fee_usd`, PnL упал на `fee_usd`,
  Net Invested **не изменился**.
- `test_transfer_insufficient_balance_400`.
- `test_transfer_to_units_greater_than_from_400` — нельзя получить больше,
  чем списано.
- `test_transfer_same_wallet_400`.
- `test_transfer_unsupported_symbol_400`.
- `test_transfer_creates_holdings_in_target_if_missing` — если в `to_wallet`
  нет `WalletHolding(symbol)`, он создаётся.
- `test_transfer_recomputes_percentages` — Σ percentage ≈ 100 после операции.

### 5.3 `test_holding_adjustment.py`

- `test_adjust_decrease` — units 0.5 → 0.498, delta=−0.002, value_delta_usd<0,
  Portfolio Value упал, PnL упал, Net Invested без изменений.
- `test_adjust_increase` — units 0.5 → 0.6, delta=+0.1, value_delta_usd>0,
  Portfolio Value вырос.
- `test_adjust_to_zero` — допустимо.
- `test_adjust_negative_units_rejected` — 400 (units_after < 0).
- `test_adjust_no_reason_no_note_ok` — оба поля опциональны.
- `test_adjust_creates_holding_if_missing` — на кошельке не было — создаётся.
- `test_adjust_syncs_aggregate` — `PortfolioAsset.units == Σ holdings`.
- `test_adjust_recomputes_percentages`.

### 5.4 `test_invariants.py`

- `test_invariant_after_contribute_by_units`.
- `test_invariant_after_swap`.
- `test_invariant_after_withdraw`.
- `test_invariant_after_transfer`.
- `test_invariant_after_adjustment`.
- `test_invariant_after_import`.

Каждый: после операции для всех `PortfolioAsset(portfolio, symbol)` —
`units == Σ WalletHolding.units` (по тому же портфелю и символу).

### 5.5 Доработка существующих тестов

- `test_contribute_by_units_writes_to_default_wallet_when_no_wallet_id`.
- `test_contribute_by_units_writes_to_specified_wallet`.
- `test_swap_within_specified_wallet` — обмен внутри одного кошелька.
- `test_swap_uses_default_wallet_if_not_specified`.
- `test_swap_insufficient_on_specific_wallet` — даже если на агрегате хватает,
  но на конкретном кошельке нет — 400.
- `test_withdraw_from_specific_wallet`.
- `test_withdraw_picks_largest_holding_when_no_wallet_id`.
- `test_import_creates_default_wallet_with_holdings`.
- `test_create_portfolio_creates_default_wallet`.

### 5.6 `test_backfill_wallets_migration.py`

- Загрузить fixture: портфели в состоянии PLAN05 (без Wallet).
- Применить миграцию `0010_backfill_default_wallets`.
- Убедиться: для каждого портфеля создан `Wallet(is_default=True, name='Общий кошелёк')`,
  все `PortfolioAsset` отражены в `WalletHolding(default_wallet, symbol, units)`,
  инвариант выполнен.

### 5.7 Запуск

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest portfolios/tests/test_wallets.py portfolios/tests/test_wallet_transfer.py portfolios/tests/test_holding_adjustment.py portfolios/tests/test_invariants.py -v
pytest portfolios/tests/ -v
```

---

## 6. Порядок внедрения

### Этап 1. Backend — модели и миграции

1. Дописать `Wallet`, `WalletHolding`, `WalletTransfer`, `HoldingAdjustment`.
2. Создать и применить миграции:

   ```powershell
   cd backend
   .\venv\Scripts\Activate.ps1
   python manage.py makemigrations portfolios -n wallets_holdings_transfers_adjustments
   python manage.py makemigrations portfolios -n backfill_default_wallets --empty
   # вписать backfill_default_wallets
   python manage.py migrate
   ```

3. Зарегистрировать модели в `admin.py`.

### Этап 2. Backend — сервис

1. Реализовать `WalletLedger` в `services.py`.
2. Покрыть юнит-тестами (`add_units`, `aggregate_units`, `sync_aggregate`).

### Этап 3. Backend — API

1. Сериализаторы (`WalletSerializer`, `WalletInputSerializer`,
   `WalletTransferInputSerializer`, `HoldingAdjustmentInputSerializer` и т.д.).
2. Вьюхи (`WalletListCreateView`, `WalletDetailView`, `WalletTransferView`,
   `HoldingAdjustView`).
3. URL-маршруты.
4. Доработка `ContributePortfolioView`, `SwapExecuteView`,
   `WithdrawPortfolioView`, `PortfolioImportView`,
   `PortfolioCreateSerializer.create` — на запись через `WalletLedger`.
5. Расширение `PortfolioCapitalSummaryView` секцией `wallets`.

### Этап 4. Backend — тесты

1. Реализовать `test_wallets.py`, `test_wallet_transfer.py`,
   `test_holding_adjustment.py`, `test_invariants.py`,
   `test_backfill_wallets_migration.py`.
2. Доработать существующие тесты на новые контракты с `wallet_id`.
3. Прогнать:

   ```powershell
   pytest portfolios/tests/ -v
   ```

### Этап 5. Frontend — API + store

1. Дописать `walletsApi` и расширить `portfolioApi.contributeByUnits` /
   `executeSwap` / `withdraw` (новое `wallet_id`).
2. Добавить в `portfolioStore.ts`: `wallets`, `fetchWallets`, `createWallet`,
   `updateWallet`, `deleteWallet`, `transferBetweenWallets`, `adjustHolding`.

### Этап 6. Frontend — UI

1. `WalletCard.tsx`, `WalletFormModal.tsx`,
   `TransferBetweenWalletsModal.tsx`, `AdjustHoldingModal.tsx`,
   `WalletSelector.tsx`.
2. На дашборде — секция «Мои кошельки» с карточками.
3. В таблице активов — разрез по кошелькам и кнопка коррекции ✏.
4. Интеграция `WalletSelector` в `ContributeModal` (режим «по монетам»),
   `SwapModal`, `WithdrawModal`.
5. Скрытие селекта, если у портфеля 1 кошелёк.

### Этап 7. Smoke-тест end-to-end

```powershell
# терминал 1
cd backend
.\venv\Scripts\Activate.ps1
python manage.py runserver

# терминал 2
cd frontend
npm run dev
```

Сценарий:

1. **Существующий пользователь** (после миграции): на дашборде появилась
   секция «Мои кошельки» с одной карточкой «Общий кошелёк», содержащей все
   текущие активы. Стоимость и PnL не изменились.
2. **Создать кошелёк «Ledger»** (тип `cold`).
3. **Перевод 0.04 BTC из «Общий кошелёк» → «Ledger»** без комиссии:
   - На Общий: BTC уменьшился, на Ledger — появился.
   - PortfolioAsset.units (BTC) не изменился.
   - Portfolio Value не изменился.
4. **Перевод с комиссией 0.001 BTC**: записан `fee_units`, Portfolio Value
   просел на ~$50, PnL просел на ~$50, Net Invested без изменений.
5. **Ручная коррекция «Ledger»: 1.0 BTC → 0.998 BTC**:
   - В таблице активов нашли строку «BTC | Ledger», нажали ✏.
   - Видим warning «PnL уменьшится на ~$100».
   - Подтвердили → PnL и Portfolio Value уменьшились, Net Invested не изменился.
   - В админке появился `HoldingAdjustment(reason='', delta=-0.002)`.
6. **Покупка 0.01 BTC по монетам с указанием wallet=«Ledger»**:
   - Балансы Общего не изменились, Ledger вырос на 0.01 BTC.
   - PortfolioAsset.units (BTC) вырос на 0.01.
   - Net Invested увеличился (через автоматическую `CapitalTransaction` из PLAN05).
7. **Swap внутри Ledger**: USDT→BTC. Баланс Общего не затрагивается.
8. **Удалить Ledger** (если не дефолтный и пуст) → 204.
9. **Проверка инварианта**: после всех операций для всех символов
   `PortfolioAsset.units == Σ WalletHolding.units`.

PowerShell-смок-скрипт: `scripts/smoke_plan06.ps1` — автоматизирует пп. 2–7
через REST.

---

## 7. Совместимость и риски

| Риск / нюанс | Решение |
|---|---|
| `PortfolioAsset.units` теперь — производная от Holdings; прямые мутации могут разрушить инвариант. | Все операции записывают через `WalletLedger.add_units(...)` + `sync_aggregate(...)`. Прямое присваивание `asset.units = X` запрещено в новых view-х. Старые места доработаны. Покрытие тестом `test_invariants.py`. |
| Существующий код фронта читает `portfolioValue.assets[i].units` — это агрегатные значения. | Они **остаются корректны** после `sync_aggregate`. Старый дашборд продолжит работать без правок, новый — добавит разрез по кошелькам сверху. |
| Удаление кошелька с активами — потеря данных. | API запрещает удаление кошелька с ненулевыми Holdings (400). Фронт показывает соответствующее сообщение. |
| Удаление дефолтного кошелька. | Запрещено (400). Сначала пользователь должен назначить другой как `is_default`. |
| Swap из кошелька, на котором нет `from_symbol`. | Возвращаем 400 с сообщением «Недостаточно X на кошельке Y». |
| Перевод комиссии: `to_units > from_units` (баг или мошенничество). | Серверная валидация: `to_units <= from_units` (max разница = 0). Для увеличения баланса — отдельная операция «коррекция». |
| Cost basis (`PortfolioAsset.initial_price`) при свопе с участием нового кошелька. | Не меняется — он остаётся «средневзвешенной по портфелю», не на уровне кошелька. Влияет только на отображение per-asset «вложенная стоимость», которое и так информационное. |
| Старые портфели с DCA-коррекцией (units_scale < 1). | Дата-миграция переносит `PortfolioAsset.units` (raw) в Holdings. `PortfolioAnalyzer` продолжает применять scale на чтение — отображение не меняется. После первого `finalize_dca_scale()` (через contribute/swap) все units консолидируются. Покрыть тестом регрессии. |
| Множество кошельков → запросы CoinGecko раздуваются. | На дашборде — один общий вызов `get_prices(symbols)` с уникальными символами. Кэш в `PriceService` защищает от дубликатов. |
| Перевод фиата (USDT) между кошельками + ручная коррекция = двойной учёт изменения PnL. | Чёткое разграничение: transfer **с fee** уже фиксирует потерю в Portfolio Value. Если пользователь дополнительно нажмёт ✏ — вторая операция, отражается отдельно. UI показывает warning. |
| Импортированный портфель имеет `is_imported=True` — нужно ли создавать «Импортированный» как дефолтный? | Да. В первой версии импорт = один кошелёк (бирж пользователь не указывал). В будущем — добавить шаг распределения активов по кошелькам. |
| LLM-промпты используют `assets[]` со старыми полями. | Контракт сохранён: `units`, `current_value`, `percentage` остаются на уровне `PortfolioAsset` и доступны через `portfolio_value` в контексте промпта. |

---

## 8. Критерии готовности

- [ ] Пользователь может создать произвольное количество кошельков с
      именем и типом.
- [ ] На дашборде видно карточки кошельков с балансами по монетам и
      USD-эквивалентом.
- [ ] Инвариант: для каждого `(portfolio, symbol)` сумма Holdings равна
      `PortfolioAsset.units`. Покрыто автотестом.
- [ ] Перевод между кошельками с указанием комиссии (`from_units >= to_units`)
      работает; разница попадает в `fee_units`/`fee_usd`. Net Invested
      не меняется, Portfolio Value уменьшается на величину комиссии.
- [ ] Ручная коррекция холдинга работает в обоих направлениях,
      приводит к корректному пересчёту Portfolio Value и PnL,
      Net Invested не меняется.
- [ ] При коррекции UI показывает warning о влиянии на PnL.
- [ ] Поля «причина» и «заметка» при коррекции опциональны.
- [ ] Покупка по монетам, swap, вывод средств принимают `wallet_id`.
      По умолчанию используется дефолтный кошелёк (или кошелёк с
      наибольшим балансом — для вывода).
- [ ] Старые портфели после миграции автоматически получают «Общий кошелёк»
      и продолжают работать без потери данных.
- [ ] Все тесты из п. 5 проходят, регрессия PLAN04/PLAN05 — без падений.

---

## 9. Опционально (вне scope)

- **Per-wallet PnL** — потребует добавить `initial_price` в `WalletHolding` и
  переносить cost basis при transfer (FIFO/AVCO).
- **Распределение по типам** — виджет «горячие vs холодные» для риск-аналитики:
  «70% капитала в холодных кошельках».
- **Шаг импорта**: при создании портфеля через импорт — диалог распределения
  по кошелькам («у вас на Binance 0.5 BTC + 1000 USDT, на Ledger 0.3 BTC»).
- **Авто-импорт балансов с биржи** через API-ключ (read-only).
- **Кросс-кошельковые свопы** — отдельный workflow «transfer + swap» в одной
  операции.
- **История переводов** на дашборде — лента всех `WalletTransfer` и
  `HoldingAdjustment` с фильтрами по кошельку и дате.
- **Экспорт CSV** по кошелькам и операциям.
- **Лимиты безопасности** — предупреждение «вы держите > X% капитала на одной
  бирже».
