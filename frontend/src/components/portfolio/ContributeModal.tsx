'use client'

import { useState } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { CheckCircle, DollarSign } from 'lucide-react'
import { formatCurrency } from '@/lib/utils'

interface ContributeModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (amount: number) => Promise<void>
  investedSoFar: number
  totalPlanned?: number
  suggestedAmount?: number
}

export function ContributeModal({
  isOpen,
  onClose,
  onConfirm,
  investedSoFar,
  totalPlanned = 0,
  suggestedAmount = 0,
}: ContributeModalProps) {
  const [amount, setAmount] = useState(suggestedAmount > 0 ? String(suggestedAmount) : '')
  const [isLoading, setIsLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    const numAmount = parseFloat(amount.replace(',', '.'))
    if (isNaN(numAmount) || numAmount <= 0) {
      setError('Введите корректную сумму')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await onConfirm(numAmount)
      setShowSuccess(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при внесении взноса')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    setAmount(suggestedAmount > 0 ? String(suggestedAmount) : '')
    setShowSuccess(false)
    setError(null)
    onClose()
  }

  if (showSuccess) {
    return (
      <Modal isOpen={isOpen} onClose={handleClose} size="md" showCloseButton={false} closeOnOverlayClick={false}>
        <div className="text-center py-6">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Взнос внесён</h2>
          <p className="text-gray-600 mb-6">
            Портфель обновлён. Криптоконсультант теперь видит актуальные данные.
          </p>
          <Button onClick={handleClose} variant="primary">
            Закрыть
          </Button>
        </div>
      </Modal>
    )
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Внести взнос" size="md">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Зафиксируйте внесённую сумму. Консультант будет учитывать её при рекомендациях.
        </p>
        {totalPlanned > 0 && (
          <p className="text-sm text-gray-500">
            Вложено: {formatCurrency(investedSoFar)} из {formatCurrency(totalPlanned)}
          </p>
        )}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Сумма ($)</label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="number"
              min="1"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Например, 1666"
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
        </div>
        {suggestedAmount > 0 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setAmount(String(suggestedAmount))}
          >
            Использовать рекомендуемую: {formatCurrency(suggestedAmount)}
          </Button>
        )}
        {error && <Alert variant="error">{error}</Alert>}
      </div>
      <ModalFooter>
        <Button variant="secondary" onClick={handleClose}>
          Отмена
        </Button>
        <Button variant="primary" onClick={handleConfirm} disabled={isLoading}>
          {isLoading ? 'Сохранение...' : 'Внести'}
        </Button>
      </ModalFooter>
    </Modal>
  )
}
