# PLAN09 — Последовательность реализации PLAN08 с минимальным расходом токенов

> **Цель документа.**
> PLAN08-realization.md описывает _что_ нужно сделать (25 атомарных агентов И-1…И-25).
> PLAN09 описывает _в каком порядке_ запускать агенты, _как их группировать_,
> _какой контекст_ передавать каждому, чтобы итоговый расход токенов был
> минимальным, а каждая подзадача решалась в отдельном чистом агент-окне.
>
> Принципы оптимизации:
> 1. **Один агент = одна узкая задача с минимальным контекстом.** В промпт
>    агента передаём только PLAN08 §нужные подразделы + 1–3 конкретных файла.
> 2. **Группировка тривиальных правок.** Если 2-3 агента трогают один файл
>    или один пакет на 5–20 строк — запускаем их одним агентом (Bundle).
> 3. **Параллельные ветки.** Независимые агенты запускаем в параллельных
>    окнах (на стороне человека-оператора), чтобы не раздувать историю.
> 4. **Явная остановка через DONE-чек.** В конце каждого спринта — короткая
>    проверка (тесты + git diff), без длинных обсуждений.
> 5. **Никаких «исследовательских» промптов.** Каждый агент получает готовый
>    список файлов; нет нужды искать «где это лежит».

---

## 0. Подготовка (один раз, человеком, до агентов)

Перед запуском любого агента — выполнить руками, ~5 минут:

```powershell
# 1) Убедиться, что cycle_engine из PLAN07 поднимается локально хотя бы со stub-данными
cd D:\Work_Cursor\CryptoConsult
git status                              # должно быть чисто или с понятным diff
git checkout -b feature/plan08-cycle    # отдельная ветка

# 2) Создать пустой .env-фрагмент для будущих переменных
@"
CYCLE_ENGINE_URL=http://localhost:8001
CYCLE_ENGINE_ENABLED=false
CYCLE_ENGINE_TIMEOUT=3.0
CYCLE_ENGINE_CACHE_TTL=600
"@ | Add-Content backend\.env

# 3) Запустить актуальный backend-test, чтобы зафиксировать «зелёную» базу
cd backend
python manage.py test
cd ..
```

Если что-то падает уже сейчас — фиксим _до_ запуска агентов, иначе будем
ловить ложные регрессии.

---

## 1. Карта спринтов и агентов

Исходные 25 агентов из PLAN08 группируем в **8 спринтов** и **12 запусков
агентов** (некоторые мелкие задачи объединены в Bundle).

| Спринт | Запуск | Агенты PLAN08 в составе | Параллельно с | Кол-во файлов | Оценка токенов |
|--------|--------|------------------------|---------------|---------------|----------------|
| S1 | A1 | И-1 + И-2 + И-3 (config + client + types) | — | 4 | small |
| S2 | A2 | И-8 (DecisionScorer + блок F) | A1 | 1 | medium |
| S2 | A3 | И-20 (тест scorer)            | A2 (после)    | 1 | small |
| S3 | A4 | И-4 (onchain proxy) + И-18 (тест) | A1, может с A5 | 2 | small |
| S3 | A5 | И-5 (institutions proxy) + И-19 (тест) | A1, может с A4 | 2 | small |
| S3 | A6 | И-6 + И-7 (regime.py + __init__) + И-17 (тест клиента) | A1 | 3 | small |
| S4 | A7 | И-10 + И-11 + И-12 (get_btc_analysis) + И-21 (тест) | S2 + S3 | 2 | medium |
| S5 | A8 | И-13 (фронт-типы) | S4 | 2 | small |
| S5 | A9 | И-14 (CycleRegimeCard) | A8 | 1 | small |
| S5 | A10 | И-15 + И-16 (встраивание + фильтр) + И-22 (smoke-тест если есть) | A9 | 1–2 | small |
| S6 | A11 | И-9 (EXIT) — **опционально** | S5 | 2 | small |
| S7 | A12 | И-23 + И-24 + И-25 (deploy/мониторинг) | всё | 2–3 | small |

«small» = до ~15k токенов входа, «medium» = 15–30k.

---

## 2. Шаблон промпта для нового агента

