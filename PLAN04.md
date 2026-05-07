# PLAN04: Покупка конкретного количества монет и обмен активов (swap)

## Цель

Добавить две новые операции с активным портфелем (демо-счёт):

1. **Пополнение конкретным количеством монеты** — пользователь может докупить
   произвольное количество единиц нужного актива из списка
   *«текущие монеты портфеля + ТОП-10 CoinGecko + стейблкоины»*.
   Поддерживается ввод цены покупки (по умолчанию — текущий рыночный курс).
2. **Обмен (swap) между активами портфеля** — обмен стейблкоинов на инвестиционный
   актив (BTC, ETH, SOL и т.д.) и обратный обмен. Расчёт идёт по текущему курсу
   CoinGecko, но пользователь обязательно может **скорректировать вручную**
   итоговое количество получаемой монеты (биржевые комиссии, slippage,
   расхождение курсов между биржами).

Существующая логика «Внести взнос в USD (DCA)» **не удаляется**, а становится
одним из режимов пополнения портфеля.

---

## 1. Пользовательские сценарии

### 1.1 Пополнение конкретной монетой

```
[Дашборд] → кнопка «Пополнить»
        │
        ▼
┌─────────────────────────────────────────────┐
│  Модалка «Пополнить портфель»               │
│  ┌─────────────┐  ┌────────────────────┐   │
│  │ По сумме $  │  │ По монетам         │   │
│  │   (DCA)     │  │ (ручная покупка)   │   │
│  └─────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────┘
        │
        ▼ (выбран режим «По монетам»)
        │
[Список позиций для добавления]
   ─ выбор монеты из выпадающего списка
     (текущие активы портфеля ∪ ТОП-10 ∪ стейблкоины)
   ─ ввод количества (units)
   ─ опц. ввод цены покупки (по умолчанию — текущая)
   ─ опц. кнопка «+ Добавить ещё монету»
        │
        ▼
[Превью] — рассчёт total_value_usd, обновлённые доли портфеля
        │
        ▼
POST /api/portfolio/contribute/units/
        │
        ▼
[Успех] → обновлённый дашборд
```

**Результат на бэкенде:**

- Для каждой позиции с `units > 0`:
  - Если актив **уже есть** в портфеле — увеличиваются `units`, пересчитывается
    средневзвешенная `initial_price`.
  - Если актива **нет** — создаётся новый `PortfolioAsset` с `is_recommended` = (символ ∈ ТОП-10).
- `Portfolio.initial_amount` += `Σ units * purchase_price` (фиксируем фактически вложенный USD).
- Создаётся одна запись `PortfolioContribution` с детализацией через
  `PortfolioContributionItem` (см. ниже).
- Все `percentage` в портфеле **пересчитываются** по текущей рыночной стоимости.

### 1.2 Обмен (swap) активов

```
[Дашборд] → кнопка «Обменять»
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ Шаг 1. Что меняем?                                  │
│ ─ Из (актив портфеля): [USDT ▼]   units: [1000.00]  │
│ ─ В (актив портфеля или ТОП-10): [BTC ▼]            │
│   текущий курс: 1 USDT = 0.0000105 BTC              │
│   получите ≈ 0.01050000 BTC                          │
└─────────────────────────────────────────────────────┘
        │  «Далее»
        ▼
┌─────────────────────────────────────────────────────┐
│ Шаг 2. Подтверждение и ручная коррекция             │
│ ─ Списать: 1000.00 USDT (≈ $1000.00)                │
│ ─ Получить: [0.01045000] BTC ← редактируется!        │
│   (биржа взяла комиссию ~0.5%; курс отличается)     │
│ ─ Авто-комиссия = разница в $: $4.76 → запишется    │
│   в PortfolioSwap.fee_usd для аналитики             │
└─────────────────────────────────────────────────────┘
        │  «Подтвердить»
        ▼
POST /api/portfolio/swap/
        │
        ▼
[Успех] → обновлённый дашборд
```

