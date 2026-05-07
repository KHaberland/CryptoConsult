# PLAN07-REALIZATION — Market Cycle Engine (агентная разбивка)

Цель: реализовать PLAN07.md (MVRV / SOPR / ETF proxy + Regime) полностью, без пропусков, free data only.
Каждый агент = изолированная задача с минимальным контекстом. Принцип: один агент видит только свой кусок.

Стек: Python 3.11+, FastAPI, pandas/numpy, ccxt, yfinance, BeautifulSoup, PostgreSQL, Redis, APScheduler.
Корневая папка нового сервиса: `cycle_engine/` (отдельно от Django backend).

Структура:
```
cycle_engine/
  app/
    config.py
    db/             # модели + миграции (SQLAlchemy + Alembic)
    ingest/         # source adapters
    features/       # SMA/EMA/RSI/ATR/zscore
    proxies/        # mvrv, sopr, etf
    regime/         # classifier
    api/            # FastAPI routers
    alerts/         # telegram + triggers
    scheduler/      # APScheduler jobs
    cache/          # redis
  tests/
  pyproject.toml
  README.md
  alembic.ini
```

---

# ЭТАП 0 — Bootstrap

## Агент 0 — каркас проекта

Создай каркас `cycle_engine/`:

* `pyproject.toml` с зависимостями: fastapi, uvicorn, pandas, numpy, scipy, ccxt, python-binance, yfinance, pandas-datareader, fredapi, requests, beautifulsoup4, httpx, sqlalchemy, alembic, psycopg2-binary, redis, apscheduler, pydantic, pydantic-settings, python-telegram-bot, pytest, pytest-asyncio, pytest-mock, freezegun
* `app/config.py` — `Settings(BaseSettings)` с переменными: `POSTGRES_URL`, `REDIS_URL`, `BINANCE_API_KEY`, `FRED_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `FARSIDE_URL`
* `app/main.py` — пустое FastAPI-приложение с health endpoint `/health`
* `alembic.ini` + `app/db/migrations/`
* `README.md` — запуск (PowerShell)

Не реализуй ingest / features / proxies — только структура.

---

# ЭТАП 1 — STORAGE (DB schema)

## Агент 1 — модель `prices_ohlcv`

В `cycle_engine/app/db/models/prices.py` создай SQLAlchemy модель `PriceOHLCV`:

* `id` (PK)
* `symbol` (str, index)
* `exchange` (str, index)
* `ts` (datetime, UTC, index)
* `open`, `high`, `low`, `close` (Numeric 20,8)
* `volume` (Numeric 28,8)
* uniq constraint `(symbol, exchange, ts)`

Ничего больше не трогай.

## Агент 2 — модели `macro_indicators`, `derivatives_metrics`

В `cycle_engine/app/db/models/macro.py`:

* `MacroIndicator` — `ts` (date, PK), `dxy`, `sp500`, `t10y` (Numeric)
* `DerivativeMetric` — `ts` (datetime, index), `funding_rate`, `open_interest`, `ls_ratio` (Numeric); uniq `(ts)`

## Агент 3 — модели `etf_flows`, `sentiment_metrics`

В `cycle_engine/app/db/models/sentiment.py`:

* `ETFFlow` — `id`, `ts` (date, index), `ticker` (str), `flow_usd` (Numeric 20,2), `source` (str); uniq `(ts, ticker, source)`
* `SentimentMetric` — `ts` (date, PK), `fear_greed` (int), `gtrends_btc` (int)

## Агент 4 — расчётные таблицы proxy + regime

В `cycle_engine/app/db/models/derived.py`:

* `MVRVProxyHistory` — `ts`, `value`, `k_cycle`, `k_liquidity`, `sma200`
* `SOPRProxyHistory` — `ts`, `value`, `p_momentum`, `f_deriv`, `v_stress`
* `ETFProxyHistory` — `ts`, `value`, `ema7`, `ema30`, `alignment_bonus`
* `RegimeHistory` — `ts`, `score`, `regime` (str), `mvrv_score`, `sopr_score`, `etf_score`, `regime_smoothed` (str)

`ts` — datetime UTC, индексируем. Все Numeric где уместно.

## Агент 5 — Alembic миграции

Создай init-миграцию Alembic, охватывающую все модели из агентов 1–4.
Партиционирование: добавь partition by RANGE(ts) для `prices_ohlcv` и `regime_history` (Postgres native partitioning, по месяцам). Создай первые 12 партиций.

Не трогай модели.

---

# ЭТАП 2 — DATA INGEST

## Агент 6 — HTTP utility (retry / backoff / rate-limit)

В `cycle_engine/app/ingest/http.py`:

* `class HttpClient` (httpx-based)
* методы `get_json`, `get_text`
* exponential backoff (1s → 32s, 5 попыток)
* respects `Retry-After`
* token bucket rate limiter (configurable rps)
* unit-friendly (зависимости через DI)

Никаких источников. Только утилита.

## Агент 7 — Binance OHLCV adapter

В `cycle_engine/app/ingest/binance.py`:

* `fetch_ohlcv(symbol, interval, limit)` — REST `/api/v3/klines`
* `fetch_funding_rate()` — `/fapi/v1/premiumIndex`
* `fetch_open_interest(symbol)` — `/fapi/v1/openInterest`
* `fetch_long_short_ratio(symbol, period='1h')` — `/futures/data/globalLongShortAccountRatio`
* возвращает pandas.DataFrame
* использует `HttpClient` из агента 6

## Агент 8 — Coinbase + Kraken adapters

В `cycle_engine/app/ingest/coinbase.py` + `kraken.py`:

* Coinbase `/products/BTC-USD/candles`
* Kraken `/0/public/OHLC`
* унифицированный DataFrame: `[ts, open, high, low, close, volume]`

Только spot OHLCV. Без деривативов.

## Агент 9 — Macro adapter (yfinance / FRED)

В `cycle_engine/app/ingest/macro.py`:

* `fetch_dxy()` — Stooq (`^DXY`) либо yfinance fallback
* `fetch_sp500()` — yfinance `^GSPC`
* `fetch_t10y()` — fredapi `DGS10`
* возвращает DataFrame по дате
* кеш в Redis на 24h

## Агент 10 — Sentiment adapter

В `cycle_engine/app/ingest/sentiment.py`:

* `fetch_fear_greed()` — `https://api.alternative.me/fng/?limit=365`
* `fetch_google_trends(['bitcoin','crypto'])` — pytrends, weekly
* возврат DataFrame