Каждый запуск агента создаём в **новом окне Cursor Agent**, чтобы не тащить
историю предыдущих задач. Промпт строим по жёсткому шаблону:

```text
КОНТЕКСТ (минимальный):
- Прочитай только эти разделы PLAN08-realization.md: §<номера>
- Прочитай файлы:
    <abs/path/file_1>
    <abs/path/file_2>
- НЕ читай ничего другого. Не делай поиск по репозиторию без необходимости.

ЗАДАЧА:
<ровно то, что должен сделать агент, по тексту PLAN08>

DONE-условие:
<2–4 пункта: что должно появиться, какие тесты пройти>

ПРАВИЛА:
- PowerShell-команды (не bash). Ответы — по-русски.
- Ничего лишнего: не рефакторить соседний код, не добавлять зависимости.
- В конце — краткое summary diff + список изменённых файлов.
```

> Этот шаблон сам по себе ~150 токенов. Каждый агент должен его получить
> в чистом виде, без «вспомнить, что мы делали раньше».

---

## 3. Точные промпты для каждого запуска

Ниже — готовые брифы. Их можно копировать **as-is** в новое окно агента.

### A1 — Конфиг + HTTP-клиент + типы (S1)

> Запускаем первым. После него остальные смогут импортировать клиент.

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §1, §2, §И-0, §И-1 (агенты И-1, И-2, И-3).
- Прочитай: backend/config/settings.py (целиком), backend/.env.example (если есть).

ЗАДАЧА:
1. В backend/config/settings.py добавь 4 переменные CYCLE_ENGINE_* (агент И-1).
2. В backend/.env.example добавь те же 4 переменные с комментариями.
3. Создай backend/market_data/cycle_engine.py с CycleEngineClient (агент И-2)
   и TypedDict-типами CycleMVRV/CycleSOPR/CycleETF/CycleRegime/CycleDashboard
   (агент И-3) в том же файле.
4. Никаких изменений вне перечисленных файлов.

DONE:
- python -c "from market_data.cycle_engine import get_default_client; print(get_default_client())"
  выполняется без ошибок.
- В клиенте есть методы get_mvrv_proxy/get_sopr_proxy/get_etf_flow/
  get_market_regime/get_dashboard/get_history.
- При CYCLE_ENGINE_ENABLED=false все методы возвращают None без HTTP.
```

### A2 — DecisionScorer (блок F) (S2)

> Не зависит от A1, можно запускать параллельно.

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-4 (агент И-8).
- Прочитай backend/advisor/decision_scorer.py целиком.

ЗАДАЧА:
- Добавь блок F (Цикл рынка) в DecisionScorer ровно так, как описано в И-8:
  поля cycle_score/cycle_regime в ScorerInput, метод _block_f_cycle,
  пересбалансировка весов A=0.20/B=0.15/C=0.15/D=0.20/E=0.15/F=0.15,
  нормализация при cycle_score=None.
- НЕ внедрять EXIT (это отдельный агент A11).

DONE:
- При cycle_score=None результаты численно идентичны старым (в пределах 1e-9).
- Σ весов всегда = 1.0; total ∈ [-2, 2].
- Изменён только backend/advisor/decision_scorer.py.
```

### A3 — Тест DecisionScorer (S2)

> Запускать ПОСЛЕ A2. Не объединяем с A2, чтобы тест писался независимо
> и поймал ошибки «по слепому ТЗ».

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-7 (агент И-20).
- Прочитай backend/advisor/decision_scorer.py (после правок A2).
- Найди существующие тесты scorer'а в backend/advisor/tests/ как образец
  стиля (только просмотреть, не править).

ЗАДАЧА:
- Создай backend/advisor/tests/test_decision_scorer_cycle.py со всеми
  кейсами из И-20 (cycle_score=None, 0.10, 0.95, regime=bear+score=0.5,
  суммы весов, диапазон).
- НЕ добавляй кейс про EXIT.

