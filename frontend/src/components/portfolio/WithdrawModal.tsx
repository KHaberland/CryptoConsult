'use client'

import { useState, useEffect } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { CheckCircle, DollarSign, ArrowRight, ArrowLeft } from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import { portfolioApi } from '@/services/api'

interface WithdrawAssetProposal {
  symbol: string
  name: string
  units_current: number
  units_to_sell: number
  current_price: number
  value_usd: number
}

interface WithdrawModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (assets: Array<{ symbol: string; units_to_sell: number }>) => Promise<void>
  totalValue: number
}

type Step = 'amount' | 'proposal' | 'success'

export function WithdrawModal({
  isOpen,
  onClose,
  onConfirm,
  totalValue,
}: WithdrawModalProps) {
  const [step, setStep] = useState<Step>('amount')
  const [amount, setAmount] = useState('')
  const [proposal, setProposal] = useState<WithdrawAssetProposal[] | null>(null)
  const [proposalTotalValue, setProposalTotalValue] = useState<number>(0)
  const [editedUnits, setEditedUnits] = useState<Record<string, number>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAmountSubmit = async () => {
    const numAmount = parseFloat(amount.replace(',', '.'))
    if (isNaN(numAmount) || numAmount <= 0) {
      setError('Введите корректную сумму')
      return
    }
    if (numAmount > totalValue) {
      setError(`Сумма не может превышать стоимость портфеля (${formatCurrency(totalValue)})`)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const data = await portfolioApi.getWithdrawProposal(numAmount)
      setProposal(data.assets)
      setProposalTotalValue(data.total_value ?? totalValue)
      setEditedUnits(
        Object.fromEntries(data.assets.map((a: WithdrawAssetProposal) => [a.symbol, a.units_to_sell]))
      )
      setStep('proposal')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при расчёте предложения')
    } finally {
      setIsLoading(false)
    }
  }

  const handleUnitsChange = (symbol: string, value: string, maxUnits: number) => {
    const num = parseFloat(value.replace(',', '.'))
    let val = isNaN(num) || num < 0 ? 0 : num
    val = Math.min(val, maxUnits)
    setEditedUnits((prev) => ({
      ...prev,
      [symbol]: val,
    }))
  }

  const handleAccept = async () => {
    if (!proposal) return

    const assets = proposal
      .map((a) => ({
        symbol: a.symbol,
        units_to_sell: editedUnits[a.symbol] ?? a.units_to_sell,
      }))
      .filter((a) => a.units_to_sell > 0)

    if (assets.length === 0) {
      setError('Укажите количество для вывода хотя бы по одному активу')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await onConfirm(assets)
      setShowSuccess(true)
      setStep('success')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при выводе средств')
    } finally {
      setIsLoading(false)
    }
  }

  const handleReject = () => {
    setStep('amount')
    setAmount('')
    setProposal(null)
    setProposalTotalValue(0)
    setEditedUnits({})
    setError(null)
    onClose()
  }

  const handleBack = () => {
    setStep('amount')
    setProposal(null)
    setProposalTotalValue(0)
    setEditedUnits({})
    setError(null)
  }

  const handleClose = () => {
    setStep('amount')
    setAmount('')
    setProposal(null)
    setProposalTotalValue(0)
    setEditedUnits({})
    setShowSuccess(false)
    setError(null)
    onClose()
  }

  // Сброс при открытии
  useEffect(() => {
    if (isOpen && step === 'amount') {
      setAmount('')
      setProposal(null)
      setProposalTotalValue(0)
      setEditedUnits({})
      setError(null)
      setShowSuccess(false)
    }
  }, [isOpen])

  // Сумма к выводу: используем value_usd из предложения, при редактировании — пропорционально
  const totalWithdrawValue = proposal
    ? proposal.reduce((sum, a) => {
        const units = editedUnits[a.symbol] ?? a.units_to_sell
        const ratio = a.units_to_sell > 0 ? units / a.units_to_sell : 0
        return sum + a.value_usd * ratio
      }, 0)
    : 0

  const valueAfterWithdraw = Math.max(0, proposalTotalValue - totalWithdrawValue)

  if (showSuccess) {
    return (
      <Modal isOpen={isOpen} onClose={handleClose} size="md" showCloseButton={false} closeOnOverlayClick={false}>
        <div className="text-center py-6">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Вывод выполнен</h2>
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

  if (step === 'amount') {
    return (
      <Modal isOpen={isOpen} onClose={handleClose} title="Вывод средств" size="md">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Какую сумму в долларах вы хотите вывести?
          </p>
          <p className="text-sm text-gray-500">
            Стоимость портфеля: {formatCurrency(totalValue)}
          </p>
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
                placeholder="Например, 500"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
          {error && <Alert variant="error">{error}</Alert>}
        </div>
        <ModalFooter>
          <Button variant="secondary" onClick={handleClose}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleAmountSubmit} disabled={isLoading}>
            {isLoading ? 'Расчёт...' : 'Далее'}
            <ArrowRight className="w-4 h-4 ml-1 inline" />
          </Button>
        </ModalFooter>
      </Modal>
    )
  }

  // step === 'proposal'
  return (
    <Modal isOpen={isOpen} onClose={handleReject} title="Предложение по выводу" size="xl">
      <div className="space-y-4">
        <div className="rounded-lg bg-gray-50 border border-gray-200 p-4">
          <p className="text-sm text-gray-600 mb-1">
            Текущая стоимость портфеля: <span className="font-semibold text-gray-900">{formatCurrency(proposalTotalValue)}</span>
          </p>
          <p className="text-sm text-gray-600">
            К выводу: <span className="font-semibold text-primary-600">{formatCurrency(totalWithdrawValue)}</span>
            {' → '}
            После вывода останется: <span className="font-semibold text-gray-900">{formatCurrency(valueAfterWithdraw)}</span>
          </p>
        </div>
        <p className="text-sm text-gray-600">
          Вы можете изменить количество единиц по каждому активу.
        </p>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-4 py-2 text-left font-medium text-gray-700">Актив</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Всего</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">К выводу</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Сумма ($)</th>
              </tr>
            </thead>
            <tbody>
              {proposal?.map((a) => {
                const units = editedUnits[a.symbol] ?? a.units_to_sell
                const ratio = a.units_to_sell > 0 ? units / a.units_to_sell : 0
                const value = a.value_usd * ratio
                return (
                  <tr key={a.symbol} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-2">
                      <span className="font-medium text-gray-900">{a.symbol}</span>
                      <span className="text-gray-500 ml-1">({a.name})</span>
                    </td>
                    <td className="px-4 py-2 text-right text-gray-600">
                      {a.units_current.toFixed(8)}
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        min="0"
                        max={a.units_current}
                        step="0.00000001"
                        value={editedUnits[a.symbol] ?? a.units_to_sell}
                        onChange={(e) => handleUnitsChange(a.symbol, e.target.value, a.units_current)}
                        className="w-full text-right px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-primary-500"
                      />
                    </td>
                    <td className="px-4 py-2 text-right font-medium">
                      {formatCurrency(value)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {error && <Alert variant="error">{error}</Alert>}
      </div>
      <ModalFooter>
        <Button variant="secondary" onClick={handleBack}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          Назад
        </Button>
        <Button variant="secondary" onClick={handleReject}>
          Отклонить
        </Button>
        <Button variant="primary" onClick={handleAccept} disabled={isLoading}>
          {isLoading ? 'Выполнение...' : 'Принять'}
        </Button>
      </ModalFooter>
    </Modal>
  )
}
