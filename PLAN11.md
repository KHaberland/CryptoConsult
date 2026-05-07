# PLAN11 — Прибыль/убыток портфеля по «введённым наличным» (USD/EUR)

> **Цель.** Добавить в систему **отдельный фиатный учёт** «сколько денег
> пользователь завёл на свои биржи/кошельки в долларах/евро», и считать
> прибыль/убыток всего портфеля по строгой формуле, заданной пользователем:
>
> ```
> profit_loss     = current_portfolio_value − cash_in_total
> profit_loss_%   = profit_loss / cash_in_total × 100%
> ```
>
> где:
> * `current_portfolio_value` — сумма `units × биржевой курс` по всем активам
>   во **выбранной базовой валюте портфеля** (USD или EUR);
> * `cash_in_total` — сумма всех «введённых наличных» в той же валюте,
>   рассчитанная **по новой отдельной модели `FiatCashFlow`**.
>
> ## Принципиальное решение архитектуры
>
> Существующий механизм считать `total_invested` через
> `Portfolio.initial_amount + Σ PortfolioContribution.amount` **не трогаем**.
> Он продолжает работать в onboarding/DCA/AI-промптах и в эндпоинтах
> `ContributePortfolioView`/`WithdrawPortfolioView`.
>
> Параллельно вводим **новый, независимый фиатный счётчик** —
> `FiatCashFlow`. На dashboard'е блок «Прибыль/убыток» считается **только
> по нему**. Привязки к конкретному кошельку (`Wallet`) у `FiatCashFlow`
> нет — это сумма по всему портфелю.
>
> ## Что входит в PLAN11
> 1. Модель `FiatCashFlow` (deposit/withdrawal, currency=USD/EUR, fx).
> 2. CRUD-API для cash-flow.
> 3. Базовая валюта на `Portfolio` + цены крипты в EUR через CoinGecko.
> 4. Новый расчёт P&L `PortfolioAnalyzer.get_fiat_pnl()`.
> 5. Расширение `PortfolioValueView` (новые поля + опц. `?currency=`).
> 6. UI: новый блок на dashboard и модалка «Завести фиат» / «Снять фиат».
>
> ## Что НЕ входит в PLAN11 (явный анти-скоуп)
> 1. **Не меняем** `Portfolio.initial_amount`, `PortfolioContribution`,
>    `PortfolioWithdrawal` — ни поля, ни логику. Onboarding,
>    `ContributeModal`, `WithdrawModal`, `WalletCard`, agent
>    `AIAdvisorService.get_system_prompt` — всё остаётся как сейчас.
> 2. Не вводим фиатный баланс на конкретный `Wallet` — `FiatCashFlow`
>    висит на портфеле.
> 3. Не храним историю крипто-цен и FX-курсов; пересчёт в EUR — текущим FX.
> 4. Налоговый/реализованный P&L (FIFO/LIFO), TWR/IRR — отдельные планы.
> 5. Валюты, отличные от USD/EUR.

---

## 1. Как сейчас считается прибыль/убыток (как-is)

### 1.1. Backend
* `backend/advisor/services.py → PortfolioAnalyzer.get_current_value()`:
  ```
  total_invested  = Portfolio.initial_amount + Σ contributions.amount   # USD, без вычета выводов
  current_value   = Σ units × units_scale × current_price_usd
  profit_loss     = current_value − total_invested
  profit_loss_%   = profit_loss / total_invested × 100
  ```
* `_get_total_invested()` (строки 46–51) НЕ вычитает `PortfolioWithdrawal`.
* `PortfolioValueView.get` (строки 188–203 `views.py`) отдаёт фронту
  `total_value`, `initial_value`, `profit_loss`, `profit_loss_percent`.

### 1.2. Хранение валют
* `Portfolio.initial_amount`, `PortfolioContribution.amount`,
  `PortfolioWithdrawal.amount` — Decimal в USD, без поля валюты.
* CoinGecko запрашивается с `vs_currencies=usd` (строки 213, 293
  `services.py`); EUR не запрашивается.

### 1.3. Frontend
* `dashboard/page.tsx` использует `portfolioValue.profit_loss /
  profit_loss_percent` и `formatCurrency` (всегда `$`).
* Понятия базовой валюты на фронте нет.

### 1.4. Что хочет пользователь
> «Я ввожу фиатную сумму в \$/€, она показывается на главной (dashboard).
> От неё считается прибыль/убыток всего портфеля. На уровне кошельков
> ничего не меняется — там по-прежнему только units криптомонет».

