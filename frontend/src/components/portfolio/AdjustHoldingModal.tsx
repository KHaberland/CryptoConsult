'use client'

import { useEffect, useMemo, useState } from 'react'
import { CheckCircle } from 'lucide-react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Alert } from '@/components/ui/Alert'
import { cn, formatCurrency, formatUnits } from '@/lib/utils'
import type {
  HoldingAdjustInput,
  Wallet,
  WalletHolding,
} from '@/services/api'

type AdjustReason = NonNullable<HoldingAdjustInput['reason']>

const REASON_OPTIONS: Array<{ value: AdjustReason; label: string }> = [
  { value: 'reconciliation', label: 'Сверка / корректировка' },
  { value: 'network_fee', label: 'Сетевая комиссия' },
  { value: 'exchange_fee', label: 'Биржевая комиссия' },
  { value: 'input_error', label: 'Исправление ошибки ввода' },
  { value: 'other', label: 'Другое' },
]

interface AdjustHoldingModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (
    walletId: number,
    symbol: string,
    data: HoldingAdjustInput,
  ) => Promise<void>
  wallet: Wallet | null
  holding: WalletHolding | null
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

function formatApiError(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: unknown } } | undefined)
    ?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (typeof data === 'object') {
    const obj = data as Record<string, unknown>
    if (typeof obj.detail === 'string') return obj.detail
    const msgs: string[] = []
    for (const v of Object.values(obj)) {
      if (Array.isArray(v)) msgs.push(...v.map((m) => String(m)))
      else if (typeof v === 'string') msgs.push(v)
    }
    if (msgs.length) return msgs.join('. ')
  }
  return fallback
}

