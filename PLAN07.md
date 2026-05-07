# PLAN07: Market Cycle Engine (MVRV / SOPR / ETF proxy без платных API)

## Цель системы

Построить **бесплатную модель оценки Bitcoin-рынка**, которая отвечает на четыре ключевых вопроса:

1. **Перегрет / нейтрален / недооценён** ли рынок прямо сейчас?
2. В какой **фазе цикла** мы находимся (накопление / рост / перегрев / распределение)?
3. Какой **институциональный спрос** (proxy через ETF flows и деривативы)?
4. Какой **риск коррекции** на горизонте 1–4 недели?

Принципиально: **никаких платных API** (Glassnode, CryptoQuant, Bloomberg). Только публичные источники + математические прокси.

---

## 1. Архитектура системы

```
┌─────────────────────────────────────────────────────────┐
│                  Data Sources (free)                    │
│   Binance · Coinbase · Yahoo · FRED · Farside · F&G     │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                    Feature Engine                       │
│   SMA / EMA / RSI / ATR / drawdown / momentum / DXY     │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                     Proxy Models                        │
│   ┌───────────────┐ ┌──────────────┐ ┌──────────────┐   │
│   │ MVRV_proxy    │ │ SOPR_proxy   │ │ ETF_flow_pxy │   │
│   └───────┬───────┘ └──────┬───────┘ └──────┬───────┘   │
└───────────┼────────────────┼────────────────┼───────────┘
            └────────────────┼────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────┐
│              Market Regime Classifier                   │
│   bear · accumulation · bull · overheated · distribution│
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              API · Dashboard · Alerts                   │
└─────────────────────────────────────────────────────────┘
```

**Слои:**

| Слой | Ответственность |
|------|-----------------|
| Data Sources | Сырые данные (price, macro, derivatives, sentiment) |
| Feature Engine | Технические индикаторы и нормализация |
| Proxy Models | Три независимые модели (MVRV / SOPR / ETF) |
| Regime Classifier | Композитный score → метка фазы цикла |
| API / Dashboard | Внешний интерфейс + алерты |

---

## 2. Бесплатные источники данных

### 2.1. Цена и спот-рынок

| Источник | Что берём | Способ |
|----------|-----------|--------|
| Binance API (spot) | OHLCV BTC/USDT, 1m–1d | REST (`/api/v3/klines`) |
| Coinbase API (spot) | OHLCV BTC/USD | REST (`/products/BTC-USD/candles`) |
| Kraken API | Backup, OHLCV | REST (`/0/public/OHLC`) |

**Почему 3 источника:** sanity-check на расхождения, защита от блокировок Binance.

### 2.2. Макро-индексы

| Индекс | Источник | Назначение |
|--------|----------|------------|
| DXY (USD index) | Stooq / Yahoo Finance | Глобальная ликвидность |
| S&P 500 | Yahoo Finance | Risk-on / risk-off |
| 10Y Treasury Yield | FRED (`DGS10`) / TradingEconomics | Ставки → давление на риск-активы |

Библиотеки: `yfinance`, `pandas-datareader`, `fredapi` (free tier).

### 2.3. Крипто-деривативы (free tier)

Binance Futures API:

- `/fapi/v1/premiumIndex` — funding rate
- `/fapi/v1/openInterest` — open interest
- `/futures/data/globalLongShortAccountRatio` — long/short ratio (limited)
- `/futures/data/topLongShortPositionRatio` — позиции топ-трейдеров

### 2.4. ETF proxy (без Bloomberg)

| Источник | Что | Метод |
|----------|-----|-------|
| Farside Investors | Дневные потоки в BTC ETF | Scraping публичных страниц (HTML table) |
| Crypto news RSS | Mentions ETF | RSS parsing + keyword filter |
| SEC EDGAR | 13F filings (опционально) | Free API |

**ВАЖНО:** scraping — только публичные данные, с задержкой и кешированием. Соблюдаем `robots.txt`.

### 2.5. Сентимент (free)

| Источник | Что | Endpoint |
|----------|-----|----------|
| Fear & Greed Index | Индекс 0–100 | `https://api.alternative.me/fng/` |
| Google Trends | Запросы "bitcoin", "crypto" | `pytrends` |
| Reddit / X (опц.) | NLP по постам | `praw` / Twitter API v2 free |

---

## 3. MVRV Proxy (без on-chain данных)

### 3.1. Идея

Оригинальный MVRV = Market Cap / Realized Cap. У нас нет on-chain Realized Cap, поэтому **заменяем Realized Value на «циклическую справедливую цену»**, построенную из SMA200 + поправок на фазу цикла и ликвидность.

### 3.2. Формула

