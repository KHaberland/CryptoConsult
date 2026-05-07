# PLAN10 — Подсчёт стоимости активов по каждому кошельку

> **Проблема.** В UI карточка кошелька (`WalletCard`) показывает по каждому
> активу `$0.00` и «Всего: $0.00». Причина строго одна: backend-сериализаторы
> `WalletHoldingSerializer` и `WalletSerializer` **не возвращают** поля
> `value_usd` и `total_value_usd`, которые читает фронт. Поля в TS-типах
> объявлены как `?optional`, поэтому ошибки нет — просто всегда `undefined → 0`.
>
> **Цель PLAN10.** Посчитать и отдавать с backend стоимость в USD:
> 1. для каждой записи `WalletHolding` (`value_usd`),
> 2. для всего `Wallet` (`total_value_usd` = сумма `value_usd` по holdings).
>
> Цены берём **одним вызовом** `PriceService.get_prices(symbols)` в view и
> прокидываем в сериализатор через `context`, чтобы не было N+1 к CoinGecko.
>
> **Принципы оптимизации токенов** (повторяем из PLAN09):
> 1. Один агент = одна узкая задача, в контексте — только нужные файлы.
> 2. Тривиальные правки одного файла объединяем в Bundle.
> 3. Независимые задачи запускаем параллельно в разных Cursor-окнах.
> 4. Никаких «исследовательских» промптов: каждому агенту даём список файлов
>    и точные строки/сигнатуры для правок.
> 5. В конце спринта — короткая DONE-проверка (тесты + git diff).

---

## 0. Подготовка (один раз, руками, ~3 минуты)

```powershell
cd D:\Work_Cursor\CryptoConsult
git status
git checkout -b feature/plan10-wallet-values

cd backend
python manage.py test portfolios
cd ..
```

Если backend-тесты уже красные — починить _до_ запуска агентов.

---

## 1. Карта агентов

Всего **6 агентов**, разбитых на **4 спринта**. S1+S2 — backend, S3 — фронт
(минимально, опциональный фоллбэк), S4 — DONE-проверка.

| Спринт | Запуск | Задача                                                         | Файлы | Зависит от | Параллельно с | Оценка |
|--------|--------|----------------------------------------------------------------|-------|------------|----------------|--------|
| S1     | A1     | Сериализатор: добавить `value_usd` и `total_value_usd`         | 1     | —          | A2 (нет — A2 после A1) | small |
| S1     | A2     | Views: подгрузить цены и прокинуть в context                   | 1     | A1         | —              | small |
| S2     | A3     | Bundle тестов: holding `value_usd`, wallet `total_value_usd`, fallback при отсутствии цены | 1 (новый) | A1+A2 | A4 | small |
| S2     | A4     | Обновить TS-тип `WalletHolding.value_usd` (убрать `?` если нужно) и доку в `services/api.ts` | 1 | A1 | A3 | xs |
| S3     | A5     | (опц.) Фоллбэк в `WalletCard`: `units * price` если `value_usd === null` | 1 | A4 | — | xs |
| S4     | A6     | DONE: прогон `python manage.py test`, ручная проверка UI, git diff | — | всё | — | xs |

«xs» = до ~5k токенов входа, «small» = до ~15k.

---

## 2. Шаблон промпта агенту (использовать дословно)

Каждого агента запускать в **новом окне Cursor Agent**:

```
Ты выполняешь ровно одну задачу из PLAN10.md (CryptoConsult).
Не исследуй проект целиком, не читай посторонние файлы.

ЗАДАЧА: <вставить из карточки агента ниже>
ФАЙЛЫ ДЛЯ ПРАВКИ: <точный список>
СПЕЦИФИКАЦИЯ: <вставить блок «что делаем» из карточки>
КРИТЕРИЙ ГОТОВНОСТИ: <вставить из карточки>

После правок: запусти ReadLints на изменённых файлах и (если задача
backend-овая) `python manage.py test portfolios.tests.<нужный модуль>`.
Не делай лишних рефакторингов соседнего кода.
```

---

## 3. Карточки агентов

### A1 — Сериализаторы кошелька: `value_usd` + `total_value_usd`

- **Файлы:** `backend/portfolios/serializers.py` (только `WalletHoldingSerializer`
  и `WalletSerializer`).
