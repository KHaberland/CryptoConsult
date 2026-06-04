'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { Header } from '@/components/layout/Header'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { ApiKeyBanner } from '@/components/ui/ApiKeyBanner'
import { Progress } from '@/components/ui/Progress'
import { ContributeModal } from '@/components/portfolio/ContributeModal'
import { WithdrawModal } from '@/components/portfolio/WithdrawModal'
import { SwapModal } from '@/components/portfolio/SwapModal'
import { WalletsSection } from '@/components/portfolio/WalletsSection'
import { AdjustHoldingModal } from '@/components/portfolio/AdjustHoldingModal'
import { ForecastModal } from '@/components/forecast/ForecastModal'
import { BtcAnalysisModal } from '@/components/forecast/BtcAnalysisModal'
import { FiatCashFlowModal } from '@/components/portfolio/FiatCashFlowModal'
import { chatApi, versionApi } from '@/services/api'
import type {
  Wallet as WalletType,
  WalletHolding,
  FiatCashFlowKind,
} from '@/services/api'
import { formatCurrency, formatPercent, formatDate, formatUnits } from '@/lib/utils'
import {
  TrendingUp,
  TrendingDown,
  Calendar,
  Target,
  RefreshCw,
  CheckCircle,
  CalendarClock,
  PlusCircle,
  Wallet,
  BarChart3,
  AlertTriangle,
  ArrowLeftRight,
  Info,
  Pencil,
  Trash2,
  ChevronDown,
  ChevronUp,
  Banknote,
} from 'lucide-react'
import { getDcaEntriesWithCumulative } from '@/lib/dca'

const STABLECOIN_SYMBOLS = new Set(['USDT', 'USDC'])