---

## 2. Архитектура новой фиат-подсистемы

### 2.1. Главное правило
* Все существующие модели/эндпоинты — **не трогаем**.
* Новая модель `FiatCashFlow(portfolio, kind, amount, currency,
  fx_rate_to_base, occurred_on, note)` хранит независимый поток фиата.
* `kind ∈ {DEPOSIT, WITHDRAWAL}`. Поле `wallet` отсутствует.
* На dashboard блок «Прибыль/убыток» использует **только** агрегаты по
  `FiatCashFlow`. Если у пользователя ещё нет ни одного `FiatCashFlow`
  — блок показывает CTA «Введите сумму, которую вы завели на свои
  кошельки, чтобы видеть прибыль/убыток».

### 2.2. Базовая валюта портфеля
* `Portfolio.base_currency` — `USD`/`EUR`, default `USD`.
* `FiatCashFlow.currency` — валюта конкретной операции (USD/EUR).
* `FiatCashFlow.fx_rate_to_base` — Decimal 12,6, курс
  `currency → portfolio.base_currency` на момент операции (для USD при
  EUR-портфеле и наоборот). При `currency == base_currency` = `1.0`.
* Курс берём через `_fx_rate(from_cur, to_cur)` (см. A4) — снимок
  «сейчас», без истории.

### 2.3. Формула (итог раздела)
```
# В выбранной валюте `cur` ∈ {USD, EUR}:

cash_in_total(cur)   = Σ flow.amount × FX(flow.currency → cur)         для kind=DEPOSIT
cash_out_total(cur)  = Σ flow.amount × FX(flow.currency → cur)         для kind=WITHDRAWAL
net_cash_in(cur)     = cash_in_total(cur) − cash_out_total(cur)

current_value(cur)   = Σ asset.units × units_scale × price(asset.symbol, cur)

profit_loss(cur)     = current_value(cur) − net_cash_in(cur)
profit_loss_%        = profit_loss(cur) / cash_in_total(cur) × 100
                       # знаменатель — БРУТТО депозитов (буквально «сумма
                       # введённых средств»). Если cash_in_total == 0,
                       # возвращаем profit_loss_% = 0 и флаг no_cash_in=True.
```

> Замечание: `current_value` берём из существующего расчёта (units по
> `PortfolioAsset` + цены CoinGecko). Никаких изменений в учёте крипты.

---

## 3. Карта агентов

Всего **9 агентов**, разбитых на **5 спринтов**.

| Спринт | Запуск | Задача                                                           | Файлы | Зависит от | Параллельно с | Оценка |
|--------|--------|------------------------------------------------------------------|-------|------------|----------------|--------|
| S1     | A1     | Модель `FiatCashFlow` + `Portfolio.base_currency`                | 1 | — | — | small |
| S1     | A2     | Миграции: schema + data-backfill (`base_currency='USD'`)         | 1 (новая) | A1 | — | xs |
| S2     | A3     | `PriceService.get_prices_in_currency(symbols, 'USD'|'EUR')`      | 1 | — | A1/A2 | small |
| S2     | A4     | `PortfolioAnalyzer.get_fiat_pnl(currency=None)` + `_fx_rate`     | 1 | A1, A3 | — | small |
| S3     | A5     | CRUD API: `FiatCashFlowListCreateView`, `FiatCashFlowDetailView` | 3 (urls/serializers/views) | A1 | A6 | small |
| S3     | A6     | Расширение `PortfolioValueView` (новые поля + `?currency=`) и эндпоинт `PATCH /api/portfolio/<id>/currency/` | 2 | A4, A5 | A5 | small |
| S4     | A7     | Frontend types + API-клиент для cash-flow и `getPortfolioValue`  | 1 | A5, A6 | A8 | xs |
| S4     | A8     | Dashboard: блок P&L по фиату + модалка `FiatCashFlowModal` (deposit/withdrawal) + переключатель USD/EUR | 3 (новый компонент + dashboard + store) | A7 | — | small |
| S5     | A9     | Тесты + DONE: backend + UI smoke + `PLAN11-realization.md`       | 1 (новый) | A4–A8 | — | small |

«xs» = до ~5k токенов входа, «small» = до ~15k.

---

## 4. Шаблон промпта агенту