DONE:
- python manage.py test advisor.tests.test_decision_scorer_cycle  → зелёные.
```

### A4 — onchain.py proxy + тест (S3)

> Зависит только от A1. Можно параллельно с A5 и A6.

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-2 (агент И-4) и §И-7 (агент И-18).
- Прочитай backend/market_data/onchain.py целиком.

ЗАДАЧА:
1. Добавь proxy-фолбэк MVRV/SOPR из cycle_engine ровно так, как в И-4:
   маркеры mvrv_proxy/sopr_proxy/mvrv_score/sopr_score, пересчёт sopr_signal.
2. Создай тест backend/market_data/tests/test_onchain_proxy.py по И-18
   (мокать cycle_engine.get_default_client; кейсы: успех, None).

DONE:
- При GLASSNODE_API_KEY="" и моке dashboard → MVRV/SOPR заполнены.
- При cycle_engine=None → старое поведение.
- Тест зелёный.
```

### A5 — institutions.py proxy + тест (S3)

> Параллельно с A4 и A6.

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-2 (агент И-5) и §И-7 (агент И-19).
- Прочитай backend/market_data/institutions.py целиком.

ЗАДАЧА:
1. Добавь ETF proxy-фолбэк по И-5: маркер etf_proxy=True, поля etf_ema7/
   etf_ema30/etf_score, etf_interpretation с «proxy».
2. Создай backend/market_data/tests/test_institutions_proxy.py по И-19.

DONE:
- При COINGLASS_API_KEY="" и моке etf-flow → flow_*_usd заполнены, summary
  непустой, etf_interpretation содержит «proxy».
- Тест зелёный.
```

### A6 — regime.py + __init__ + тест клиента (S3)

> Параллельно с A4/A5. Объединяем три мелких агента (И-6, И-7, И-17),
> потому что все трогают пакет market_data и весят суммарно <100 строк.

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-3 (агенты И-6, И-7) и §И-7 (агент И-17).
- Прочитай backend/market_data/__init__.py.
- Прочитай backend/market_data/cycle_engine.py (после A1).

ЗАДАЧА:
1. Создай backend/market_data/regime.py с get_btc_cycle_regime() (И-6).
2. Добавь экспорт в backend/market_data/__init__.py (И-7).
3. Создай backend/market_data/tests/test_cycle_client.py по И-17:
   успех+кэш, enabled=False, 500, Timeout, JSONDecodeError.

DONE:
- from market_data import get_btc_cycle_regime — работает.
- python manage.py test market_data.tests.test_cycle_client → зелёный.
```

### A7 — get_btc_analysis + тест (S4)

> Зависит от S2 (A2) и S3 (A4+A5+A6).
> Объединяем И-10, И-11, И-12 + И-21 — все правят один файл services.py
> и один тест.

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-5 целиком (агенты И-10, И-11, И-12)
  и §И-7 (агент И-21).
- Прочитай backend/advisor/services.py целиком.
- (Только посмотреть, не править) backend/advisor/decision_scorer.py
  чтобы знать сигнатуру ScorerInput.

ЗАДАЧА:
1. В get_btc_analysis():
   - вызвать get_btc_cycle_regime() с try/except → cycle;
   - прокинуть cycle_score / cycle_regime в ScorerInput;
   - расширить data_context (proxy-маркеры, новый раздел «11. Цикл рынка»);
   - в JSON-схему prompt'а добавить секцию 11;
   - в return добавить ключ "cycle": _normalize_cycle(cycle).
2. Реализуй pure-функцию _normalize_cycle в том же файле.
3. В fallback-блоке (catch ошибки LLM) тоже добавь "cycle": None.
4. Создай backend/advisor/tests/test_btc_analysis_cycle.py по И-21:
   2 кейса (cycle есть / cycle=None).

DONE:
- Регрессия: при моке get_btc_cycle_regime→None ответ совпадает с
  baseline (запиши baseline-фикстуру).
- При cycle≠None в ответе появляются "cycle": {...} и "F" в signal_blocks.
- Все тесты зелёные.
```

### A8 — Frontend-типы (S5)

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-6 (агент И-13).
- Прочитай frontend/src/components/forecast/BtcAnalysisModal.tsx
  и frontend/src/services/api.ts (только секции, где живёт BtcAnalysisData).

ЗАДАЧА:
- Добавь типы CycleComponents/CycleRaw/CycleData и поле cycle?: CycleData|null
  в BtcAnalysisData. Сигнал расширь до 'BUY'|'HOLD'|'REDUCE' (EXIT — отдельно).
- В services/api.ts продублируй CycleData, если там есть локальные типы btc-analysis.

DONE:
- npx tsc --noEmit (или npm run typecheck) проходит.
```

