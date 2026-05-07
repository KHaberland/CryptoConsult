'use client'

import { useEffect, useState } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Alert } from '@/components/ui/Alert'
import { cn } from '@/lib/utils'
import type {
  Wallet,
  WalletCreateInput,
  WalletType,
  WalletUpdateInput,
} from '@/services/api'

const TYPE_OPTIONS: Array<{ value: WalletType; label: string }> = [
  { value: 'exchange', label: 'Биржа' },
  { value: 'hot', label: 'Горячий' },
  { value: 'cold', label: 'Холодный' },
  { value: 'bank', label: 'Банк' },
  { value: 'other', label: 'Другое' },
]

interface WalletFormModalProps {
  isOpen: boolean
  onClose: () => void
  /** Если передан — модалка работает в режиме редактирования. */
  wallet?: Wallet | null
  /** Создание нового кошелька. */
  onCreate?: (data: WalletCreateInput) => Promise<unknown>
  /** Обновление существующего. */
  onUpdate?: (id: number, data: WalletUpdateInput) => Promise<unknown>
}

interface FormState {
  name: string
  type: WalletType
  note: string
}

const DEFAULT_STATE: FormState = {
  name: '',
  type: 'exchange',
  note: '',
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
      if (Array.isArray(v)) {
        msgs.push(...v.map((m) => String(m)))
      } else if (typeof v === 'string') {
        msgs.push(v)
      }
    }
    if (msgs.length) return msgs.join('. ')
  }
  return fallback
}

export function WalletFormModal({
  isOpen,
  onClose,
  wallet,
  onCreate,
  onUpdate,
}: WalletFormModalProps) {
  const isEdit = Boolean(wallet)
  const [state, setState] = useState<FormState>(DEFAULT_STATE)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<{ name?: string }>({})

  useEffect(() => {
    if (!isOpen) return
    if (wallet) {
      setState({
        name: wallet.name ?? '',
        type: wallet.type ?? 'other',
        note: wallet.note ?? '',
      })
    } else {
      setState(DEFAULT_STATE)
    }
    setError(null)
    setFieldError({})
    setSubmitting(false)
  }, [isOpen, wallet])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return

    const name = state.name.trim()
    if (!name) {
      setFieldError({ name: 'Введите название кошелька' })
      return
    }

    const payload: WalletCreateInput = {
      name,
      type: state.type,
      note: state.note.trim() ? state.note.trim() : undefined,
    }

    setSubmitting(true)
    setError(null)
    setFieldError({})

    try {
      if (isEdit && wallet && onUpdate) {
        await onUpdate(wallet.id, payload)
      } else if (!isEdit && onCreate) {
        await onCreate(payload)
      } else {
        throw new Error('Обработчик не передан')
      }
      onClose()
    } catch (err: unknown) {
      setError(
        formatApiError(
          err,
          isEdit
            ? 'Не удалось обновить кошелёк'
            : 'Не удалось создать кошелёк',
        ),
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={submitting ? () => undefined : onClose}
      title={isEdit ? 'Редактировать кошелёк' : 'Добавить кошелёк'}
      size="md"
      closeOnOverlayClick={!submitting}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Alert variant="error">{error}</Alert>}

        <Input
          label="Название"
          placeholder="Например, Binance основной"
          value={state.name}
          onChange={(e) =>
            setState((s) => ({ ...s, name: e.target.value }))
          }
          error={fieldError.name}
          autoFocus
          maxLength={100}
        />

        <div className="w-full">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Тип
          </label>
          <select
            value={state.type}
            onChange={(e) =>
              setState((s) => ({
                ...s,
                type: e.target.value as WalletType,
              }))
            }
            className={cn(
              'w-full px-4 py-2 border rounded-lg transition-colors duration-200 bg-white',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
              'border-gray-300',
            )}
          >
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <Input
          label="Заметка (необязательно)"
          placeholder="Например, для долгосрочного хранения"
          value={state.note}
          onChange={(e) =>
            setState((s) => ({ ...s, note: e.target.value }))
          }
          maxLength={255}
        />

        <ModalFooter>
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button type="submit" variant="primary" isLoading={submitting}>
            {isEdit ? 'Сохранить' : 'Создать'}
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  )
}

export default WalletFormModal