```
Ты выполняешь ровно одну задачу из PLAN11.md (CryptoConsult).
Не исследуй проект целиком, не читай посторонние файлы.

ЗАДАЧА: <вставить из карточки агента ниже>
ФАЙЛЫ ДЛЯ ПРАВКИ: <точный список>
СПЕЦИФИКАЦИЯ: <вставить блок «что делаем» из карточки>
КРИТЕРИЙ ГОТОВНОСТИ: <вставить из карточки>

ВАЖНО: НЕ меняй существующие модели Portfolio.initial_amount,
PortfolioContribution, PortfolioWithdrawal, Wallet, WalletHolding и
связанную с ними логику. PLAN11 — это полностью новая параллельная
подсистема FiatCashFlow.

После правок: запусти ReadLints на изменённых файлах и
`python manage.py test portfolios.tests.<нужный модуль>`.
```

---

## 5. Карточки агентов

### A1 — Модель `FiatCashFlow` + `Portfolio.base_currency`

* **Файлы:** `backend/portfolios/models.py`.
* **Что делаем:**
  1. В `Portfolio` добавить поле:
     ```python
     CURRENCY_USD = 'USD'
     CURRENCY_EUR = 'EUR'
     CURRENCY_CHOICES = [
         (CURRENCY_USD, 'Доллар США (USD)'),
         (CURRENCY_EUR, 'Евро (EUR)'),
     ]
     base_currency = models.CharField(
         max_length=3, choices=CURRENCY_CHOICES, default=CURRENCY_USD,
         verbose_name='Базовая валюта для P&L по фиату',
     )
     ```
     `Portfolio.initial_amount` НЕ трогаем (его валюта по-прежнему USD,
     это часть «старого» учёта, для P&L по фиату не используется).
  2. Новая модель в конце файла:
     ```python
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
             Portfolio, on_delete=models.CASCADE,
             related_name='fiat_cash_flows',
             verbose_name='Портфель',
         )
         kind = models.CharField(
             max_length=12, choices=KIND_CHOICES,
             verbose_name='Тип операции',
         )
         amount = models.DecimalField(
             max_digits=14, decimal_places=2,
             verbose_name='Сумма',
         )
         currency = models.CharField(
             max_length=3, choices=Portfolio.CURRENCY_CHOICES,
             verbose_name='Валюта операции',
         )
         fx_rate_to_base = models.DecimalField(
             max_digits=12, decimal_places=6,
             default=Decimal('1.000000'),
             verbose_name='Курс currency → portfolio.base_currency',
         )
         occurred_on = models.DateField(verbose_name='Дата операции')
         note = models.CharField(
             max_length=200, blank=True, default='',
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
     ```
* **Чего НЕ делаем:** не правим `Portfolio.initial_amount`,
  `PortfolioContribution`, `PortfolioWithdrawal`, `Wallet*`,
  `PortfolioSwap`, `HoldingAdjustment`, `PortfolioAsset`.
* **Критерий готовности:** `python manage.py makemigrations portfolios`
  успешно сгенерировал миграцию (НЕ применять — это A2). ReadLints чист.

### A2 — Миграция и data-backfill

* **Файлы:** `backend/portfolios/migrations/0010_fiat_cashflow.py` (новый,
  имя по факту нумерации миграций).
* **Что делаем:**
  1. Schema-миграция от `makemigrations` (A1).
  2. Data-backfill через `RunPython`:
     * `Portfolio.objects.update(base_currency='USD')`.
     * `FiatCashFlow` начально пуст — backfill не нужен.
  3. `reverse_code = migrations.RunPython.noop`.
* **Критерий готовности:** `python manage.py migrate portfolios` —
  зелёный; в shell `Portfolio.objects.first().base_currency == 'USD'`.

### A3 — Цены крипты в нескольких валютах

* **Файлы:** `backend/portfolios/services.py` (только `PriceService`).
* **Что делаем:**
  1. Новый публичный метод
     ```python
     def get_prices_in_currency(
         self, symbols: list[str], currency: str = 'USD'
     ) -> dict[str, float]:
         """Возвращает {SYMBOL: price_in_currency}. currency: 'USD'|'EUR'."""
     ```
     внутри: один HTTP-запрос
     `vs_currencies = currency.lower()` к `simple/price`. Ключ кэша —
     `prices_<currency_lower>:<sorted_symbols>`. Ошибки/rate-limit —
     те же fallback'ы, что в `get_prices`.
  2. Существующий `get_prices(symbols)` оставить рабочим (USD-альтернатива):
     можно реализовать его как тонкую обёртку
     `return self.get_prices_in_currency(symbols, 'USD')` или оставить
     как есть, без поломки сигнатуры.
  3. Если `currency == 'EUR'` и CoinGecko вернул пусто — fallback:
     запросить USD-цены и применить FX-курс (см. `_fx_rate` в A4).
     При этом проставить флаг `_eur_via_fx_fallback = True` в кэше
     (опционально), чтобы A4 мог отдать `fx_stale=True`.
