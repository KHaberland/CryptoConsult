'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeftRight,
  CheckCircle,
} from 'lucide-react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { formatCurrency, formatUnits } from '@/lib/utils'
import { portfolioApi } from '@/services/api'
import type { Wallet, WalletTransferInput } from '@/services/api'

interface TransferBetweenWalletsModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (data: WalletTransferInput) => Promise<void>
  wallets: Wallet[]
  /** Кошелёк-источник по умолчанию (если открыто из карточки кошелька). */
  defaultFromWalletId?: number
}

interface TradableAsset {
  symbol: string
  name: string
  current_price: number
}

type Step = 'form' | 'success'

function toNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined) return 0
  const n = typeof value === 'number' ? value : parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

function parseDecimalInput(raw: string): number {
  return parseFloat((raw || '').replace(',', '.'))
}

export function TransferBetweenWalletsModal({
  isOpen,
  onClose,
  onConfirm,
  wallets,
  defaultFromWalletId,
}: TransferBetweenWalletsModalProps) {
  const [step, setStep] = useState<Step>('form')

  const [fromWalletId, setFromWalletId] = useState<string>('')
  const [toWalletId, setToWalletId] = useState<string>('')
  const [symbol, setSymbol] = useState<string>('')
  const [fromUnits, setFromUnits] = useState<string>('')
  const [toUnits, setToUnits] = useState<string>('')
  const [note, setNote] = useState<string>('')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Текущие цены для расчёта USD-комиссии. Если запрос не получится —
  // просто не покажем USD-эквивалент, ввод по units работает в любом случае.
  const [prices, setPrices] = useState<Record<string, number>>({})
  const [pricesLoading, setPricesLoading] = useState(false)

  // Сброс формы при открытии модалки.
  useEffect(() => {
    if (!isOpen) return

    setStep('form')
    setError(null)
    setSubmitting(false)
    setNote('')
    setFromUnits('')
    setToUnits('')

    const candidateFromId =
      defaultFromWalletId && wallets.some((w) => w.id === defaultFromWalletId)
        ? defaultFromWalletId
        : wallets.find((w) => (w.holdings ?? []).some((h) => toNumber(h.units) > 0))?.id ??
          wallets[0]?.id

    setFromWalletId(candidateFromId ? String(candidateFromId) : '')

    const firstTo = wallets.find((w) => w.id !== candidateFromId)
    setToWalletId(firstTo ? String(firstTo.id) : '')

    setSymbol('')
  }, [isOpen, wallets, defaultFromWalletId])

  // Загружаем цены один раз при открытии. Используем тот же эндпоинт, что и SwapModal,
  // чтобы не плодить новые API. Не блокируем форму, если запрос упадёт.
  useEffect(() => {
    if (!isOpen) return
    if (Object.keys(prices).length > 0) return

    let cancelled = false
    setPricesLoading(true)
    portfolioApi
      .getTradableAssets()
      .then((data) => {
        if (cancelled) return
        const map: Record<string, number> = {}
        for (const a of data.assets as TradableAsset[]) {
          map[a.symbol] = toNumber(a.current_price)
        }
        setPrices(map)
      })
      .catch(() => {
        // Цены опциональны — комиссия в USD просто не отобразится.
      })
      .finally(() => {
        if (!cancelled) setPricesLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  const fromWallet = useMemo(
    () => wallets.find((w) => String(w.id) === fromWalletId) || null,
    [wallets, fromWalletId],
  )

  const toWallet = useMemo(
    () => wallets.find((w) => String(w.id) === toWalletId) || null,
    [wallets, toWalletId],
  )

  // Активы доступные для перевода — только те, что есть на исходном кошельке.
  const symbolOptions = useMemo(() => {
    const holdings = fromWallet?.holdings ?? []
    return holdings
      .filter((h) => toNumber(h.units) > 0)
      .map((h) => ({
        symbol: h.symbol,
        units: toNumber(h.units),
      }))
      .sort((a, b) => a.symbol.localeCompare(b.symbol))
  }, [fromWallet])

  // Если выбранный символ исчез из набора (после смены fromWallet) — сбросим выбор.
  useEffect(() => {
    if (!symbol) return
    if (!symbolOptions.some((o) => o.symbol === symbol)) {
      setSymbol('')
    }
  }, [symbol, symbolOptions])

  const availableUnits = useMemo(() => {
    if (!symbol) return 0
    return symbolOptions.find((o) => o.symbol === symbol)?.units ?? 0
  }, [symbol, symbolOptions])

  const symbolPrice = symbol ? prices[symbol] ?? 0 : 0

  const fromUnitsNum = parseDecimalInput(fromUnits)
  const toUnitsNum = parseDecimalInput(toUnits)
  const hasFromUnits = !isNaN(fromUnitsNum) && fromUnitsNum > 0
  const hasToUnits = !isNaN(toUnitsNum) && toUnitsNum > 0

  const feeUnits = hasFromUnits && hasToUnits ? Math.max(0, fromUnitsNum - toUnitsNum) : 0
  const feeUsd = symbolPrice > 0 ? feeUnits * symbolPrice : 0
  const fromUsd = symbolPrice > 0 && hasFromUnits ? fromUnitsNum * symbolPrice : 0
  const toUsd = symbolPrice > 0 && hasToUnits ? toUnitsNum * symbolPrice : 0

  // Удобство: при изменении fromUnits подставляем то же значение в toUnits,
  // если пользователь ещё не правил поле toUnits вручную.
  const handleFromUnitsChange = (value: string) => {
    setFromUnits(value)
    if (!toUnits || toUnits === fromUnits) {
      setToUnits(value)
    }
  }

  const handleUseMax = () => {
    if (availableUnits <= 0) return
    const formatted = availableUnits.toString()
    setFromUnits(formatted)
    setToUnits(formatted)
  }

  const handleSwapWallets = () => {
    if (!fromWalletId || !toWalletId) return
    setFromWalletId(toWalletId)
    setToWalletId(fromWalletId)
    setSymbol('')
    setFromUnits('')
    setToUnits('')
  }

  const validate = (): string | null => {
    if (!fromWallet) return 'Выберите кошелёк-источник.'
    if (!toWallet) return 'Выберите кошелёк-получатель.'
    if (fromWallet.id === toWallet.id) {
      return 'Кошелёк-источник и кошелёк-получатель не могут совпадать.'
    }
    if (!symbol) return 'Выберите актив для перевода.'
    if (!hasFromUnits) return 'Введите количество к отправке (> 0).'
    if (!hasToUnits) return 'Введите количество к получению (> 0).'
    if (toUnitsNum > fromUnitsNum) {
      return 'Количество к получению не может превышать количество к отправке.'
    }
    if (fromUnitsNum > availableUnits + 1e-12) {
      return `Недостаточно средств: на «${fromWallet.name}» доступно ${formatUnits(availableUnits)} ${symbol}.`
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      await onConfirm({
        from_wallet_id: fromWallet!.id,
        to_wallet_id: toWallet!.id,
        symbol,
        from_units: fromUnitsNum,
        to_units: toUnitsNum,
        note: note.trim() || undefined,
      })
      setStep('success')
    } catch (err: unknown) {
      const data = (err as { response?: { data?: unknown } } | undefined)?.response?.data
      let message = 'Не удалось выполнить перевод.'
      if (typeof data === 'string') {
        message = data
      } else if (data && typeof data === 'object') {
        const obj = data as Record<string, unknown>
        if (typeof obj.detail === 'string') {
          message = obj.detail
        } else {
          const msgs: string[] = []
          for (const v of Object.values(obj)) {
            if (Array.isArray(v)) msgs.push(...v.map((m) => String(m)))
            else if (typeof v === 'string') msgs.push(v)
          }
          if (msgs.length) message = msgs.join('. ')
        }
      } else if (err instanceof Error && err.message) {
        message = err.message
      }
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
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
          <h2 className="text-xl font-bold text-gray-900 mb-2">Перевод выполнен</h2>
          <p className="text-gray-600 mb-6">
            Балансы кошельков обновлены.
          </p>
          <Button onClick={handleClose} variant="primary">
            Закрыть
          </Button>
        </div>
      </Modal>
    )
  }

  // === Form ===
  const canSubmit = !submitting && wallets.length >= 2

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Перевод между кошельками"
      size="lg"
      closeOnOverlayClick={!submitting}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {wallets.length < 2 ? (
          <Alert variant="info">
            Для перевода нужно минимум два кошелька. Создайте ещё один кошелёк.
          </Alert>
        ) : (
          <p className="text-sm text-gray-600">
            Перемещение актива между кошельками внутри портфеля. Разница между
            отправленным и полученным количеством учитывается как комиссия и
            уменьшает общий баланс портфеля.
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Откуда
            </label>
            <select
              value={fromWalletId}
              onChange={(e) => {
                setFromWalletId(e.target.value)
                setSymbol('')
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
              disabled={submitting}
            >
              <option value="">— выбрать —</option>
              {wallets.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                  {w.is_default ? ' (по умолчанию)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="flex justify-center pb-1">
            <button
              type="button"
              onClick={handleSwapWallets}
              className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-500"
              title="Поменять местами"
              disabled={submitting || !fromWalletId || !toWalletId}
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Куда
            </label>
            <select
              value={toWalletId}
              onChange={(e) => setToWalletId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
              disabled={submitting}
            >
              <option value="">— выбрать —</option>
              {wallets
                .filter((w) => String(w.id) !== fromWalletId)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                    {w.is_default ? ' (по умолчанию)' : ''}
                  </option>
                ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Актив
          </label>
          <select
            value={symbol}
            onChange={(e) => {
              setSymbol(e.target.value)
              setFromUnits('')
              setToUnits('')
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
            disabled={submitting || !fromWallet || symbolOptions.length === 0}
          >
            <option value="">
              {symbolOptions.length === 0
                ? '— на исходном кошельке нет активов —'
                : '— выбрать —'}
            </option>
            {symbolOptions.map((o) => (
              <option key={o.symbol} value={o.symbol}>
                {o.symbol} — доступно {formatUnits(o.units)}
              </option>
            ))}
          </select>
          {symbol && (
            <p className="mt-1 text-xs text-gray-500">
              Доступный баланс:{' '}
              <span className="font-medium text-gray-800">
                {formatUnits(availableUnits)} {symbol}
              </span>
              {symbolPrice > 0 && (
                <>
                  {' '}
                  ≈{' '}
                  <span className="font-medium text-gray-800">
                    {formatCurrency(availableUnits * symbolPrice)}
                  </span>
                </>
              )}
              {pricesLoading && !symbolPrice && (
                <span className="ml-2 text-gray-400">(загрузка цены…)</span>
              )}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">
                Отправлено {symbol && <span className="text-gray-400">({symbol})</span>}
              </label>
              {symbol && availableUnits > 0 && (
                <button
                  type="button"
                  onClick={handleUseMax}
                  className="text-xs text-primary-600 hover:underline"
                  disabled={submitting}
                >
                  Использовать всё
                </button>
              )}
            </div>
            <input
              type="number"
              min="0"
              step="0.00000001"
              value={fromUnits}
              onChange={(e) => handleFromUnitsChange(e.target.value)}
              placeholder="0.00"
              disabled={submitting || !symbol}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
            />
            {hasFromUnits && symbolPrice > 0 && (
              <p className="text-xs text-gray-500 mt-1">≈ {formatCurrency(fromUsd)}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Получено {symbol && <span className="text-gray-400">({symbol})</span>}
            </label>
            <input
              type="number"
              min="0"
              step="0.00000001"
              value={toUnits}
              onChange={(e) => setToUnits(e.target.value)}
              placeholder="0.00"
              disabled={submitting || !symbol}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
            />
            {hasToUnits && symbolPrice > 0 && (
              <p className="text-xs text-gray-500 mt-1">≈ {formatCurrency(toUsd)}</p>
            )}
          </div>
        </div>

        {symbol && (
          <div className="flex justify-center text-gray-400">
            <ArrowDown className="w-5 h-5" />
          </div>
        )}

        {hasFromUnits && hasToUnits && (
          <div
            className={`rounded-lg border p-3 text-sm ${
              feeUnits > 0
                ? 'border-yellow-200 bg-yellow-50 text-yellow-800'
                : 'border-emerald-200 bg-emerald-50 text-emerald-800'
            }`}
          >
            <div className="flex items-start gap-2">
              {feeUnits > 0 ? (
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
              )}
              <div>
                {feeUnits > 0 ? (
                  <>
                    <p>
                      Комиссия сети / биржи:{' '}
                      <span className="font-semibold">
                        {formatUnits(feeUnits)} {symbol}
                      </span>
                      {symbolPrice > 0 && (
                        <>
                          {' '}
                          ≈{' '}
                          <span className="font-semibold">
                            {formatCurrency(feeUsd)}
                          </span>
                        </>
                      )}
                      .
                    </p>
                    <p className="text-xs mt-1 opacity-80">
                      Эта сумма уменьшит общий баланс портфеля. Net Invested не меняется.
                    </p>
                  </>
                ) : (
                  <p>Комиссии нет — переведено ровно {formatUnits(fromUnitsNum)} {symbol}.</p>
                )}
              </div>
            </div>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Заметка (необязательно)
          </label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Например: перевод на холодный кошелёк"
            maxLength={200}
            disabled={submitting}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
          />
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <ModalFooter>
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button type="submit" variant="primary" isLoading={submitting} disabled={!canSubmit}>
            Перевести
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  )
}

export default TransferBetweenWalletsModal
