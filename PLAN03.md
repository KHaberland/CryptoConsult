# PLAN03: Импорт существующего портфеля пользователя

## Цель

Добавить возможность пользователю при входе в программу указать, что у него **уже есть** криптовалютный портфель (на холодном кошельке, бирже или в любом другом виде), и ввести его текущий состав. Импортированный портфель учитывается далее наравне с портфелем, созданным «с нуля» по методике сервиса (DCA, базовая структура и т.д.).

---

## 1. Логика пользовательского сценария

```
Пользователь открывает приложение
        │
        ▼
[Onboarding / Welcome]
        │
        ▼
Вопрос: "У вас уже есть инвестиционный портфель?"
        │
        ├── НЕТ ──► Текущая методика
        │           (анкета → DCA → базовый/кастомный портфель → дашборд)
        │
        └── ДА  ──► Краткая анкета (риск-профиль)
                    │
                    ▼
                    Импорт портфеля:
                    - выбор монет из ТОП-10
                    - ввод количества единиц или суммы $
                    - дата (опц.) и средняя цена покупки (опц.)
                    │
                    ▼
                    Проверка состава:
                    - все монеты в ТОП-10 → OK
                    - есть монета вне ТОП-10
                      → показать предупреждение:
                        «Этот альткойн не относится к рекомендуемым
                        для долгосрочного инвестирования. Рекомендуем
                        обменять его на одну из монет ТОП-10
                        согласно нашим рекомендациям.»
                      → пользователь может: оставить как «прочее»
                        либо удалить позицию
                    │
                    ▼
                    AI-анализ импортированного портфеля
                    │
                    ▼
                    Дашборд (отображение реальных активов и P/L)
```

### Ключевые принципы

1. **ТОП-10 — это «белый список»** монет из `PriceService.fetch_top_coins_from_coingecko(per_page=10)` без стейблкоинов в качестве «инвестиционного актива» (стейблы остаются разрешёнными как ликвидная подушка). Список динамический — обновляется через CoinGecko API.
2. **Анкета остаётся обязательной** даже при импорте (нужен горизонт, допустимая просадка, опыт — без них AI-консультант не может дать корректные рекомендации). Но из неё убираются вопросы DCA / базовый портфель — они нерелевантны.
3. **Импортированный портфель — это `Portfolio` с флагом `is_imported=True`**. У него нет «начального плана», только реальные позиции. Сумма `initial_amount` рассчитывается из суммы введённых позиций по текущим ценам CoinGecko (либо по введённой пользователем средней цене покупки, если он её указал).
4. **Не входящие в ТОП-10 монеты** не блокируют импорт, но отображаются с предупреждением и помечаются флагом `is_recommended=False` на уровне `PortfolioAsset`.

---

## 2. Backend — изменения

### 2.1 `portfolios/models.py` — расширить модели

**`Portfolio`** — добавить флаг импорта:

```python
class Portfolio(models.Model):
    # ... существующие поля ...

    # Импортирован ли портфель пользователем (уже существующий) или создан с нуля
    is_imported = models.BooleanField(
        default=False,
        verbose_name='Импортирован пользователем'
    )
```

**`PortfolioAsset`** — добавить флаг и опц. дату покупки:

```python
class PortfolioAsset(models.Model):
    # ... существующие поля ...

    # Является ли монета рекомендуемой (входит в ТОП-10 без стейблов)
    is_recommended = models.BooleanField(
        default=True,
        verbose_name='Входит в рекомендуемый ТОП-10'
    )

    # Дата покупки (опционально, для импортированных портфелей)
    purchased_at = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата покупки'
    )
```

> Если монета вне ТОП-10 — `is_recommended=False`. Это позволит дашборду визуально маркировать такие активы и AI-консультанту учитывать их в рекомендациях.

**Миграция:**

```powershell
cd backend
.\venv\Scripts\python manage.py makemigrations portfolios
.\venv\Scripts\python manage.py migrate
```

### 2.2 `portfolios/services.py` — список ТОП-10 для импорта

Добавить в класс `PriceService` метод:

```python
def get_top10_recommended_symbols(self) -> List[str]:
    """
    ТОП-10 ликвидных криптовалют для долгосрочного инвестирования
    (CoinGecko по капитализации, исключая стейблкоины).
    Используется для валидации импортируемого портфеля.
    """
    top = self.fetch_top_coins_from_coingecko(per_page=15)
    if not top:
        return ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "DOT", "LINK"]

    result: List[str] = []
    for coin in top:
        sym = (coin.get("symbol") or "").upper()
        if sym in ("BTC", "ETH"):
            result.append(sym)
            continue
        if (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS:
            continue
        result.append(sym)
        if len(result) >= 10:
            break
    return result[:10]


def get_top10_recommended_assets(self) -> List[Dict]:
    """
    То же, что get_top10_recommended_symbols, но с расширенными данными
    (имя, цена, market_cap) для UI-выбора при импорте.
    """
    top = self.fetch_top_coins_from_coingecko(per_page=15)
    if not top:
        return []
    result: List[Dict] = []
    for coin in top:
        sym = (coin.get("symbol") or "").upper()
        if (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS:
            continue
        result.append({
            "symbol": sym,
            "name": coin.get("name") or sym,
            "current_price": coin.get("current_price") or 0,
            "market_cap": coin.get("market_cap") or 0,
        })
        if len(result) >= 10:
            break
    return result
```

### 2.3 `portfolios/views.py` — новые endpoints

Добавить два View:

```python
class Top10RecommendedView(APIView):
    """ТОП-10 ликвидных криптовалют для импорта портфеля."""
    permission_classes = (AllowAny,)

    def get(self, request):
        price_service = PriceService()
        assets = price_service.get_top10_recommended_assets()
        return Response({
            "top10": assets,
            "count": len(assets),
        })


class PortfolioImportView(APIView):
    """
    Импорт существующего портфеля пользователя.

    Body:
    {
        "name": "Мой портфель (импорт)",
        "target_years": 5,
        "assets": [
            {
                "symbol": "BTC",
                "units": 0.15,                       # количество монет
                "purchase_price": 60000,             # средняя цена покупки (опц.)
                "purchased_at": "2024-03-15"         # опц.
            },
            {
                "symbol": "ETH",
                "value_usd": 2500                    # альтернативный ввод: сумма $
            },
            {
                "symbol": "SHIB",                    # вне ТОП-10
                "units": 1000000
            }
        ]
    }

    Логика:
    - Если уже есть активный портфель — 400.
    - Проверяем все символы через PriceService.is_symbol_supported,
      неподдерживаемые символы возвращаем как warnings (не fail).
    - Получаем текущие цены CoinGecko.
    - Для каждого актива:
        * units берётся напрямую, либо value_usd / current_price.
        * initial_price = purchase_price (если указано) иначе current_price.
        * is_recommended = symbol in TOP10
    - Считаем initial_amount = sum(units * initial_price).
    - Считаем percentage по текущей рыночной стоимости (units * current_price)
      нормированное на 100%.
    - Возвращаем созданный портфель + список «нерекомендуемых» активов
      с пояснением.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        session_id = request.session_id

        if Portfolio.objects.filter(session_id=session_id, is_active=True).exists():
            return Response(
                {'detail': 'У вас уже есть активный портфель.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        name = request.data.get('name', 'Мой портфель')
        target_years = int(request.data.get('target_years', 5))
        assets_input = request.data.get('assets', [])

        if not assets_input:
            return Response(
                {'detail': 'Список активов не может быть пустым.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        price_service = PriceService()
        top10 = set(price_service.get_top10_recommended_symbols())

        # Фильтруем поддерживаемые символы (известные CoinGecko)
        symbols_supported = []
        unsupported_warnings = []
        for a in assets_input:
            sym = (a.get('symbol') or '').upper().strip()
            if not sym:
                continue
            if PriceService.is_symbol_supported(sym):
                symbols_supported.append(sym)
            else:
                unsupported_warnings.append({
                    'symbol': sym,
                    'message': f'Символ "{sym}" не поддерживается сервисом и будет пропущен.'
                })

        if not symbols_supported:
            return Response({
                'detail': 'Ни один из указанных активов не поддерживается.',
                'warnings': unsupported_warnings,
            }, status=status.HTTP_400_BAD_REQUEST)

        prices = price_service.get_prices(symbols_supported)

        # Парсим позиции в единицы, считаем initial_amount и доли
        parsed = []
        non_recommended = []
        total_initial = 0.0
        total_current = 0.0

        for a in assets_input:
            sym = (a.get('symbol') or '').upper().strip()
            if not sym or not PriceService.is_symbol_supported(sym):
                continue

            current_price = prices.get(sym, 0) or 0
            purchase_price_raw = a.get('purchase_price')
            purchase_price = float(purchase_price_raw) if purchase_price_raw else current_price

            units_raw = a.get('units')
            value_raw = a.get('value_usd')

            if units_raw not in (None, ''):
                units = float(units_raw)
            elif value_raw not in (None, '') and current_price > 0:
                units = float(value_raw) / current_price
            else:
                continue

            if units <= 0:
                continue

            initial_value = units * purchase_price
            current_value = units * current_price
            total_initial += initial_value
            total_current += current_value

            is_recommended = sym in top10
            parsed.append({
                'symbol': sym,
                'name': a.get('name') or sym,
                'units': units,
                'initial_price': purchase_price,
                'current_price': current_price,
                'current_value': current_value,
                'is_recommended': is_recommended,
                'purchased_at': a.get('purchased_at') or None,
            })

            if not is_recommended:
                non_recommended.append({
                    'symbol': sym,
                    'name': a.get('name') or sym,
                    'message': (
                        f'Альткойн {sym} не входит в наш ТОП-10 ликвидных монет '
                        f'для долгосрочного инвестирования. Рекомендуем обменять '
                        f'его на одну из монет ТОП-10 согласно нашим рекомендациям.'
                    )
                })

        if not parsed:
            return Response({
                'detail': 'Не удалось рассчитать ни одной позиции (проверьте units / value_usd).',
                'warnings': unsupported_warnings,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Создаём Portfolio
        portfolio = Portfolio.objects.create(
            session_id=session_id,
            name=name,
            initial_amount=Decimal(str(round(total_initial, 2))),
            target_years=target_years,
            is_imported=True,
        )

        # Доли — по текущей рыночной стоимости
        for p in parsed:
            pct = (p['current_value'] / total_current * 100) if total_current > 0 else 0
            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol=p['symbol'],
                name=p['name'],
                percentage=round(pct, 2),
                initial_price=Decimal(str(p['initial_price'])),
                units=Decimal(str(p['units'])),
                is_recommended=p['is_recommended'],
                purchased_at=p['purchased_at'],
            )

        return Response({
            'success': True,
            'portfolio': PortfolioSerializer(portfolio).data,
            'non_recommended': non_recommended,
            'warnings': unsupported_warnings,
            'summary': {
                'total_initial': round(total_initial, 2),
                'total_current': round(total_current, 2),
                'profit_loss': round(total_current - total_initial, 2),
                'profit_loss_percent': round(
                    (total_current - total_initial) / total_initial * 100, 2
                ) if total_initial > 0 else 0,
            }
        }, status=status.HTTP_201_CREATED)
```