* **Чего НЕ делаем:** не правим `get_prices_with_changes`, не трогаем
  Wallet-сериализаторы.
* **Критерий готовности:** в `manage.py shell`
  `PriceService().get_prices_in_currency(['BTC','ETH'], 'EUR')` отдаёт
  словарь с положительными числами.

### A4 — Сервис расчёта P&L по новой формуле + `_fx_rate`

* **Файлы:** `backend/advisor/services.py` (только `PortfolioAnalyzer`).
* **Что делаем:**
  1. Внутрь `PortfolioAnalyzer` (или рядом, в том же модуле) добавить
     утилиту:
     ```python
     def _fx_rate(from_cur: str, to_cur: str) -> tuple[Decimal, bool]:
         """
         Возвращает (rate, stale). rate — Decimal, stale=True если
         внешний источник недоступен и rate взят как 1.0 (или из кэша).
         """
     ```
     Минимально:
     * USD↔USD / EUR↔EUR → `(Decimal('1'), False)`.
     * USD→EUR / EUR→USD: один HTTP-запрос к
       `https://api.exchangerate.host/latest?base=USD&symbols=EUR`
       (без ключа). Кэш в Django-cache на 1 час. Ошибка → `(1.0, True)`.
  2. Новый метод:
     ```python
     def get_fiat_pnl(self, currency: str | None = None) -> Dict:
         """
         P&L портфеля по фиатному учёту FiatCashFlow.

         currency: 'USD'|'EUR'|None. None → portfolio.base_currency.

         Возвращает:
           {
             'currency': 'USD'|'EUR',
             'cash_in_total': float,    # Σ deposit-операций
             'cash_out_total': float,   # Σ withdrawal-операций
             'net_cash_in': float,
             'current_value': float,    # стоимость портфеля в currency
             'profit_loss': float,
             'profit_loss_percent': float,
             'no_cash_in': bool,        # True, если cash_in_total == 0
             'fx_stale': bool,
           }

         Алгоритм:
           1. Берём portfolio.base_currency как `base`.
           2. Если currency != base — fx_b2c = _fx_rate(base, currency).
              Иначе fx_b2c = 1.0.
           3. cash_in_base  = Σ flow.amount_in_base для kind=DEPOSIT.
              cash_out_base = Σ flow.amount_in_base для kind=WITHDRAWAL.
              Переводим в `currency` умножением на fx_b2c.
           4. current_value: prices = PriceService().
              get_prices_in_currency(symbols, currency); далее
              current_value = Σ asset.units × units_scale × prices[symbol]
              (units_scale из существующего _get_dca_corrected_invested()).
           5. profit_loss = current_value − net_cash_in.
              profit_loss_percent = profit_loss / cash_in_total × 100,
              иначе 0.0 (no_cash_in=True).
         """
     ```
  3. Существующий `get_current_value()` НЕ трогаем — он продолжает
     возвращать legacy-метрики для AI-промптов.
* **Чего НЕ делаем:** не правим `get_drawdown`, `get_time_metrics`,
  AI-промпты, реструктуризацию.
* **Критерий готовности:** `manage.py shell` —
  `PortfolioAnalyzer(p).get_fiat_pnl('USD')` на портфеле без
  `FiatCashFlow` возвращает `cash_in_total=0`, `no_cash_in=True`,
  `profit_loss_percent=0`, `current_value` совпадает с
  `get_current_value()['current_value']` (USD).

### A5 — CRUD API для FiatCashFlow

* **Файлы:** `backend/portfolios/serializers.py`,
  `backend/portfolios/views.py`, `backend/portfolios/urls.py`.
