# PLAN08-REALIZATION — Интеграция Market Cycle Engine в BTC-анализ CryptoConsult

> **Связь с PLAN07-realization.md.**
> PLAN07-realization.md описывает сборку **изолированного микросервиса** `cycle_engine/`
> (FastAPI + PostgreSQL + Redis + APScheduler), который считает **MVRV / SOPR / ETF
> proxy** и **Market Regime** только по бесплатным источникам (Binance / Coinbase /
> Kraken / yfinance / FRED / Farside / Fear & Greed) и отдаёт результаты по REST:
> `/api/v1/cycle/{mvrv-proxy, sopr-proxy, etf-flow, market-regime, dashboard, history}`.
>
> Этот документ (PLAN08) описывает **вторую половину работы** — как _CryptoConsult_
> (Django backend `backend/` + Next.js `frontend/`) **потребляет** этот микросервис
> и встраивает его метрики в существующий поток `get_btc_analysis()` и
> `DecisionScorer`, а также как новый «режим рынка» отображается в модалке
> анализа BTC. PLAN07-realization.md и PLAN08-realization.md вместе образуют
> законченный план end-to-end.

---

## 0. Что уже есть в CryptoConsult (контекст)

| Слой | Файл | Роль |
|------|------|------|
| Сбор он-чейн (MVRV/SOPR/exchange flow/LTH) | `backend/market_data/onchain.py` | Сейчас MVRV/SOPR живут **только** при наличии `GLASSNODE_API_KEY`, иначе `None` |
| ETF потоки + новости | `backend/market_data/institutions.py` | Coinglass (`COINGLASS_API_KEY`) для ETF + CryptoPanic для новостей |
| Деривативы | `backend/market_data/derivatives.py` | Funding / OI / liquidations / long-short |
| Макро | `backend/market_data/macro.py` | FRED (Fed Funds, 10Y, DXY, S&P) |
| Sentiment | `backend/market_data/fear_greed.py` + `sentiment.py` | F&G index + новостной sentiment |
| Скорер сигнала | `backend/advisor/decision_scorer.py` | 5 блоков A–E, веса 25/20/20/20/15, диапазон `-2..+2`, BUY/HOLD/REDUCE |
| Главный отчёт по BTC | `backend/advisor/services.py::AIAdvisorService.get_btc_analysis` | Собирает всё → формирует `data_context` → LLM → JSON-ответ |
| API endpoint | `GET /api/v1/btc-analysis/` (`backend/advisor/views.py::BtcAnalysisView`) | Дёргает `get_btc_analysis` |
| Фронт | `frontend/src/components/forecast/BtcAnalysisModal.tsx` + `BtcAnalysisContent.tsx` | Карточки sections, signal-бейдж, сценарии, рекомендации |

После PLAN07-realization у нас появится дополнительный сервис, доступный по
`http://cycle-engine:8001/api/v1/cycle/...` (или `http://localhost:8001/...` в dev).

---

## 1. Цели интеграции (PLAN08)

1. **Заменить «нет данных» для MVRV / SOPR на proxy-значения** из cycle_engine
   (когда `GLASSNODE_API_KEY` пуст).
2. **Заменить/дополнить ETF-блок proxy-EMA-сигналом** из cycle_engine
   (когда `COINGLASS_API_KEY` пуст или `flow_*_usd == 0`).
3. **Добавить новый блок F — «Цикл рынка»** в `DecisionScorer`, использующий
   композитный score `[0..1]` и регим (`bear / accumulation / bull / overheated /
   distribution`) из cycle_engine.
4. **Расширить `data_context`** для LLM-промпта: новые числа MVRV proxy / SOPR
   proxy / ETF EMA + текстовое объяснение режима.
5. **Расширить ответ `/api/v1/btc-analysis/`** новым блоком `cycle: {...}` и
   отрисовать его в модалке `BtcAnalysisModal` (отдельная карточка
   «Режим рынка + три прокси»).
6. **Сохранить полную деградируемость**: если cycle_engine выключен / упал —
   старая логика работает без изменений (feature-flag `CYCLE_ENGINE_ENABLED`).

---

## 2. Архитектура интеграции