### 2.4 `portfolios/urls.py` — добавить маршруты

```python
urlpatterns = [
    # ... существующие ...
    path('top10/', Top10RecommendedView.as_view(), name='portfolio_top10'),
    path('import/', PortfolioImportView.as_view(), name='portfolio_import'),
]
```

И импорт `Top10RecommendedView, PortfolioImportView` в начале файла.

### 2.5 `portfolios/serializers.py` — обновить сериализатор

В `PortfolioAssetSerializer` добавить поля `is_recommended`, `purchased_at`, `units`. В `PortfolioSerializer` добавить `is_imported`.

### 2.6 `users/models.py` — отметка о наличии портфеля у пользователя

В `InvestorProfile` добавить:

```python
class InvestorProfile(models.Model):
    # ... существующие поля ...

    # Был ли у пользователя уже существующий портфель на момент входа
    has_existing_portfolio = models.BooleanField(
        default=False,
        verbose_name='Имел портфель до входа в сервис'
    )
```

Это поле — для аналитики и подстройки промптов AI-консультанта (текст «вы недавно начали» vs «вы уже инвестируете»).

### 2.7 `advisor/services.py` — учесть импорт в системном промпте

В методе формирования системного промпта (`get_system_prompt` / эквивалент) добавить:

```python
if portfolio and getattr(portfolio, 'is_imported', False):
    prompt_lines.append(
        "ВАЖНО: пользователь импортировал уже существующий портфель. "
        "Не предлагайте полностью пересоздавать его. Анализируйте текущий "
        "состав, отмечайте позиции вне ТОП-10 и давайте рекомендации "
        "по постепенной ребалансировке."
    )

    non_rec = portfolio.assets.filter(is_recommended=False)
    if non_rec.exists():
        prompt_lines.append(
            "Активы вне ТОП-10 ликвидных: "
            + ", ".join(f"{a.symbol} ({a.percentage}%)" for a in non_rec)
            + ". Для каждого рекомендуйте обмен на актив из ТОП-10."
        )
```