**Правила обмена:**

- **Из** — только актив, **уже находящийся в портфеле** (нельзя «продать то, чего нет»).
- **В** — любой актив из (текущие монеты ∪ ТОП-10 ∪ стейблкоины).
- `from_units` ≤ `units_current` (с учётом `units_scale` для DCA).
- `to_units` редактируется пользователем; по умолчанию `to_units = (from_units * from_price) / to_price`.
- `Portfolio.initial_amount` **не меняется** (это перераспределение, а не приток капитала).
- `PortfolioContribution` / `PortfolioWithdrawal` **не создаются**.
- Если из-за коррекции стоимость портфеля изменилась — это нормально (отразится в P/L и просадке).
- Если в результате обмена `units` исходного актива стало 0 — **актив не удаляется**, остаётся с `units = 0` и `percentage = 0` (чтобы сохранить историю); удалить можно через реструктуризацию.

### 1.3 Список доступных монет

Единая утилита (см. п. 2.4) возвращает объединение:

1. Все символы текущих `PortfolioAsset` активного портфеля.
2. ТОП-10 по капитализации (без стейблкоинов): `PriceService.get_top10_recommended_symbols()`.
3. Стейблкоины: `USDT`, `USDC` (минимально достаточно).

---

## 2. Backend — изменения

### 2.1 Модели — `backend/portfolios/models.py`

#### Новая модель `PortfolioContributionItem`

```python
class PortfolioContributionItem(models.Model):
    """Детализация взноса по конкретной монете (для режима «по монетам»)."""

    contribution = models.ForeignKey(
        PortfolioContribution,
        on_delete=models.CASCADE,
        related_name='items',
    )
    symbol = models.CharField(max_length=10)
    units = models.DecimalField(max_digits=20, decimal_places=8)
    purchase_price = models.DecimalField(max_digits=20, decimal_places=8)
    value_usd = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = 'Позиция взноса'
        verbose_name_plural = 'Позиции взносов'
```

#### Новая модель `PortfolioSwap`

```python
class PortfolioSwap(models.Model):
    """Обмен одного актива портфеля на другой (внутренняя операция, без cash-in/out)."""

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='swaps',
    )

    from_symbol = models.CharField(max_length=10)
    from_units = models.DecimalField(max_digits=20, decimal_places=8)
    from_price = models.DecimalField(max_digits=20, decimal_places=8)

    to_symbol = models.CharField(max_length=10)
    to_units = models.DecimalField(max_digits=20, decimal_places=8)
    to_price = models.DecimalField(max_digits=20, decimal_places=8)

    # Расчётное количество to_units по рынку (для аналитики)
    to_units_expected = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )

    # Разница в USD между ожидаемым и фактическим (комиссия + slippage)
    fee_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Комиссия / разница ($)'
    )

    note = models.CharField(max_length=200, blank=True)

    swapped_at = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Обмен активов'
        verbose_name_plural = 'Обмены активов'
        ordering = ['-swapped_at']

    def __str__(self):
        return f'{self.from_units} {self.from_symbol} → {self.to_units} {self.to_symbol}'
```

#### Миграция

`backend/portfolios/migrations/0006_contribution_items_and_swaps.py` — авто-сгенерированная.

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python manage.py makemigrations portfolios -n contribution_items_and_swaps
python manage.py migrate
```

### 2.2 Сериализаторы — `backend/portfolios/serializers.py`

```python
class ContributionItemInputSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=10)
    units = serializers.FloatField(min_value=0.0)
    purchase_price = serializers.FloatField(required=False, allow_null=True, min_value=0.0)
    purchased_at = serializers.DateField(required=False, allow_null=True)

    def validate_symbol(self, value):
        sym = value.upper().strip()
        if not PriceService.is_symbol_supported(sym):
            raise serializers.ValidationError(
                f"Символ '{sym}' не поддерживается."
            )
        return sym