## Агент 11 — Farside ETF scraper

В `cycle_engine/app/ingest/farside.py`:

* `scrape_daily_flows()` — парсинг HTML-таблицы Farside (BeautifulSoup)
* respect robots.txt (User-Agent + delay 2s)
* возврат DataFrame `[ts, ticker, flow_usd]`
* fallback: если структура HTML сломалась → log error + raise `FarsideStructureError`
* кеш в Redis на 6h

## Агент 12 — Ingest orchestrator (write to DB)

В `cycle_engine/app/ingest/orchestrator.py`:

* `ingest_prices()` — Binance + Coinbase + Kraken → upsert в `prices_ohlcv`
* `ingest_macro()` → `macro_indicators`
* `ingest_derivatives()` → `derivatives_metrics`
* `ingest_etf()` → `etf_flows`
* `ingest_sentiment()` → `sentiment_metrics`
* idempotent upsert (ON CONFLICT DO UPDATE)

Использует адаптеры из агентов 7–11. Не реализует scheduler.

## Агент 13 — APScheduler jobs

В `cycle_engine/app/scheduler/jobs.py`:

* `prices_hourly` — каждый час
* `derivatives_hourly` — каждый час
* `macro_daily` — 22:00 UTC
* `etf_daily` — 21:00 UTC
* `sentiment_daily` — 22:00 UTC
* `gtrends_weekly` — Sunday 00:00 UTC
* `recompute_all_hourly` — каждый час (proxies + regime)

Подключи в `app/main.py` (startup event).

---

# ЭТАП 3 — FEATURE ENGINE

## Агент 14 — SMA / EMA

В `cycle_engine/app/features/moving.py`:

* `sma(series, window)`
* `ema(series, span)`
* pure pandas, без побочных эффектов
* docstring с формулами

## Агент 15 — RSI / ATR

В `cycle_engine/app/features/oscillators.py`:

* `rsi(close, window=14)` — Wilder's RSI
* `atr(high, low, close, window=14)` — Wilder's ATR

## Агент 16 — drawdown from ATH

В `cycle_engine/app/features/drawdown.py`:

* `drawdown_from_ath(close)` → Series с (ATH - price)/ATH
* `current_drawdown(close) -> float`

## Агент 17 — z-score normalization

В `cycle_engine/app/features/zscore.py`:

* `zscore(series, lookback)` — rolling z-score
* `clip_zscore(series, lo=-3, hi=3)`

## Агент 18 — feature aggregator

В `cycle_engine/app/features/build.py`:

* `build_features(prices_df, macro_df, deriv_df) -> dict`
* собирает: sma200, ema7, ema30, rsi14, atr14, drawdown, dxy_change_90d, sp_trend_90d, funding_z, oi_change_z, atr_rel_z

Не вычисляет proxies.

---

# ЭТАП 4 — PROXY MODELS

## Агент 19 — MVRV proxy

В `cycle_engine/app/proxies/mvrv.py`:

* `compute_k_cycle(drawdown: float) -> float` — по формуле PLAN07 §3.3
* `compute_k_liquidity(dxy_change, sp_trend) -> float` — clip [0.7, 1.3]
* `compute_mvrv_proxy(price, sma200, k_cycle, k_liquidity) -> float`
* `mvrv_score(mvrv_proxy) -> float` — clip((x-0.7)/3.3, 0, 1)
* возвращает dict `{value, k_cycle, k_liquidity, sma200, score}`

Чисто детерминированно. Без I/O.

## Агент 20 — SOPR proxy

В `cycle_engine/app/proxies/sopr.py`:

* `compute_p_momentum(rsi14)` — `(rsi-50)/50`
* `compute_f_derivatives(funding_z, oi_change_z)` — sum z-scores
* `compute_v_stress(atr_rel_z)`
* `compute_sopr_proxy(p_mom, f_deriv, v_stress, a=0.20, b=0.15, c=0.10)`
* `sopr_score(sopr_proxy)` — clip((x-0.95)/0.4, 0, 1)
* возвращает dict со всеми компонентами

## Агент 21 — ETF flow proxy

В `cycle_engine/app/proxies/etf.py`:

* `compute_etf_emas(flows_series)` → ema7, ema30
* `compute_alignment_bonus(price_change_7d, etf_ema7)` — формула §5.4
* `compute_etf_proxy(ema7, ema30, alignment_bonus)`
* `etf_score(etf_z)` — clip((z+2)/4, 0, 1)
* возвращает dict

---

# ЭТАП 5 — REGIME CLASSIFIER

## Агент 22 — композитный score + регим

В `cycle_engine/app/regime/classifier.py`:

* `compute_score(mvrv_score, sopr_score, etf_score) -> float`
  формула: `0.4*mvrv + 0.3*sopr + 0.3*etf`
* `classify_regime(score) -> str` — bear/accumulation/bull/overheated/distribution по таблице §6.3
* возвращает dict `{score, regime, weights}`

Без сглаживания.

## Агент 23 — сглаживание режима (3-day mode)

В `cycle_engine/app/regime/smoothing.py`:

* `smooth_regime(history: list[str]) -> str` — mode of last 3
* `should_transition(prev_regime, new_regime, last3) -> bool` — переход только если 3 дня в новой зоне
* возврат `(smoothed_regime, transitioned: bool)`

## Агент 24 — regime pipeline (write to DB)

В `cycle_engine/app/regime/pipeline.py`:

* `recompute_regime(ts)`:
  1. читает features из БД
  2. вызывает proxies (агенты 19–21)
  3. вызывает classifier (22)
  4. вызывает smoothing (23) на основе `regime_history`
  5. пишет `MVRVProxyHistory`, `SOPRProxyHistory`, `ETFProxyHistory`, `RegimeHistory`