$$
\text{MVRV}_{\text{proxy}} = \frac{P}{\text{SMA}_{200} \cdot k_{\text{cycle}} \cdot k_{\text{liquidity}}}
$$

где:

- `P` — текущая цена BTC
- `SMA200` — простое скользящее среднее за 200 дней
- `k_cycle` — поправка на фазу цикла (drawdown от ATH)
- `k_liquidity` — поправка на макро-ликвидность (DXY + S&P)

### 3.3. Расчёт компонентов

#### 1) SMA200

```python
sma200 = price_series.rolling(window=200).mean()
```

#### 2) k_cycle (фаза рынка)

```python
drawdown = (ATH - price) / ATH

if drawdown > 0.50:        # глубокая коррекция
    k_cycle = 0.85
elif 0.20 < drawdown <= 0.50:
    k_cycle = 1.0
elif drawdown <= 0.20:     # рядом с ATH
    k_cycle = 1.2 + 0.1 * (1 - drawdown / 0.20)   # плавно 1.2 → 1.3
```

#### 3) k_liquidity

```python
dxy_change = (DXY_today - DXY_90d_ago) / DXY_90d_ago
sp_trend   = (SP500_today - SP500_90d_ago) / SP500_90d_ago

k_liquidity = 1 + (-0.5 * dxy_change) + (0.3 * sp_trend)
k_liquidity = clip(k_liquidity, 0.7, 1.3)
```

Логика:
- Растёт DXY → отток ликвидности → справедливая цена ниже → знаменатель меньше → MVRV выше → раньше сигнал перегрева.
- Растёт S&P → risk-on → справедливая цена выше.

### 3.4. Интерпретация

| MVRV proxy | Состояние |
|------------|-----------|
| < 1.0 | дно / капитуляция |
| 1.0 – 1.5 | накопление |
| 1.5 – 2.5 | бычий рынок |
| 2.5 – 3.5 | перегрев |
| > 3.5 | пузырь / топ |

---

## 4. SOPR Proxy (без on-chain данных)

### 4.1. Идея

SOPR (Spent Output Profit Ratio) показывает, **продают ли в прибыль**. Без UTXO-данных строим прокси на основе моментума, давления деривативов и волатильности.

### 4.2. Формула

$$
\text{SOPR}_{\text{proxy}} = 1 + a \cdot P_{\text{momentum}} + b \cdot F_{\text{derivatives}} - c \cdot V_{\text{stress}}
$$

Базовые коэффициенты (калибруются на исторических данных):

- `a = 0.20`
- `b = 0.15`
- `c = 0.10`

### 4.3. Компоненты

#### 1) Price momentum

```python
P_momentum = (RSI(14) - 50) / 50    # нормировка в [-1; +1]
```

#### 2) Derivatives pressure

```python
F_derivatives = normalize(funding_rate_8h) + normalize(OI_change_7d)
# normalize → z-score за последние 90 дней
```

Высокий funding + рост OI = трейдеры лонгуют с плечом → давление на фиксацию.

#### 3) Volatility stress

```python
V_stress = ATR(14) / price          # относительная волатильность
V_stress = normalize(V_stress, lookback=180)
```

Высокая волатильность = стресс → SOPR прокси снижается.

### 4.4. Интерпретация

| SOPR proxy | Значение |
|------------|----------|
| < 1.0 | капитуляция (продают в убыток) |
| 1.0 – 1.05 | нейтрально |
| 1.05 – 1.15 | лёгкая фиксация прибыли |
| 1.15 – 1.30 | сильный profit-taking |
| > 1.30 | распределение / top zone |

---

## 5. ETF Flow Proxy (без Bloomberg)

### 5.1. Цель

Оценить **институциональный спрос** через публичные данные о потоках в spot BTC ETF.

### 5.2. Входные данные

| Поле | Источник |
|------|----------|
| `etf_flow_usd_daily` | Farside (scrape) |
| `etf_news_sentiment` | RSS + keyword classifier |
| `btc_price_change_pct` | Binance |

### 5.3. Формула

```python
etf_ema7  = EMA(etf_flow_usd_daily, span=7)
etf_ema30 = EMA(etf_flow_usd_daily, span=30)

ETF_proxy_raw = 0.6 * etf_ema7 + 0.4 * etf_ema30
ETF_proxy = ETF_proxy_raw + alignment_bonus
```

### 5.4. Price alignment rule

```python
if price_change_7d > 0 and etf_ema7 > 0:
    alignment_bonus = +0.2 * |etf_ema7|     # подтверждённый buy-pressure
elif price_change_7d > 0 and etf_ema7 < 0:
    alignment_bonus = -0.3 * |etf_ema7|     # рост без ETF → слабый
elif price_change_7d < 0 and etf_ema7 < 0:
    alignment_bonus = -0.2 * |etf_ema7|     # подтверждённое распределение
else:
    alignment_bonus = 0
```

