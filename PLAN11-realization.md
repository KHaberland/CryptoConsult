# PLAN11-REALIZATION — Прибыль/убыток портфеля по «введённым наличным»

> Параллельный фиатный учёт `FiatCashFlow` для расчёта P&L портфеля
> по строгой формуле `profit_loss = current_value − net_cash_in`
> в выбранной базовой валюте (USD/EUR). Существующий
> `Portfolio.initial_amount + Σ PortfolioContribution` НЕ менялся —
> онбординг/DCA/AI-промпты/`ContributeModal` остались как в PLAN10.
>
> План: `PLAN11.md`. Эта страница описывает, **что фактически
> реализовано** девятью агентами A1–A9.

---

## 0. Контекст: что было до PLAN11

| Слой | Файл | Роль до PLAN11 |
|------|------|----------------|
| Модели | `backend/portfolios/models.py` | `Portfolio`, `PortfolioAsset`, `PortfolioContribution`, `PortfolioWithdrawal`, `Wallet*`, `PortfolioSwap`, `HoldingAdjustment` |
| Расчёт P&L | `backend/advisor/services.py::PortfolioAnalyzer.get_current_value()` | `total_invested = initial_amount + Σ contributions`, всё в USD |
| Цены | `backend/portfolios/services.py::PriceService.get_prices()` | Только USD, через CoinGecko `vs_currencies=usd` |
| API стоимости | `backend/portfolios/views.py::PortfolioValueView` | Отдавал `total_value`/`initial_value`/`profit_loss`/`profit_loss_percent` (USD) |
| Frontend | `frontend/src/app/dashboard/page.tsx` | Блок «Прибыль/убыток» считался по `portfolioValue.profit_loss`, всегда в `$` |

PLAN10 закрыл мультикошельковую модель (`Wallet`/`WalletHolding`/
`WalletTransfer`/`HoldingAdjustment`). PLAN11 **не пересекается** с
этой подсистемой — фиатный счётчик висит на портфеле в целом, а не
на конкретном кошельке.

---

## 1. Что фактически реализовано (карта изменений)

```
┌──────────────────────────────────────────────────────────────────┐
│  Backend (Django, backend/)                                      │
│                                                                  │
│  portfolios/models.py            ← A1: + Portfolio.base_currency │
│                                       + FiatCashFlow             │
│  portfolios/migrations/          ← A2: 0010_fiat_cashflow.py     │
│      0010_fiat_cashflow.py             (schema + data-backfill)  │
│  portfolios/services.py          ← A3: PriceService.             │
│                                       get_prices_in_currency()   │
│                                       + EUR через USD×FX         │
│  advisor/services.py             ← A4: _fx_rate()                │
│                                       + PortfolioAnalyzer.       │
│                                         get_fiat_pnl()           │
│  portfolios/serializers.py       ← A5: FiatCashFlowSerializer    │
│  portfolios/views.py             ← A5/A6: FiatCashFlowListCreate │
│                                          FiatCashFlowDetail      │
│                                          PortfolioBaseCurrency   │
│                                          + PortfolioValueView    │
│                                            теперь отдаёт         │
│                                            fiat_pnl + base_curr  │
│  portfolios/urls.py              ← A5/A6: + cash-flows/          │
│                                           + <id>/currency/       │
│                                                                  │
│  portfolios/tests/test_fiat_cash_flow.py  ← A9 (8 тестов)        │
└──────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js, frontend/)                                   │
│                                                                  │
│  src/services/api.ts             ← A7: типы FiatCashFlow/FiatPnl │
│                                       + portfolioApi:            │
│                                         listFiatCashFlows        │
│                                         createFiatCashFlow       │
│                                         deleteFiatCashFlow       │
│                                         setBaseCurrency          │
│                                         getPortfolioValue(?cur)  │
│  src/store/portfolioStore.ts     ← A8: baseCurrency, fiatPnl,    │
│                                       fiatCashFlows,             │
│                                       fetchFiatCashFlows(),      │
│                                       fetchPortfolioValue()      │
│  src/components/portfolio/                                       │
│    FiatCashFlowModal.tsx         ← A8: модалка deposit/withdraw  │
│  src/app/dashboard/page.tsx      ← A8: блок «Финансы по фиату»   │
│                                       + переключатель USD/EUR    │
└──────────────────────────────────────────────────────────────────┘
```