export default function DashboardPage() {
  const router = useRouter()
  const [showContributeModal, setShowContributeModal] = useState(false)
  const [showWithdrawModal, setShowWithdrawModal] = useState(false)
  const [showSwapModal, setShowSwapModal] = useState(false)
  const [showForecastModal, setShowForecastModal] = useState(false)
  const [showBtcAnalysisModal, setShowBtcAnalysisModal] = useState(false)
  const [usdcInfoDismissed, setUsdcInfoDismissed] = useState<boolean>(true)
  const [usdEurRateInput, setUsdEurRateInput] = useState('')
  const [usdEurRateSaving, setUsdEurRateSaving] = useState(false)
  const [usdEurRateError, setUsdEurRateError] = useState<string | null>(null)
  // PLAN11 (A8): модалка фиат-операций + флаги UI для блока «Финансы по фиату».
  const [fiatModalMode, setFiatModalMode] = useState<FiatCashFlowKind | null>(null)
  const [showFiatCashFlows, setShowFiatCashFlows] = useState<boolean>(false)
  const [adjustTarget, setAdjustTarget] = useState<{
    wallet: WalletType
    holding: WalletHolding
  } | null>(null)
  const [btcAnalysisData, setBtcAnalysisData] = useState<{
    sections: Array<{ title: string; content: string }>
    forecast_6months: string
    buy_recommendation: string
  } | null>(null)
  const [btcAnalysisLoading, setBtcAnalysisLoading] = useState(false)
  const [btcAnalysisError, setBtcAnalysisError] = useState<string | null>(null)
  const [forecastData, setForecastData] = useState<{
    days: number
    positive: { description: string; probability: number }
    negative: { description: string; probability: number }
    base: { description: string; probability: number }
    portfolio_outlook?: { most_likely_scenario: string; description: string }
  } | null>(null)
  const [forecastLoading, setForecastLoading] = useState(false)
  const [forecastError, setForecastError] = useState<string | null>(null)
  const [apiKeyConfigured, setApiKeyConfigured] = useState<boolean | null>(null)
  const { initSession, isReady } = useSessionStore()
  const {
    portfolioValue,
    profile,
    hasPortfolio,
    hasProfile,
    isLoading,
    error,
    fetchPortfolioValue,
    fetchProfile,
    contribute,
    contributeByUnits,
    withdraw,
    swap,
    wallets,
    adjustHolding,
    baseCurrency,
    fiatPnl,
    fxStale,
    manualUsdEurRate,
    fiatCashFlows,
    fetchFiatCashFlows,
    createFiatCashFlow,
    deleteFiatCashFlow,
    setBaseCurrency,
  } = usePortfolioStore()
  
  // Инициализация сессии
  useEffect(() => {
    initSession()
  }, [initSession])

  useEffect(() => {
    setUsdEurRateInput(
      manualUsdEurRate == null ? '' : String(manualUsdEurRate)
    )
  }, [manualUsdEurRate])
  
  // Загрузка данных после инициализации сессии
  useEffect(() => {
    if (isReady) {
      fetchProfile()
      fetchPortfolioValue()
    }
  }, [isReady, fetchProfile, fetchPortfolioValue])

  // PLAN11 (A8): подгружаем список фиатных операций один раз после
  // готовности сессии. Дальше он живёт в сторе и обновляется на
  // create/delete (PortfolioStore.createFiatCashFlow / deleteFiatCashFlow).
  useEffect(() => {
    if (isReady && hasPortfolio) {
      fetchFiatCashFlows()
    }
  }, [isReady, hasPortfolio, fetchFiatCashFlows])

  // Проверка наличия API ключа
  useEffect(() => {
    if (!isReady) return
    versionApi.getFull()
      .then((data) => setApiKeyConfigured(data.api_key_configured))
      .catch(() => setApiKeyConfigured(null))
  }, [isReady])

  // Чтение статуса USDC-информера из localStorage (один раз показываем)
  useEffect(() => {
    if (typeof window === 'undefined') return
    const dismissed = window.localStorage.getItem('usdc_info_dismissed') === '1'
    setUsdcInfoDismissed(dismissed)
  }, [])

  const handleDismissUsdcInfo = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('usdc_info_dismissed', '1')
    }
    setUsdcInfoDismissed(true)
  }
  
  // Если нет профиля — редирект на анкету
  useEffect(() => {
    if (isReady && !isLoading && !hasProfile) {
      router.push('/questionnaire')
    }
  }, [hasProfile, isLoading, isReady, router])
  
  // Если нет портфеля — редирект на анкету
  useEffect(() => {
    if (isReady && !isLoading && hasProfile && !hasPortfolio) {
      router.push('/questionnaire')
    }
  }, [hasPortfolio, hasProfile, isLoading, isReady, router])
  
  const handleRefresh = () => {
    fetchPortfolioValue(true, baseCurrency) // force = true для ручного обновления
  }

  // PLAN11 (A8): переключение базовой валюты USD/EUR. Сначала PATCH на
  // бэке (пересчитывает FX у cash-flow'ов), затем перерисовка dashboard.
  const handleSwitchCurrency = async (cur: 'USD' | 'EUR') => {
    if (cur === baseCurrency) return
    try {
      await setBaseCurrency(cur)
    } catch {
      // ошибка уже сохранена в store.error
    }
  }

  const handleSaveUsdEurRate = async () => {
    const normalized = usdEurRateInput.trim().replace(',', '.')
    const rate = parseFloat(normalized)
    if (!Number.isFinite(rate) || rate <= 0) {
      setUsdEurRateError('Введите курс USD→EUR больше нуля')
      return
    }

    setUsdEurRateSaving(true)
    setUsdEurRateError(null)
    try {
      await setBaseCurrency('EUR', rate)
    } catch {
      // ошибка уже сохранена в store.error
    } finally {
      setUsdEurRateSaving(false)
    }
  }

  // PLAN11 (A8): удаление cash-flow с подтверждением. Используем
  // нативный confirm() — это минимально допустимое UX-решение из спека.
  const handleDeleteCashFlow = async (id: number) => {
    if (typeof window !== 'undefined') {
      const ok = window.confirm('Удалить эту фиатную операцию? Действие необратимо.')
      if (!ok) return
    }
    try {
      await deleteFiatCashFlow(id)
    } catch {
      // ошибка уже сохранена в store.error
    }
  }

  const handleForecastClick = async (days: number) => {
    setShowForecastModal(true)
    setForecastData(null)
    setForecastError(null)
    setForecastLoading(true)
    try {
      const data = await chatApi.getMarketForecast(days)
      setForecastData(data)
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : null
      setForecastError(msg || 'Не удалось получить прогноз')
    } finally {
      setForecastLoading(false)
    }
  }

  const handleBtcAnalysisClick = async () => {
    setShowBtcAnalysisModal(true)
    setBtcAnalysisData(null)
    setBtcAnalysisError(null)
    setBtcAnalysisLoading(true)
    try {
      const data = await chatApi.getBtcAnalysis()
      setBtcAnalysisData(data)
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : null
      setBtcAnalysisError(msg || 'Не удалось выполнить анализ BTC')
    } finally {
      setBtcAnalysisLoading(false)
    }
  }
  
  if (!isReady || isLoading || !portfolioValue) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="flex items-center justify-center h-[calc(100vh-64px)]">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }
  
  const progressPercent = portfolioValue.days_active / (portfolioValue.days_active + portfolioValue.days_remaining) * 100

  // Данные из бэкенда — актуальные (учитывают все взносы)
  const investedSoFar = portfolioValue.initial_value
  const totalInvestment = Number(profile?.investment_amount ?? portfolioValue.initial_value ?? 0)
  const showDcaBreakdown = (profile?.use_dca && (profile.experience_level === 'beginner' ? 3 : (profile.dca_parts ?? 4)) > 1) ?? false
  const parts = profile?.use_dca ? (profile.experience_level === 'beginner' ? 3 : (profile.dca_parts ?? 4)) : 1
  const amount = profile?.investment_amount ?? portfolioValue.initial_value ?? 0
  const startDate = portfolioValue.start_date ? new Date(portfolioValue.start_date) : new Date()
  const dcaEntries = getDcaEntriesWithCumulative(parts, Number(amount), startDate, new Date())

  // Количество выполненных входов: начальный + взносы
  const contributionsCount = portfolioValue.contributions?.length ?? 0
  const doneEntriesCount = Math.min(1 + contributionsCount, parts)

  // Рекомендуемая сумма следующего взноса (при DCA)
  const remaining = totalInvestment - investedSoFar
  const remainingParts = Math.max(0, parts - doneEntriesCount)
  const suggestedAmount = remainingParts > 0 && remaining > 0
    ? Math.round((remaining / remainingParts) * 100) / 100
    : 0

  const displayAssets = portfolioValue.assets
  const displayTotalValue = portfolioValue.total_value

  // Активы вне ТОП-10 (для импортированных портфелей).
  const allNonRecommendedAssets = portfolioValue.assets.filter(
    (a) => a.is_recommended === false,
  )

  const aggregatedAssets = showDcaBreakdown ? displayAssets : portfolioValue.assets

  // Карта агрегатных метрик по symbol — нужна, чтобы подмешать к каждому
  // wallet-holding цену/24ч/PL%, которые считает бэкенд.
  const aggregatedBySymbol = new Map(aggregatedAssets.map((a) => [a.symbol, a]))

  // Сумма units по каждому symbol — для пропорционального распределения PL
  // и initial_value между кошельками.
  const totalUnitsBySymbol = new Map<string, number>()
  for (const w of wallets) {
    for (const h of w.holdings ?? []) {
      const u = typeof h.units === 'number' ? h.units : parseFloat(String(h.units))
      if (Number.isFinite(u)) {
        totalUnitsBySymbol.set(h.symbol, (totalUnitsBySymbol.get(h.symbol) ?? 0) + u)
      }
    }
  }

  // Сортируем кошельки: дефолтный — первым, далее по имени.
  const walletsSorted = [...wallets].sort((a, b) => {
    if (a.is_default !== b.is_default) return a.is_default ? -1 : 1
    return a.name.localeCompare(b.name)
  })

  type WalletAssetRow = {
    key: string
    wallet: WalletType
    holding: WalletHolding
    symbol: string
    name: string
    units: number
    current_price: number
    current_value: number
    change_24h: number
    profit_loss: number
    profit_loss_percent: number
    percentage: number
    is_recommended?: boolean
  }

  const walletAssetRows: WalletAssetRow[] = []
  for (const w of walletsSorted) {
    for (const h of w.holdings ?? []) {
      const units =
        typeof h.units === 'number' ? h.units : parseFloat(String(h.units))
      if (!Number.isFinite(units) || units <= 0) continue
      const agg = aggregatedBySymbol.get(h.symbol)
      const valueUsd =
        h.value_usd !== null && h.value_usd !== undefined
          ? typeof h.value_usd === 'number'
            ? h.value_usd
            : parseFloat(String(h.value_usd))
          : NaN
      const totalUnits = totalUnitsBySymbol.get(h.symbol) ?? 0
      const share = totalUnits > 0 ? units / totalUnits : 0
      const current_price = agg?.current_price ?? 0
      const current_value = Number.isFinite(valueUsd)
        ? valueUsd
        : units * current_price
      const initial_value = (agg?.initial_value ?? 0) * share
      const profit_loss = current_value - initial_value
      const profit_loss_percent = agg?.profit_loss_percent ?? 0
      const percentage =
        displayTotalValue > 0 ? (current_value / displayTotalValue) * 100 : 0
      walletAssetRows.push({
        key: `${w.id}:${h.symbol}`,
        wallet: w,
        holding: h,
        symbol: h.symbol,
        name: agg?.name ?? h.symbol,
        units,
        current_price,
        current_value,
        change_24h: agg?.change_24h ?? 0,
        profit_loss,
        profit_loss_percent,
        percentage,
        is_recommended: agg?.is_recommended,
      })
    }
  }

  // Если данных по кошелькам ещё нет — показываем старую агрегированную таблицу.
  const showWalletBreakdown = walletAssetRows.length > 0
  const usdcAsset = allNonRecommendedAssets.find((a) => a.symbol === 'USDC')
  const nonRecommendedAssets = allNonRecommendedAssets.filter(
    (a) => a.symbol !== 'USDC',
  )
  const hasUsdc = !!usdcAsset
  const hasNonRecommended = nonRecommendedAssets.length > 0

  // --- PLAN11 (A8): данные для блока «Финансы по фиату» ---
  // Берём из стора актуальную базовую валюту и P&L по фиатному учёту.
  // Если cash-flow'ов ещё нет — `fiat_pnl.no_cash_in === true` и блок
  // показывает CTA «Введите сумму…», а не нули.
  const fiatCurrency = (fiatPnl?.currency ?? baseCurrency) as 'USD' | 'EUR'
  const fiatNoCashIn = fiatPnl?.no_cash_in ?? true
  const fiatProfit = fiatPnl?.profit_loss ?? 0
  const fiatProfitPercent = fiatPnl?.profit_loss_percent ?? 0
  const fiatIsProfit = fiatProfit >= 0
  const effectiveUsdEurRate = manualUsdEurRate ?? (
    fiatCurrency === 'EUR' && displayTotalValue > 0 && fiatPnl?.current_value
      ? fiatPnl.current_value / displayTotalValue
      : null
  )
  const displayTotalValueEur = effectiveUsdEurRate
    ? displayTotalValue * effectiveUsdEurRate
    : fiatCurrency === 'EUR'
      ? fiatPnl?.current_value ?? null
      : null
  const recentFiatCashFlows = fiatCashFlows.slice(0, 5)

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {apiKeyConfigured === false && (
          <ApiKeyBanner variant="dashboard" className="mb-6" />
        )}
        {error && (
          <Alert variant="error" className="mb-6">
            {error}
          </Alert>
        )}
        {hasUsdc && !usdcInfoDismissed && (
          <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
            <div className="flex items-start gap-3 text-blue-900">
              <Info className="w-5 h-5 mt-0.5 shrink-0" />
              <div className="text-sm space-y-2 flex-1">
                <p className="font-medium">
                  Стейблкоин USDC — стратегический кэш
                </p>
                <p>
                  В портфеле присутствует доля стейблкоина <strong>USDC</strong>,
                  выполняющего функцию ликвидного резерва и управления риском.
                  Текущая доля USDC (~5–15%) является допустимой и
                  соответствует практике управления рисками в условиях
                  рыночной волатильности.
                </p>
                <p>Рекомендуется сохранять USDC как стратегический кэш для:</p>
                <ul className="list-disc list-inside space-y-0.5 ml-1">
                  <li>докупки активов на коррекциях;</li>
                  <li>ребалансировки портфеля;</li>
                  <li>обеспечения ликвидности.</li>
                </ul>
                <p>
                  Конвертация USDC в инвестиционные активы должна
                  осуществляться по сигналам рынка и стратегии распределения
                  капитала.
                </p>
                <div className="pt-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleDismissUsdcInfo}
                  >
                    Ок
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
        {hasNonRecommended && (
          <div className="mb-6 rounded-lg border border-orange-200 bg-orange-50 p-4">
            <div className="flex items-start gap-3 text-orange-800">
              <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0" />
              <div className="text-sm space-y-1">
                <p className="font-medium">
                  В вашем портфеле есть активы вне ТОП-10
                </p>
                <p>
                  {nonRecommendedAssets.map((a) => a.symbol).join(', ')} — эти
                  альткойны не относятся к рекомендуемым для долгосрочного
                  инвестирования. Рассмотрите их обмен на одну из монет ТОП-10
                  согласно нашим рекомендациям.
                </p>
              </div>
            </div>
          </div>
        )}
        
        {/* PLAN11 (A8): главный блок «Финансы по фиату» — заметнее
            старого расчёта от Portfolio.initial_amount, показывается всегда
            (CTA при отсутствии cash-flow'ов). */}
        <Card className="mb-6">
          <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-2">
            <CardTitle className="flex items-center gap-2">
              <Banknote className="w-5 h-5 text-primary-600" />
              Финансы по фиату
              {fxStale && (
                <span
                  className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800"
                  title="Курс USD↔EUR временно недоступен; расчёт идёт по курсу 1.0"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  FX недоступен
                </span>
              )}
            </CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2">
                <label
                  htmlFor="usd-eur-rate"
                  className="text-xs text-gray-600 whitespace-nowrap"
                >
                  Курс USD→EUR
                </label>
                <input
                  id="usd-eur-rate"
                  type="number"
                  min="0"
                  step="0.000001"
                  value={usdEurRateInput}
                  onChange={(e) => {
                    setUsdEurRateInput(e.target.value)
                    setUsdEurRateError(null)
                  }}
                  placeholder="0.92"
                  className="w-24 rounded-md border border-gray-300 px-2 py-1 text-sm tabular-nums focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleSaveUsdEurRate}
                  disabled={usdEurRateSaving}
                >
                  {usdEurRateSaving ? '...' : 'Сохранить'}
                </Button>
              </div>
              <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5">
                {(['USD', 'EUR'] as const).map((cur) => {
                  const active = fiatCurrency === cur
                  return (
                    <button
                      key={cur}
                      type="button"
                      onClick={() => handleSwitchCurrency(cur)}
                      className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
                        active
                          ? 'bg-white text-gray-900 shadow-sm'
                          : 'text-gray-600 hover:text-gray-900'
                      }`}
                      aria-pressed={active}
                    >
                      {cur}
                    </button>
                  )
                })}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {usdEurRateError && (
              <Alert variant="warning" className="mb-4">
                {usdEurRateError}
              </Alert>
            )}
            {fiatNoCashIn ? (
              // CTA — пользователь ещё не зафиксировал ни одного депозита.
              <div className="rounded-lg border border-dashed border-primary-300 bg-primary-50/40 p-4">
                <div className="flex items-start gap-3">
                  <Info className="w-5 h-5 mt-0.5 text-primary-600 shrink-0" />
                  <div className="flex-1">
                    <p className="font-medium text-gray-900 mb-1">
                      Введите сумму, которую вы завели на свои кошельки или
                      биржу
                    </p>
                    <p className="text-sm text-gray-600 mb-3">
                      От этой суммы будет считаться прибыль/убыток всего
                      портфеля. Учёт ведётся отдельно от плана DCA и
                      кошельковых остатков.
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setFiatModalMode('deposit')}
                    >
                      <PlusCircle className="w-4 h-4 mr-1" />
                      Внести фиат
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Введено наличных</p>
                    <p className="text-2xl font-bold text-gray-900 tabular-nums">
                      {formatCurrency(fiatPnl?.cash_in_total ?? 0, fiatCurrency)}
                    </p>
                    {fiatPnl && fiatPnl.cash_out_total > 0 && (
                      <p className="text-xs text-gray-500 mt-1">
                        Выведено: {formatCurrency(fiatPnl.cash_out_total, fiatCurrency)}{' · '}
                        Чистый завод: {formatCurrency(fiatPnl.net_cash_in, fiatCurrency)}
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Текущая стоимость</p>
                    <p className="text-2xl font-bold text-gray-900 tabular-nums">
                      {formatCurrency(displayTotalValue)}
                    </p>
                    {displayTotalValueEur != null ? (
                      <p className="text-xs text-gray-500 mt-1">
                        ≈ {formatCurrency(displayTotalValueEur, 'EUR')}
                      </p>
                    ) : (
                      <p className="text-xs text-gray-500 mt-1">
                        Введите курс USD→EUR, чтобы увидеть сумму в евро
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Прибыль / Убыток</p>
                    <div className="flex items-center">
                      {fiatIsProfit ? (
                        <TrendingUp className="w-6 h-6 text-green-500 mr-2" />
                      ) : (
                        <TrendingDown className="w-6 h-6 text-red-500 mr-2" />
                      )}
                      <span
                        className={`text-2xl font-bold tabular-nums ${
                          fiatIsProfit ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {formatCurrency(fiatProfit, fiatCurrency)}
                      </span>
                    </div>
                    <p
                      className={`text-sm mt-1 ${
                        fiatIsProfit ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      ({formatPercent(fiatProfitPercent)})
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 mt-5">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setFiatModalMode('deposit')}
                  >
                    <PlusCircle className="w-4 h-4 mr-1" />
                    Внести фиат
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setFiatModalMode('withdrawal')}
                  >
                    <Wallet className="w-4 h-4 mr-1" />
                    Снять фиат
                  </Button>
                </div>
              </>
            )}

            {/* Список последних cash-flow'ов — складывается под кнопкой */}
            {fiatCashFlows.length > 0 && (
              <div className="mt-5 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowFiatCashFlows((v) => !v)}
                  className="flex items-center gap-1 text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  {showFiatCashFlows ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                  Последние операции ({fiatCashFlows.length})
                </button>
                {showFiatCashFlows && (
                  <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          <th className="px-3 py-2 text-left font-medium text-gray-700">Дата</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">Тип</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-700">Сумма</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">Заметка</th>
                          <th className="px-3 py-2 text-right font-medium text-gray-700 w-10" aria-label="Действия" />
                        </tr>
                      </thead>
                      <tbody>
                        {recentFiatCashFlows.map((flow) => {
                          const isDeposit = flow.kind === 'deposit'
                          const amountNum =
                            typeof flow.amount === 'number'
                              ? flow.amount
                              : parseFloat(String(flow.amount))
                          return (
                            <tr
                              key={flow.id}
                              className="border-b border-gray-100 last:border-0"
                            >
                              <td className="px-3 py-2 text-gray-700 whitespace-nowrap">
                                {formatDate(flow.occurred_on)}
                              </td>
                              <td className="px-3 py-2">
                                <span
                                  className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                                    isDeposit
                                      ? 'bg-green-100 text-green-700'
                                      : 'bg-orange-100 text-orange-700'
                                  }`}
                                >
                                  {isDeposit ? (
                                    <PlusCircle className="w-3 h-3" />
                                  ) : (
                                    <Wallet className="w-3 h-3" />
                                  )}
                                  {isDeposit ? 'Депозит' : 'Вывод'}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-right font-medium text-gray-900 tabular-nums whitespace-nowrap">
                                {formatCurrency(
                                  Number.isFinite(amountNum) ? amountNum : 0,
                                  flow.currency,
                                )}
                              </td>
                              <td className="px-3 py-2 text-gray-600 max-w-[240px] truncate" title={flow.note || undefined}>
                                {flow.note || <span className="text-gray-400">—</span>}
                              </td>
                              <td className="px-3 py-2 text-right">
                                <button
                                  type="button"
                                  onClick={() => handleDeleteCashFlow(flow.id)}
                                  className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-600"
                                  aria-label="Удалить операцию"
                                  title="Удалить операцию"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                    {fiatCashFlows.length > recentFiatCashFlows.length && (
                      <div className="px-3 py-2 text-xs text-gray-500 bg-gray-50 border-t border-gray-200">
                        Показаны последние {recentFiatCashFlows.length} из{' '}
                        {fiatCashFlows.length} операций.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Portfolio Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Total Value Card */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Мой портфель</CardTitle>
              <Button variant="secondary" size="sm" onClick={handleRefresh}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Обновить
              </Button>
            </CardHeader>
            <CardContent>
              {/* PLAN12: legacy-блок «Прибыль/убыток от Portfolio.initial_amount»
                  убран — он давал фантомную просадку при зеркальных
                  парах PortfolioContribution+HoldingAdjustment.
                  Главный P&L теперь — в блоке «Финансы по фиату» наверху. */}
              <div>
                <p className="text-sm text-gray-600">Текущая стоимость</p>
                <p className="text-3xl font-bold text-gray-900">
                  {formatCurrency(displayTotalValue)}
                </p>
                {(showDcaBreakdown || totalInvestment > investedSoFar) && (
                  <p className="text-sm text-gray-500 mt-1">
                    Вложено по плану DCA: {formatCurrency(investedSoFar)}
                    {totalInvestment > 0 && ` из ${formatCurrency(totalInvestment)}`}
                  </p>
                )}
              </div>

              {/* Разбивка по датам входа (DCA) */}
              {showDcaBreakdown && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <div className="flex items-center gap-2 mb-3">
                    <CalendarClock className="w-5 h-5 text-primary-600" />
                    <span className="font-semibold text-gray-900">Разбивка по входам</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-3">
                    По мере наступления даты взноса к портфелю добавляется сумма.
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          <th className="px-4 py-2 text-left font-medium text-gray-700">Вход</th>
                          <th className="px-4 py-2 text-left font-medium text-gray-700">Дата</th>
                          <th className="px-4 py-2 text-right font-medium text-gray-700">Сумма</th>
                          <th className="px-4 py-2 text-right font-medium text-gray-700">Стоимость после входа</th>
                          <th className="px-4 py-2 text-center font-medium text-gray-700 w-24">Статус</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dcaEntries.map((e) => {
                          const isDone = e.entryNumber <= doneEntriesCount
                          return (
                            <tr
                              key={e.entryNumber}
                              className={`border-b border-gray-100 last:border-0 ${
                                isDone ? 'bg-primary-50/50' : ''
                              }`}
                            >
                              <td className="px-4 py-2 font-medium text-gray-900">Вход {e.entryNumber}</td>
                              <td className="px-4 py-2 text-gray-700">{e.dateStr}</td>
                              <td className="px-4 py-2 text-right font-medium">
                                {formatCurrency(e.amountPerEntry)}
                              </td>
                              <td className="px-4 py-2 text-right font-semibold text-primary-600">
                                {formatCurrency(e.cumulativeAmount)}
                              </td>
                              <td className="px-4 py-2 text-center">
                                {isDone ? (
                                  <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                                    <CheckCircle className="w-3.5 h-3.5" />
                                    Выполнено
                                  </span>
                                ) : (
                                  <span className="text-xs text-gray-500">Запланировано</span>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    Итого будет вложено: {formatCurrency(dcaEntries[dcaEntries.length - 1]?.cumulativeAmount ?? 0)}
                  </p>
                  {remainingParts > 0 && (
                    <Button
                      variant="primary"
                      size="sm"
                      className="mt-3"
                      onClick={() => setShowContributeModal(true)}
                    >
                      <PlusCircle className="w-4 h-4 mr-1" />
                      Внести взнос
                    </Button>
                  )}
                </div>
              )}

              {/* Вывод средств */}
              <div className="mt-6 pt-6 border-t border-gray-200">
                <div className="flex items-center gap-2 mb-3">
                  <Wallet className="w-5 h-5 text-primary-600" />
                  <span className="font-semibold text-gray-900">Вывод средств</span>
                </div>
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-200">
                        <th className="px-4 py-2 text-left font-medium text-gray-700">Дата вывода</th>
                        <th className="px-4 py-2 text-right font-medium text-gray-700">Сумма вывода</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(portfolioValue.withdrawals?.length ?? 0) > 0 ? (
                        portfolioValue.withdrawals?.map((w) => (
                          <tr key={w.id} className="border-b border-gray-100 last:border-0">
                            <td className="px-4 py-2 text-gray-700">{formatDate(w.withdrawn_at)}</td>
                            <td className="px-4 py-2 text-right font-medium text-gray-900">
                              {formatCurrency(w.amount)}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={2} className="px-4 py-4 text-center text-gray-500">
                            Нет выводов
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
              
              {/* Timeline */}
              <div className="mt-6 pt-6 border-t">
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <div className="flex items-center">
                    <Calendar className="w-4 h-4 mr-1" />
                    <span>Начало: {formatDate(portfolioValue.start_date)}</span>
                  </div>
                  <div className="flex items-center">
                    <Target className="w-4 h-4 mr-1" />
                    <span>Цель: {formatDate(portfolioValue.target_date)}</span>
                  </div>
                </div>
                <Progress value={progressPercent} showLabel />
                <p className="text-sm text-gray-500 mt-1 text-center">
                  {portfolioValue.days_active} дней активен • {portfolioValue.days_remaining} дней осталось
                </p>
              </div>
            </CardContent>
          </Card>
          
          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Быстрые действия</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Link href="/chat?cmd=recommendation" className="block">
                <Button className="w-full" variant="primary">
                  Получить рекомендацию
                </Button>
              </Link>
              <Link href="/chat?cmd=status" className="block">
                <Button className="w-full" variant="secondary">
                  Статус портфеля
                </Button>
              </Link>
              <Button
                className="w-full"
                variant="secondary"
                onClick={handleBtcAnalysisClick}
              >
                <BarChart3 className="w-4 h-4 mr-1" />
                Анализ BTC
              </Button>
              {(totalInvestment > investedSoFar || !showDcaBreakdown) && (
                <Button
                  className="w-full"
                  variant="secondary"
                  onClick={() => setShowContributeModal(true)}
                >
                  <PlusCircle className="w-4 h-4 mr-1" />
                  Внести взнос
                </Button>
              )}
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => setShowSwapModal(true)}
                disabled={displayAssets.length === 0}
              >
                <ArrowLeftRight className="w-4 h-4 mr-1" />
                Обменять
              </Button>
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => setShowWithdrawModal(true)}
              >
                <Wallet className="w-4 h-4 mr-1" />
                Вывод средств
              </Button>
            </CardContent>
          </Card>
        </div>
        
        {/* Мои кошельки */}
        <WalletsSection />

        {/* Assets Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Состав портфеля</CardTitle>
            {showDcaBreakdown && (
              <span className="text-sm text-gray-500 font-normal">
                На сегодня ({formatCurrency(investedSoFar)} из {formatCurrency(totalInvestment)})
              </span>
            )}
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-gray-600 border-b">
                    <th className="pb-3 font-medium">Актив</th>
                    {showWalletBreakdown && (
                      <th className="pb-3 font-medium">Кошелёк</th>
                    )}
                    <th className="pb-3 font-medium text-right">Доля</th>
                    <th className="pb-3 font-medium text-right">Количество</th>
                    <th className="pb-3 font-medium text-right">Цена</th>
                    <th className="pb-3 font-medium text-right">24ч</th>
                    <th className="pb-3 font-medium text-right">Стоимость</th>
                    <th className="pb-3 font-medium text-right">P/L</th>
                    {showWalletBreakdown && (
                      <th className="pb-3 font-medium text-right w-10" aria-label="Действия" />
                    )}
                  </tr>
                </thead>
                <tbody>
                  {showWalletBreakdown
                    ? walletAssetRows.map((row) => (
                        <tr key={row.key} className="border-b last:border-0">
                          <td className="py-4">
                            <div className="flex items-center">
                              <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center mr-3">
                                <span className="text-xs font-bold text-primary-600">
                                  {row.symbol.slice(0, 2)}
                                </span>
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <p className="font-medium text-gray-900">{row.symbol}</p>
                                  {row.is_recommended === false &&
                                    (STABLECOIN_SYMBOLS.has(row.symbol) ? (
                                      <span
                                        className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700"
                                        title="Стейблкоин — стратегический кэш для ребалансировки и докупки на коррекциях."
                                      >
                                        <Info className="w-3 h-3" />
                                        стейблкоин
                                      </span>
                                    ) : (
                                      <span
                                        className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700"
                                        title="Не входит в ТОП-10. Рекомендуем обмен на актив из ТОП-10."
                                      >
                                        <AlertTriangle className="w-3 h-3" />
                                        не ТОП-10
                                      </span>
                                    ))}
                                </div>
                                <p className="text-sm text-gray-500">{row.name}</p>
                              </div>
                            </div>
                          </td>
                          <td className="py-4">
                            <div className="flex items-center gap-2">
                              <span className="text-gray-900">{row.wallet.name}</span>
                              {row.wallet.is_default && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary-100 text-primary-700">
                                  по умолчанию
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900 tabular-nums">
                              {row.percentage.toFixed(2)}%
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900 tabular-nums">
                              {formatUnits(row.units)}{' '}
                              <span className="text-gray-500 text-sm">{row.symbol}</span>
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900">
                              {formatCurrency(row.current_price)}
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <span className={row.change_24h >= 0 ? 'text-green-600' : 'text-red-600'}>
                              {formatPercent(row.change_24h)}
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900 font-medium tabular-nums">
                              {formatCurrency(row.current_value)}
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <div className={row.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}>
                              <span className="font-medium tabular-nums">
                                {formatCurrency(row.profit_loss)}
                              </span>
                              <span className="text-sm ml-1">
                                ({formatPercent(row.profit_loss_percent)})
                              </span>
                            </div>
                          </td>
                          <td className="py-4 text-right">
                            <button
                              type="button"
                              onClick={() =>
                                setAdjustTarget({ wallet: row.wallet, holding: row.holding })
                              }
                              className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700"
                              aria-label={`Скорректировать ${row.symbol} в кошельке ${row.wallet.name}`}
                              title="Скорректировать баланс"
                            >
                              <Pencil className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))
                    : aggregatedAssets.map((asset) => (
                        <tr key={asset.symbol} className="border-b last:border-0">
                          <td className="py-4">
                            <div className="flex items-center">
                              <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center mr-3">
                                <span className="text-xs font-bold text-primary-600">
                                  {asset.symbol.slice(0, 2)}
                                </span>
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <p className="font-medium text-gray-900">{asset.symbol}</p>
                                  {asset.is_recommended === false &&
                                    (STABLECOIN_SYMBOLS.has(asset.symbol) ? (
                                      <span
                                        className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700"
                                        title="Стейблкоин — стратегический кэш для ребалансировки и докупки на коррекциях."
                                      >
                                        <Info className="w-3 h-3" />
                                        стейблкоин
                                      </span>
                                    ) : (
                                      <span
                                        className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700"
                                        title="Не входит в ТОП-10. Рекомендуем обмен на актив из ТОП-10."
                                      >
                                        <AlertTriangle className="w-3 h-3" />
                                        не ТОП-10
                                      </span>
                                    ))}
                                </div>
                                <p className="text-sm text-gray-500">{asset.name}</p>
                              </div>
                            </div>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900">{asset.percentage}%</span>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900 tabular-nums">
                              {formatUnits(asset.units)}{' '}
                              <span className="text-gray-500 text-sm">{asset.symbol}</span>
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900">
                              {formatCurrency(asset.current_price)}
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <span className={asset.change_24h >= 0 ? 'text-green-600' : 'text-red-600'}>
                              {formatPercent(asset.change_24h)}
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-gray-900 font-medium">
                              {formatCurrency(asset.current_value)}
                            </span>
                          </td>
                          <td className="py-4 text-right">
                            <div className={asset.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}>
                              <span className="font-medium">
                                {formatCurrency(asset.profit_loss)}
                              </span>
                              <span className="text-sm ml-1">
                                ({formatPercent(asset.profit_loss_percent)})
                              </span>
                            </div>
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </main>

      <ContributeModal
        isOpen={showContributeModal}
        onClose={() => setShowContributeModal(false)}
        onConfirm={async (amt) => {
          await contribute(amt)
        }}
        onConfirmUnits={async (items, walletId) => {
          await contributeByUnits(items, walletId)
        }}
        investedSoFar={investedSoFar}
        totalPlanned={totalInvestment > 0 ? totalInvestment : undefined}
        suggestedAmount={suggestedAmount}
        wallets={wallets}
      />
      <WithdrawModal
        isOpen={showWithdrawModal}
        onClose={() => setShowWithdrawModal(false)}
        onConfirm={async (assets) => {
          await withdraw(assets)
        }}
        totalValue={displayTotalValue}
        wallets={wallets}
      />
      <SwapModal
        isOpen={showSwapModal}
        onClose={() => setShowSwapModal(false)}
        onConfirm={async (data, walletId) => {
          await swap(data, walletId)
        }}
        portfolioAssets={displayAssets.map((a) => ({
          symbol: a.symbol,
          name: a.name,
          current_price: a.current_price,
        }))}
        wallets={wallets}
      />
      <ForecastModal
        isOpen={showForecastModal}
        onClose={() => setShowForecastModal(false)}
        forecast={forecastData}
        isLoading={forecastLoading}
        error={forecastError}
      />
      <BtcAnalysisModal
        isOpen={showBtcAnalysisModal}
        onClose={() => setShowBtcAnalysisModal(false)}
        data={btcAnalysisData}
        isLoading={btcAnalysisLoading}
        error={btcAnalysisError}
      />
      <AdjustHoldingModal
        isOpen={adjustTarget !== null}
        onClose={() => setAdjustTarget(null)}
        onConfirm={adjustHolding}
        wallet={adjustTarget?.wallet ?? null}
        holding={adjustTarget?.holding ?? null}
      />
      {/* PLAN11 (A8): модалка ввода/вывода фиата. Открывается из блока
          «Финансы по фиату»; режим определяется кнопкой («Внести» / «Снять»). */}
      <FiatCashFlowModal
        isOpen={fiatModalMode !== null}
        onClose={() => setFiatModalMode(null)}
        mode={fiatModalMode ?? 'deposit'}
        defaultCurrency={fiatCurrency}
        onSubmit={async (input) => {
          return createFiatCashFlow(input)
        }}
      />
    </div>
  )
}