class ContributeByUnitsSerializer(serializers.Serializer):
    items = ContributionItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('Укажите хотя бы одну позицию.')
        # запрещаем нулевые units
        for it in value:
            if it.get('units', 0) <= 0:
                raise serializers.ValidationError('Количество должно быть больше нуля.')
        return value


class SwapInputSerializer(serializers.Serializer):
    from_symbol = serializers.CharField(max_length=10)
    from_units = serializers.FloatField(min_value=0.0)
    to_symbol = serializers.CharField(max_length=10)
    to_units = serializers.FloatField(min_value=0.0)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        attrs['from_symbol'] = attrs['from_symbol'].upper().strip()
        attrs['to_symbol'] = attrs['to_symbol'].upper().strip()
        if attrs['from_symbol'] == attrs['to_symbol']:
            raise serializers.ValidationError('Из и В не могут совпадать.')
        if attrs['from_units'] <= 0 or attrs['to_units'] <= 0:
            raise serializers.ValidationError('Количество должно быть больше нуля.')
        for sym in (attrs['from_symbol'], attrs['to_symbol']):
            if not PriceService.is_symbol_supported(sym):
                raise serializers.ValidationError(f"Символ '{sym}' не поддерживается.")
        return attrs
```

### 2.3 Views — `backend/portfolios/views.py`

#### Расширение `ContributePortfolioView`

Сделать **двухрежимной**:

- Старый формат `{ "amount": <usd> }` — режим DCA (без изменений).
- Новый формат `{ "items": [...] }` — режим «по монетам». Делегирует в
  `_contribute_by_units(portfolio, items)`.

```python
def post(self, request):
    portfolio = ...  # как сейчас

    items = request.data.get('items')
    if items is not None:
        return self._contribute_by_units(portfolio, request.data)

    # ниже — текущая логика «по сумме $»
    ...
```

`_contribute_by_units` алгоритм:

1. Валидация `ContributeByUnitsSerializer`.
2. Получить текущие цены для всех уникальных `symbol` из `items` через `PriceService.get_prices`.
3. Если в портфеле сейчас активна **DCA-коррекция** (см. `PortfolioAnalyzer.get_units_scale()`),
   **«затвердить» её**: для каждого существующего `PortfolioAsset`
   `asset.units = asset.units * units_scale`, и пересчитать
   `Portfolio.initial_amount` так, чтобы при последующем чтении `units_scale == 1.0`.
   *(Альтернатива — внести флаг `dca_finalized` в `Portfolio`. Решение: достаточно фактического пересчёта.)*
   Это нужно, чтобы новые «реальные» units не масштабировались.
4. Для каждой позиции `(symbol, units, purchase_price?)`:
   - `purchase_price = purchase_price or current_price[symbol]`.
   - `value_usd = units * purchase_price`.
   - Если `PortfolioAsset` существует: новая
     `initial_price = (old_units * old_initial_price + units * purchase_price) / (old_units + units)`,
     `units += units`.
   - Иначе создать новый с `is_recommended = symbol in top10_set`,
     `initial_price = purchase_price`, `units = units`,
     `purchased_at = purchased_at` (если передан).
   - Записать `PortfolioContributionItem`.
5. `Portfolio.initial_amount` += `Σ value_usd`.
6. Создать `PortfolioContribution(amount = Σ value_usd)` (для совместимости с историей).
7. **Пересчитать `percentage`** всех активов:
   `percentage_i = units_i * current_price_i / total_current_value * 100`.
8. Сохранить и вернуть актуальный `PortfolioSerializer`.

#### Новые view: котировка swap

```python
class SwapQuoteView(APIView):
    """Расчёт котировки обмена по текущему курсу."""
    permission_classes = (AllowAny,)

    def get(self, request):
        portfolio = ...  # активный
        from_symbol = (request.query_params.get('from_symbol') or '').upper()
        to_symbol = (request.query_params.get('to_symbol') or '').upper()
        try:
            from_units = float(request.query_params.get('from_units') or 0)
        except ValueError:
            return Response({'detail': 'from_units некорректен.'}, status=400)
        # валидация: from_symbol — реально в портфеле; ...
        # цены, расчёт to_units_expected = from_units * from_price / to_price
        # вернуть {from_units, from_price, to_price, to_units_expected, value_usd}