```
                             ┌─────────────────────────────┐
                             │   cycle_engine (PLAN07)     │
                             │   FastAPI :8001             │
                             │   /api/v1/cycle/*           │
                             └──────────────┬──────────────┘
                                            │  HTTP (cached)
                                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  CryptoConsult Django backend  (backend/)                        │
│                                                                  │
│   market_data/cycle_engine.py    ← НОВЫЙ HTTP-клиент             │
│            │                                                     │
│            ├──► onchain.py        (mvrv/sopr proxy fallback)     │
│            ├──► institutions.py   (etf proxy fallback)           │
│            └──► advisor/services.py::get_btc_analysis            │
│                       │                                          │
│                       ├──► decision_scorer.py (новый блок F)     │
│                       └──► формирует ответ + cycle блок          │
└──────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
                     frontend/  ← рендерит cycle gauge + 3 прокси
```

Принципы:

- **HTTP-only интеграция** (не импортируем Python-модули из `cycle_engine/`):
  это сохраняет изоляцию из PLAN07 и позволяет деплоить сервисы независимо.
- **Кэш ответов cycle_engine** на стороне Django (Redis или
  `django.core.cache`, TTL = 5–15 мин), чтобы не дёргать сервис на каждый
  запрос пользователя.
- **Graceful degradation**: при таймауте / 5xx / выключенном флаге клиент
  возвращает `None` и весь старый pipeline работает без изменений.
- **Никаких изменений в `cycle_engine/`** — его API уже определено
  PLAN07-realization §7.4 / §31. Меняем только сторону потребителя.

---

## 3. Структура агентов (по образцу PLAN07-realization)

Каждый агент = изолированная задача, минимальный контекст, не редактирует
чужие модули. Обозначения: `Aгент И-N` (Integration-N) — отличаются от
`Агент N` PLAN07-realization, чтобы их можно было выполнять независимо.

---

# ЭТАП И-0 — Конфигурация и feature-flag

## Агент И-1 — settings + .env

В `backend/config/settings.py`:

* добавить блок:
  ```python
  CYCLE_ENGINE_URL = os.environ.get("CYCLE_ENGINE_URL", "http://localhost:8001")
  CYCLE_ENGINE_ENABLED = os.environ.get("CYCLE_ENGINE_ENABLED", "false").lower() == "true"
  CYCLE_ENGINE_TIMEOUT = float(os.environ.get("CYCLE_ENGINE_TIMEOUT", "3.0"))  # сек
  CYCLE_ENGINE_CACHE_TTL = int(os.environ.get("CYCLE_ENGINE_CACHE_TTL", "600"))  # сек
  ```

В `backend/.env.example` добавить эти 4 переменные с комментариями
(включая ссылку на PLAN07-realization, чтобы знать, как поднять сервис).

В корневом `README.md` (раздел запуска backend) — короткий блок про cycle_engine
со ссылкой на `PLAN07-realization.md`. Пример PowerShell-команды для запуска
обоих сервисов параллельно (cycle_engine отдельным окном).

Не трогать ничего другого.

---

# ЭТАП И-1 — HTTP-клиент cycle_engine

## Агент И-2 — `CycleEngineClient`

Создать `backend/market_data/cycle_engine.py`:

* класс `CycleEngineClient` (sync, requests):
  * `__init__(base_url, timeout, cache_ttl, enabled)`
  * приватные методы `_get(path) -> Optional[dict]`:
    * читает кэш (`django.core.cache`, ключ `cycle:{path}`);
    * если кэша нет → `requests.get(base_url + path, timeout=timeout)`;
    * 200 → парсит JSON, кладёт в кэш на `cache_ttl`, возвращает;
    * 4xx/5xx/timeout/`enabled=False` → возвращает `None`, пишет
      `logger.warning(...)`;
  * публичные методы:
    * `get_mvrv_proxy() -> Optional[dict]`
    * `get_sopr_proxy() -> Optional[dict]`
    * `get_etf_flow() -> Optional[dict]`
    * `get_market_regime() -> Optional[dict]`
    * `get_dashboard() -> Optional[dict]`  ← один батч, экономит сеть
    * `get_history(days: int = 30) -> Optional[list]`
* фабрика `get_default_client()` — singleton, читает settings.
* константы путей берём из PLAN07 §7.4:
  ```
  /api/v1/cycle/mvrv-proxy
  /api/v1/cycle/sopr-proxy
  /api/v1/cycle/etf-flow
  /api/v1/cycle/market-regime
  /api/v1/cycle/dashboard
  /api/v1/cycle/history?days=N
  ```