* idempotent (upsert по ts)

---

# ЭТАП 6 — REDIS CACHE

## Агент 25 — Redis layer

В `cycle_engine/app/cache/redis_store.py`:

* `RedisStore` с методами `get_latest_regime()`, `set_latest_regime(payload)`, `get_proxy(name)`, `set_proxy(name, payload)`
* TTL = 90 минут
* JSON serialization

После `recompute_regime` обновляем Redis.

---

# ЭТАП 7 — API SERVICE

## Агент 26 — pydantic схемы ответов

В `cycle_engine/app/api/schemas.py`:

* `MVRVResponse`, `SOPRResponse`, `ETFResponse`
* `RegimeResponse` (с components, raw, explanation)
* `DashboardResponse` (всё одним пакетом)
* `HistoryItem`, `HistoryResponse`

Соответствуют примеру JSON в PLAN07 §7.4.

## Агент 27 — endpoint `/cycle/mvrv-proxy`

В `cycle_engine/app/api/routes/mvrv.py`:

* GET `/api/v1/cycle/mvrv-proxy`
* читает из Redis → fallback на БД
* возвращает `MVRVResponse`

## Агент 28 — endpoint `/cycle/sopr-proxy`

В `cycle_engine/app/api/routes/sopr.py`. Аналогично агенту 27.

## Агент 29 — endpoint `/cycle/etf-flow`

В `cycle_engine/app/api/routes/etf.py`. Аналогично агенту 27, плюс EMA + raw daily массив за 90 дней.

## Агент 30 — endpoint `/cycle/market-regime`

В `cycle_engine/app/api/routes/regime.py`:

* GET `/api/v1/cycle/market-regime`
* возвращает score + regime + components + raw + `explanation` (текст)
* генератор `explanation` — функция `build_explanation(components, raw, regime)` в том же файле, шаблон в стиле примера §7.4

## Агент 31 — endpoint `/cycle/dashboard`

В `cycle_engine/app/api/routes/dashboard.py`:

* GET `/api/v1/cycle/dashboard`
* объединяет ответы из агентов 27–30 в один `DashboardResponse`

## Агент 32 — endpoint `/cycle/history`

В `cycle_engine/app/api/routes/history.py`:

* GET `/api/v1/cycle/history?days=N` (default=30, max=1825)
* возвращает массив `HistoryItem` из `RegimeHistory`

## Агент 33 — подключение роутеров + OpenAPI

В `cycle_engine/app/main.py`:

* подключи все роутеры под префиксом `/api/v1/cycle`
* включи Swagger UI на `/docs`
* CORS open (для фронта)

---

# ЭТАП 8 — ALERTS

## Агент 34 — Telegram client

В `cycle_engine/app/alerts/telegram.py`:

* `class TelegramNotifier` (python-telegram-bot)
* `send(message: str)` — async
* graceful failure (log + не падать)

## Агент 35 — alert triggers + debounce

В `cycle_engine/app/alerts/triggers.py`:

* `check_triggers(current, previous, window=24h)`:
  - regime → `overheated` 3 дня подряд
  - SOPR delta_24h > +0.10
  - ETF outflow_1d < -500M USD
  - score пересёк 0.9 вверх
* debounce через Redis-key `alert:<type>:last_ts` (TTL 24h)
* возвращает list of alert payloads

## Агент 36 — alert dispatcher

В `cycle_engine/app/alerts/dispatcher.py`:

* `dispatch_alerts()` — вызывается после `recompute_regime`
* читает текущее + предыдущее состояние из БД
* зовёт `check_triggers` → `TelegramNotifier.send`
* email канал — заглушка (TODO-комментарий, не реализовывать)

Подключи в `recompute_all_hourly` (агент 13).

---

# ЭТАП 9 — DASHBOARD (Next.js, опционально)

## Агент 37 — страница `/cycle` + API client

В `frontend/src/app/cycle/page.tsx`:

* fetch `/api/v1/cycle/dashboard`
* loading / error states
* layout: gauge сверху, ниже 4 виджета
* добавь типы в `frontend/src/services/api.ts`: `CycleDashboard`, `CycleRegime`, `CycleMVRV`, `CycleSOPR`, `CycleETF`

