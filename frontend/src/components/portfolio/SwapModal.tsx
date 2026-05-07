'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import {
  ArrowLeft,
  ArrowRight,
  ArrowDown,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import { portfolioApi, type Wallet } from '@/services/api'
import { WalletSelector } from '@/components/portfolio/WalletSelector'

interface PortfolioAssetLike {
  symbol: string
  name: string
  current_price: number
}

interface TradableAsset {
  symbol: string
  name: string
  current_price: number
  is_recommended: boolean
  in_portfolio: boolean
  is_stable: boolean
}

interface SwapQuote {
  from_symbol: string
  from_units: number
  from_price: number
  to_symbol: string
  to_units_expected: number
  to_price: number
  value_usd: number
}

interface SwapModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (
    data: {
      from_symbol: string
      from_units: number
      to_symbol: string
      to_units: number
      note?: string
    },
    walletId?: number | null
  ) => Promise<void>
  portfolioAssets: PortfolioAssetLike[]
  /**
   * Список кошельков портфеля. Swap всегда происходит внутри одного
   * кошелька (см. PLAN06 — Агент 12), поэтому селектор кошельков
   * выбирается до выбора актива «Из». Если кошелёк один — селектор
   * скрыт автоматически (WalletSelector).
   */
  wallets?: Wallet[]
}

/** Безопасное приведение `units` (number | string | null) к number. */
function toUnitsNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined) return 0
  const n = typeof value === 'number' ? value : parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

type Step = 'form' | 'preview' | 'success'