Никакой бизнес-логики, никаких вычислений — только сеть и кэш.

## Агент И-3 — типы ответа

В том же `cycle_engine.py` (или отдельный `cycle_engine_types.py` —
выбор автора) объявить `TypedDict` для ответов:

* `CycleMVRV { value, k_cycle, k_liquidity, sma200, score }`
* `CycleSOPR { value, p_momentum, f_deriv, v_stress, score }`
* `CycleETF  { value, ema7, ema30, alignment_bonus, score, raw_daily: list }`
* `CycleRegime { ts, score, regime, components, raw, explanation }`
* `CycleDashboard { mvrv, sopr, etf, regime }` (все поля Optional)

Используем эти типы во всех потребителях — облегчает рефакторинг.

---

# ЭТАП И-2 — Внедрение proxy в существующие источники

## Агент И-4 — patch `onchain.py` (MVRV / SOPR fallback)

В `backend/market_data/onchain.py::get_btc_onchain`:

После блока «Glassnode — опционально», **если `result["mvrv"] is None`** или
`result["sopr"] is None`:

```python
from .cycle_engine import get_default_client

client = get_default_client()
dash = client.get_dashboard() if client else None
if dash:
    if result["mvrv"] is None and dash.get("mvrv"):
        result["mvrv"] = float(dash["mvrv"]["value"])
        result["mvrv_proxy"] = True            # маркер: это proxy
        result["mvrv_score"] = float(dash["mvrv"]["score"])
    if result["sopr"] is None and dash.get("sopr"):
        result["sopr"] = float(dash["sopr"]["value"])
        result["sopr_proxy"] = True
        result["sopr_score"] = float(dash["sopr"]["score"])
        # пересчитать sopr_signal по тем же порогам:
        v = result["sopr"]
        result["sopr_signal"] = 1 if v < 1.0 else (-1 if v > 1.05 else 0)
```

В `_interpret_onchain` оставить логику без изменений — пороги те же.

В docstring `get_btc_onchain` отметить новые поля `mvrv_proxy`, `sopr_proxy`,
`mvrv_score`, `sopr_score`.

## Агент И-5 — patch `institutions.py` (ETF proxy fallback)

В `backend/market_data/institutions.py::get_btc_institutions`:

После Coinglass-блока, **если** `result["total_aum_usd"] == 0` **или**
`result["flow_7d_usd"] == 0`:

```python
from .cycle_engine import get_default_client
client = get_default_client()
etf = client.get_etf_flow() if client else None
if etf:
    result["flow_1d_usd"] = float(etf.get("raw_daily", [0])[-1] or 0)
    result["flow_7d_usd"] = float(etf["ema7"]) * 7   # приведение EMA → 7д объём
    result["etf_proxy"] = True
    result["etf_ema7"] = float(etf["ema7"])
    result["etf_ema30"] = float(etf["ema30"])
    result["etf_score"] = float(etf["score"])
    result["etf_interpretation"] = (
        f"proxy ETF flow (EMA7={result['etf_ema7']:,.0f}, "
        f"alignment_bonus={etf.get('alignment_bonus', 0):+.2f})"
    )
```

`summary` собирать как и раньше — он сам подхватит новые числа.
Маркер `etf_proxy=True` важен: фронт может показать пометку
«ETF: proxy на основе Farside».

---

# ЭТАП И-3 — Регим: новый источник «cycle»

## Агент И-6 — `market_data/regime.py`

Создать `backend/market_data/regime.py`:

```python
def get_btc_cycle_regime() -> Optional[Dict]:
    """
    Возвращает:
        {
          "ts": str,
          "score": float,        # [0,1]
          "regime": str,         # bear|accumulation|bull|overheated|distribution
          "regime_smoothed": str,
          "components": { mvrv_score, sopr_score, etf_score },
          "raw": { mvrv_proxy, sopr_proxy, etf_ema7 },
          "explanation": str
        }
    или None при недоступности cycle_engine.
    """
```

Под капотом — `CycleEngineClient.get_market_regime()`. Без вычислений.

## Агент И-7 — экспорт из пакета

В `backend/market_data/__init__.py` добавить:

```python
from .regime import get_btc_cycle_regime
```