## Агент 38 — RegimeGauge

`frontend/src/components/cycle/RegimeGauge.tsx`:

* Recharts RadialBar
* цветовая шкала: bear=серый, accumulation=синий, bull=зелёный, overheated=оранжевый, distribution=красный
* показывает score [0..1] + лейбл регима

## Агент 39 — MVRVChart

`frontend/src/components/cycle/MVRVChart.tsx`:

* линейный график за 5 лет
* зоны (background bands): <1, 1–1.5, 1.5–2.5, 2.5–3.5, >3.5

## Агент 40 — SOPRChart

`frontend/src/components/cycle/SOPRChart.tsx`:

* линейный график с уровнями 1.0 / 1.05 / 1.15 / 1.30

## Агент 41 — ETFFlowsBar

`frontend/src/components/cycle/ETFFlowsBar.tsx`:

* Bar chart дневных потоков
* линия EMA7

## Агент 42 — RegimeHeatmap

`frontend/src/components/cycle/RegimeHeatmap.tsx`:

* heatmap 12 месяцев × дни
* цвет по региму

---

# ЭТАП 10 — ТЕСТЫ

Все тесты в `cycle_engine/tests/`. pytest. Где нужны API-моки — `pytest-mock` + `respx`. Время — `freezegun`.

## Агент T1 — тест HTTP utility

`tests/ingest/test_http.py`:

* retry на 500 → успех на 3-й попытке
* respect Retry-After
* rate limiter ограничивает rps
* финальный fail после 5 попыток

## Агент T2 — тесты ingest adapters (моки)

`tests/ingest/test_adapters.py`:

* Binance OHLCV → корректный DataFrame, типы, сортировка
* Coinbase / Kraken — то же
* Macro (yfinance мок) — корректные колонки
* Fear & Greed — корректный парсинг
* Farside — мок HTML фикстура → корректный DataFrame; сломанный HTML → `FarsideStructureError`

## Агент T3 — тест orchestrator + idempotency

`tests/ingest/test_orchestrator.py`:

* двойной вызов `ingest_prices` не плодит дубликаты
* upsert обновляет close/volume

## Агент T4 — тесты feature engine (синтетика)

`tests/features/test_features.py`:

* SMA/EMA на синусоиде
* RSI на монотонной серии = 100 (рост) / 0 (падение)
* ATR на постоянной серии = 0
* drawdown на серии с ATH в начале
* z-score на N(0,1) ≈ 0

## Агент T5 — тесты MVRV proxy

`tests/proxies/test_mvrv.py`:

* `k_cycle`: drawdown=0.6 → 0.85; 0.3 → 1.0; 0.1 → ~1.25
* `k_liquidity`: clip [0.7, 1.3]
* `mvrv_proxy` на P=2*SMA200, k=1, k=1 → 2.0
* `mvrv_score` границ: 0.7→0, 4.0→1, посередине

## Агент T6 — тесты SOPR proxy

`tests/proxies/test_sopr.py`:

* RSI=50 → p_momentum=0
* RSI=80 → p_momentum=0.6
* при нулевых компонентах sopr_proxy=1.0
* `sopr_score` границ

## Агент T7 — тесты ETF proxy

`tests/proxies/test_etf.py`:

* alignment: price+,ema+ → +0.2*|ema7|
* alignment: price+,ema- → -0.3*|ema7|
* alignment: price-,ema- → -0.2*|ema7|
* etf_score границ

## Агент T8 — тесты regime classifier

`tests/regime/test_classifier.py`:

* score = 0.4*0.5 + 0.3*0.5 + 0.3*0.5 = 0.5 → "bull"
* границы: 0.19→bear, 0.21→accumulation, 0.71→overheated, 0.91→distribution
* compute_score формула match

## Агент T9 — тесты сглаживания

`tests/regime/test_smoothing.py`:

* last3 = [bull, bull, overheated] → smoothed = bull
* last3 = [overheated]*3 → переход = True
* last3 = [bull, overheated, bull] → переход = False