### A9 — Компонент CycleRegimeCard (S5)

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-6 (агент И-14).
- Прочитай 1–2 существующие карточки модалки как образец стиля
  (например, BtcAnalysisContent.tsx — только посмотреть классы Tailwind).

ЗАДАЧА:
- Создай frontend/src/components/forecast/CycleRegimeCard.tsx по И-14:
  цветная полоса score, бейдж режима, 3 sub-карточки (MVRV/SOPR/ETF),
  explanation, футер «Free proxy · cycle_engine».
- Чистый Tailwind, без Recharts.

DONE:
- Файл компилируется, экспорт по умолчанию.
- Никаких других правок.
```

### A10 — Встраивание карточки + фильтр секций (S5)

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-6 (агенты И-15, И-16) и §И-7 (агент И-22).
- Прочитай frontend/src/components/forecast/BtcAnalysisContent.tsx целиком.

ЗАДАЧА:
1. Импорт + рендер <CycleRegimeCard cycle={data.cycle} /> по И-15.
2. Обнови строку «Блоки: A=… B=…» с поддержкой F.
3. Добавь фильтр секции с заголовком «11.» / «Цикл рынка» по И-16.
4. (Если в проекте есть jest/vitest) добавь smoke-тест по И-22; иначе
   пропусти и явно укажи это в summary.

DONE:
- Локально открыть модалку с моковым ответом, увидеть карточку.
- Не дублируется секция 11 из LLM.
```

### A11 — EXIT-сигнал (S6, опционально)

> Делается, только если бизнес-решение «вводим EXIT» подтверждено.

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-4 (агент И-9).
- Прочитай backend/advisor/decision_scorer.py (после A2)
  и frontend/src/components/forecast/BtcAnalysisContent.tsx (после A10).

ЗАДАЧА:
1. Внедри EXIT_THRESHOLD=-1.5 в decision_scorer.py + ветку в _score_to_signal.
2. Расширь тип signal на фронте до 'BUY'|'HOLD'|'REDUCE'|'EXIT'.
3. В SignalBadge добавь стилизацию EXIT (red-200/red-400/red-900, «Выход»).
4. Дополни test_decision_scorer_cycle.py кейсом total=-1.7 → EXIT.

DONE:
- Тест EXIT зелёный, фронт компилируется.
```

### A12 — Деплой + мониторинг (S7)

> Объединяем И-23, И-24, И-25 — все короткие, трогают разные неисходные
> файлы (compose/scripts/views.py).

```text
КОНТЕКСТ:
- Прочитай PLAN08-realization.md §И-8 целиком (агенты И-23, И-24, И-25).
- Проверь наличие docker-compose.yml и scripts/. README.md.
- Прочитай backend/advisor/views.py.

ЗАДАЧА:
1. Если есть docker-compose.yml — добавь сервис cycle-engine (И-23),
   иначе создай scripts/dev-up.ps1 по И-23.
2. Дополни README.md и backend/.env.example блоком про cycle_engine (И-24).
3. В backend/advisor/views.py::BtcAnalysisView добавь в response поле
   cycle_engine_status: "online"|"offline" по И-25.
4. Лог-префикс "cycle_engine.client" — проверить, что используется в
   cycle_engine.py (если нет — добавить).

DONE:
- scripts/dev-up.ps1 запускает оба сервиса (или docker compose up).
- В response /api/v1/btc-analysis/ есть cycle_engine_status.
```

---

## 4. Зависимости и параллелизм (граф)

```
                  ┌──── A1 (config+client+types) ────┐
                  │                                  │
                  │                       ┌──── A4 (onchain+test) ─┐
                  │                       │                        │
   start ─────────┼─── A2 (scorer F) ──── A3 (scorer test)         │
                  │                       │                        │
                  │                       ├──── A5 (instit.+test) ─┤
                  │                       │                        │
                  │                       └──── A6 (regime+client test) ─┘
                  │                                                 │
                  └─────────────────────► A7 (get_btc_analysis+test)
                                                          │
                       ┌──── A8 (FE types) ────┐          │
                       │                        │         │
                       └─► A9 (Card) ── A10 (встраивание+фильтр)
                                                          │
                                              A11 (EXIT, опц.)
                                                          │
                                              A12 (deploy/мониторинг)