Чтобы в `services.py` единый импорт:

```python
from market_data import (
    get_btc_derivatives, get_btc_onchain, get_macro_data,
    get_btc_institutions, get_btc_sentiment, get_btc_cycle_regime,
)
```

---

# ЭТАП И-4 — Расширение DecisionScorer

## Агент И-8 — новый блок F + перебалансировка весов

В `backend/advisor/decision_scorer.py`:

1. Расширить `ScorerInput`:

   ```python
   # Cycle (PLAN08 / cycle_engine)
   cycle_score: Optional[float] = None       # [0,1]; None = блок выкл.
   cycle_regime: Optional[str] = None        # bear/accumulation/...
   ```

2. Добавить:

   ```python
   WEIGHT_F = 0.15  # Цикл рынка (новый)
   ```

   и понизить остальные на пропорциональные доли так, чтобы
   `Σ = 1.00`. Базовое решение (отражает важность регима):

   | Блок | Старый | Новый |
   |------|--------|-------|
   | A    | 0.25   | 0.20  |
   | B    | 0.20   | 0.15  |
   | C    | 0.20   | 0.15  |
   | D    | 0.20   | 0.20  |
   | E    | 0.15   | 0.15  |
   | F    | —      | 0.15  |
   | **Σ**| 1.00   | 1.00  |

   Эти константы держим в одном месте, чтобы при отключении блока F
   можно было нормализовать.

3. Реализовать `_block_f_cycle(inp) -> int`:

   ```python
   if inp.cycle_score is None:
       return 0
   s = inp.cycle_score
   regime = (inp.cycle_regime or "").lower()

   # Сдвиг по чистому score:
   if s < 0.20:    score = 2     # bear → DCA-buy
   elif s < 0.40:  score = 1     # accumulation
   elif s < 0.70:  score = 0     # bull
   elif s < 0.90:  score = -1    # overheated
   else:           score = -2    # distribution

   # Дополнительная коррекция по сглаженному regime
   if regime == "distribution": score = min(score, -1)
   if regime == "bear":         score = max(score,  1)
   return max(-2, min(2, score))
   ```

4. В `compute()`:

   * считать `f = self._block_f_cycle(inp)`;
   * если `inp.cycle_score is None`:
     * **не считать F**, но **отнормировать** оставшиеся веса:
       `w_i' = w_i / (1 - WEIGHT_F)` — суммарный диапазон `±2` сохраняется;
   * иначе использовать таблицу выше.

5. В `_compute_total_score` корректно работать с динамическими весами.

6. Обновить docstring модуля: 6 блоков, диапазон сохранён, пороги
   BUY/HOLD/REDUCE те же (`±0.75`).

## Агент И-9 — порог EXIT (опционально, но в PLAN_BTC)

В PLAN_BTC.md упоминается сигнал **EXIT** при score < -30 (шкала -100..+100).
В нашей шкале -2..+2 это эквивалент `total < -1.5`. Добавить:

```python
EXIT_THRESHOLD = -1.5
```

В `_score_to_signal`:

```python
if total < EXIT_THRESHOLD: return "EXIT"
if total < REDUCE_THRESHOLD: return "REDUCE"
if total > BUY_THRESHOLD: return "BUY"
return "HOLD"
```

В типах фронта добавить `'EXIT'` (см. агент И-13).
Если решено не вводить EXIT в этом релизе — этот агент пропускаем.

---

# ЭТАП И-5 — Интеграция в `get_btc_analysis`

## Агент И-10 — pull cycle data + ScorerInput

В `backend/advisor/services.py::get_btc_analysis`:

1. После блока «Fear & Greed, деривативы, он-чейн, макро» вызвать:

   ```python
   try:
       cycle = get_btc_cycle_regime()
   except Exception:
       cycle = None
   ```

2. Прокинуть в `ScorerInput`:

   ```python
   cycle_score=cycle.get("score") if cycle else None,
   cycle_regime=(cycle.get("regime_smoothed") or cycle.get("regime")) if cycle else None,
   ```

3. В возврат `get_btc_analysis` добавить ключ `cycle`:

   ```python
   "cycle": cycle if cycle else None,
   ```

4. Не ломать обратную совместимость остальных полей.

## Агент И-11 — расширение `data_context` для LLM