Старый блок «Прибыль/убыток» на dashboard, `ContributeModal`/
`WithdrawModal`, `WalletCard`, `AIAdvisorService.get_system_prompt`
— остались без изменений.

---

## 2. Карточки агентов A1–A9 (как реализовано)

### A1 — Модель `FiatCashFlow` + `Portfolio.base_currency`

* **Файлы:** `backend/portfolios/models.py`.
* **Сделано:**
  - В `Portfolio` добавлены константы `CURRENCY_USD`/`CURRENCY_EUR`
    и поле `base_currency = CharField(choices=CURRENCY_CHOICES,
    default='USD')`.
  - В конец файла добавлена новая модель `FiatCashFlow` со всеми
    полями из спецификации: `portfolio`/`kind`/`amount`/`currency`/
    `fx_rate_to_base` (DecimalField 12,6, default=`1.000000`)/
    `occurred_on`/`note`/`created_at`. Ordering
    `['-occurred_on', '-created_at']`, индекс по
    `(portfolio, kind, occurred_on)`.
  - Свойство `amount_in_base = amount × fx_rate_to_base` —
    единственная точка истины для перевода суммы в базовую валюту
    портфеля (используется и в A4, и в фронте).
* **Не трогали:** `Portfolio.initial_amount` (как и прежде, USD),
  `PortfolioContribution`, `PortfolioWithdrawal`, `Wallet*`,
  `PortfolioSwap`, `HoldingAdjustment`.
* **Антискоуп:** поле `wallet` у `FiatCashFlow` отсутствует —
  привязка только к портфелю.

### A2 — Миграция + data-backfill