* **Что делаем:**
  1. Сериализатор:
     ```python
     class FiatCashFlowSerializer(serializers.ModelSerializer):
         amount_in_base = serializers.FloatField(read_only=True)

         class Meta:
             model = FiatCashFlow
             fields = ['id', 'kind', 'amount', 'currency',
                       'fx_rate_to_base', 'amount_in_base',
                       'occurred_on', 'note', 'created_at']
             read_only_fields = ['id', 'fx_rate_to_base',
                                 'amount_in_base', 'created_at']
     ```
     Валидация: `kind ∈ {deposit, withdrawal}`,
     `currency ∈ {USD, EUR}`, `amount > 0`,
     `occurred_on <= today`. Если `occurred_on` не указана — `today`.
  2. Views:
     * `FiatCashFlowListCreateView(APIView)`:
       — `GET /api/portfolio/cash-flows/?kind=deposit|withdrawal&currency=USD|EUR`
         → список (с фильтрами по kind/currency, пагинация не нужна).
       — `POST /api/portfolio/cash-flows/` body
         `{kind, amount, currency, occurred_on?, note?}`. На сервере:
         `fx_rate_to_base = _fx_rate(currency, portfolio.base_currency)[0]`.
         Если FX недоступен — записать с `fx_rate_to_base=1.0` и
         вернуть HTTP 201 с предупреждением `fx_stale: true` в теле.
     * `FiatCashFlowDetailView(APIView)`:
       — `DELETE /api/portfolio/cash-flows/<id>/` — удаление операции
         (мягкое удаление не нужно: cash-flow всегда можно ввести
         заново). 404 если cash-flow не принадлежит активному
         портфелю по `session_id`.
       — `PATCH` поддерживать только редактирование `note` и
         `occurred_on`. Изменение `amount`/`currency`/`kind` —
         запретить (пусть пользователь удалит и создаст заново).
  3. URLs:
     ```python
     path('cash-flows/', FiatCashFlowListCreateView.as_view()),
     path('cash-flows/<int:pk>/', FiatCashFlowDetailView.as_view()),
     ```
* **Чего НЕ делаем:** не делаем `bulk-create`, не привязываем к Wallet,
  не пишем CSV-импорт.
* **Критерий готовности:** `POST /api/portfolio/cash-flows/` body
  `{"kind":"deposit","amount":1000,"currency":"USD"}` создаёт запись;
  `GET` отдаёт список; `DELETE` удаляет.

### A6 — Расширение `PortfolioValueView` и смена базовой валюты

* **Файлы:** `backend/portfolios/serializers.py`,
  `backend/portfolios/views.py`, `backend/portfolios/urls.py`.
* **Что делаем:**
  1. В `PortfolioValueView.get` (строки 126–205 текущего `views.py`):
     * Принять query `?currency=USD|EUR`. Если не указан — взять
       `portfolio.base_currency`. Любое другое значение → 400.
     * После старого расчёта добавить вызов
       `fiat = analyzer.get_fiat_pnl(currency)`.
     * В ответе добавить новые поля рядом со старыми (старые
       сохраняем как есть для обратной совместимости):
       ```python
       'fiat_pnl': {
           'currency': fiat['currency'],
           'cash_in_total': round(fiat['cash_in_total'], 2),
           'cash_out_total': round(fiat['cash_out_total'], 2),
           'net_cash_in': round(fiat['net_cash_in'], 2),
           'current_value': round(fiat['current_value'], 2),
           'profit_loss': round(fiat['profit_loss'], 2),
           'profit_loss_percent': round(fiat['profit_loss_percent'], 2),
           'no_cash_in': fiat['no_cash_in'],
           'fx_stale': fiat['fx_stale'],
       },
       'base_currency': portfolio.base_currency,
       ```
       Старые поля (`total_value`, `initial_value`, `profit_loss`,
       `profit_loss_percent`) **оставляем нетронутыми** — фронт
       мигрирует на `fiat_pnl` поэтапно.
  2. Новая вью `PortfolioBaseCurrencyView(APIView)`:
     ```
     PATCH /api/portfolio/<id>/currency/
     body: {"base_currency": "EUR"}
     ```
     * Валидация: `USD` или `EUR`.
     * При смене (`USD↔EUR`) — пересчитать `fx_rate_to_base` у всех
       `FiatCashFlow` через `_fx_rate(flow.currency, new_base)`.
       `transaction.atomic()`.
     * Ответ: `{ok: true, base_currency: 'EUR', fx_stale: bool}`.
  3. URLs: добавить маршрут `currency/`.
* **Чего НЕ делаем:** не правим `ContributePortfolioView`,
  `WithdrawPortfolioView`, AI-эндпоинты.
* **Критерий готовности:** `GET /api/portfolio/value/?currency=EUR`
  отдаёт `fiat_pnl` в EUR; `PATCH /api/portfolio/<id>/currency/` меняет
  базовую валюту и пересчитывает FX у cash-flow'ов.

### A7 — Frontend types + API-клиент