В том же `get_btc_analysis`, при формировании `data_context`:

* в раздел «5. Он-чейн»: если `mvrv_proxy=True`, дописать
  `(proxy: cycle_engine, MVRV_score=…)`. Аналогично для SOPR.
* в раздел «7. Институциональный фактор»: если `etf_proxy=True`,
  добавить блок:
  ```
  ETF (proxy): EMA7=$320M, EMA30=$210M, alignment=+0.20, score=0.74
  Источник: Farside (бесплатно, через cycle_engine)
  ```
* добавить **новый раздел «11. Цикл рынка»** в текстовый контекст:
  ```
  11. ЦИКЛ РЫНКА (cycle_engine, PLAN07):
  • Score: 0.78 / 1.00
  • Регим: overheated (smoothed: overheated)
  • MVRV proxy: 2.9 (score 0.82)
  • SOPR proxy: 1.18 (score 0.71)
  • ETF EMA7:  $320M  (score 0.74)
  • Объяснение: <explanation из cycle_engine>
  ```
* в JSON-схему ответа LLM (в самом prompt) добавить элемент:
  ```
  {"title": "11. Цикл рынка (Market Regime)",
   "content": "Используй данные из блока 11 выше (regime, score, proxies).
               Если регим overheated/distribution — подчеркни риск.
               Если bear/accumulation — упомяни возможность DCA."}
  ```
* если `cycle is None` — раздел не добавлять, секцию 11 не запрашивать.

## Агент И-12 — нормализация ответа

В `get_btc_analysis` при сборке итогового dict:

```python
return {
    ...,
    "signal": signal,
    "signal_score": round(signal_score, 2),
    "signal_blocks": signal_blocks,        # теперь содержит и "F"
    "cycle": _normalize_cycle(cycle),      # см. ниже
}
```

`_normalize_cycle(c)` — pure-функция в том же файле:

```python
def _normalize_cycle(c):
    if not c: return None
    return {
        "score": float(c.get("score", 0)),
        "regime": c.get("regime", ""),
        "regime_smoothed": c.get("regime_smoothed", c.get("regime", "")),
        "components": {
            "mvrv_score": float(c.get("components", {}).get("mvrv_score", 0)),
            "sopr_score": float(c.get("components", {}).get("sopr_score", 0)),
            "etf_score":  float(c.get("components", {}).get("etf_score", 0)),
        },
        "raw": {
            "mvrv_proxy": float(c.get("raw", {}).get("mvrv_proxy", 0)),
            "sopr_proxy": float(c.get("raw", {}).get("sopr_proxy", 0)),
            "etf_ema7":   float(c.get("raw", {}).get("etf_ema7", 0)),
        },
        "explanation": c.get("explanation", ""),
    }
```

В фолбэк-блоке (catch при ошибке LLM) тоже добавить `"cycle": None`.

---

# ЭТАП И-6 — Фронт: типы и UI

## Агент И-13 — типы

В `frontend/src/components/forecast/BtcAnalysisModal.tsx` расширить
`BtcAnalysisData`:

```ts
export interface CycleComponents {
  mvrv_score: number
  sopr_score: number
  etf_score: number
}

export interface CycleRaw {
  mvrv_proxy: number
  sopr_proxy: number
  etf_ema7:   number
}

export interface CycleData {
  score: number             // [0,1]
  regime: 'bear' | 'accumulation' | 'bull' | 'overheated' | 'distribution' | string
  regime_smoothed?: string
  components: CycleComponents
  raw: CycleRaw
  explanation: string
}

export interface BtcAnalysisData {
  ...                       // прежние поля
  cycle?: CycleData | null
  signal?: 'BUY' | 'HOLD' | 'REDUCE' | 'EXIT'   // если внедрён И-9
}
```

Также в `frontend/src/services/api.ts` (если там есть типы для btc-analysis)
добавить аналогичный type `CycleData` и проверить, что fetch-функция
возвращает обновлённую форму.

## Агент И-14 — компонент `CycleRegimeCard`

Создать `frontend/src/components/forecast/CycleRegimeCard.tsx`:

* props: `cycle: CycleData`
* визуал:
  * крупный индикатор `score` (0..1) — простая цветная полоса
    (зелёная при <0.4, синяя 0.4–0.7, оранжевая 0.7–0.9, красная >0.9);
  * лейбл регима + цвет:
    * bear → серый,
    * accumulation → синий,
    * bull → зелёный,
    * overheated → оранжевый,
    * distribution → красный;
  * 3 sub-карточки внутри: MVRV (`raw.mvrv_proxy` + `components.mvrv_score`),
    SOPR (`raw.sopr_proxy` + `components.sopr_score`),
    ETF (`raw.etf_ema7` + `components.etf_score`);
  * строка `explanation` (как разъяснение для пользователя);
  * футер: бейдж «Free proxy · cycle_engine» (отделяет от платных
    Glassnode/Coinglass, чтобы пользователь понимал источник).
* без зависимости от Recharts, чистый Tailwind.

## Агент И-15 — встраивание в `BtcAnalysisContent`

В `frontend/src/components/forecast/BtcAnalysisContent.tsx`:

1. после блока с `signal` и до карты sections добавить:

   ```tsx
   {data.cycle && <CycleRegimeCard cycle={data.cycle} />}
   ```

2. в `SignalBadge`-строке (где сейчас «Блоки: A=… B=… …») вывод обновить:

   ```tsx
   data.signal_blocks
     ? `Блоки: A=${...} B=${...} C=${...} D=${...} E=${...}` +
       (data.signal_blocks.F !== undefined ? ` F=${data.signal_blocks.F}` : '')
     : 'Структура, импульс, деривативы, он-чейн, макро, цикл'
   ```

3. поддержать сигнал EXIT в `SignalBadge` (если внедрён И-9):

   ```ts
   EXIT: { icon: ..., bg: 'bg-red-200', border: 'border-red-400',
           text: 'text-red-900', label: 'Выход' }
   ```

4. ничего больше не менять.

## Агент И-16 — sections-фильтр (опционально)

LLM теперь возвращает 11 секций. Если карточный список отображается
полностью, то `cycle` будет дублирован (раздел 11 + `CycleRegimeCard`).
Решение: в `BtcAnalysisContent` отфильтровать секции с заголовком,
содержащим `'11.'` или `'Цикл рынка'`, аналогично существующим
фильтрам секций 9 и 10:

```tsx
.filter((s) =>
  (!data.scenario_forecast || !s.title.includes('9. Сценарный')) &&
  (!data.profile_recommendations || !s.title.includes('10. Инвестиционные')) &&
  (!data.cycle || !s.title.includes('11.'))
)
```

---

# ЭТАП И-7 — Тесты

Все тесты в `backend/advisor/tests/` и `backend/market_data/tests/`
(если каталог отсутствует — создать с пустым `__init__.py`).
Используем `unittest.mock` (стек уже в проекте, без добавления
зависимостей).

## Агент И-17 — `tests/market_data/test_cycle_client.py`

* успешный `_get` → возвращает dict; повторный вызов — кэш-хит
  (мок `requests.get` вызвался 1 раз);
* `enabled=False` → возвращает `None` без сетевых вызовов;
* HTTP 500 → `None`, лог-warning;
* `requests.Timeout` → `None`;
* JSON-decode-ошибка → `None`.

## Агент И-18 — `tests/market_data/test_onchain_proxy.py`

* `GLASSNODE_API_KEY` отсутствует, cycle_engine-клиент возвращает
  валидный dashboard → `result["mvrv"]`/`sopr`/`mvrv_proxy`/`sopr_proxy`
  заполнены, `sopr_signal` пересчитан корректно.
* cycle_engine вернул `None` → старое поведение (None/0).

## Агент И-19 — `tests/market_data/test_institutions_proxy.py`

* `COINGLASS_API_KEY` отсутствует → используется `etf` из cycle_engine,
  `flow_1d_usd`, `flow_7d_usd`, `etf_ema7`, `etf_score`, `etf_proxy=True`
  установлены, `summary` непустой, `etf_interpretation` содержит «proxy».

## Агент И-20 — `tests/advisor/test_decision_scorer_cycle.py`

* `cycle_score=None` → результат равен старому DecisionScorer
  (числовая регрессия на 3-4 фикстурах, погрешность `< 1e-9`).
* `cycle_score=0.10` (deep bear) → `block_f = +2`, total смещается вверх.
* `cycle_score=0.95` (distribution) → `block_f = -2`, total смещается вниз.
* `cycle_regime='bear'` + `cycle_score=0.5` → `f = max(0, 1) = 1`
  (downgrade не происходит, upgrade происходит).