export function SwapModal({
  isOpen,
  onClose,
  onConfirm,
  portfolioAssets,
  wallets = [],
}: SwapModalProps) {
  const [step, setStep] = useState<Step>('form')

  const [tradableAssets, setTradableAssets] = useState<TradableAsset[]>([])
  const [assetsLoading, setAssetsLoading] = useState(false)
  const [assetsError, setAssetsError] = useState<string | null>(null)

  const [fromSymbol, setFromSymbol] = useState('')
  const [toSymbol, setToSymbol] = useState('')
  const [fromUnits, setFromUnits] = useState('')

  // Кошелёк, в рамках которого выполняется swap. Изначально — default.
  // Если кошелёк один — WalletSelector сам авто-выберет его и скроется.
  const defaultWalletId = useMemo(() => {
    const def = wallets.find((w) => w.is_default)
    return def ? def.id : wallets[0]?.id ?? null
  }, [wallets])
  const [selectedWalletId, setSelectedWalletId] = useState<number | null>(
    defaultWalletId
  )

  const [quote, setQuote] = useState<SwapQuote | null>(null)
  const [toUnitsEdited, setToUnitsEdited] = useState('')
  const [note, setNote] = useState('')

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Сброс при открытии
  useEffect(() => {
    if (isOpen) {
      setStep('form')
      setFromSymbol('')
      setToSymbol('')
      setFromUnits('')
      setSelectedWalletId(defaultWalletId)
      setQuote(null)
      setToUnitsEdited('')
      setNote('')
      setError(null)
    }
  }, [isOpen, defaultWalletId])

  // Загрузка списка доступных монет (для To).
  // Важно: не включаем assetsLoading/tradableAssets.length в deps —
  // setState внутри эффекта вызвал бы cleanup и отменил бы in-flight запрос.
  useEffect(() => {
    if (!isOpen) return
    if (tradableAssets.length > 0) return

    let cancelled = false
    setAssetsLoading(true)
    setAssetsError(null)
    portfolioApi
      .getTradableAssets()
      .then((data) => {
        if (cancelled) return
        setTradableAssets(data.assets)
      })
      .catch((err: any) => {
        if (cancelled) return
        setAssetsError(
          err?.response?.data?.detail || 'Не удалось загрузить список доступных монет'
        )
      })
      .finally(() => {
        if (!cancelled) setAssetsLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  const fromAsset = useMemo(
    () => portfolioAssets.find((a) => a.symbol === fromSymbol) || null,
    [portfolioAssets, fromSymbol]
  )

  const toAssetMeta = useMemo(
    () => tradableAssets.find((a) => a.symbol === toSymbol) || null,
    [tradableAssets, toSymbol]
  )

  // Выбранный кошелёк и баланс по символам на нём (units > 0).
  // Swap всегда происходит внутри одного кошелька (PLAN06 — Агент 12),
  // поэтому «Из» ограничиваем только теми активами, которые реально лежат
  // на выбранном кошельке.
  const selectedWallet = useMemo(
    () =>
      selectedWalletId !== null
        ? wallets.find((w) => w.id === selectedWalletId) ?? null
        : null,
    [wallets, selectedWalletId]
  )

  const walletUnitsBySymbol = useMemo(() => {
    const map: Record<string, number> = {}
    for (const h of selectedWallet?.holdings ?? []) {
      const u = toUnitsNumber(h.units)
      if (u > 0) {
        map[h.symbol] = u
      }
    }
    return map
  }, [selectedWallet])

  // Доступные «Из»-варианты:
  //   * если кошельки переданы и выбран конкретный → только символы с units > 0
  //     на этом кошельке (пересечение с portfolioAssets для UX-имени);
  //   * иначе (legacy / нет кошельков) → все активы портфеля.
  const fromOptions = useMemo(() => {
    if (selectedWallet) {
      return portfolioAssets.filter(
        (a) => (walletUnitsBySymbol[a.symbol] ?? 0) > 0
      )
    }
    return portfolioAssets
  }, [portfolioAssets, selectedWallet, walletUnitsBySymbol])

  // Если выбранного «Из» больше нет на новом кошельке — сбрасываем,
  // чтобы пользователь не отправил заведомо невалидный запрос.
  useEffect(() => {
    if (!selectedWallet) return
    if (fromSymbol && !(fromSymbol in walletUnitsBySymbol)) {
      setFromSymbol('')
      setFromUnits('')
    }
  }, [selectedWallet, walletUnitsBySymbol, fromSymbol])

  // Доступные To-варианты: всё кроме выбранного fromSymbol
  const toOptions = useMemo(
    () => tradableAssets.filter((a) => a.symbol !== fromSymbol),
    [tradableAssets, fromSymbol]
  )

  const fromUnitsNum = parseFloat((fromUnits || '').replace(',', '.'))
  const toUnitsEditedNum = parseFloat((toUnitsEdited || '').replace(',', '.'))

  const fromUnitsAvailableOnWallet =
    fromSymbol && selectedWallet ? walletUnitsBySymbol[fromSymbol] ?? 0 : null

  const handleWalletChange = useCallback((walletId: number) => {
    setSelectedWalletId(walletId)
  }, [])

  const handleNext = async () => {
    if (wallets.length > 0 && selectedWalletId === null) {
      setError('Выберите кошелёк для обмена')
      return
    }
    if (!fromSymbol) {
      setError('Выберите актив, который вы продаёте')
      return
    }
    if (!toSymbol) {
      setError('Выберите актив, который вы покупаете')
      return
    }
    if (fromSymbol === toSymbol) {
      setError('Активы «Из» и «В» не могут совпадать')
      return
    }
    if (isNaN(fromUnitsNum) || fromUnitsNum <= 0) {
      setError('Введите количество > 0')
      return
    }
    if (
      selectedWallet &&
      fromUnitsAvailableOnWallet !== null &&
      fromUnitsNum - fromUnitsAvailableOnWallet > 1e-9
    ) {
      setError(
        `На кошельке «${selectedWallet.name}» доступно ` +
          `${fromUnitsAvailableOnWallet.toFixed(8)} ${fromSymbol}.`
      )
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const q = await portfolioApi.getSwapQuote(
        {
          from_symbol: fromSymbol,
          to_symbol: toSymbol,
          from_units: fromUnitsNum,
        },
        selectedWalletId != null ? { wallet_id: selectedWalletId } : undefined
      )
      setQuote(q)
      setToUnitsEdited(q.to_units_expected.toFixed(8))
      setStep('preview')
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || err?.message || 'Не удалось рассчитать котировку'
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleConfirm = async () => {
    if (!quote) return

    if (isNaN(toUnitsEditedNum) || toUnitsEditedNum <= 0) {
      setError('Количество получаемой монеты должно быть > 0')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await onConfirm(
        {
          from_symbol: quote.from_symbol,
          from_units: quote.from_units,
          to_symbol: quote.to_symbol,
          to_units: toUnitsEditedNum,
          note: note.trim() || undefined,
        },
        selectedWalletId
      )
      setStep('success')
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || err?.message || 'Ошибка при выполнении обмена'
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleBack = () => {
    setStep('form')
    setError(null)
  }

  const handleClose = () => {
    setStep('form')
    setError(null)
    onClose()
  }

  // === Success ===
  if (step === 'success') {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleClose}
        size="md"
        showCloseButton={false}
        closeOnOverlayClick={false}
      >
        <div className="text-center py-6">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Обмен выполнен</h2>
          <p className="text-gray-600 mb-6">
            Состав портфеля обновлён. Криптоконсультант теперь видит актуальные данные.
          </p>
          <Button onClick={handleClose} variant="primary">
            Закрыть
          </Button>
        </div>
      </Modal>
    )
  }

  // === Preview ===
  if (step === 'preview' && quote) {
    const expected = quote.to_units_expected
    const edited = isNaN(toUnitsEditedNum) ? 0 : toUnitsEditedNum
    const diffUnits = edited - expected
    const feeUsd = -diffUnits * quote.to_price // если получили меньше — комиссия положительна
    const hasCorrection = Math.abs(diffUnits) / Math.max(expected, 1e-12) > 1e-6

    return (
      <Modal
        isOpen={isOpen}
        onClose={handleClose}
        title="Подтверждение обмена"
        size="lg"
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-gray-50 border border-gray-200 p-4 text-sm space-y-1">
            <p>
              <span className="text-gray-600">Курс из: </span>
              <span className="font-medium text-gray-900">
                1 {quote.from_symbol} ≈ {formatCurrency(quote.from_price)}
              </span>
            </p>
            <p>
              <span className="text-gray-600">Курс в: </span>
              <span className="font-medium text-gray-900">
                1 {quote.to_symbol} ≈ {formatCurrency(quote.to_price)}
              </span>
            </p>
            <p>
              <span className="text-gray-600">Стоимость обмена: </span>
              <span className="font-medium text-gray-900">
                {formatCurrency(quote.value_usd)}
              </span>
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3">
            <div className="rounded-lg border border-gray-200 p-3">
              <p className="text-xs font-medium text-gray-500 mb-1">Списать</p>
              <p className="text-lg font-semibold text-gray-900">
                {quote.from_units.toFixed(8)} {quote.from_symbol}
              </p>
              <p className="text-xs text-gray-500">
                ≈ {formatCurrency(quote.from_units * quote.from_price)}
              </p>
            </div>

            <div className="flex justify-center">
              <ArrowDown className="w-5 h-5 text-gray-400" />
            </div>

            <div className="rounded-lg border border-gray-200 p-3">
              <p className="text-xs font-medium text-gray-500 mb-1">
                Получить ({quote.to_symbol})
              </p>
              <input
                type="number"
                min="0"
                step="0.00000001"
                value={toUnitsEdited}
                onChange={(e) => setToUnitsEdited(e.target.value)}
                className="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-lg font-semibold"
              />
              <p className="text-xs text-gray-500 mt-1">
                По рынку: {expected.toFixed(8)} {quote.to_symbol}. Скорректируйте
                фактически полученное количество (с учётом биржевой комиссии и
                расхождения курсов).
              </p>
            </div>
          </div>

          {hasCorrection && (
            <div
              className={`rounded-lg border p-3 text-sm flex items-start gap-2 ${
                feeUsd >= 0
                  ? 'border-yellow-200 bg-yellow-50 text-yellow-800'
                  : 'border-blue-200 bg-blue-50 text-blue-800'
              }`}
            >
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <div>
                {feeUsd >= 0 ? (
                  <p>
                    Получено меньше расчётного на{' '}
                    <span className="font-semibold">
                      {Math.abs(diffUnits).toFixed(8)} {quote.to_symbol}
                    </span>
                    . Это будет учтено как комиссия / slippage:{' '}
                    <span className="font-semibold">{formatCurrency(feeUsd)}</span>.
                  </p>
                ) : (
                  <p>
                    Получено больше расчётного на{' '}
                    <span className="font-semibold">
                      {Math.abs(diffUnits).toFixed(8)} {quote.to_symbol}
                    </span>{' '}
                    (≈ {formatCurrency(Math.abs(feeUsd))}).
                  </p>
                )}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Заметка (опционально)
            </label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Например: Binance, рыночный ордер"
              maxLength={200}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
            />
          </div>

          {error && <Alert variant="error">{error}</Alert>}
        </div>
        <ModalFooter>
          <Button variant="secondary" onClick={handleBack} disabled={isLoading}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Назад
          </Button>
          <Button variant="primary" onClick={handleConfirm} disabled={isLoading}>
            {isLoading ? 'Выполнение...' : 'Подтвердить'}
          </Button>
        </ModalFooter>
      </Modal>
    )
  }

  // === Form ===
  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Обмен активов" size="lg">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Обмен между активами портфеля без cash-in/out. Расчёт по текущему
          рыночному курсу; на следующем шаге можно скорректировать итоговое
          количество (с учётом биржевой комиссии и slippage).
        </p>

        {assetsLoading && (
          <p className="text-sm text-gray-500">Загрузка списка монет…</p>
        )}
        {assetsError && <Alert variant="error">{assetsError}</Alert>}

        <WalletSelector
          wallets={wallets}
          value={selectedWalletId}
          onChange={handleWalletChange}
          label="Кошелёк"
          disabled={isLoading}
          hint="Обмен происходит внутри одного кошелька. Доступны только активы, лежащие на выбранном кошельке."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Из (актив портфеля)
            </label>
            <select
              value={fromSymbol}
              onChange={(e) => setFromSymbol(e.target.value)}
              disabled={selectedWallet !== null && fromOptions.length === 0}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm disabled:bg-gray-50 disabled:text-gray-500"
            >
              <option value="">— выбрать —</option>
              {fromOptions.map((a) => {
                const u = walletUnitsBySymbol[a.symbol]
                const suffix =
                  selectedWallet && u !== undefined
                    ? ` — доступно ${u.toFixed(8)}`
                    : ''
                return (
                  <option key={a.symbol} value={a.symbol}>
                    {a.symbol} — {a.name}
                    {suffix}
                  </option>
                )
              })}
            </select>
            {selectedWallet && fromOptions.length === 0 && (
              <p className="text-xs text-amber-600 mt-1">
                На кошельке «{selectedWallet.name}» нет активов для обмена.
              </p>
            )}
            {fromAsset && fromAsset.current_price > 0 && (
              <p className="text-xs text-gray-500 mt-1">
                Курс: {formatCurrency(fromAsset.current_price)}
                {selectedWallet && fromUnitsAvailableOnWallet !== null && (
                  <>
                    {' · '}
                    Доступно: {fromUnitsAvailableOnWallet.toFixed(8)} {fromSymbol}
                  </>
                )}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              В (актив портфеля или ТОП-10)
            </label>
            <select
              value={toSymbol}
              onChange={(e) => setToSymbol(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
              disabled={assetsLoading}
            >
              <option value="">— выбрать —</option>
              <optgroup label="В портфеле">
                {toOptions
                  .filter((a) => a.in_portfolio)
                  .map((a) => (
                    <option key={a.symbol} value={a.symbol}>
                      {a.symbol} — {a.name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="ТОП-10">
                {toOptions
                  .filter((a) => !a.in_portfolio && a.is_recommended)
                  .map((a) => (
                    <option key={a.symbol} value={a.symbol}>
                      {a.symbol} — {a.name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Стейблкоины">
                {toOptions
                  .filter((a) => !a.in_portfolio && !a.is_recommended && a.is_stable)
                  .map((a) => (
                    <option key={a.symbol} value={a.symbol}>
                      {a.symbol} — {a.name}
                    </option>
                  ))}
              </optgroup>
            </select>
            {toAssetMeta && toAssetMeta.current_price > 0 && (
              <p className="text-xs text-gray-500 mt-1">
                Курс: {formatCurrency(toAssetMeta.current_price)}
              </p>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Количество {fromSymbol || ''}
          </label>
          <input
            type="number"
            min="0"
            step="0.00000001"
            value={fromUnits}
            onChange={(e) => setFromUnits(e.target.value)}
            placeholder="0.00"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
          />
        </div>

        {/* Превью расчёта */}
        {fromAsset &&
          toAssetMeta &&
          fromAsset.current_price > 0 &&
          toAssetMeta.current_price > 0 &&
          !isNaN(fromUnitsNum) &&
          fromUnitsNum > 0 && (
            <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-sm">
              <p>
                <span className="text-gray-600">Текущий курс: </span>
                <span className="font-medium text-gray-900">
                  1 {fromSymbol} ={' '}
                  {(fromAsset.current_price / toAssetMeta.current_price).toFixed(8)}{' '}
                  {toSymbol}
                </span>
              </p>
              <p>
                <span className="text-gray-600">Получите ≈ </span>
                <span className="font-semibold text-gray-900">
                  {(
                    (fromUnitsNum * fromAsset.current_price) /
                    toAssetMeta.current_price
                  ).toFixed(8)}{' '}
                  {toSymbol}
                </span>
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Стоимость обмена ≈{' '}
                {formatCurrency(fromUnitsNum * fromAsset.current_price)}
              </p>
            </div>
          )}

        {error && <Alert variant="error">{error}</Alert>}
      </div>
      <ModalFooter>
        <Button variant="secondary" onClick={handleClose}>
          Отмена
        </Button>
        <Button
          variant="primary"
          onClick={handleNext}
          disabled={
            isLoading ||
            assetsLoading ||
            (selectedWallet !== null && fromOptions.length === 0)
          }
        >
          {isLoading ? 'Расчёт...' : 'Далее'}
          <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </ModalFooter>
    </Modal>
  )
}