```

#### Новый view: исполнение swap

```python
class SwapExecuteView(APIView):
    permission_classes = (AllowAny,)

    @transaction.atomic
    def post(self, request):
        portfolio = ...  # активный
        s = SwapInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        # 1. Найти PortfolioAsset(from_symbol)
        # 2. Учесть units_scale для DCA-портфелей (см. WithdrawPortfolioView)
        # 3. Проверить from_units <= units_available
        # 4. Получить цены
        # 5. Списать from_units c исходного актива (asset.units -= from_units / scale)
        # 6. Найти/создать PortfolioAsset(to_symbol):
        #    - если есть: асинхронно пересчитать initial_price (средневзвешенная)
        #    - если нет: создать с initial_price = to_price (рыночной), is_recommended ∈ top10
        # 7. Зачислить to_units (с учётом scale аналогично 5).
        # 8. Сохранить PortfolioSwap с
        #    to_units_expected = from_units * from_price / to_price,
        #    fee_usd = (to_units_expected - to_units) * to_price.
        # 9. Пересчитать percentage всех активов по рыночной стоимости.
        # 10. Вернуть PortfolioSerializer + summary swap.
```

> **Важно про `units_scale`:** в `WithdrawPortfolioView` и `RebalancePortfolioView`
> уже есть аналогичная логика. Чтобы не дублировать, вынести «применение scale
> и затвердевание DCA» в утилиту в `PortfolioAnalyzer` (см. п. 2.5).

### 2.4 Утилита «список доступных монет для покупки/обмена»

В `PriceService` (`backend/portfolios/services.py`) добавить:

```python
class PriceService:
    # ...

    @classmethod
    def get_stablecoin_symbols(cls) -> List[str]:
        """Стейблкоины, доступные для swap по умолчанию."""
        return ['USDT', 'USDC']

    def get_available_for_trade(self, portfolio_symbols: List[str]) -> List[Dict]:
        """
        Список монет, доступных для покупки/обмена в активном портфеле:
        union(текущие активы, ТОП-10, стейблкоины).
        Возвращает [{symbol, name, current_price, is_recommended, in_portfolio}].
        """
        top10 = self.get_top10_recommended_assets()
        top_map = {c['symbol'].upper(): c for c in top10}
        portfolio_set = {s.upper() for s in portfolio_symbols}

        symbols = list(portfolio_set
                       | set(top_map.keys())
                       | set(self.get_stablecoin_symbols()))

        # подтягиваем имена и цены пачкой
        prices = self.get_prices(symbols)
        result = []
        for sym in symbols:
            data = top_map.get(sym, {})
            result.append({
                'symbol': sym,
                'name': data.get('name') or sym,
                'current_price': prices.get(sym, 0),
                'is_recommended': sym in top_map,
                'in_portfolio': sym in portfolio_set,
                'is_stable': sym in cls.get_stablecoin_symbols(),
            })
        # сортировка: сначала текущие портфельные, потом ТОП-10, потом остальные
        result.sort(key=lambda x: (not x['in_portfolio'], not x['is_recommended'], x['symbol']))
        return result
```

И новый view:

```python
class TradableAssetsView(APIView):
    """Список монет, доступных для пополнения / обмена."""
    permission_classes = (AllowAny,)

    def get(self, request):
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id, is_active=True
        ).first()
        symbols = [a.symbol for a in portfolio.assets.all()] if portfolio else []
        items = PriceService().get_available_for_trade(symbols)
        return Response({'assets': items, 'count': len(items)})