* Сумма весов всегда `1.0`; диапазон `total ∈ [-2, 2]`.
* (Если внедрён И-9) `total = -1.7` → `signal = "EXIT"`.

## Агент И-21 — `tests/advisor/test_btc_analysis_cycle.py`

* `get_btc_analysis(session_id=...)` с моками всех источников + моком
  `get_btc_cycle_regime` (возвращает фикстуру regime overheated).
* В возврате есть ключ `cycle`, форма соответствует `_normalize_cycle`.
* `signal_blocks` содержит ключ `'F'`.
* Параллельно — тест с `get_btc_cycle_regime → None`:
  `cycle is None`, `'F' not in signal_blocks`, веса нормализованы.

## Агент И-22 — Frontend тест (smoke)

`frontend/src/components/forecast/__tests__/CycleRegimeCard.test.tsx`
(если в проекте уже есть jest/vitest) — рендер с фикстурой, проверка
что `regime` отображается, что 3 sub-карточки видны.
Если тестового стенда фронта нет — пропустить агент.

---

# ЭТАП И-8 — Развёртывание (dev + prod)

## Агент И-23 — docker-compose / dev-скрипты

Если в репозитории есть `docker-compose.yml` — добавить сервис
`cycle-engine` (образ из `cycle_engine/`, порт `8001`,
зависимость от `postgres-cycle` и `redis-cycle`).

Если нет — создать `scripts/dev-up.ps1`:

```powershell
# 1) Cycle engine (отдельным окном)
Start-Process powershell -ArgumentList "-NoExit","-Command",
  "cd cycle_engine; uvicorn app.main:app --port 8001"

# 2) Django backend
$env:CYCLE_ENGINE_URL = "http://localhost:8001"
$env:CYCLE_ENGINE_ENABLED = "true"
cd backend
python manage.py runserver 8000
```

(Команды соответствуют правилу пользователя — PowerShell-синтаксис,
без bash.)

## Агент И-24 — миграции / БД

В Django миграциях ничего не меняется — все данные cycle_engine
живут в его собственной БД (см. PLAN07 §1, §7).

Однако нужно расширить `backend/.env.example` (см. И-1) и при необходимости
обновить инструкции по поднятию dev (раздел README) и production
(переменные окружения).

## Агент И-25 — мониторинг и логи

* Все вызовы `CycleEngineClient` логируем с tag-префиксом
  `cycle_engine` (поле `extra={"source": "cycle_engine"}`),
  чтобы можно было фильтровать в Sentry / logs.
* В endpoint `/api/v1/btc-analysis/` (`backend/advisor/views.py`)
  добавить в response **только при наличии cycle**: ключ
  `cycle_engine_status: "online"|"offline"`. Не обязателен,
  но удобен для дебага фронта.

---

# 4. Итоговая последовательность спринтов

| # | Спринт | Агенты PLAN08 | Зависимость от PLAN07-realization |
|---|--------|---------------|------------------------------------|
| S1 | Конфиг + клиент | И-1, И-2, И-3 | cycle_engine развёрнут хотя бы со stub-данными (агент 0 PLAN07) |
| S2 | Скорер + тесты | И-8, И-20 | Не зависит — можно параллельно |
| S3 | onchain/institutions proxy | И-4, И-5, И-18, И-19 | Завершены sprint 5,6,7 PLAN07 (proxies) |
| S4 | regime импорт | И-6, И-7 | Завершён sprint 3 PLAN07 (regime simple) |
| S5 | get_btc_analysis | И-10, И-11, И-12, И-21 | S3 + S4 |
| S6 | Frontend | И-13, И-14, И-15, И-16, И-22 | S5 |
| S7 | EXIT-сигнал (опц.) | И-9 | S2 |
| S8 | Deploy / Mon | И-23, И-24, И-25 | Все sprints PLAN07 завершены |

---

# 5. DONE-условия PLAN08 (готовность к merge)

- [ ] `CYCLE_ENGINE_ENABLED=false` ⇒ `get_btc_analysis` ведёт себя
      побитово как до PLAN08 (регрессионный тест).
