'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Alert } from '@/components/ui/Alert'
import { portfolioApi, pricesApi } from '@/services/api'
import { formatCurrency } from '@/lib/utils'
import {
  TrendingUp,
  Plus,
  Trash2,
  Loader2,
  AlertTriangle,
  Sparkles,
  ArrowRight,
  X,
  Briefcase,
  ShieldCheck,
  RefreshCw,
  Info,
} from 'lucide-react'

const STABLECOIN_SYMBOLS = new Set(['USDT', 'USDC'])

interface ImportAsset {
  symbol: string
  inputMode: 'units' | 'value'
  units: string
  valueUsd: string
  purchasePrice: string
  purchasedAt: string
}

interface Top10Coin {
  symbol: string
  name: string
  current_price: number
  market_cap: number
}

interface ImportResult {
  success: boolean
  portfolio: {
    id: number
    name: string
    initial_amount: number | string
    target_years: number
    is_imported: boolean
    assets: Array<{
      symbol: string
      name: string
      percentage: number | string
      is_recommended: boolean
    }>
  }
  non_recommended: Array<{ symbol: string; name: string; message: string }>
  warnings: Array<{ symbol: string; message: string }>
  summary: {
    total_initial: number
    total_current: number
    profit_loss: number
    profit_loss_percent: number
  }
}

const emptyAsset = (symbol = ''): ImportAsset => ({
  symbol,
  inputMode: 'units',
  units: '',
  valueUsd: '',
  purchasePrice: '',
  purchasedAt: '',
})