## Агент T10 — тест pipeline (интеграционный)

`tests/regime/test_pipeline.py`:

* вставить фикстуры в БД (sqlite in-memory)
* запустить `recompute_regime(ts)`
* проверить, что записаны 4 строки (mvrv/sopr/etf/regime)
* повторный вызов — upsert, не дубликат

## Агент T11 — тесты API (FastAPI TestClient)

`tests/api/test_endpoints.py`:

* все 6 endpoints возвращают 200
* схема ответа соответствует pydantic моделям
* `/history?days=30` — длина <= 30
* `/history?days=99999` → 422 (валидация max=1825)
* `/dashboard` содержит все секции

## Агент T12 — тесты алертов

`tests/alerts/test_alerts.py`:

* triggers срабатывают на правильных условиях
* debounce: повторный alert в окне 24h не отправляется
* mock `TelegramNotifier.send` — проверяем количество вызовов
* graceful failure: telegram down → не валит pipeline

## Агент T13 — тест расписания (smoke)

`tests/scheduler/test_jobs.py`:

* APScheduler регистрирует все 7 job-ов
* freezegun: `recompute_all_hourly` вызывает orchestrator + recompute_regime + dispatch_alerts

## Агент T14 — e2e тест MVP

`tests/e2e/test_mvp.py`:

1. `ingest_*` (mocked sources, 30 дней синтетических данных)
2. `recompute_regime` для каждой даты
3. GET `/api/v1/cycle/dashboard` → 200
4. score ∈ [0,1], regime ∈ {bear, accumulation, bull, overheated, distribution}
5. `/history?days=30` возвращает 30 точек

---

# PIPELINE FLOW (контроль)

```
scheduler → orchestrator (ingest) → DB
                                     ↓
                                  features
                                     ↓
                                  proxies (mvrv, sopr, etf)
                                     ↓
                                  regime classifier + smoothing
                                     ↓
                              DB + Redis cache
                                     ↓
                          API endpoints  +  alert dispatcher → Telegram
```

---

# DONE CONDITION (MVP — соответствие PLAN07 §11)

- [ ] все 14 групп тестов зелёные (`pytest -q`)
- [ ] `/api/v1/cycle/market-regime` возвращает корректный JSON (формат §7.4)
- [ ] daily обновления работают (scheduler логирует выполнения)
- [ ] три proxy показываются (`/mvrv-proxy`, `/sopr-proxy`, `/etf-flow`)
- [ ] alerts в Telegram на тестовое условие (force script) — отправлены
- [ ] API latency p95 < 1s (тест с `pytest-benchmark`)
- [ ] uptime: graceful degradation если Farside упал (используем последние данные из БД)

---

# ПРИОРИТЕТ ВЫПОЛНЕНИЯ (MVP first, по PLAN07 §10)

| # | Агенты |
|---|--------|
| Sprint 1 — Data | 0, 1–5, 6–13 |
| Sprint 2 — Features | 14–18, T4 |
| Sprint 3 — Regime simple | 22, 24, T8, T9, T10 |
| Sprint 4 — API | 26–33, T11 |
| Sprint 5 — MVRV полный | 19, T5 |
| Sprint 6 — SOPR полный | 20, T6 |
| Sprint 7 — ETF полный | 21, 11, T7 |
| Sprint 8 — Alerts | 34–36, T12 |
| Sprint 9 — Storage opt | партиционирование (агент 5) + Redis (25) |
| Sprint 10 — Dashboard | 37–42 |
| Финал | T1, T2, T3, T13, T14 |

---

# ПРИНЦИПЫ ДЛЯ КАЖДОГО АГЕНТА

1. Читай только свой раздел PLAN07-realization.md и упомянутые в нём файлы.
2. Не редактируй чужие модули.
3. Все денежные/ценовые поля — `Decimal` или `Numeric`, не `float`.
4. Все детерминированные расчёты — pure functions, без I/O.
5. Любое внешнее API — через `HttpClient` (агент 6).
6. UTC везде.
7. После своей работы добавь/обнови соответствующий тест из ЭТАПА 10, если он попадает в твою зону.