- [ ] `CYCLE_ENGINE_ENABLED=true` + рабочий cycle_engine ⇒
      ответ содержит блок `cycle`, `signal_blocks` содержит `F`,
      MVRV/SOPR/ETF — без «нет данных», когда платных ключей нет.
- [ ] cycle_engine упал / 500 / timeout ⇒ ответ корректный, без `cycle`,
      без 5xx у Django, в логах warning.
- [ ] Сумма весов `Σ w = 1.0` в обеих ветках (с F и без).
- [ ] Все тесты И-17 — И-22 зелёные.
- [ ] Frontend модалка показывает `CycleRegimeCard` с разными
      состояниями (bear/bull/overheated) — визуальная проверка
      на тестовых фикстурах.
- [ ] README / .env.example обновлены, понятна процедура поднятия.

---

# 6. Чего НЕ делаем в PLAN08

1. **Не дублируем** ingestion-логику: cycle_engine — единственный
   владелец источников MVRV/SOPR/ETF proxy.
2. **Не пишем cycle_engine-данные в Django БД** (только кэш в Redis).
3. **Не меняем `cycle_engine/` API** — если требуется новый эндпоинт,
   это правка PLAN07-realization, не PLAN08.
4. **Не делаем websocket / SSE** на cycle_engine — пока polling+кэш.
5. **Не делаем алерты** в Django (Telegram уже реализован в PLAN07
   агентами 34–36).
6. **Не делаем новую страницу `/cycle`** на фронте — она уже описана
   в PLAN07 (агенты 37–42). PLAN08 интегрирует данные **только в
   модалку BTC-анализа**, чтобы пользователь видел регим там, где
   уже привык смотреть.

---

# 7. Принципы для всех агентов PLAN08

1. Каждый агент читает только свой раздел PLAN08-realization.md и
   упомянутые в нём файлы.
2. Никаких изменений в `cycle_engine/` (это контракт PLAN07).
3. Любой сетевой вызов к cycle_engine — через `CycleEngineClient`,
   не через `requests.get` напрямую.
4. UTC времена, `Decimal` для денег (везде, где переходит в БД),
   `float` допустим только в проксированных ответах от cycle_engine
   (мы их и так не сохраняем в БД).
5. Феатур-флаг `CYCLE_ENGINE_ENABLED` уважает каждый узел.
6. Все новые пути логируются под общим логгером
   `logger = logging.getLogger("cycle_engine.client")`.
7. После своей работы — добавить/обновить тест из ЭТАПА И-7,
   если он попадает в зону агента.

---

# 8. Связь PLAN07-realization × PLAN08-realization (мини-карта)

| Что | Где описано | Кто реализует |
|-----|-------------|---------------|
| Сбор сырых данных (Binance/FRED/Farside/F&G) | PLAN07 §2, агенты 6–11 | cycle_engine |
| Расчёт MVRV / SOPR / ETF proxy | PLAN07 §3–5, агенты 19–21 | cycle_engine |
| Композитный score + regime + smoothing | PLAN07 §6, агенты 22–24 | cycle_engine |
| REST API `/api/v1/cycle/*` | PLAN07 §7.4, агенты 26–33 | cycle_engine |
| Telegram-алерты | PLAN07 §7.5, агенты 34–36 | cycle_engine |
| Standalone Next.js страница `/cycle` | PLAN07 агенты 37–42 | cycle_engine + frontend |
| **HTTP-клиент в Django** | **PLAN08 §И-1, агенты И-2/И-3** | **CryptoConsult** |
| **MVRV/SOPR proxy fallback в `onchain.py`** | **PLAN08 §И-2, агент И-4** | **CryptoConsult** |
| **ETF proxy fallback в `institutions.py`** | **PLAN08 §И-2, агент И-5** | **CryptoConsult** |
| **Блок F в DecisionScorer** | **PLAN08 §И-4, агент И-8** | **CryptoConsult** |
| **`get_btc_analysis` с cycle-блоком** | **PLAN08 §И-5, агенты И-10/11/12** | **CryptoConsult** |
| **`CycleRegimeCard` в модалке BTC** | **PLAN08 §И-6, агенты И-13/14/15** | **CryptoConsult (frontend)** |
| **Деплой и feature-flag** | **PLAN08 §И-8, агенты И-23/24/25** | **CryptoConsult** |

Эта карта — единственная точка истины о разделении ответственности
между двумя реализациями.