export default function ImportPortfolioPage() {
  const router = useRouter()
  const { initSession, isReady, userName, hasCompletedOnboarding } = useSessionStore()
  const { profile, fetchProfile, hasProfile } = usePortfolioStore()

  const [top10, setTop10] = useState<Top10Coin[]>([])
  const [allSupported, setAllSupported] = useState<string[]>([])
  const [loadingMeta, setLoadingMeta] = useState(true)
  const [assets, setAssets] = useState<ImportAsset[]>([emptyAsset('BTC')])
  const [targetYears, setTargetYears] = useState<number>(5)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)

  useEffect(() => {
    initSession()
  }, [initSession])

  // Если пользователь не залогинен / не прошёл онбординг — отправляем туда.
  useEffect(() => {
    if (!isReady) return
    if (!userName) {
      router.push('/login')
      return
    }
    if (!hasCompletedOnboarding) {
      router.push('/onboarding/welcome')
    }
  }, [isReady, userName, hasCompletedOnboarding, router])

  useEffect(() => {
    if (!isReady) return
    fetchProfile()
  }, [isReady, fetchProfile])

  // Без профиля импорт невозможен — отправляем на анкету.
  useEffect(() => {
    if (isReady && hasProfile === false) {
      router.push('/questionnaire?mode=import')
    }
  }, [isReady, hasProfile, router])

  useEffect(() => {
    if (profile?.investment_horizon) {
      setTargetYears(profile.investment_horizon)
    }
  }, [profile])

  useEffect(() => {
    let cancelled = false
    setLoadingMeta(true)
    Promise.all([
      portfolioApi.getTop10().catch(() => ({ top10: [] as Top10Coin[], count: 0 })),
      pricesApi
        .getSupported()
        .catch(() => ({ symbols: [] as string[] })),
    ])
      .then(([topData, supportedData]) => {
        if (cancelled) return
        const topList = (topData?.top10 ?? []) as Top10Coin[]
        setTop10(topList)
        const symbols = (supportedData?.symbols ?? []) as string[]
        setAllSupported(symbols)
      })
      .finally(() => {
        if (!cancelled) setLoadingMeta(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const top10Symbols = useMemo(
    () => new Set(top10.map((c) => c.symbol)),
    [top10],
  )

  const top10Map = useMemo(() => {
    const m = new Map<string, Top10Coin>()
    top10.forEach((c) => m.set(c.symbol, c))
    return m
  }, [top10])

  // Категоризация выпадающего списка: ТОП-10 сверху, прочие — снизу.
  const otherSymbols = useMemo(() => {
    return allSupported
      .filter((s) => !top10Symbols.has(s))
      .sort((a, b) => a.localeCompare(b))
  }, [allSupported, top10Symbols])

  // Текущая стоимость портфеля по введённым значениям (по текущим ценам ТОП-10).
  const estimatedTotalUsd = useMemo(() => {
    let total = 0
    for (const a of assets) {
      if (!a.symbol) continue
      const coin = top10Map.get(a.symbol)
      const currentPrice = coin?.current_price ?? 0
      if (a.inputMode === 'value') {
        const v = parseFloat(a.valueUsd)
        if (!isNaN(v) && v > 0) total += v
      } else if (a.inputMode === 'units' && currentPrice > 0) {
        const u = parseFloat(a.units)
        if (!isNaN(u) && u > 0) total += u * currentPrice
      }
    }
    return total
  }, [assets, top10Map])

  const nonRecommendedAssets = assets.filter(
    (a) => a.symbol && !top10Symbols.has(a.symbol) && allSupported.includes(a.symbol),
  )

  const updateAsset = <K extends keyof ImportAsset>(
    index: number,
    field: K,
    value: ImportAsset[K],
  ) => {
    setAssets((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], [field]: value }
      return next
    })
  }

  const addAsset = () => {
    const used = new Set(assets.map((a) => a.symbol).filter(Boolean))
    const nextSym =
      top10.find((c) => !used.has(c.symbol))?.symbol ??
      otherSymbols.find((s) => !used.has(s)) ??
      ''
    setAssets((prev) => [...prev, emptyAsset(nextSym)])
  }

  const removeAsset = (index: number) => {
    setAssets((prev) => prev.filter((_, i) => i !== index))
  }

  const isValid = useMemo(() => {
    if (assets.length === 0) return false
    return assets.some((a) => {
      if (!a.symbol) return false
      if (a.inputMode === 'units') {
        const u = parseFloat(a.units)
        return !isNaN(u) && u > 0
      }
      const v = parseFloat(a.valueUsd)
      return !isNaN(v) && v > 0
    })
  }, [assets])

  const handleSubmit = async () => {
    if (!isValid || isSubmitting) return
    setIsSubmitting(true)
    setError(null)
    try {
      const payload = {
        name: 'Мой портфель (импорт)',
        target_years: targetYears,
        assets: assets
          .filter((a) => {
            if (!a.symbol) return false
            if (a.inputMode === 'units') {
              const u = parseFloat(a.units)
              return !isNaN(u) && u > 0
            }
            const v = parseFloat(a.valueUsd)
            return !isNaN(v) && v > 0
          })
          .map((a) => {
            const base: {
              symbol: string
              units?: number
              value_usd?: number
              purchase_price?: number
              purchased_at?: string
            } = { symbol: a.symbol }
            if (a.inputMode === 'units') {
              base.units = parseFloat(a.units)
            } else {
              base.value_usd = parseFloat(a.valueUsd)
            }
            const pp = parseFloat(a.purchasePrice)
            if (!isNaN(pp) && pp > 0) base.purchase_price = pp
            if (a.purchasedAt) base.purchased_at = a.purchasedAt
            return base
          }),
      }
      const data = (await portfolioApi.import(payload)) as ImportResult
      setResult(data)
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null
      setError(msg || 'Не удалось импортировать портфель')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleGoToDashboard = () => {
    router.push('/dashboard')
  }

  // Подсказка для замены: первая монета из ТОП-10 — рекомендация по умолчанию.
  const replacementSymbol = top10[0]?.symbol ?? 'BTC'

  if (!isReady || !userName || !hasCompletedOnboarding) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-white">
        <Loader2 className="w-12 h-12 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white p-4">
      {/* Модалка с результатом импорта */}
      {result && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
              <div className="flex items-center">
                <Sparkles className="w-6 h-6 text-yellow-500 mr-2" />
                <h2 className="text-xl font-bold text-gray-900">Портфель импортирован</h2>
              </div>
              <button
                onClick={handleGoToDashboard}
                className="text-gray-400 hover:text-gray-600"
                aria-label="Закрыть"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-green-800 font-medium">
                  Импортировано позиций: {result.portfolio.assets.length}
                </p>
                <p className="text-green-700 text-sm mt-1">
                  Стоимость по ценам покупки: {formatCurrency(result.summary.total_initial)}
                  {' '}→ Текущая стоимость: {formatCurrency(result.summary.total_current)}
                </p>
                <p
                  className={`text-sm mt-1 font-medium ${
                    result.summary.profit_loss >= 0 ? 'text-green-800' : 'text-red-700'
                  }`}
                >
                  P/L: {formatCurrency(result.summary.profit_loss)} (
                  {result.summary.profit_loss_percent.toFixed(2)}%)
                </p>
              </div>

              {/* Структура импортированного портфеля */}
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Состав портфеля</h3>
                <div className="space-y-2">
                  {result.portfolio.assets.map((a) => (
                    <div
                      key={a.symbol}
                      className="flex items-center justify-between border rounded-lg p-3"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900">{a.symbol}</span>
                        <span className="text-gray-500 text-sm">{a.name}</span>
                        {a.is_recommended ? (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                            ТОП-10
                          </span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700">
                            не рекомендуется
                          </span>
                        )}
                      </div>
                      <span className="font-semibold text-primary-600">
                        {Number(a.percentage).toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* USDC — стратегический кэш, не помечаем как «вне ТОП-10». */}
              {result.non_recommended.some((nr) => nr.symbol === 'USDC') && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2 text-blue-900 font-medium">
                    <Info className="w-5 h-5" />
                    Стейблкоин USDC — стратегический кэш
                  </div>
                  <div className="text-sm text-blue-900 space-y-2">
                    <p>
                      В портфеле присутствует доля стейблкоина{' '}
                      <strong>USDC</strong>, выполняющего функцию ликвидного
                      резерва и управления риском. Текущая доля USDC (~5–15%)
                      является допустимой и соответствует практике управления
                      рисками в условиях рыночной волатильности.
                    </p>
                    <p>Рекомендуется сохранять USDC как стратегический кэш для:</p>
                    <ul className="list-disc list-inside space-y-0.5 ml-1">
                      <li>докупки активов на коррекциях;</li>
                      <li>ребалансировки портфеля;</li>
                      <li>обеспечения ликвидности.</li>
                    </ul>
                    <p>
                      Конвертация USDC в инвестиционные активы должна
                      осуществляться по сигналам рынка и стратегии
                      распределения капитала.
                    </p>
                  </div>
                </div>
              )}

              {/* Предупреждения о монетах вне ТОП-10 (без стейблкоина USDC). */}
              {result.non_recommended.filter((nr) => nr.symbol !== 'USDC').length > 0 && (
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 space-y-2">
                  <div className="flex items-center gap-2 text-orange-800 font-medium">
                    <AlertTriangle className="w-5 h-5" />
                    Активы вне ТОП-10
                  </div>
                  {result.non_recommended
                    .filter((nr) => nr.symbol !== 'USDC')
                    .map((nr) => (
                      <div key={nr.symbol} className="text-sm text-orange-800">
                        <p>{nr.message}</p>
                        <p className="mt-1 flex items-center gap-1 text-orange-900">
                          <RefreshCw className="w-4 h-4" />
                          Рекомендуемая замена: продать {nr.symbol} и купить{' '}
                          <strong>{replacementSymbol}</strong> на ту же сумму.
                        </p>
                      </div>
                    ))}
                </div>
              )}

              {/* Игнорируемые символы */}
              {result.warnings.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
                  <p className="font-medium mb-1">Часть символов пропущена:</p>
                  <ul className="list-disc list-inside space-y-1">
                    {result.warnings.map((w) => (
                      <li key={w.symbol}>{w.message}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="sticky bottom-0 bg-white border-t px-6 py-4">
              <Button onClick={handleGoToDashboard} className="w-full">
                Перейти в дашборд
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto pt-8 pb-24">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-2">
            <TrendingUp className="w-10 h-10 text-primary-600 mr-2" />
            <h1 className="text-2xl font-bold text-primary-600">Крипто-Консультант</h1>
          </div>
          <p className="text-gray-600">Импорт существующего портфеля</p>
        </div>

        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}

        {/* Описание */}
        <Card className="mb-6 border-blue-200 bg-blue-50">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <Briefcase className="w-5 h-5 text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-800 space-y-1">
                <p className="font-medium">
                  Введите состав вашего реального портфеля.
                </p>
                <p>
                  Используйте монеты из ТОП-10 ликвидных криптовалют. Если у вас
                  есть альткойн вне этого списка, вы сможете его указать, но он
                  будет помечен как «не рекомендуется для долгосрочного инвестирования».
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Горизонт инвестирования */}
        <Card className="mb-6">
          <CardContent>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              Горизонт инвестирования
            </h2>
            <p className="text-sm text-gray-600 mb-3">
              На сколько лет вы планируете удерживать портфель?
            </p>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                min={1}
                max={7}
                value={targetYears}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (!isNaN(v)) setTargetYears(Math.min(Math.max(v, 1), 7))
                }}
                className="w-24"
              />
              <span className="text-gray-700">лет</span>
            </div>
          </CardContent>
        </Card>

        {/* Активы */}
        <Card className="mb-6">
          <CardContent>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Состав портфеля
            </h2>

            {loadingMeta ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-primary-600" />
              </div>
            ) : (
              <div className="space-y-4">
                {assets.map((asset, index) => {
                  const isRecommended = asset.symbol
                    ? top10Symbols.has(asset.symbol)
                    : true
                  const coin = top10Map.get(asset.symbol)
                  return (
                    <div
                      key={index}
                      className={`rounded-lg border p-4 space-y-3 ${
                        asset.symbol &&
                        !isRecommended &&
                        !STABLECOIN_SYMBOLS.has(asset.symbol)
                          ? 'border-orange-200 bg-orange-50/40'
                          : 'border-gray-200'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <select
                          value={asset.symbol}
                          onChange={(e) =>
                            updateAsset(index, 'symbol', e.target.value)
                          }
                          className="flex-1 p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                        >
                          <option value="">— выберите монету —</option>
                          <optgroup label="ТОП-10 рекомендуемых">
                            {top10.map((c) => (
                              <option key={c.symbol} value={c.symbol}>
                                {c.symbol} — {c.name}
                              </option>
                            ))}
                          </optgroup>
                          {otherSymbols.length > 0 && (
                            <optgroup label="Прочие (не рекомендуются для долгосрочного холда)">
                              {otherSymbols.map((s) => (
                                <option key={s} value={s}>
                                  {s}
                                </option>
                              ))}
                            </optgroup>
                          )}
                        </select>

                        {asset.symbol &&
                          (isRecommended ? (
                            <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700">
                              <ShieldCheck className="w-3.5 h-3.5" />
                              ТОП-10
                            </span>
                          ) : STABLECOIN_SYMBOLS.has(asset.symbol) ? (
                            <span
                              className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700"
                              title="Стейблкоин — стратегический кэш для ребалансировки и докупки на коррекциях."
                            >
                              <Info className="w-3.5 h-3.5" />
                              стейблкоин
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-orange-100 text-orange-700">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              не рекомендуется
                            </span>
                          ))}

                        <button
                          onClick={() => removeAsset(index)}
                          className="p-2 text-red-500 hover:bg-red-50 rounded-lg disabled:opacity-40"
                          disabled={assets.length <= 1}
                          aria-label="Удалить позицию"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>

                      {/* Способ ввода */}
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => updateAsset(index, 'inputMode', 'units')}
                          className={`flex-1 py-1.5 text-sm rounded-md border ${
                            asset.inputMode === 'units'
                              ? 'border-primary-500 bg-primary-50 text-primary-700'
                              : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          Количество монет
                        </button>
                        <button
                          type="button"
                          onClick={() => updateAsset(index, 'inputMode', 'value')}
                          className={`flex-1 py-1.5 text-sm rounded-md border ${
                            asset.inputMode === 'value'
                              ? 'border-primary-500 bg-primary-50 text-primary-700'
                              : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          Сумма в $
                        </button>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {asset.inputMode === 'units' ? (
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">
                              Количество монет
                            </label>
                            <Input
                              type="number"
                              step="any"
                              min={0}
                              value={asset.units}
                              onChange={(e) =>
                                updateAsset(index, 'units', e.target.value)
                              }
                              placeholder="0.15"
                            />
                          </div>
                        ) : (
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">
                              Сумма, $
                            </label>
                            <Input
                              type="number"
                              step="any"
                              min={0}
                              value={asset.valueUsd}
                              onChange={(e) =>
                                updateAsset(index, 'valueUsd', e.target.value)
                              }
                              placeholder="2500"
                            />
                          </div>
                        )}

                        <div>
                          <label className="block text-xs text-gray-500 mb-1">
                            Средняя цена покупки, $ (опц.)
                          </label>
                          <Input
                            type="number"
                            step="any"
                            min={0}
                            value={asset.purchasePrice}
                            onChange={(e) =>
                              updateAsset(index, 'purchasePrice', e.target.value)
                            }
                            placeholder={
                              coin?.current_price
                                ? coin.current_price.toString()
                                : '60000'
                            }
                          />
                        </div>

                        <div className="sm:col-span-2">
                          <label className="block text-xs text-gray-500 mb-1">
                            Дата покупки (опц.)
                          </label>
                          <Input
                            type="date"
                            value={asset.purchasedAt}
                            onChange={(e) =>
                              updateAsset(index, 'purchasedAt', e.target.value)
                            }
                          />
                        </div>
                      </div>

                      {coin && asset.inputMode === 'units' && (
                        <p className="text-xs text-gray-500">
                          Текущая цена {asset.symbol}:{' '}
                          {formatCurrency(coin.current_price)}
                        </p>
                      )}
                    </div>
                  )
                })}

                <button
                  onClick={addAsset}
                  className="flex items-center text-primary-600 hover:text-primary-700"
                >
                  <Plus className="w-5 h-5 mr-1" />
                  Добавить позицию
                </button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* USDC — стратегический кэш, не помечаем как «вне ТОП-10». */}
        {nonRecommendedAssets.some((a) => a.symbol === 'USDC') && (
          <Card className="mb-6 border-blue-200 bg-blue-50">
            <CardContent className="py-4">
              <div className="flex items-start gap-3 text-sm text-blue-900">
                <Info className="w-5 h-5 mt-0.5" />
                <div className="space-y-2">
                  <p className="font-medium">
                    Стейблкоин USDC — стратегический кэш
                  </p>
                  <p>
                    В портфеле присутствует доля стейблкоина{' '}
                    <strong>USDC</strong>, выполняющего функцию ликвидного
                    резерва и управления риском. Текущая доля USDC (~5–15%)
                    является допустимой и соответствует практике управления
                    рисками в условиях рыночной волатильности.
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
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Предупреждения о монетах вне ТОП-10 (без стейблкоина USDC). */}
        {nonRecommendedAssets.filter((a) => a.symbol !== 'USDC').length > 0 && (
          <Card className="mb-6 border-orange-200 bg-orange-50">
            <CardContent className="py-4">
              <div className="flex items-start gap-3 text-sm text-orange-800">
                <AlertTriangle className="w-5 h-5 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium">Внимание!</p>
                  {nonRecommendedAssets
                    .filter((a) => a.symbol !== 'USDC')
                    .map((a) => (
                      <p key={a.symbol}>
                        Альткойн <strong>{a.symbol}</strong> не входит в ТОП-10
                        ликвидных криптомонет для долгосрочного инвестирования.
                        Рекомендуем обменять его на одну из монет нашего ТОП-10.
                      </p>
                    ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Итоговая стоимость */}
        <Card className="mb-6">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-700">
                Итоговая стоимость портфеля по текущим ценам:
              </span>
              <span className="text-xl font-bold text-primary-600">
                {formatCurrency(estimatedTotalUsd)}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Точная сумма будет рассчитана на сервере по актуальным ценам CoinGecko.
            </p>
          </CardContent>
        </Card>

        <Button
          onClick={handleSubmit}
          className="w-full py-4"
          disabled={!isValid || isSubmitting || loadingMeta}
          isLoading={isSubmitting}
        >
          Импортировать портфель
        </Button>
      </div>
    </div>
  )
}