* **Файлы:** `frontend/src/services/api.ts`.
* **Что делаем:**
  1. Типы:
     ```ts
     export type FiatCurrency = 'USD' | 'EUR'
     export type FiatCashFlowKind = 'deposit' | 'withdrawal'

     export interface FiatCashFlow {
       id: number
       kind: FiatCashFlowKind
       amount: number | string
       currency: FiatCurrency
       fx_rate_to_base: number | string
       amount_in_base: number
       occurred_on: string
       note: string
       created_at: string
     }

     export interface FiatPnl {
       currency: FiatCurrency
       cash_in_total: number
       cash_out_total: number
       net_cash_in: number
       current_value: number
       profit_loss: number
       profit_loss_percent: number
       no_cash_in: boolean
       fx_stale: boolean
     }
     ```
     В существующем `PortfolioValue`-типе добавить
     `fiat_pnl?: FiatPnl; base_currency?: FiatCurrency`.
  2. Методы `portfolioApi`:
     ```ts
     listFiatCashFlows(params?: {kind?: FiatCashFlowKind; currency?: FiatCurrency}): Promise<{items: FiatCashFlow[]}>
     createFiatCashFlow(input: {kind: FiatCashFlowKind; amount: number; currency: FiatCurrency; occurred_on?: string; note?: string}): Promise<FiatCashFlow & {fx_stale?: boolean}>
     deleteFiatCashFlow(id: number): Promise<void>
     setBaseCurrency(portfolioId: number, currency: FiatCurrency): Promise<{ok: true; base_currency: FiatCurrency; fx_stale: boolean}>
     getPortfolioValue(currency?: FiatCurrency): Promise<PortfolioValue>
     ```
* **Критерий готовности:** `npx tsc --noEmit` чист.

### A8 — Dashboard: блок «Введено наличных» + модалка

* **Файлы:**
  - `frontend/src/components/portfolio/FiatCashFlowModal.tsx` (новый),
  - `frontend/src/app/dashboard/page.tsx`,
  - `frontend/src/store/portfolioStore.ts`.