---

## 3. Frontend — изменения

### 3.1 `services/api.ts` — новые методы

```typescript
export const portfolioApi = {
  // ... существующие ...

  getTop10: async () => {
    const response = await api.get('/portfolio/top10/')
    return response.data as {
      top10: Array<{
        symbol: string
        name: string
        current_price: number
        market_cap: number
      }>
      count: number
    }
  },

  import: async (data: {
    name?: string
    target_years: number
    assets: Array<{
      symbol: string
      name?: string
      units?: number
      value_usd?: number
      purchase_price?: number
      purchased_at?: string
    }>
  }) => {
    const response = await api.post('/portfolio/import/', data)
    return response.data
  },
}
```

И в `profileApi.create` принимать новое поле `has_existing_portfolio`.

### 3.2 Новый шаг onboarding: вопрос о наличии портфеля

**Файл:** `frontend/src/app/onboarding/existing-portfolio/page.tsx` (создать)

Простой экран с двумя кнопками:

```tsx
'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { useSessionStore } from '@/store/sessionStore'
import { Briefcase, Sparkles } from 'lucide-react'

export default function ExistingPortfolioQuestionPage() {
  const router = useRouter()
  const { setHasExistingPortfolio } = useSessionStore()

  const handleAnswer = (hasExisting: boolean) => {
    setHasExistingPortfolio(hasExisting)
    if (hasExisting) {
      // Сначала риск-профиль, потом импорт
      router.push('/questionnaire?mode=import')
    } else {
      router.push('/questionnaire')
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50 p-4">
      <div className="max-w-2xl mx-auto pt-8">
        <Card>
          <CardContent className="py-8 text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">
              У вас уже есть инвестиционный портфель?
            </h1>
            <p className="text-gray-600 mb-8">
              Например, на бирже или холодном кошельке.
              Если да — мы импортируем его и продолжим работать
              с реальными активами.
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              <Button
                onClick={() => handleAnswer(false)}
                variant="secondary"
                className="py-6 text-lg"
              >
                <Sparkles className="w-5 h-5 mr-2" />
                Нет, начать с нуля
              </Button>
              <Button
                onClick={() => handleAnswer(true)}
                className="py-6 text-lg"
              >
                <Briefcase className="w-5 h-5 mr-2" />
                Да, ввести существующий
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  )
}
```

### 3.3 `store/sessionStore.ts` — флаг `hasExistingPortfolio`

Добавить в стейт и persistence (localStorage `has_existing_portfolio`):

```typescript
interface SessionState {
  // ... существующие ...
  hasExistingPortfolio: boolean | null

  setHasExistingPortfolio: (value: boolean) => void
}
```

Persist в `localStorage.setItem('has_existing_portfolio', String(value))` и при `initSession` — читать обратно.

### 3.4 Адаптация `app/questionnaire/page.tsx` под режим `mode=import`

Если `searchParams.get('mode') === 'import'`:

1. **Скрыть** вопросы:
   - `use_dca`, `dca_parts` (DCA не применим — портфель уже куплен)
   - `use_default_portfolio` (портфель будет импортирован)
   - `market_analysis` (показывается на отдельной странице после импорта)

2. **При `handleSubmit`:**
   - Создать `InvestorProfile` с `has_existing_portfolio=true`.
   - **НЕ** вызывать `createPortfolio` (базовый портфель не нужен).
   - Редирект на `/portfolio/import`.

```typescript
if (mode === 'import') {
  await createProfile({ ...payload, has_existing_portfolio: true })
  router.push('/portfolio/import')
  return
}
```

### 3.5 Новая страница импорта портфеля

**Файл:** `frontend/src/app/portfolio/import/page.tsx` (создать)