export function AdjustHoldingModal({
  isOpen,
  onClose,
  onConfirm,
  wallet,
  holding,
}: AdjustHoldingModalProps) {
  const [step, setStep] = useState<Step>('form')

  const [unitsAfter, setUnitsAfter] = useState<string>('')
  const [reason, setReason] = useState<AdjustReason | ''>('')
  const [note, setNote] = useState<string>('')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const currentUnits = useMemo(
    () => toNumber(holding?.units),
    [holding],
  )
  const currentValueUsd = useMemo(
    () => toNumber(holding?.value_usd),
    [holding],
  )
  // Цену получаем из value_usd / units самого холдинга — это согласуется с тем,
  // что пользователь видит в карточке кошелька, и не требует дополнительного запроса.
  const unitPrice = useMemo(() => {
    if (currentUnits <= 0) return 0
    return currentValueUsd / currentUnits
  }, [currentUnits, currentValueUsd])

  // Сброс формы при открытии. По умолчанию подставляем текущий баланс,
  // чтобы пользователь правил конкретное число, а не вводил его с нуля.
  useEffect(() => {
    if (!isOpen) return
    setStep('form')
    setError(null)
    setSubmitting(false)
    setReason('')
    setNote('')
    setUnitsAfter(holding ? String(currentUnits) : '')
  }, [isOpen, holding, currentUnits])

  const unitsAfterNum = parseDecimalInput(unitsAfter)
  const hasValidUnitsAfter =
    !isNaN(unitsAfterNum) && unitsAfterNum >= 0
  const delta = hasValidUnitsAfter ? unitsAfterNum - currentUnits : 0
  const valueDeltaUsd = unitPrice > 0 ? delta * unitPrice : 0
  const valueAfterUsd = unitPrice > 0 ? unitsAfterNum * unitPrice : 0
  const isUnchanged =
    hasValidUnitsAfter && Math.abs(delta) < 1e-12

  const validate = (): string | null => {
    if (!wallet || !holding) return 'Не выбран кошелёк или актив.'
    if (unitsAfter.trim() === '') return 'Введите новый баланс.'
    if (isNaN(unitsAfterNum)) return 'Введите корректное число.'
    if (unitsAfterNum < 0) return 'Баланс не может быть отрицательным.'
    if (isUnchanged) return 'Новый баланс совпадает с текущим — корректировка не требуется.'
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting || !wallet || !holding) return

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      const payload: HoldingAdjustInput = {
        units_after: unitsAfterNum,
      }
      if (reason) payload.reason = reason
      const trimmedNote = note.trim()
      if (trimmedNote) payload.note = trimmedNote

      await onConfirm(wallet.id, holding.symbol, payload)
      setStep('success')
    } catch (err: unknown) {
      setError(formatApiError(err, 'Не удалось скорректировать баланс.'))
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
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Баланс скорректирован
          </h2>
          <p className="text-gray-600 mb-6">
            Новый баланс {holding?.symbol ?? ''} сохранён. Стоимость портфеля
            обновлена.
          </p>
          <Button onClick={handleClose} variant="primary">
            Закрыть
          </Button>
        </div>
      </Modal>
    )
  }

  // === Form ===
  if (!wallet || !holding) {
    return null
  }

  const deltaSign = delta > 0 ? '+' : ''
  const valueSign = valueDeltaUsd > 0 ? '+' : ''

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Корректировка баланса"
      size="md"
      closeOnOverlayClick={!submitting}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm space-y-1">
          <p className="text-gray-600">
            Кошелёк:{' '}
            <span className="font-medium text-gray-900">{wallet.name}</span>
            {wallet.is_default && (
              <span className="ml-1 text-xs text-gray-500">
                (по умолчанию)
              </span>
            )}
          </p>
          <p className="text-gray-600">
            Актив:{' '}
            <span className="font-medium text-gray-900">{holding.symbol}</span>
          </p>
          <p className="text-gray-600">
            Текущий баланс:{' '}
            <span className="font-medium text-gray-900 tabular-nums">
              {formatUnits(currentUnits)} {holding.symbol}
            </span>
            {unitPrice > 0 && (
              <>
                {' '}
                ≈{' '}
                <span className="font-medium text-gray-900 tabular-nums">
                  {formatCurrency(currentValueUsd)}
                </span>
              </>
            )}
          </p>
        </div>

        <Input
          label="Новый баланс"
          type="number"
          min="0"
          step="0.00000001"
          value={unitsAfter}
          onChange={(e) => setUnitsAfter(e.target.value)}
          autoFocus
          disabled={submitting}
          hint={
            unitPrice > 0
              ? `Цена для расчёта: ${formatCurrency(unitPrice)} / ${holding.symbol}`
              : 'USD-эквивалент будет недоступен — у актива нет рыночной цены.'
          }
        />

        {hasValidUnitsAfter && !isUnchanged && (
          <div
            className={cn(
              'rounded-lg border p-3 text-sm',
              delta < 0
                ? 'border-amber-200 bg-amber-50 text-amber-800'
                : 'border-emerald-200 bg-emerald-50 text-emerald-800',
            )}
          >
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-xs uppercase tracking-wide opacity-70">
                  Изменение (units)
                </p>
                <p className="font-semibold tabular-nums">
                  {deltaSign}
                  {formatUnits(delta)} {holding.symbol}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide opacity-70">
                  Изменение (USD)
                </p>
                <p className="font-semibold tabular-nums">
                  {unitPrice > 0
                    ? `${valueSign}${formatCurrency(valueDeltaUsd)}`
                    : '—'}
                </p>
              </div>
              <div className="col-span-2 pt-2 border-t border-current/10">
                <p className="text-xs uppercase tracking-wide opacity-70">
                  Новый баланс
                </p>
                <p className="font-semibold tabular-nums">
                  {formatUnits(unitsAfterNum)} {holding.symbol}
                  {unitPrice > 0 && (
                    <>
                      {' '}
                      ≈ {formatCurrency(valueAfterUsd)}
                    </>
                  )}
                </p>
              </div>
            </div>
          </div>
        )}

        <Alert variant="warning" title="Это изменит PnL">
          Net Invested не изменится.
        </Alert>

        <div className="w-full">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Причина (необязательно)
          </label>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value as AdjustReason | '')}
            disabled={submitting}
            className={cn(
              'w-full px-4 py-2 border rounded-lg transition-colors duration-200 bg-white',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
              'border-gray-300',
            )}
          >
            <option value="">— не указана —</option>
            {REASON_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <Input
          label="Заметка (необязательно)"
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Например: списано на газ при выводе"
          maxLength={200}
          disabled={submitting}
        />

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
          <Button
            type="submit"
            variant="primary"
            isLoading={submitting}
            disabled={!hasValidUnitsAfter || isUnchanged}
          >
            Сохранить
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  )
}

export default AdjustHoldingModal