- **Что делаем:**
  1. В `WalletHoldingSerializer` добавить `value_usd = serializers.SerializerMethodField()`:
     - `get_value_usd(obj)` берёт `prices = self.context.get('prices') or {}`,
       `price = prices.get(obj.symbol)`. Если `price is None` → возвращаем
       `None` (фронт умеет с `null`).
     - Иначе: `Decimal(price) * obj.units`, округление до 2 знаков, отдать как
       `float` (как делают остальные сериализаторы стоимости в проекте).
     - Добавить `'value_usd'` в `Meta.fields` и в `read_only_fields`.
  2. В `WalletSerializer`:
     - Добавить `total_value_usd = serializers.SerializerMethodField()`.
     - `get_total_value_usd(obj)` суммирует `get_value_usd` по `obj.holdings.all()`
       с тем же `prices` из context. Если ни одной цены нет — вернуть `None`,
       чтобы UI понимал, что данные недоступны (или `0.0` — выбрать первое; в
       MVP проще `0.0`, чтобы «Всего» не пропадало).
     - Добавить `'total_value_usd'` в `Meta.fields` и в `read_only_fields`.
  3. Чтобы избежать дублирования логики и двойного цикла — вычислять
     `value_usd` для каждого holding один раз; `get_total_value_usd` может
     просто пройти по `obj.holdings.all()` и применить ту же формулу
     (модели в БД нет — это чисто read-only). Допустимый размер цикла.
- **Чего НЕ делаем:** не лезем в views, не правим WalletCreate/Update сериализаторы.
- **Критерий готовности:** ReadLints чист, `python manage.py shell` импорт
  сериализатора не падает.

### A2 — Views: подгрузка цен в context

- **Файлы:** `backend/portfolios/views.py` (только `WalletListCreateView`,
  `WalletDetailView`, и любые места, где после mutate возвращается
  `WalletSerializer(...).data` — POST создания, PATCH, transfer, adjust, swap).
- **Что делаем:**
  1. В `WalletListCreateView.get` после `wallets = ...prefetch_related('holdings')`:
     ```python
     symbols = sorted({h.symbol for w in wallets for h in w.holdings.all()})
     prices = PriceService().get_prices(symbols) if symbols else {}
     return Response(WalletSerializer(wallets, many=True, context={'prices': prices}).data)
     ```
  2. В `WalletDetailView.get/patch` — то же самое, но для одного кошелька:
     ```python
     symbols = sorted({h.symbol for h in wallet.holdings.all()})
     prices = PriceService().get_prices(symbols) if symbols else {}
     return Response(WalletSerializer(wallet, context={'prices': prices}).data)
     ```
  3. В `WalletListCreateView.post` (после `Wallet.objects.create(...)`) —
     контекст можно отдавать пустым (новый кошелёк → holdings=[] → 0).
  4. В `WalletTransferView` и `HoldingAdjustmentView` (и любой view, что
     возвращает `WalletSerializer(...).data` после изменения) — добавить
     тот же блок с подгрузкой цен, чтобы фронт мгновенно увидел свежие суммы.
  5. Импорт `PriceService` уже есть в `views.py` (используется в других
     местах) — переиспользуем.
- **Чего НЕ делаем:** не меняем сериализаторы, не вводим кэш руками
  (`PriceService` уже кэширует), не трогаем permissions/маршруты.
- **Критерий готовности:** `python manage.py runserver` поднимается, GET
  `/api/portfolio/wallets/` возвращает поля `value_usd` и `total_value_usd`.

### A3 — Тесты для backend (Bundle: 3 кейса в одном файле)

- **Файлы:** новый `backend/portfolios/tests/test_wallet_value_usd.py`.
- **Что делаем:** один `TestCase` с тремя тестами, мокая `PriceService.get_prices`:
  1. `test_holding_value_usd_present` — кошелёк с 0.5 BTC + 1 ETH, mock
     возвращает `{'BTC': 100000, 'ETH': 3500}`. Проверить, что
     `holdings[0].value_usd == 50000.00` и `holdings[1].value_usd == 3500.00`.
  2. `test_total_value_usd_sum` — на том же кошельке `total_value_usd ==
     53500.00`.
  3. `test_value_usd_null_when_no_price` — для символа, отсутствующего в
     `SYMBOL_TO_ID` (например `XYZ`), `value_usd is None`, а
     `total_value_usd` либо `0.0`, либо суммирует только известные — выбрать
     поведение из A1 и зафиксировать его в тесте.
- **Можно подсмотреть:** структуру setUp() — в `backend/portfolios/tests/test_wallet.py`
  и `test_transfer.py` (там уже есть рабочая фабрика портфеля + кошелька).