```

### 2.5 Рефакторинг — общая утилита для DCA-затвердевания

Добавить в `PortfolioAnalyzer` метод:

```python
def finalize_dca_scale(self) -> float:
    """
    Если активна DCA-коррекция (units_scale < 1.0), «затвердить» её:
    units каждого актива = units * scale, initial_amount пересчитывается так,
    чтобы дальнейшие операции работали с реальными units (scale = 1.0).
    Возвращает применённый scale.
    """
    scale = self.get_units_scale()
    if scale >= 1.0 - 1e-9:
        return 1.0
    with transaction.atomic():
        for asset in self.portfolio.assets.all():
            if asset.units:
                asset.units = float(asset.units) * scale
                asset.save(update_fields=['units'])
        # после finalize total_invested рассчитанный из contributions + initial_amount
        # должен быть = текущему отображаемому. Простейший вариант:
        # initial_amount := total_invested * scale,
        # но это дёшево и надёжно только если DCA ещё не «достроена» полностью.
        # Безопасно: пересчитать initial_amount = (initial_amount * scale).
        new_initial = float(self.portfolio.initial_amount) * scale
        self.portfolio.initial_amount = round(new_initial, 2)
        self.portfolio.save(update_fields=['initial_amount'])
    return scale
```

Использовать его в `ContributePortfolioView._contribute_by_units` и в `SwapExecuteView`
**до** изменения units, чтобы новые операции работали в одной системе координат.

### 2.6 URL-маршруты — `backend/portfolios/urls.py`

```python
path('contribute/', ContributePortfolioView.as_view(), ...),  # уже есть; теперь двухрежимный
path('swap/quote/', SwapQuoteView.as_view(), name='portfolio_swap_quote'),
path('swap/', SwapExecuteView.as_view(), name='portfolio_swap'),
path('tradable-assets/', TradableAssetsView.as_view(), name='portfolio_tradable_assets'),
```

### 2.7 Helper — «пересчёт долей по рынку»

Чтобы не дублировать в трёх местах (contribute-by-units, swap, на будущее), вынести в
`backend/portfolios/services.py`:

```python
def recompute_percentages_by_market(portfolio: Portfolio, prices: Dict[str, float]) -> None:
    """Пересчитать PortfolioAsset.percentage пропорционально текущей рыночной стоимости."""
    assets = list(portfolio.assets.all())
    values = []
    total = 0.0
    for a in assets:
        units = float(a.units or 0)
        price = prices.get(a.symbol, 0) or float(a.initial_price or 0)
        v = units * price
        values.append(v)
        total += v
    if total <= 0:
        return
    for a, v in zip(assets, values):
        a.percentage = round(v / total * 100, 2)
        a.save(update_fields=['percentage'])
    # выравнивание округления, чтобы Σ = 100
    diff = 100.0 - sum(float(a.percentage) for a in portfolio.assets.all())
    if abs(diff) > 0.001 and assets:
        last = portfolio.assets.order_by('-id').first()
        last.percentage = round(float(last.percentage) + diff, 2)
        last.save(update_fields=['percentage'])
```

---

## 3. Frontend — изменения

### 3.1 Расширение API-клиента — `frontend/src/services/api.ts`

```ts
contribute: async (amount: number) => {
  const response = await api.post('/portfolio/contribute/', { amount })
  return response.data
},

contributeByUnits: async (
  items: Array<{
    symbol: string
    units: number
    purchase_price?: number
    purchased_at?: string
  }>
) => {
  const response = await api.post('/portfolio/contribute/', { items })
  return response.data
},

getSwapQuote: async (params: {
  from_symbol: string
  to_symbol: string
  from_units: number
}) => {
  const response = await api.get('/portfolio/swap/quote/', { params })
  return response.data as {
    from_symbol: string
    from_units: number
    from_price: number
    to_symbol: string
    to_units_expected: number
    to_price: number
    value_usd: number
  }
},