```

Параллельно можно запускать:
- **A1 ↔ A2** (разные файлы, нет зависимости).
- **A4 ↔ A5 ↔ A6** (разные модули в `market_data/`).
- **A8 → A9 → A10** строго последовательно (один пакет компонентов).

Если работаешь один — последовательность по строкам таблицы. Если есть
несколько окон агента — параллельные ветки помечены выше.

---

## 5. Чек-листы между спринтами

После каждого спринта **до запуска следующего** делаем короткий чек:

```powershell
# После S1 (A1)
cd backend
python -c "from market_data.cycle_engine import get_default_client; print(get_default_client())"

# После S2 (A2+A3)
python manage.py test advisor.tests.test_decision_scorer_cycle

# После S3 (A4+A5+A6)
python manage.py test market_data.tests
python manage.py test advisor.tests       # старые тесты должны быть зелёными

# После S4 (A7)
python manage.py test                     # вся backend-часть зелёная

# После S5 (A8+A9+A10)
cd ..\frontend
npm run typecheck
npm run dev                               # глазами проверить модалку

# После S6/S7
docker compose up -d cycle-engine        # либо scripts\dev-up.ps1
```

Каждый чек ~30 секунд. Если упал — ловим _в этом же_ агентском окне,
не открывая новый, чтобы не тратить токены на повторное чтение файлов.

---

## 6. Антишаблоны (что НЕ делаем для экономии токенов)

1. **Не передавать агенту весь PLAN08-realization.md.** Только нужные §.
   Файл — 782 строки, это ~12k токенов на ровном месте.
2. **Не объединять разные слои в один агент.** «Backend + Frontend в одном
   запуске» = большой контекст и каша. Граница: backend/ vs frontend/.
3. **Не добавлять «исследовательские» подзадачи** типа «найди, как это
   используется». Если файл/функция нужны — путь явно прописан в брифе.
4. **Не запускать агентов без очистки рабочей директории.**
   `git status` должен быть понятным в начале, иначе агент будет «чинить»
   чужие изменения.
5. **Не давать агенту право добавлять зависимости.** Все нужные пакеты
   (`requests`, `django.core.cache`) уже есть.
6. **Не позволять агенту запускать `python manage.py test` без `-k`.**
   Прогон всего тест-сьюта — лишние токены в выводе. Прогон только
   нового модуля — достаточно.

---

## 7. Финальная проверка PLAN08 DONE

После A12 запускаем единый интеграционный тест-чек:

```powershell
# Backend полный прогон
cd backend
python manage.py test
cd ..

# Frontend
cd frontend
npm run typecheck
cd ..

# Ручной e2e (15 минут)
# 1) CYCLE_ENGINE_ENABLED=false → /api/v1/btc-analysis отвечает как раньше.
# 2) CYCLE_ENGINE_ENABLED=true + cycle_engine поднят → ответ содержит
#    cycle{...} и signal_blocks.F.
# 3) Останавливаем cycle_engine → ответ снова без cycle, в логах warning.
```

Если все три кейса проходят — PLAN08 закрыт.

---

## 8. Резюме экономии

| Метрика | Без PLAN09 (один большой агент) | По PLAN09 (12 запусков) |
|---------|----------------------------------|-------------------------|
| Токенов входа на запуск | ~80–120k (весь репо в контексте) | 5–25k на запуск |
| Суммарно входа | ~120k × 1 | ~150–200k за все 12 |
| Шанс «галлюцинаций» правок в чужом коде | высокий | низкий (контекст узкий) |
| Изоляция отказа | весь чат рушится | падает только один спринт |
| Возможность параллелить | нет | A1‖A2, A4‖A5‖A6, etc. |

Главный выигрыш — **не суммарные токены**, а **изоляция и предсказуемость**:
один агент читает 1–3 файла и одну страницу плана, делает узкую правку,
закрывается. Это структурно дешевле, чем держать «всё-в-одном» окно
с 700+ строками плана.