### 5.5. Интерпретация

| ETF flow (нормированный) | Значение |
|--------------------------|----------|
| < -1σ | distribution (отток) |
| -1σ … +1σ | neutral |
| +1σ … +2σ | accumulation |
| > +2σ | institutional bull phase |

---

## 6. Market Regime Classifier

### 6.1. Нормализация под-скоров

Каждый прокси конвертируем в `score ∈ [0; 1]`:

```python
mvrv_score = clip((mvrv_proxy - 0.7) / (4.0 - 0.7), 0, 1)
sopr_score = clip((sopr_proxy - 0.95) / (1.35 - 0.95), 0, 1)
etf_score  = clip((etf_z + 2) / 4, 0, 1)   # z-score сжатый в [0;1]
```

### 6.2. Композитный score

```python
score = 0.4 * mvrv_score + 0.3 * sopr_score + 0.3 * etf_score
```

Веса (`0.4 / 0.3 / 0.3`) — стартовые, далее калибруются бэктестом.

### 6.3. Режимы

| Score | Режим | Действие |
|-------|-------|----------|
| < 0.20 | **bear market** | накопление, DCA-mode |
| 0.20 – 0.40 | **accumulation** | плавный buy |
| 0.40 – 0.70 | **bull trend** | hold / trim на профите |
| 0.70 – 0.90 | **overheated** | take profit поэтапно |
| > 0.90 | **distribution top** | risk-off, фиксация |

### 6.4. Сглаживание режима

Чтобы не «дёргался» на шуме:

```python
regime_smoothed = mode of last 3 daily regimes
```

Переход в новый режим — только если 3 дня подряд в новой зоне.

---

## 7. Техническая реализация

### 7.1. Стек

| Компонент | Технология |
|-----------|-----------|
| Backend API | Python · FastAPI |
| Расчёты | `pandas`, `numpy`, `scipy` |
| Биржевые данные | `ccxt`, `python-binance` |
| Финансовые данные | `yfinance`, `pandas-datareader`, `fredapi` |
| Scraping | `requests`, `beautifulsoup4`, `httpx` |
| Хранилище | PostgreSQL (history) + Redis (real-time) |
| Шедулер | APScheduler / Celery beat |
| Мониторинг | Prometheus + Grafana |

### 7.2. Расписание (cron)

| Задача | Частота |
|--------|---------|
| Цена BTC (1h candles) | 1× в час |
| Деривативы (funding, OI) | 1× в час |
| Макро (DXY, S&P, 10Y) | 1× в день (после закрытия US) |
| ETF flows (Farside scrape) | 1× в день (вечер UTC) |
| Fear & Greed | 1× в день |
| Google Trends | 1× в неделю |
| Recompute proxies | каждый час |
| Recompute regime | каждый час |

### 7.3. Структура БД

```sql
-- сырые данные
prices_ohlcv          (symbol, exchange, ts, open, high, low, close, volume)
macro_indicators      (ts, dxy, sp500, t10y)
derivatives_metrics   (ts, funding_rate, open_interest, ls_ratio)
etf_flows             (ts, ticker, flow_usd, source)
sentiment_metrics     (ts, fear_greed, gtrends_btc)

-- расчётные
mvrv_proxy_history    (ts, value, k_cycle, k_liquidity, sma200)
sopr_proxy_history    (ts, value, p_momentum, f_deriv, v_stress)
etf_proxy_history     (ts, value, ema7, ema30, alignment_bonus)
regime_history        (ts, score, regime, mvrv_score, sopr_score, etf_score)
```

### 7.4. API endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/v1/cycle/mvrv-proxy` | Текущее значение + история |
| GET | `/api/v1/cycle/sopr-proxy` | Текущее значение + компоненты |
| GET | `/api/v1/cycle/etf-flow` | EMA + raw daily |
| GET | `/api/v1/cycle/market-regime` | Score + регим + объяснение |
| GET | `/api/v1/cycle/dashboard` | Всё одним пакетом для UI |
| GET | `/api/v1/cycle/history?days=N` | Исторические данные |

#### Пример ответа `/market-regime`

```json
{
  "ts": "2026-05-07T09:00:00Z",
  "score": 0.78,
  "regime": "overheated",
  "components": {
    "mvrv_score": 0.82,
    "sopr_score": 0.71,
    "etf_score":  0.74
  },
  "raw": {
    "mvrv_proxy": 2.9,
    "sopr_proxy": 1.18,
    "etf_ema7":   320_000_000
  },
  "explanation": "Цена выше SMA200 на 65%, funding на 90-дневном максимуме, ETF inflows +320M / 7d EMA. Высокий риск take-profit."
}
```