executeSwap: async (data: {
  from_symbol: string
  from_units: number
  to_symbol: string
  to_units: number
  note?: string
}) => {
  const response = await api.post('/portfolio/swap/', data)
  return response.data
},

getTradableAssets: async () => {
  const response = await api.get('/portfolio/tradable-assets/')
  return response.data as {
    assets: Array<{
      symbol: string
      name: string
      current_price: number
      is_recommended: boolean
      in_portfolio: boolean
      is_stable: boolean
    }>
    count: number
  }
},
```

### 3.2 Обновление стора — `frontend/src/store/portfolioStore.ts`

Добавить экшены:

```ts
contributeByUnits: (items: Array<{
  symbol: string
  units: number
  purchase_price?: number
  purchased_at?: string
}>) => Promise<void>

swap: (data: {
  from_symbol: string
  from_units: number
  to_symbol: string
  to_units: number
  note?: string
}) => Promise<void>
```

Реализация — по образцу `contribute` / `withdraw` (вызов API → обновить
`portfolioValue` через `getValue()`).

### 3.3 Расширение `ContributeModal.tsx`

Добавить переключатель режимов в верхней части модалки:

```tsx
type Mode = 'usd' | 'units'
const [mode, setMode] = useState<Mode>('usd')
```

В режиме `usd` — текущий UI (без изменений).

В режиме `units` — список добавляемых позиций:

```tsx
interface Position {
  id: string         // local
  symbol: string
  units: string      // input
  price: string      // input (опционально)
}

const [positions, setPositions] = useState<Position[]>([
  { id: '1', symbol: '', units: '', price: '' },
])
```

UI: для каждой позиции — селект монеты (`tradableAssets`), input количества,
input цены (опц.), кнопка «удалить». Снизу кнопка «+ Добавить ещё монету».

Подвал:
- Сводка: `Всего: $${formatCurrency(totalUsd)}`.
- При сабмите — `portfolioApi.contributeByUnits(positions)`.

Загрузку списка `tradableAssets` делать через `useEffect` при открытии модалки.

### 3.4 Новый компонент `SwapModal.tsx`

`frontend/src/components/portfolio/SwapModal.tsx`:

Шаги:
- `'form'` — выбор из/в и `from_units`.
- `'preview'` — расчётное `to_units_expected`, поле для редактирования `to_units`,
  предупреждение о комиссии. Кнопки «Назад» / «Подтвердить».
- `'success'` — подтверждение.

Ключевые состояния:

```tsx
const [step, setStep] = useState<'form' | 'preview' | 'success'>('form')
const [fromSymbol, setFromSymbol] = useState('')
const [toSymbol, setToSymbol] = useState('')
const [fromUnits, setFromUnits] = useState('')
const [toUnitsEdited, setToUnitsEdited] = useState('')
const [quote, setQuote] = useState<SwapQuote | null>(null)
```

При шаге `form` → клик «Далее»:
```ts
const q = await portfolioApi.getSwapQuote({
  from_symbol: fromSymbol,
  to_symbol: toSymbol,
  from_units: parseFloat(fromUnits),
})
setQuote(q)
setToUnitsEdited(q.to_units_expected.toFixed(8))
setStep('preview')
```

При шаге `preview` → клик «Подтвердить»:
```ts
await store.swap({
  from_symbol: fromSymbol,
  from_units: parseFloat(fromUnits),
  to_symbol: toSymbol,
  to_units: parseFloat(toUnitsEdited),
})
setStep('success')
```

UI коррекции: разница `to_units_edited - to_units_expected` подсвечивается жёлтым;
показываем оценку «комиссии» в $.

В `from_symbol` — селект **только из текущих активов портфеля** (`assets`).
В `to_symbol` — селект из всех `tradableAssets` (включая текущие активы и ТОП-10).

### 3.5 Дашборд — `frontend/src/app/dashboard/page.tsx`

В блоке кнопок действий (рядом с «Пополнить» / «Вывести») добавить «Обменять»:

```tsx
<Button onClick={() => setShowSwapModal(true)} variant="secondary">
  <ArrowLeftRight className="w-4 h-4 mr-1" />
  Обменять