UI:
- Заголовок: «Импорт существующего портфеля».
- Поле «Горизонт инвестирования» (берётся из профиля по умолчанию).
- Список позиций: для каждой — selectбокс с символом монеты + опции:
  - **Из ТОП-10** (получаем через `portfolioApi.getTop10()`) — нормальный синий бейдж.
  - **Прочее** — выпадающий список всех `PriceService` символов, помечен оранжевым «не рекомендуется для долгосрочного холда».
- Поле ввода: либо «Количество монет» либо «Сумма в $» (toggle).
- Опц. поле: средняя цена покупки `$`.
- Опц. поле: дата покупки.
- Кнопка `+ Добавить позицию`.
- Снизу: «Итоговая стоимость портфеля по текущим ценам: $XX,XXX».
- Если в списке есть монета вне ТОП-10 — баннер-предупреждение:
  > ⚠️ Альткойн `{symbol}` не входит в ТОП-10 ликвидных криптомонет для долгосрочного инвестирования. Рекомендуем обменять его на одну из монет нашего ТОП-10 согласно рекомендациям.
- Кнопка «Импортировать портфель».

После успешного импорта:
- Показать модалку с AI-анализом (как в `portfolio/create`), но дополнительно — для каждой не-рекомендуемой монеты:
  > 🔄 Рекомендуемая замена: предложение продать `{symbol}` и купить `{recommended_symbol}` на ту же сумму.
- По кнопке «Перейти в дашборд» — редирект на `/dashboard`.

Псевдо-структура компонента:

```tsx
'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { portfolioApi, pricesApi } from '@/services/api'
// ... UI imports

interface ImportAsset {
  symbol: string
  inputMode: 'units' | 'value'   // что вводит пользователь
  units: number
  valueUsd: number
  purchasePrice: number | ''
  purchasedAt: string
}

export default function ImportPortfolioPage() {
  const router = useRouter()
  const { profile, fetchProfile } = usePortfolioStore()
  const [top10, setTop10] = useState<Array<{ symbol: string; name: string; current_price: number }>>([])
  const [allSupported, setAllSupported] = useState<string[]>([])
  const [assets, setAssets] = useState<ImportAsset[]>([
    { symbol: 'BTC', inputMode: 'units', units: 0, valueUsd: 0, purchasePrice: '', purchasedAt: '' }
  ])
  const [targetYears, setTargetYears] = useState(5)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    portfolioApi.getTop10().then(d => setTop10(d.top10))
    pricesApi.getSupported().then(d => setAllSupported(d.symbols))
    fetchProfile()
  }, [])

  useEffect(() => {
    if (profile?.investment_horizon) setTargetYears(profile.investment_horizon)
  }, [profile])

  const top10Symbols = useMemo(() => new Set(top10.map(c => c.symbol)), [top10])

  const nonRecommended = assets.filter(a => a.symbol && !top10Symbols.has(a.symbol))

  const handleSubmit = async () => {
    setIsSubmitting(true)
    setError(null)
    try {
      const payload = {
        name: 'Мой портфель (импорт)',
        target_years: targetYears,
        assets: assets
          .filter(a => a.symbol && (a.units > 0 || a.valueUsd > 0))
          .map(a => ({
            symbol: a.symbol,
            ...(a.inputMode === 'units' ? { units: a.units } : { value_usd: a.valueUsd }),
            ...(a.purchasePrice ? { purchase_price: Number(a.purchasePrice) } : {}),
            ...(a.purchasedAt ? { purchased_at: a.purchasedAt } : {}),
          }))
      }
      const data = await portfolioApi.import(payload)
      setResult(data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка импорта портфеля')
    } finally {
      setIsSubmitting(false)
    }
  }

  // ... UI рендеринг (см. описание выше)
}
```

### 3.6 Маркировка не-рекомендуемых активов в дашборде

**Файл:** `frontend/src/app/dashboard/page.tsx`

В рендере списка активов: если у актива `is_recommended === false` — показать оранжевый бейдж «не входит в ТОП-10» с тултипом-рекомендацией.

При наличии любых не-рекомендуемых активов — показать баннер сверху дашборда:
> ⚠️ В вашем портфеле есть активы вне ТОП-10. Рассмотрите их обмен на рекомендуемые.

### 3.7 Изменение цепочки навигации

В `app/onboarding/welcome/page.tsx` (или последний экран вводного onboarding) — после кнопки «Дальше» вместо `router.push('/questionnaire')` использовать `router.push('/onboarding/existing-portfolio')`.