### 7.5. Алерты

| Триггер | Канал |
|---------|-------|
| Переход в `overheated` 3 дня подряд | Telegram / email |
| Резкий рост SOPR за 24h (> +0.10) | Telegram |
| ETF outflow > -500M / 1d | Telegram |
| `score` пересёк 0.9 вверх | Telegram + UI banner |

### 7.6. Dashboard (опционально)

- Next.js + Recharts
- Главные виджеты:
  1. Большой gauge со `score` и режимом
  2. График `MVRV_proxy` за 5 лет с зонами
  3. График `SOPR_proxy` с уровнями
  4. Bar chart ETF daily flows + EMA7
  5. Heatmap всех режимов по дням за 12 месяцев

---

## 8. Главная идея системы

> Мы **не пытаемся скопировать Glassnode** или повторить on-chain метрики 1:1.
>
> Мы строим **«cycle intelligence model»** — поведенческую модель цикла, основанную на:
> - макро-ликвидности (DXY, ставки, S&P),
> - структуре деривативного рынка (funding, OI),
> - институциональном потоке (ETF),
> - техническом моментуме (RSI, ATR, drawdown).
>
> Эти сигналы **исторически коррелируют** с фазами цикла BTC сильнее, чем кажется. Их комбинация даёт устойчивый proxy без платных API.

---

## 9. Что эта система реально даёт

1. **Видеть перегрев рынка раньше толпы** — за 2–6 недель до локального топа.
2. **Понимать фазу цикла без on-chain API** — accumulation / bull / overheated / distribution.
3. **Ловить переходы между фазами:**
   `накопление → рост → перегрев → распределение → дно → накопление`
4. **Делать осознанный risk management:**
   - в `bear` / `accumulation` — DCA-buy
   - в `bull` — hold + trailing stop
   - в `overheated` — поэтапная фиксация
   - в `distribution` — risk-off, переход в стейблы / кеш

---

## 10. Roadmap внедрения

### Этап 1 — Data Layer (1–2 недели)

- [ ] Подключить Binance / Coinbase / Kraken (OHLCV)
- [ ] Подключить yfinance (DXY, S&P, 10Y)
- [ ] Подключить Fear & Greed API
- [ ] Настроить PostgreSQL + Redis
- [ ] Написать ingest jobs + миграции

### Этап 2 — Feature Engine (3–5 дней)

- [ ] SMA / EMA / RSI / ATR / drawdown
- [ ] Z-score нормализация
- [ ] Юнит-тесты на синтетических рядах

### Этап 3 — Proxy Models (1–2 недели)

- [ ] MVRV proxy + калибровка на 2017 / 2021 / 2024 циклах
- [ ] SOPR proxy + бэктест
- [ ] ETF Flow proxy (Farside scraper + EMA)

### Этап 4 — Regime Classifier (3–5 дней)

- [ ] Композитный score
- [ ] Сглаживание (3-дневное mode)
- [ ] Бэктест переходов на 2018–2025

### Этап 5 — API + Alerts (1 неделя)

- [ ] FastAPI endpoints
- [ ] Telegram-бот для алертов
- [ ] Документация (Swagger / OpenAPI)

### Этап 6 — Dashboard (опционально, 1–2 недели)

- [ ] Next.js страница `/cycle`
- [ ] Recharts графики + gauge
- [ ] История режимов

### Этап 7 — Калибровка и улучшения (continuous)

- [ ] Подбор весов через grid-search на исторических данных
- [ ] Добавление Reddit / X NLP-сентимента
- [ ] ML-модель поверх proxy-скоров (опционально, sklearn / xgboost)

---

## 11. Метрики успеха

| Метрика | Целевое значение |
|---------|------------------|
| Точность определения топа (±4 недели) | ≥ 75% на исторических циклах |
| Точность определения дна (±4 недели) | ≥ 70% |
| Latency `score` (от события до UI) | < 1 час |
| Uptime API | ≥ 99% |
| Стоимость инфры | $0 на API + хостинг $10–30/мес |

---

## 12. Ограничения и риски

1. **Прокси ≠ on-chain.** В моменты резких аномалий (хардфорки, BlackSwan) прокси может расходиться с реальным MVRV/SOPR.
2. **Scraping Farside** может сломаться при изменении HTML — нужен мониторинг + fallback.
3. **Binance / Coinbase API** имеют rate limits — обязательно кеширование и backoff.
4. **Калибровка на 2–3 циклах** — не гарантирует работу в новых условиях (например, если ETF приток станет постоянным и выйдет из z-score нормы).
5. **Не финансовый совет.** Система — это **инструмент анализа**, а не торговый сигнал.
