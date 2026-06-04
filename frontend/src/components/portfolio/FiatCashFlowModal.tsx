'use client'

import { useEffect, useState } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { CheckCircle, DollarSign, Euro, AlertTriangle } from 'lucide-react'
import type {
  FiatCashFlow,
  FiatCashFlowKind,
  FiatCurrency,
} from '@/services/api'

/**
 * Модалка ввода/вывода фиата (PLAN11 — A8).
 *
 * Используется на dashboard'е в блоке «Финансы по фиату» для двух операций:
 *   * `mode === 'deposit'` — пользователь зафиксировал, сколько $/€ он
 *     завёл на свои биржи/кошельки;
 *   * `mode === 'withdrawal'` — пользователь зафиксировал вывод фиата
 *     наружу.
 *
 * Сама модалка только собирает форму и зовёт `onSubmit`. Логика создания
 * `FiatCashFlow` через API и обновления стора лежит на dashboard'е /
 * `portfolioStore.ts` (см. A7/A8), чтобы модалка оставалась переиспользуемой.
 */

interface FiatCashFlowModalProps {
  isOpen: boolean
  onClose: () => void
  mode: FiatCashFlowKind
  defaultCurrency: FiatCurrency
  /**
   * Хендлер сохранения операции. Должен резолвиться, если запись создана,
   * и реджектиться (с `Error` или axios-ошибкой), если что-то пошло не так.
   * Опционально может вернуть созданный cash-flow с флагом `fx_stale`,
   * который модалка покажет в success-стейте.
   */
  onSubmit: (input: {
    kind: FiatCashFlowKind
    amount: number
    currency: FiatCurrency
    occurred_on: string
    note: string
  }) => Promise<(FiatCashFlow & { fx_stale?: boolean }) | void>
}

/** Сегодняшняя дата в формате `YYYY-MM-DD` (для `<input type="date">`). */
function todayIso(): string {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export function FiatCashFlowModal({
  isOpen,
  onClose,
  mode,
  defaultCurrency,
  onSubmit,
}: FiatCashFlowModalProps) {
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState<FiatCurrency>(defaultCurrency)
  const [occurredOn, setOccurredOn] = useState<string>(todayIso())
  const [note, setNote] = useState('')

  const [isLoading, setIsLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [fxStaleWarn, setFxStaleWarn] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Сброс формы при каждом открытии модалки. Делать сброс при `onClose`
  // нельзя: тогда новые props (`defaultCurrency`, `mode`) применятся
  // только после следующего открытия, что приведёт к рассинхрону UI.
  useEffect(() => {
    if (isOpen) {
      setAmount('')
      setCurrency(defaultCurrency)
      setOccurredOn(todayIso())
      setNote('')
      setError(null)
      setShowSuccess(false)
      setFxStaleWarn(false)
    }
  }, [isOpen, defaultCurrency, mode])

  const titles = {
    deposit: 'Внести фиат',
    withdrawal: 'Снять фиат',
  } as const

  const submitLabels = {
    deposit: 'Внести',
    withdrawal: 'Снять',
  } as const

  const successHeadings = {
    deposit: 'Депозит зафиксирован',
    withdrawal: 'Вывод зафиксирован',
  } as const

  const handleConfirm = async () => {
    const numAmount = parseFloat((amount || '').replace(',', '.'))
    if (!Number.isFinite(numAmount) || numAmount <= 0) {
      setError('Введите корректную сумму больше нуля')
      return
    }

    // Валидация даты: пустая или будущая — отказываем (бэкенд тоже проверяет
    // `occurred_on <= today`, см. PLAN11 §A5, но дешевле отсечь на фронте).
    const today = todayIso()
    if (!occurredOn) {
      setError('Укажите дату операции')
      return
    }
    if (occurredOn > today) {
      setError('Дата операции не может быть в будущем')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const created = await onSubmit({
        kind: mode,
        amount: numAmount,
        currency,
        occurred_on: occurredOn,
        note: note.trim(),
      })
      setFxStaleWarn(Boolean(created && created.fx_stale))
      setShowSuccess(true)
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object'
          ? (err as { response?: { data?: { detail?: string } }; message?: string })
              .response?.data?.detail ??
            (err as { message?: string }).message
          : null
      setError(detail || 'Не удалось сохранить операцию')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    setShowSuccess(false)
    setError(null)
    setFxStaleWarn(false)
    onClose()
  }

  if (showSuccess) {
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
            {successHeadings[mode]}
          </h2>
          <p className="text-gray-600 mb-4">
            Блок «Финансы по фиату» уже обновлён.
          </p>
          {fxStaleWarn && (
            <Alert variant="warning" className="text-left mb-4">
              Курс USD↔EUR временно недоступен, операция записана с курсом{' '}
              <strong>1.0</strong>. После восстановления курса можно
              переключить базовую валюту, чтобы пересчитать FX.
            </Alert>
          )}
          <Button onClick={handleClose} variant="primary">
            Закрыть
          </Button>
        </div>
      </Modal>
    )
  }

  const CurrencyIcon = currency === 'EUR' ? Euro : DollarSign

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={titles[mode]}
      size="md"
    >
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          {mode === 'deposit'
            ? 'Зафиксируйте сумму, которую вы завели на свои биржи/кошельки. От неё рассчитывается прибыль/убыток всего портфеля.'
            : 'Зафиксируйте сумму, которую вы вывели с бирж/кошельков в фиат. Эта сумма уменьшит «чистый завод» и повлияет на расчёт прибыли/убытка.'}
        </p>

        {/* Сумма */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Сумма
          </label>
          <div className="relative">
            <CurrencyIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="number"
              min="0"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Например, 1000"
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Валюта */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Валюта операции
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(['USD', 'EUR'] as const).map((cur) => {
              const Icon = cur === 'EUR' ? Euro : DollarSign
              const active = currency === cur
              return (
                <button
                  key={cur}
                  type="button"
                  onClick={() => setCurrency(cur)}
                  disabled={isLoading}
                  className={`flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    active
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {cur}
                </button>
              )
            })}
          </div>
        </div>

        {/* Дата */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Дата операции
          </label>
          <input
            type="date"
            value={occurredOn}
            onChange={(e) => setOccurredOn(e.target.value)}
            max={todayIso()}
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        {/* Комментарий */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Комментарий (опционально)
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Например: «Пополнение Binance с карты Wise»"
            rows={2}
            maxLength={200}
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none"
          />
          <p className="text-xs text-gray-500 mt-1">
            До 200 символов. Курс к базовой валюте портфеля бэкенд проставит
            автоматически.
          </p>
        </div>

        {error && (
          <Alert variant="error">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          </Alert>
        )}
      </div>

      <ModalFooter>
        <Button variant="secondary" onClick={handleClose} disabled={isLoading}>
          Отмена
        </Button>
        <Button
          variant="primary"
          onClick={handleConfirm}
          disabled={isLoading}
        >
          {isLoading ? 'Сохранение…' : submitLabels[mode]}
        </Button>
      </ModalFooter>
    </Modal>
  )
}