В `app/page.tsx` — при отсутствии профиля редирект на `/onboarding/welcome` (как сейчас) → onboarding → новый экран `existing-portfolio` → анкета или импорт.

---

## 4. Список файлов

### Backend (создать / изменить)

| Файл | Действие |
|------|----------|
| `backend/portfolios/models.py` | Изменить (добавить `is_imported`, `is_recommended`, `purchased_at`) |
| `backend/portfolios/migrations/0005_*.py` | Создать (через `makemigrations`) |
| `backend/portfolios/services.py` | Изменить (добавить `get_top10_recommended_symbols`, `get_top10_recommended_assets`) |
| `backend/portfolios/views.py` | Изменить (добавить `Top10RecommendedView`, `PortfolioImportView`) |
| `backend/portfolios/urls.py` | Изменить (добавить маршруты `/top10/`, `/import/`) |
| `backend/portfolios/serializers.py` | Изменить (новые поля в сериализаторах) |
| `backend/users/models.py` | Изменить (`has_existing_portfolio`) |
| `backend/users/migrations/0003_*.py` | Создать |
| `backend/users/serializers.py` | Изменить (новое поле) |
| `backend/advisor/services.py` | Изменить (учёт импорта в системном промпте) |
| `backend/portfolios/tests/test_import.py` | Создать (см. п. 5) |

### Frontend (создать / изменить)

| Файл | Действие |
|------|----------|
| `frontend/src/services/api.ts` | Изменить (новые методы `getTop10`, `import`) |
| `frontend/src/store/sessionStore.ts` | Изменить (флаг `hasExistingPortfolio`) |
| `frontend/src/store/portfolioStore.ts` | Изменить (метод `importPortfolio`) |
| `frontend/src/app/onboarding/existing-portfolio/page.tsx` | Создать |
| `frontend/src/app/onboarding/welcome/page.tsx` | Изменить (редирект на новый экран) |
| `frontend/src/app/questionnaire/page.tsx` | Изменить (режим `mode=import`) |
| `frontend/src/app/portfolio/import/page.tsx` | Создать |
| `frontend/src/app/dashboard/page.tsx` | Изменить (маркер «не ТОП-10» + баннер) |
| `frontend/src/components/ui/CoinSelector.tsx` | Создать (выбор монеты с разделением ТОП-10 / прочее) |

---

## 5. Тесты

### 5.1 Backend (`portfolios/tests/test_import.py`)

```python
import pytest
from rest_framework.test import APIClient
from portfolios.models import Portfolio, PortfolioAsset


@pytest.mark.django_db
class TestPortfolioImport:
    def setup_method(self):
        self.client = APIClient()
        self.session_id = 'test-import-session-001'
        self.client.credentials(HTTP_X_SESSION_ID=self.session_id)

    def test_import_only_top10(self):
        """Импорт портфеля из монет ТОП-10."""
        response = self.client.post('/api/portfolio/import/', {
            'name': 'Test',
            'target_years': 5,
            'assets': [
                {'symbol': 'BTC', 'units': 0.1, 'purchase_price': 60000},
                {'symbol': 'ETH', 'units': 1.0, 'purchase_price': 2000},
            ]
        }, format='json')
        assert response.status_code == 201
        data = response.json()
        assert data['portfolio']['is_imported'] is True
        assert len(data['non_recommended']) == 0
        assert Portfolio.objects.filter(session_id=self.session_id).count() == 1

    def test_import_with_non_top10(self):
        """Импорт с альткойном вне ТОП-10 — выдаём предупреждение."""
        response = self.client.post('/api/portfolio/import/', {
            'target_years': 3,
            'assets': [
                {'symbol': 'BTC', 'units': 0.05},
                {'symbol': 'SHIB', 'units': 1_000_000},
            ]
        }, format='json')
        assert response.status_code == 201
        data = response.json()
        assert len(data['non_recommended']) == 1
        assert data['non_recommended'][0]['symbol'] == 'SHIB'
        assert 'обменять' in data['non_recommended'][0]['message'].lower()

    def test_import_unsupported_symbol(self):
        """Полностью неизвестный символ → warning."""
        response = self.client.post('/api/portfolio/import/', {
            'target_years': 5,
            'assets': [
                {'symbol': 'BTC', 'units': 0.1},
                {'symbol': 'XYZ123', 'units': 100},
            ]
        }, format='json')
        assert response.status_code == 201
        data = response.json()
        assert any(w['symbol'] == 'XYZ123' for w in data['warnings'])

    def test_import_value_usd_input(self):
        """Ввод суммы в долларах вместо units."""
        response = self.client.post('/api/portfolio/import/', {
            'target_years': 5,
            'assets': [
                {'symbol': 'BTC', 'value_usd': 5000},
            ]
        }, format='json')
        assert response.status_code == 201
        asset = PortfolioAsset.objects.first()
        assert float(asset.units) > 0

    def test_cannot_import_when_active_exists(self):
        """Нельзя импортировать, если уже есть активный портфель."""
        Portfolio.objects.create(
            session_id=self.session_id,
            initial_amount=1000,
            target_years=5,
            is_active=True,
        )
        response = self.client.post('/api/portfolio/import/', {
            'target_years': 5,
            'assets': [{'symbol': 'BTC', 'units': 0.1}],
        }, format='json')
        assert response.status_code == 400

    def test_top10_endpoint(self):
        response = self.client.get('/api/portfolio/top10/')
        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 10
        symbols = [a['symbol'] for a in data['top10']]
        assert 'BTC' in symbols and 'ETH' in symbols
        # Стейблкоинов в ТОП-10 быть не должно
        assert 'USDT' not in symbols and 'USDC' not in symbols
```