* **Что делаем:**
  1. **Модалка `FiatCashFlowModal`:**
     * Props: `isOpen`, `onClose`, `mode: 'deposit'|'withdrawal'`,
       `defaultCurrency: FiatCurrency`, `onSubmit(input) => Promise`.
     * Поля: сумма (number), валюта (radio USD/EUR, default
       `defaultCurrency`), дата (date input, default = today),
       заметка (textarea, опц.).
     * Submit вызывает `portfolioApi.createFiatCashFlow(...)` и
       обновляет dashboard через store.
     * Состояния: success (зелёная плашка) / error (Alert).
     * Внешний стиль — как у `ContributeModal`/`WithdrawModal` (Modal +
       ModalFooter + Button + Alert).
  2. **`portfolioStore.ts`** добавить:
     ```ts
     baseCurrency: 'USD' | 'EUR'
     setBaseCurrency(c): Promise<void>
     fiatCashFlows: FiatCashFlow[]
     fetchFiatCashFlows(): Promise<void>
     fiatPnl: FiatPnl | null
     fetchPortfolioValue(currency?): Promise<void>  # заполняет fiatPnl
     ```
  3. **Dashboard `dashboard/page.tsx`:**
     * Над существующим блоком «Прибыль/убыток» (строка ~404 в
       текущем файле) добавить **новый главный блок** «Финансы по фиату»:
       ```
       [ USD | EUR ]   ← переключатель базовой валюты
       Введено наличных:   {formatCurrency(cash_in_total, currency)}
       Выведено:           {formatCurrency(cash_out_total, currency)}
                           (показывать только если > 0)
       Текущая стоимость:  {formatCurrency(fiat_pnl.current_value, currency)}
       Прибыль/убыток:     {formatCurrency(profit_loss, currency)}
                           ({formatPercent(profit_loss_percent)})
       [ + Внести фиат ]   [ − Снять фиат ]
       ```
       — Если `no_cash_in === true` (нет ни одного депозита):
         показывать CTA «Введите сумму, которую вы завели на свои
         кошельки/биржу, чтобы видеть прибыль/убыток» и кнопку
         «+ Внести фиат». P&L-цифры спрятать.
       — Если `fx_stale === true`: маленькая иконка-предупреждение
         «Курс USD↔EUR временно недоступен; считаем по 1.0».
     * **Старый блок** «Прибыль/убыток» (строки ~414–426 текущего
       dashboard'а) — **оставить как есть**; он показывает
       legacy-расчёт от `Portfolio.initial_amount`. Рекомендация:
       перенести его ниже на странице с подписью «Старый расчёт по
       плану DCA» или скрыть под кнопкой «Подробнее»; финальное
       решение — за исполнителем агента, главное чтобы новый блок
       был сверху и заметнее.
     * Под блоком «Введено наличных» добавить раскрывающийся список
       последних 5 cash-flow'ов (`fiatCashFlows`) с маленькой
       кнопкой удаления (для каждого — иконка корзины,
       подтверждение через `confirm()`).
     * `formatCurrency` и `formatPercent` — обновить
       `formatCurrency(value: number, currency: 'USD'|'EUR' = 'USD')`,
       чтобы подставлял `$`/`€` (через `Intl.NumberFormat`).
  4. **WalletCard / основной портфель** — НЕ ТРОГАЕМ. Карточки
     кошельков продолжают показывать units и USD-стоимость
     по PLAN10.
* **Критерий готовности:**
  * Кнопка «+ Внести фиат» на dashboard открывает модалку, после
    submit P&L-блок обновляется без перезагрузки.
  * При смене USD/EUR через переключатель цифры пересчитываются
    (`PATCH .../currency/` + `getPortfolioValue(eur)`).
  * Если cash-flow'ов нет — показан CTA, а не «$0.00».
  * Карточки кошельков и таблица активов выглядят как сейчас (только
    цены/стоимости в таблице активов могут быть в выбранной валюте,
    если фронт читает их из `assets`-секции, обновлённой в A6 —
    но это опционально, можно оставить таблицу в USD).

### A9 — Тесты + DONE

* **Файлы:** `backend/portfolios/tests/test_fiat_cash_flow.py` (новый),
  `PLAN11-realization.md` (новый, по образцу `PLAN10-realization.md`).
* **Бэкенд-тесты (один TestCase, моки `PriceService.get_prices_in_currency`
  и `_fx_rate`):**
  1. `test_create_fiat_deposit_persists_fx_rate` — POST
     `{kind:deposit, amount:1000, currency:USD}` в EUR-портфеле:
     запись создана с `fx_rate_to_base ≈ 0.92` (или другой моковый).
  2. `test_get_fiat_pnl_no_cash_in` — пустой `FiatCashFlow`:
     `cash_in_total=0`, `no_cash_in=True`, `profit_loss_percent=0`.
  3. `test_get_fiat_pnl_basic` — портфель USD, 1 BTC,
     `get_prices_in_currency` возвращает `{BTC: 30000}`, один
     `FiatCashFlow(kind=deposit, amount=20000, currency=USD)`.
     Ожидание: `cash_in_total=20000`, `current_value=30000`,
     `profit_loss=10000`, `profit_loss_percent=50.0`.
  4. `test_get_fiat_pnl_with_withdrawal` — депозит 1000 USD, вывод
     200 USD, current_value 1100. Ожидание: `cash_in_total=1000`,
     `cash_out_total=200`, `net_cash_in=800`,
     `profit_loss=1100-800=300`, `profit_loss_percent=300/1000*100=30`.
  5. `test_get_fiat_pnl_eur_uses_fx_and_eur_prices` —
     base_currency=EUR, mock `_fx_rate(USD,EUR)=0.9`,
     `get_prices_in_currency(...,'EUR')` возвращает EUR-цены.
     Один cash-flow в USD на 1000. Проверить, что
     `cash_in_total ≈ 900 EUR` и `current_value` берётся из
     EUR-цен.
  6. `test_change_base_currency_recalculates_fx` — PATCH
     `/api/portfolio/<id>/currency/` с `EUR` пересчитывает
     `fx_rate_to_base` у существующих cash-flow'ов.
  7. `test_delete_fiat_cash_flow` — DELETE; затем
     `get_fiat_pnl().cash_in_total` уменьшился ровно на удалённую
     сумму (в base).
  8. `test_legacy_metrics_unchanged` — старый
     `analyzer.get_current_value()['profit_loss']` НЕ зависит от
     наличия `FiatCashFlow` (создан портфель + 1 cash-flow,
     старая метрика как до создания cash-flow).
* **DONE (руками):**
  ```powershell
  cd D:\Work_Cursor\CryptoConsult\backend
  python manage.py migrate
  python manage.py test portfolios

  cd ..\frontend
  npm run lint
  npm run dev
  # Открыть http://localhost:3000/dashboard:
  #  1. На пустом cash-flow видим CTA «Введите сумму...».
  #  2. Жмём «+ Внести фиат» → 1000 USD → видим
  #     cash_in_total=1000, current_value=портфель в USD,
  #     P&L согласован.
  #  3. Переключаем EUR → суммы пересчитались.
  #  4. Жмём «− Снять фиат» → 200 USD → cash_out=200,
  #     net_cash_in=800, P&L изменился.
  #  5. Удаляем последний cash-flow → значения возвращаются.
  #  6. Карточки кошельков и таблица активов выглядят как до
  #     PLAN11 (units и долларовые суммы).
  ```
* **Критерий готовности:** `python manage.py test portfolios` зелёный,
  smoke UI пройден, `PLAN11-realization.md` создан.

---

## 6. Порядок запуска

```
S1: A1  ──►  A2
                │
S2:           ├──►  A3
                │     │
                │     └──►  A4
                │            │
S3:                          ├──►  A5
                │            │     │
                │            │     └──►  A6
                │            │            │
S4:                                       ├──►  A7
                │            │            │     │
                │            │            │     └──►  A8
                │            │            │
S5:                                       └──►  A9 (DONE)
```

Минимальный путь до «фикса» (только USD, без EUR):
**A1 → A2 → A4 (без EUR-веток) → A5 → A6 (без `?currency=`) → A7 → A8
(без переключателя валюты) → A9** — это полностью отвечает на
запрос «ввожу долларовую сумму, вижу P&L». EUR-флоу можно отгрузить
вторым слайсом (A3 + EUR-ветки в A4/A6 + переключатель в A8).

---

## 7. DONE-чек (для PR-описания)

* [ ] Модель `FiatCashFlow` добавлена; `Portfolio.base_currency` есть.
* [ ] Миграция применена; существующие портфели имеют
      `base_currency='USD'`.
* [ ] `PriceService.get_prices_in_currency([...], 'EUR')` отдаёт цены
      в EUR.
* [ ] `PortfolioAnalyzer.get_fiat_pnl('USD')` и `('EUR')` считают
      по формуле раздела 2.3, корректно обрабатывают `no_cash_in` и
      `fx_stale`.
* [ ] CRUD-эндпоинты `cash-flows/` и `cash-flows/<id>/` работают.
* [ ] `GET /api/portfolio/value/` отдаёт новый блок `fiat_pnl` рядом
      со старыми полями.
* [ ] `PATCH /api/portfolio/<id>/currency/` меняет базовую валюту и
      пересчитывает FX у cash-flow'ов.
* [ ] На dashboard виден новый блок «Финансы по фиату» с переключателем
      USD/EUR и кнопками «+ Внести фиат» / «− Снять фиат».
* [ ] При отсутствии cash-flow видна CTA, а не нули.
* [ ] **Карточки кошельков и таблица активов отображаются как до
      PLAN11** (units и USD-стоимость по PLAN10) — регрессий нет.
* [ ] **Старый расчёт `get_current_value()` на бэкенде не изменился**
      (тест `test_legacy_metrics_unchanged`).
* [ ] `python manage.py test portfolios` — зелёный.
* [ ] PR-описание содержит два скриншота dashboard'а: «нет фиата»
      (CTA) и «есть фиат» (P&L-блок).

---

## 8. Сводная формула (то, что должно быть)

```
# В выбранной валюте `cur` ∈ {USD, EUR}:

cash_in_total(cur)   = Σ flow.amount × FX(flow.currency → cur)         для kind=DEPOSIT
cash_out_total(cur)  = Σ flow.amount × FX(flow.currency → cur)         для kind=WITHDRAWAL
net_cash_in(cur)     = cash_in_total(cur) − cash_out_total(cur)

current_value(cur)   = Σ asset.units × units_scale × price(asset.symbol, cur)

profit_loss(cur)     = current_value(cur) − net_cash_in(cur)
profit_loss_pct      = profit_loss(cur) / cash_in_total(cur) × 100
                       # знаменатель — БРУТТО депозитов («сумма
                       # введённых средств»). При cash_in_total == 0
                       # возвращаем 0 и поднимаем флаг no_cash_in.
```

> **Важно.** `current_value` использует тот же расчёт, что в
> существующем `get_current_value()` (units по `PortfolioAsset` × цены
> CoinGecko). Никаких изменений в учёте крипты или кошельков нет.
> Все «введённые наличные» хранятся **только** в `FiatCashFlow`,
> отдельно от `Portfolio.initial_amount`/`PortfolioContribution`/
> `PortfolioWithdrawal`.