* **Файлы:** `backend/portfolios/migrations/0010_fiat_cashflow.py`.
* **Сделано:**
  - `AddField` для `Portfolio.base_currency` (default='USD').
  - `CreateModel` для `FiatCashFlow` (с индексом и FK).
  - `RunPython(backfill_base_currency, reverse_code=noop)` явно
    проставляет `base_currency='USD'` всем существующим портфелям
    (страховка поверх default'а).
  - Откат — no-op: миграция сводится к удалению таблицы/поля.
* **Зависимость:** `('portfolios', '0009_portfolioswap_wallet')`.

### A3 — Цены крипты в нескольких валютах

* **Файлы:** `backend/portfolios/services.py` (только `PriceService`).
* **Сделано:**
  - Новый метод `PriceService.get_prices_in_currency(symbols,
    currency='USD', use_cache=True)` с отдельным кэш-ключом
    `prices_<currency_lower>:<sorted_symbols>` и поддержкой
    `vs_currencies=eur` в CoinGecko.
  - Для USD стейблкоины (`USDT`/`USDC`) фиксируются как 1.0,
    если CoinGecko не вернул значение (как в старом `get_prices`).
  - Fallback для EUR через USD×FX: `_eur_prices_via_usd_fx`
    дёргает `advisor.services._fx_rate('USD', 'EUR')` и считает
    EUR-цены через USD-цены. При срабатывании fallback'а в кэш
    кладётся флаг `prices_eur:<...>:eur_via_fx_fallback=True`,
    который позже читает A4 для выставления `fx_stale=True`.
  - Существующий `get_prices(symbols)` (USD) не тронут — все
    legacy-вызовы продолжают работать.
* **Чего не делали:** не правили `get_prices_with_changes`,
  `get_market_data`, ничего из Wallet-сериализаторов.

### A4 — Сервис расчёта P&L по новой формуле + `_fx_rate`

* **Файлы:** `backend/advisor/services.py`.
* **Сделано:**
  - Утилита модульного уровня `_fx_rate(from_cur, to_cur) ->
    Tuple[Decimal, bool]`:
    - `USD↔USD`/`EUR↔EUR` → `(Decimal('1'), False)`.
    - `USD↔EUR` — один HTTP-запрос к
      `https://api.exchangerate.host/latest?base=USD&symbols=EUR`,
      Decimal-курс кэшируется в `django.core.cache` под ключом
      `fx_rate_usd_eur` на 1 час (`_FX_CACHE_TTL_SECONDS`).
    - Любая ошибка/неподдерживаемая валюта → `(Decimal('1'),
      True)` + warning-лог.
  - Новый метод `PortfolioAnalyzer.get_fiat_pnl(currency=None)`,
    реализующий формулу §2.3 PLAN11:
    1. `base = portfolio.base_currency`, `cur = currency or base`.
    2. Если `cur != base` — `fx_b2c = _fx_rate(base, cur)`,
       иначе `fx_b2c = 1`.
    3. `cash_in_base/cash_out_base = Σ flow.amount_in_base` по
       соответствующему `kind`. Переводим в `cur` умножением на
       `fx_b2c`.
    4. `current_value = Σ asset.units × units_scale ×
       PriceService.get_prices_in_currency(symbols, cur)[symbol]`
       (`units_scale` берём из существующего
       `_get_dca_corrected_invested()` — это сохраняет ту же
       DCA-коррекцию, что и legacy-расчёт).
    5. `profit_loss = current_value − net_cash_in`,
       `profit_loss_percent = profit_loss / cash_in_total × 100`
       (знаменатель — БРУТТО депозитов).
       При `cash_in_total == 0` → `0.0` и флаг `no_cash_in=True`.
    6. `fx_stale=True` если `_fx_rate` вернул stale **или** для
       EUR-портфеля сработал fallback `eur_via_fx_fallback` из A3.
  - `get_current_value()` НЕ тронут — он по-прежнему возвращает
    legacy-метрики, которые используются в AI-промптах
    (`AIAdvisorService.get_system_prompt`).
* **Чего не делали:** не правили `get_drawdown`, `get_time_metrics`,
  `AIAdvisorService.*`, реструктуризацию.

### A5 — CRUD API для `FiatCashFlow`

* **Файлы:** `backend/portfolios/serializers.py`,
  `backend/portfolios/views.py`, `backend/portfolios/urls.py`.
* **Сделано:**
  - `FiatCashFlowSerializer` (ModelSerializer) с полями `id`,
    `kind`, `amount`, `currency`, `fx_rate_to_base`,
    `amount_in_base`, `occurred_on`, `note`, `created_at`.
    `read_only_fields = ('id', 'fx_rate_to_base', 'amount_in_base',
    'created_at')`. Валидаторы:
    - `amount > 0`;
    - `kind ∈ {deposit, withdrawal}`;
    - `currency ∈ {USD, EUR}`;
    - `occurred_on <= today`; если не указана — подставляется
      `today`.
  - `FiatCashFlowListCreateView` (`APIView`, `AllowAny`):
    - `GET /api/portfolio/cash-flows/?kind=&currency=` — список
      cash-flow'ов активного портфеля; фильтры по `kind`/
      `currency` с валидацией значений (400 при невалидных).
    - `POST /api/portfolio/cash-flows/` — создаёт запись;
      `fx_rate_to_base = _fx_rate(currency, portfolio.base_currency)`
      (квантуется до 6 знаков ROUND_HALF_UP через `_quantize_fx`).
      Если FX недоступен — поле остаётся `1.0`, в ответе
      добавляется `fx_stale: true`.
  - `FiatCashFlowDetailView` (`APIView`, `AllowAny`):
    - `PATCH /api/portfolio/cash-flows/<id>/` — редактируются
      только `note` и `occurred_on`. Любое другое поле в теле →
      400 «удалите и создайте заново».
    - `DELETE /api/portfolio/cash-flows/<id>/` — жёсткое удаление;
      запись должна принадлежать активному портфелю сессии,
      иначе 404.
  - URL-маршруты `cash-flows/` и `cash-flows/<int:pk>/`
    зарегистрированы в `portfolios/urls.py`.
* **Чего не делали:** не делали `bulk-create`, не привязывали к
  Wallet, не писали CSV-импорт.

### A6 — Расширение `PortfolioValueView` + смена базовой валюты

* **Файлы:** `backend/portfolios/views.py`,
  `backend/portfolios/urls.py`.
* **Сделано:**
  - `PortfolioValueView.get`:
    - Принимает query `?currency=USD|EUR`. Пустая/отсутствующая
      строка — берётся `portfolio.base_currency`. Любое другое
      значение → 400.
    - После старого расчёта вызывает
      `analyzer.get_fiat_pnl(currency)` и кладёт результат в ответ
      под ключом `fiat_pnl` (с округлением до 2 знаков). Рядом
      добавлен `base_currency`. Старые поля (`total_value`,
      `initial_value`, `profit_loss`, `profit_loss_percent`)
      сохранены как есть — для обратной совместимости и плавной
      миграции фронта.
  - Новая вью `PortfolioBaseCurrencyView`:
    - `PATCH /api/portfolio/<int:pk>/currency/` body
      `{"base_currency": "USD"|"EUR"}`. Любое другое значение → 400.
    - При фактической смене валюты (`USD↔EUR`):
      `transaction.atomic()` + `select_for_update()` на портфеле и
      его cash-flow'ах. Для каждого `FiatCashFlow` пересчитывается
      `fx_rate_to_base = _fx_rate(flow.currency, new_base)`,
      квантуется до 6 знаков. Если хотя бы один курс из fallback'а
      — в ответе `fx_stale: true`.
    - Ответ: `{ok: true, base_currency, fx_stale}`.
* **Чего не делали:** не правили `ContributePortfolioView`,
  `WithdrawPortfolioView`, AI-эндпоинты.

### A7 — Frontend types + API-клиент

* **Файлы:** `frontend/src/services/api.ts`.
* **Сделано:**
  - Типы: `FiatCurrency = 'USD' | 'EUR'`,
    `FiatCashFlowKind = 'deposit' | 'withdrawal'`,
    `FiatCashFlow`, `FiatPnl`. В существующий тип `PortfolioValue`
    добавлены опциональные поля `fiat_pnl?: FiatPnl` и
    `base_currency?: FiatCurrency`.
  - Методы `portfolioApi`:
    - `listFiatCashFlows(params?: {kind?, currency?}) →
      Promise<{items: FiatCashFlow[]}>`;
    - `createFiatCashFlow(input) → Promise<FiatCashFlow &
      {fx_stale?: boolean}>`;
    - `deleteFiatCashFlow(id) → Promise<void>`;
    - `setBaseCurrency(portfolioId, currency) → Promise<{ok,
      base_currency, fx_stale}>`;
    - `getPortfolioValue(currency?) → Promise<PortfolioValue>` —
      типизированная обёртка над `GET /api/portfolio/value/?currency=`.

### A8 — Dashboard: блок «Финансы по фиату» + модалка

* **Файлы:**
  - `frontend/src/components/portfolio/FiatCashFlowModal.tsx`
    (новый);
  - `frontend/src/store/portfolioStore.ts`;
  - `frontend/src/app/dashboard/page.tsx`.
* **Сделано:**
  - **`FiatCashFlowModal`** — единая модалка для `mode:
    'deposit'|'withdrawal'`: поля сумма / радио USD-EUR /
    дата / заметка. Стиль — как у `ContributeModal`/
    `WithdrawModal`. После успешного POST блок P&L обновляется
    через store, без перезагрузки.
  - **`portfolioStore`** — `baseCurrency`, `fiatPnl`,
    `fiatCashFlows`, `fetchFiatCashFlows()`,
    `fetchPortfolioValue(currency?)`, `setBaseCurrency(c)` (PATCH
    `/api/portfolio/<id>/currency/` → `getPortfolioValue(c)`).
  - **`dashboard/page.tsx`** — над старым блоком «Прибыль/убыток»
    появился новый главный блок «Финансы по фиату» с
    переключателем USD/EUR, цифрами `cash_in_total`/
    `cash_out_total`/`current_value`/`profit_loss`/
    `profit_loss_percent` и кнопками «+ Внести фиат» / «− Снять
    фиат». При `no_cash_in=true` цифры скрыты и показан CTA. При
    `fx_stale=true` — иконка-предупреждение «Курс USD↔EUR временно
    недоступен; считаем по 1.0».
  - **WalletCard и таблица активов НЕ тронуты** — карточки
    кошельков по-прежнему показывают units и USD-стоимость по
    PLAN10.

### A9 — Тесты + DONE (этот документ)

* **Файлы:**
  - `backend/portfolios/tests/test_fiat_cash_flow.py` (новый,
    один `TestCase` с восемью методами);
  - `PLAN11-realization.md` (этот документ).

**Тесты** (`FiatCashFlowTests`):

| # | Метод | Что проверяет |
|---|-------|--------------|
| 1 | `test_create_fiat_deposit_persists_fx_rate` | POST `cash-flows/` в EUR-портфеле с USD-депозитом: `fx_rate_to_base = _fx_rate('USD','EUR') = 0.92` (мок), запись сохранена с `Decimal('0.920000')`, в теле `fx_stale=false`. |
| 2 | `test_get_fiat_pnl_no_cash_in` | Пустой `FiatCashFlow` → `cash_in_total=0`, `no_cash_in=True`, `profit_loss_percent=0`, `fx_stale=False`. |
| 3 | `test_get_fiat_pnl_basic` | USD, 1 BTC @ $30 000, депозит $20 000 → `cash_in_total=20000`, `current_value=30000`, `profit_loss=10000`, `profit_loss_percent=50.0`. |
| 4 | `test_get_fiat_pnl_with_withdrawal` | Депозит $1 000, вывод $200, `current_value=$1 100` → `net_cash_in=800`, `profit_loss=300`, `profit_loss_percent=300/1000=30%` (знаменатель — БРУТТО депозитов, как в §2.3). |
| 5 | `test_get_fiat_pnl_eur_uses_fx_and_eur_prices` | `base_currency=EUR`, мок `_fx_rate(USD,EUR)=0.9`, мок `get_prices_in_currency(...,'EUR')={'BTC':27000}`. Один USD cash-flow на 1 000 с `fx_rate_to_base=0.9` → `cash_in_total≈900 EUR`, `current_value=27 000 EUR`. |
| 6 | `test_change_base_currency_recalculates_fx` | `PATCH /api/portfolio/<id>/currency/` (USD → EUR) пересчитывает `fx_rate_to_base` у всех существующих cash-flow'ов через `_fx_rate(flow.currency, new_base)`. |
| 7 | `test_delete_fiat_cash_flow` | `DELETE /api/portfolio/cash-flows/<id>/` → `cash_in_total` уменьшился ровно на удалённую сумму (в base). |
| 8 | `test_legacy_metrics_unchanged` | `analyzer.get_current_value().profit_loss` НЕ зависит от наличия `FiatCashFlow`: создание депозита не сдвигает legacy-метрики (антискоуп §0 PLAN11). |

Все внешние интеграции мокаются:
* `portfolios.services.PriceService.get_prices_in_currency` —
  крипто-цены в нужной валюте;
* `portfolios.services.PriceService.get_prices_with_changes` — для
  legacy-теста #8;
* `advisor.services._fx_rate` — курс USD↔EUR в `get_fiat_pnl`;
* `portfolios.views._fx_rate` — курс USD↔EUR в `POST cash-flows/`
  и `PATCH <id>/currency/`.

В `setUp` чистится глобальный in-memory `price_cache`, чтобы
EUR-через-USD×FX-флаги из предыдущих тестов не поднимали
`fx_stale=True` в текущем.

---

## 3. Контрольный прогон

```powershell
cd D:\Work_Cursor\CryptoConsult\backend
python manage.py migrate
python manage.py test portfolios.tests.test_fiat_cash_flow -v 2
# Ran 8 tests — OK

python manage.py test portfolios
# Ran 106 tests — OK (никаких регрессий в существующих тестах)
```

UI-smoke (`PLAN11.md` §A9):

```powershell
cd D:\Work_Cursor\CryptoConsult\frontend
npm run lint
npm run dev
# Открыть http://localhost:3000/dashboard:
#  1. На пустом cash-flow видим CTA «Введите сумму...».
#  2. Жмём «+ Внести фиат» → 1000 USD → видим cash_in_total=1000,
#     current_value=портфель в USD, P&L согласован.
#  3. Переключаем EUR → суммы пересчитались (PATCH .../currency/
#     + GET /api/portfolio/value/?currency=EUR).
#  4. Жмём «− Снять фиат» → 200 USD → cash_out=200,
#     net_cash_in=800, P&L изменился.
#  5. Удаляем последний cash-flow → значения возвращаются.
#  6. Карточки кошельков и таблица активов выглядят как до
#     PLAN11 (units и USD-стоимость по PLAN10).
```

---

## 4. DONE-чек (по `PLAN11.md` §7)

* [x] Модель `FiatCashFlow` добавлена; `Portfolio.base_currency`
      есть (A1).
* [x] Миграция `0010_fiat_cashflow.py` применена; существующие
      портфели имеют `base_currency='USD'` (A2).
* [x] `PriceService.get_prices_in_currency([...], 'EUR')` отдаёт
      цены в EUR (с fallback USD×FX) (A3).
* [x] `PortfolioAnalyzer.get_fiat_pnl('USD')` и `('EUR')` считают
      по формуле §2.3 PLAN11, корректно обрабатывают `no_cash_in`
      и `fx_stale` (A4 + тесты #2, #3, #4, #5).
* [x] CRUD-эндпоинты `cash-flows/` и `cash-flows/<id>/` работают
      (A5 + тесты #1, #7).
* [x] `GET /api/portfolio/value/` отдаёт новый блок `fiat_pnl`
      рядом со старыми полями (A6).
* [x] `PATCH /api/portfolio/<id>/currency/` меняет базовую валюту
      и пересчитывает FX у cash-flow'ов (A6 + тест #6).
* [x] На dashboard виден новый блок «Финансы по фиату» с
      переключателем USD/EUR и кнопками «+ Внести фиат» /
      «− Снять фиат» (A8).
* [x] При отсутствии cash-flow видна CTA, а не нули (A8).
* [x] **Карточки кошельков и таблица активов отображаются как до
      PLAN11** (units и USD-стоимость по PLAN10) — регрессий нет
      (A8 не трогал `WalletCard` и таблицу активов).
* [x] **Старый расчёт `get_current_value()` на бэкенде не
      изменился** (тест #8 `test_legacy_metrics_unchanged`).
* [x] `python manage.py test portfolios` — зелёный (106/106).

---

## 5. Антискоуп (что НЕ менялось)

* `Portfolio.initial_amount` (USD, как и прежде), миграции
  моделей `PortfolioContribution`, `PortfolioWithdrawal`,
  `Wallet`, `WalletHolding`, `WalletTransfer`,
  `HoldingAdjustment`, `PortfolioSwap`, `PortfolioAsset`.
* `ContributePortfolioView`, `WithdrawPortfolioView`,
  `RebalancePortfolioView`, `SwapExecuteView`,
  `WalletTransferView`, `HoldingAdjustView` — все остались на
  legacy-расчёте.
* `AIAdvisorService.get_system_prompt` и AI-эндпоинты
  (`/api/advisor/*`) — продолжают читать `get_current_value()`,
  а не `get_fiat_pnl()`. AI-промпты не упоминают `FiatCashFlow`.
* Frontend: `ContributeModal`, `WithdrawModal`, `WalletCard`,
  таблица активов в dashboard'е — без изменений.
* Не введён фиатный баланс на конкретный `Wallet` (по плану).
* Не сохраняем историю крипто-цен и FX-курсов: и `_fx_rate`, и
  `get_prices_in_currency` — это снимки «сейчас» с TTL-кэшем.
* Не реализован реализованный P&L по FIFO/LIFO, TWR/IRR — это
  отдельные планы.
* Валюты, кроме USD/EUR, не поддерживаются.

---

## 6. Известные хвосты / дальнейшие шаги

* `_fx_rate` использует `exchangerate.host` без API-ключа. На
  production стоит вынести URL в `settings` и при необходимости
  подключить резервного провайдера.
* В `get_fiat_pnl` `units_scale` берётся из
  `_get_dca_corrected_invested()`, чтобы P&L по фиату совпадал с
  отображаемой стоимостью legacy-блока для DCA-портфелей. Если в
  будущем DCA-коррекцию «затвердят» (см. `finalize_dca_scale`) —
  поведение сохранится (`scale == 1.0`).
* Frontend: блок «Финансы по фиату» сейчас показывается всегда
  при наличии активного портфеля. Если появится потребность —
  можно скрывать его до первой инициализации сессии.