- **Критерий готовности:** `python manage.py test portfolios.tests.test_wallet_value_usd`
  — зелёный.

### A4 — Фронт-типы: чистка `WalletHolding`/`Wallet` в `services/api.ts`

- **Файлы:** `frontend/src/services/api.ts`.
- **Что делаем:**
  1. В `WalletHolding` поле `value_usd` оставить `?: number | string | null`
     (бэкенд может вернуть `null` при отсутствии цены — это нормально),
     но добавить JSDoc-комментарий: `/** USD-стоимость holding'а на момент
     запроса; null, если цена недоступна. */`.
  2. В `Wallet` — `total_value_usd?: number | string | null`, JSDoc:
     `/** Сумма value_usd по holdings; 0, если ни одной цены не получено. */`.
  3. Если в `dashboard/page.tsx` уже есть приведение к `parseFloat(String(...))`
     — ничего не трогаем.
- **Чего НЕ делаем:** не правим компоненты, не трогаем store.
- **Критерий готовности:** `npx tsc --noEmit` (или `npm run lint`) проходит.

### A5 — (опц.) Фоллбэк в `WalletCard` на `units * price`

> Запускать **только если** A6 покажет, что при пустом ответе CoinGecko суммы
> в UI пропадают и это раздражает. Иначе пропустить.

- **Файлы:** `frontend/src/components/portfolio/WalletCard.tsx`.
- **Что делаем:** если `h.value_usd` приходит `null/undefined`, но в
  `usePortfolioStore`/dashboard уже есть `aggregatedBySymbol[symbol].current_price`
  — использовать `units * current_price`. Простейший вариант: пробросить
  `pricesBySymbol?: Record<string, number>` пропом в `WalletCard` из
  `WalletsSection`/`dashboard` и фоллбечить только в нём.
- **Критерий готовности:** при ручной проверке (`fetch` смокать, чтобы
  цена `value_usd` была `null`) сумма всё равно отображается.

### A6 — DONE: прогон тестов и smoke-проверка UI

- **Файлы:** —
- **Что делаем (руками):**
  ```powershell
  cd D:\Work_Cursor\CryptoConsult\backend
  python manage.py test portfolios
  cd ..\frontend
  npm run lint
  npm run dev
  # Открыть http://localhost:3000/dashboard, убедиться, что:
  # - в карточке каждого кошелька рядом с символом стоит сумма в $,
  # - «Всего» по кошельку = сумме строк,
  # - сумма всех «Всего» по кошелькам ≈ общей стоимости портфеля сверху.
  ```
- **Если что-то падает** — починить локально, не запускать новый агент.
- **Критерий готовности:** скрин/описание в коммит-сообщении PR.

---

## 4. Порядок запуска

```
S1: A1  ──►  A2
                │
S2:           ├──►  A3 (тесты)        ── параллельно ──┐
                │                                       │
              ├──►  A4 (TS-типы)      ── параллельно ──┘
                │
S3 (опц.):    └──►  A5 (фронт-фоллбэк)
                          │
S4:                       └──►  A6 (DONE)
```

Минимально нужный путь до «фикса в проде»: **A1 → A2 → A6** (≤ 30 минут
работы агентов). A3/A4/A5 — для устойчивости и красоты.

---

## 5. Что НЕ входит в PLAN10 (явный анти-скоуп)

- Кэширование агрегата `total_value_usd` в БД (это уже `services/PriceService`
  делает на уровне цен).
- Исторические снимки стоимости (Wallet snapshots) — это отдельная задача.
- Пересчёт `PortfolioAsset.value_usd` или агрегатов портфеля — здесь не трогаем.
- Любые изменения формата чисел/локализации — оставляем как сейчас (`formatCurrency`).

---

## 6. DONE-чек (для PR-описания)

- [ ] `WalletHoldingSerializer` отдаёт `value_usd` (число или `null`).
- [ ] `WalletSerializer` отдаёт `total_value_usd`.
- [ ] `WalletListCreateView`, `WalletDetailView`, `WalletTransferView`,
      `HoldingAdjustmentView` (и прочие mutate-вью кошелька) прокидывают
      `prices` в context сериализатора одним батчем.
- [ ] `python manage.py test portfolios` — зелёный.
- [ ] В UI на dashboard суммы по holding'ам и «Всего» по кошельку считаются
      и не равны `$0.00`.
- [ ] Сумма всех «Всего» по кошелькам ≈ общей стоимости портфеля сверху.