</Button>
```

И сам компонент:

```tsx
<SwapModal
  isOpen={showSwapModal}
  onClose={() => setShowSwapModal(false)}
  portfolioAssets={assets}
/>
```

Существующая `<ContributeModal />` остаётся — внутри добавляется
переключатель режимов (см. п. 3.3).

### 3.6 Иконки

Использовать иконки из `lucide-react`:
- «Обменять» — `ArrowLeftRight`.
- «Купить монету» в `ContributeModal` — `Coins`.

---

## 4. Тесты — `backend/portfolios/tests/`

### 4.1 `test_contribute_by_units.py`

Сценарии:
- `test_contribute_by_units_existing_asset` — докупка в уже существующий BTC:
  units увеличиваются, средневзвешенная `initial_price` корректна,
  `Portfolio.initial_amount` += `units * price`.
- `test_contribute_by_units_new_asset` — добавление новой монеты, которой не было:
  создаётся `PortfolioAsset` с `is_recommended` = True (если в ТОП-10).
- `test_contribute_by_units_alt_outside_top10` — добавление SHIB:
  `is_recommended = False`.
- `test_contribute_by_units_recomputes_percentages` — после операции
  Σ `percentage` ≈ 100, доли соответствуют рыночной стоимости.
- `test_contribute_by_units_finalizes_dca_scale` — после операции в DCA-портфеле
  `units_scale == 1.0`, текущая стоимость не «прыгает».
- `test_contribute_by_units_invalid_symbol` — отказ.
- `test_contribute_by_units_zero_units` — отказ.
- `test_contribute_by_units_creates_contribution_item` — записи в `PortfolioContributionItem`.

### 4.2 `test_swap.py`

Сценарии:
- `test_swap_quote_basic` — стейбл → BTC, проверка расчёта.
- `test_swap_execute_stable_to_btc` — корректное списание USDT, начисление BTC,
  доли пересчитаны, `initial_amount` не изменилось, создан `PortfolioSwap`.
- `test_swap_with_manual_correction` — `to_units` < `to_units_expected`:
  `fee_usd` > 0; стоимость портфеля чуть упала.
- `test_swap_btc_to_stable` — обратный обмен.
- `test_swap_to_new_asset` — обмен в монету, которой не было в портфеле
  (создаётся новый `PortfolioAsset`).
- `test_swap_insufficient_units` — `from_units` > `units_current` → 400.
- `test_swap_same_symbol` → 400.
- `test_swap_unsupported_symbol` → 400.
- `test_swap_finalizes_dca_scale` — DCA-портфель: после swap scale = 1.0.

### 4.3 `test_tradable_assets.py`

- `test_tradable_assets_includes_portfolio_top10_stables` —
  пересечение и метка `in_portfolio`.

### 4.4 Фикстуры

В `backend/conftest.py` (или соответствующем `tests/conftest.py`) добавить
mock `PriceService.get_prices` через `monkeypatch`, как в `test_import.py`,
чтобы тесты не били в реальный CoinGecko.

---

## 5. Порядок внедрения (поэтапно)

### Этап 1. Backend — модели и миграция

1. Дописать `PortfolioContributionItem`, `PortfolioSwap` в `models.py`.
2. Создать и применить миграцию:
   ```powershell
   cd backend
   .\venv\Scripts\Activate.ps1
   python manage.py makemigrations portfolios -n contribution_items_and_swaps
   python manage.py migrate
   ```
3. Зарегистрировать модели в `admin.py` (опционально, для отладки).

### Этап 2. Backend — утилиты

1. Добавить `PriceService.get_stablecoin_symbols`, `get_available_for_trade`.
2. Добавить `recompute_percentages_by_market` в `services.py`.
3. Добавить `PortfolioAnalyzer.finalize_dca_scale` в `advisor/services.py`.

### Этап 3. Backend — API

1. Расширить `ContributePortfolioView` (двухрежимный POST).
2. Создать `SwapQuoteView`, `SwapExecuteView`, `TradableAssetsView`.
3. Добавить новые сериализаторы.
4. Зарегистрировать маршруты.

### Этап 4. Backend — тесты

1. Написать тесты из п. 4.
2. Прогнать:
   ```powershell
   cd backend
   .\venv\Scripts\Activate.ps1
   pytest portfolios/tests/test_contribute_by_units.py portfolios/tests/test_swap.py portfolios/tests/test_tradable_assets.py -v
   ```

### Этап 5. Frontend — API + store

1. Дописать методы в `services/api.ts`.
2. Дописать экшены `contributeByUnits`, `swap` в `portfolioStore.ts`.

### Этап 6. Frontend — UI

1. Расширить `ContributeModal.tsx` (переключатель режимов).
2. Создать `SwapModal.tsx`.
3. Добавить кнопку «Обменять» и подключить `SwapModal` в `dashboard/page.tsx`.

### Этап 7. Smoke-тест end-to-end

1. Запустить backend и frontend:
   ```powershell
   # терминал 1
   cd backend
   .\venv\Scripts\Activate.ps1
   python manage.py runserver

   # терминал 2
   cd frontend
   npm run dev
   ```
2. На дашборде:
   - Пополнить 0.005 BTC по своей цене → проверить, что доли пересчитались.
   - Обменять 100 USDT → BTC, изменить вручную итог на ~95% от расчётного →
     проверить, что в БД `PortfolioSwap.fee_usd > 0`, портфель сошёлся.
   - Обратный обмен BTC → USDT.

---

## 6. Совместимость и риски

| Риск / нюанс | Решение |
|---|---|
| Старые портфели с активной DCA-коррекцией могут «прыгать» по стоимости после первой операции. | `finalize_dca_scale` пересчитывает units и `initial_amount` атомарно — текущая стоимость не меняется, далее всё работает как с `scale = 1.0`. |
| Округление при пересчёте `percentage` — Σ может не равняться 100. | В `recompute_percentages_by_market` остаточная разница записывается в последний актив. |
| Пользователь обменивает всё из актива → актив с `units = 0`. | Не удаляем — оставляем для истории. Удалить можно через реструктуризацию. |
| Swap в монету, которой нет в `SYMBOL_TO_ID`. | Сериализатор валидирует через `PriceService.is_symbol_supported`. |
| CoinGecko вернул нулевую цену. | `SwapQuoteView` отдаёт 400 «Не удалось получить курс»; `SwapExecuteView` — то же. |
| Существующий `ContributePortfolioView` ломает контракт. | Старый формат (`amount`) сохраняется без изменений; новый формат (`items`) — отдельная ветка. |
| Записи `PortfolioContribution` влияют на DCA-расчёты в `PortfolioAnalyzer`. | При режиме «по монетам» создаём `PortfolioContribution(amount = Σ value_usd)` — DCA-логика продолжает корректно работать. |
| Frontend старого формата (одно поле USD) после обновления модалки. | Режим `usd` оставлен по умолчанию для обратной совместимости. |

---

## 7. Опционально (вне scope этого плана)

- История операций (взносы / выводы / обмены) единым списком на дашборде.
- AI-консультант: при запросе «купить N BTC» — автоматически предложить
  `contributeByUnits`-операцию или swap из стейблкоина.
- Поддержка нескольких стейблкоинов в `swap` (DAI, USDC, USDS) — уже технически
  работает через `is_symbol_supported`, требуется только добавить их в
  `get_stablecoin_symbols()` и обеспечить актуальные цены.
- Лимиты: «нельзя обменять более X% от стоимости портфеля за одну операцию» (не нужно сейчас).
- Логирование комиссий обмена в аналитику дашборда («суммарно потеряно на комиссиях: $XX»).