### 5.2 Frontend — ручное тестирование

Сценарии:

1. **Новый пользователь — нет портфеля.** Проходит онбординг → отвечает «Нет» → стандартная анкета → базовый портфель → дашборд. Поведение не должно измениться по сравнению с текущим.
2. **Новый пользователь — есть портфель из ТОП-10.** Отвечает «Да» → краткая анкета (без вопросов про DCA) → импорт BTC + ETH + SOL → AI-анализ → дашборд показывает реальные активы и P/L.
3. **Импорт с альткойном вне ТОП-10.** Импортирует BTC + SHIB → видит баннер-предупреждение «не рекомендуем для долгосрочного» → подтверждает → в дашборде SHIB помечен оранжевым бейджем.
4. **Импорт суммой в $.** Указывает «1000 USD в BTC» → backend пересчитывает в units по текущей цене → корректно отображается в дашборде.
5. **Защита:** уже есть импортированный портфель → попытка повторного импорта → 400.

---

## 6. Порядок выполнения

1. **Backend модели + миграции** (~20 мин)
2. **Backend `services.py`: ТОП-10** (~10 мин)
3. **Backend views + urls + serializers** (~30 мин)
4. **Backend тесты импорта** (~25 мин)
5. **Frontend: api.ts + sessionStore** (~10 мин)
6. **Frontend: страница вопроса `existing-portfolio`** (~15 мин)
7. **Frontend: адаптация анкеты под `mode=import`** (~20 мин)
8. **Frontend: страница импорта `/portfolio/import`** (~60 мин)
9. **Frontend: маркер не-рекомендуемых на дашборде** (~15 мин)
10. **Backend: учёт импорта в промпте AI-консультанта** (~10 мин)
11. **Ручное тестирование сценариев** (~30 мин)

**Итого:** ~4 часа

---

## 7. Открытые вопросы / возможные расширения

1. **Стейблкоины при импорте.** USDT/USDC не входят в ТОП-10 «инвестиционных», но логично считать их «нейтральной» позицией, а не «не рекомендованной». Пометить отдельным флагом `is_stablecoin=True` без оранжевого баннера.
2. **Автоматическое предложение ребалансировки.** После импорта запустить расчёт «как должен выглядеть ваш портфель по нашей методике с учётом анкеты» и показать diff (продать X, купить Y). Можно реализовать в следующем PLAN04.
3. **История взносов / выводов до импорта.** В рамках MVP не учитываем — пользователь вводит только текущий снимок. Для будущих версий можно расширить на ввод истории сделок.
4. **Множественные источники.** Если пользователь хранит часть на бирже, часть на холодном кошельке — пока импортируется как единый портфель. В будущем можно добавить разделение по «местам хранения».
5. **Кэш ТОП-10.** Метод `get_top10_recommended_symbols` уже использует кэш CoinGecko (TTL 5 минут). Дополнительно кэшировать на уровне Django не нужно.
