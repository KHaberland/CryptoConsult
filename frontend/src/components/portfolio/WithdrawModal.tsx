'use client'

import { useEffect, useMemo, useState } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { CheckCircle, DollarSign, ArrowRight, ArrowLeft } from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import { portfolioApi, type Wallet } from '@/services/api'

interface WithdrawAssetProposal {
  symbol: string
  name: string
  units_current: number
  units_to_sell: number
  current_price: number
  value_usd: number
}

interface WithdrawAssetPayload {
  symbol: string
  units_to_sell: number
  wallet_id?: number | null
}

interface WithdrawModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (assets: WithdrawAssetPayload[]) => Promise<void>
  totalValue: number
  /**
   * Список кошельков портфеля. Используется для выбора кошелька списания
   * по каждому активу (PLAN06 — Агент F12 / Агент 13).
   *
   *   * 0 / 1 кошелёк → колонка «Кошелёк» скрыта, бэкенд сам подберёт
   *     кошелёк (стратегия max-units), wallet_id не отправляется.
   *   * >1 кошельков → для каждого актива по умолчанию выбран кошелёк
   *     с максимальным балансом, пользователь может переключить.
   */
  wallets?: Wallet[]
}

type Step = 'amount' | 'proposal' | 'success'

/** Безопасное приведение `units` (number | string | null) к number. */
function toUnitsNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined) return 0
  const n = typeof value === 'number' ? value : parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

/** units символа на конкретном кошельке (0, если такого holding нет). */
function unitsOnWallet(wallet: Wallet | undefined, symbol: string): number {
  if (!wallet) return 0
  const h = (wallet.holdings ?? []).find((x) => x.symbol === symbol)
  return toUnitsNumber(h?.units)
}

export function WithdrawModal({
  isOpen,
  onClose,
  onConfirm,
  totalValue,
  wallets = [],
}: WithdrawModalProps) {
  const [step, setStep] = useState<Step>('amount')
  const [amount, setAmount] = useState('')
  const [proposal, setProposal] = useState<WithdrawAssetProposal[] | null>(null)
  const [proposalTotalValue, setProposalTotalValue] = useState<number>(0)
  const [editedUnits, setEditedUnits] = useState<Record<string, number>>({})
  // Выбранный кошелёк списания по каждому символу. null → бэкенд сам
  // выберет кошелёк с max units (см. PLAN06 — Агент 13).
  const [walletBySymbol, setWalletBySymbol] = useState<
    Record<string, number | null>
  >({})
  const [isLoading, setIsLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Показываем колонку «Кошелёк» только если кошельков больше одного.
  // При 0/1 кошельках UI остаётся прежним, бэкенд сам подберёт кошелёк.
  const showWalletColumn = wallets.length > 1

  /** wallet с максимальным балансом для symbol, или null если ни на одном нет. */
  const pickDefaultWalletId = (symbol: string): number | null => {
    let bestId: number | null = null
    let bestUnits = 0
    for (const w of wallets) {
      const u = unitsOnWallet(w, symbol)
      if (u > 0 && u > bestUnits) {
        bestUnits = u
        bestId = w.id
      }
    }
    return bestId
  }

  /** Доступно units на выбранном кошельке (или Σ по всем, если кошелёк не задан). */
  const availableUnits = (
    symbol: string,
    walletId: number | null,
    fallback: number
  ): number => {
    if (walletId === null) return fallback
    const w = wallets.find((x) => x.id === walletId)
    return unitsOnWallet(w, symbol)
  }

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
      // Дефолт: для каждого актива — кошелёк с максимальным балансом.
      // Если кошельков нет / только один — оставляем null (бэкенд решает).
      if (showWalletColumn) {
        setWalletBySymbol(
          Object.fromEntries(
            data.assets.map((a: WithdrawAssetProposal) => [
              a.symbol,
              pickDefaultWalletId(a.symbol),
            ])
          )
        )
      } else {
        setWalletBySymbol({})
      }
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

  const handleWalletChange = (symbol: string, walletIdRaw: string) => {
    const walletId = walletIdRaw === '' ? null : Number(walletIdRaw)
    const nextId = walletId !== null && Number.isFinite(walletId) ? walletId : null
    setWalletBySymbol((prev) => ({ ...prev, [symbol]: nextId }))
    // Если новое количество > доступного на новом кошельке — обрезаем.
    const a = proposal?.find((x) => x.symbol === symbol)
    if (!a) return
    const cap = availableUnits(symbol, nextId, a.units_current)
    setEditedUnits((prev) => {
      const cur = prev[symbol] ?? a.units_to_sell
      if (cur > cap) {
        return { ...prev, [symbol]: cap }
      }
      return prev
    })
  }

  const handleAccept = async () => {
    if (!proposal) return

    const assets: WithdrawAssetPayload[] = proposal
      .map((a) => {
        const walletId = walletBySymbol[a.symbol] ?? null
        const cap = availableUnits(a.symbol, walletId, a.units_current)
        const units = editedUnits[a.symbol] ?? a.units_to_sell
        // Защита: если количество > доступного на выбранном кошельке —
        // это валидационная ошибка, не отправляем заведомо плохой запрос.
        return {
          symbol: a.symbol,
          units_to_sell: units,
          wallet_id: walletId,
          _cap: cap,
          _walletName:
            walletId !== null
              ? wallets.find((w) => w.id === walletId)?.name ?? null
              : null,
        }
      })
      .filter((a) => a.units_to_sell > 0) as Array<
      WithdrawAssetPayload & { _cap: number; _walletName: string | null }
    >

    if (assets.length === 0) {
      setError('Укажите количество для вывода хотя бы по одному активу')
      return
    }

    // Валидация: каждое количество должно умещаться на выбранном кошельке.
    for (const a of assets) {
      if (a.units_to_sell - a._cap > 1e-9) {
        const where = a._walletName
          ? `на кошельке «${a._walletName}»`
          : 'в портфеле'
        setError(
          `Для ${a.symbol} ${where} доступно ${a._cap.toFixed(8)} — это ` +
            `меньше указанных ${a.units_to_sell.toFixed(8)}.`
        )
        return
      }
    }

    setIsLoading(true)
    setError(null)

    try {
      await onConfirm(
        assets.map(({ symbol, units_to_sell, wallet_id }) => ({
          symbol,
          units_to_sell,
          wallet_id,
        }))
      )
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
    setWalletBySymbol({})
    setError(null)
    onClose()
  }

  const handleBack = () => {
    setStep('amount')
    setProposal(null)
    setProposalTotalValue(0)
    setEditedUnits({})
    setWalletBySymbol({})
    setError(null)
  }

  const handleClose = () => {
    setStep('amount')
    setAmount('')
    setProposal(null)
    setProposalTotalValue(0)
    setEditedUnits({})
    setWalletBySymbol({})
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
      setWalletBySymbol({})
      setError(null)
      setShowSuccess(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  // Сумма к выводу: используем value_usd из предложения, при редактировании — пропорционально
  const totalWithdrawValue = useMemo(() => {
    if (!proposal) return 0
    return proposal.reduce((sum, a) => {
      const units = editedUnits[a.symbol] ?? a.units_to_sell
      const ratio = a.units_to_sell > 0 ? units / a.units_to_sell : 0
      return sum + a.value_usd * ratio
    }, 0)
  }, [proposal, editedUnits])

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
          {showWalletColumn
            ? 'Вы можете изменить количество и выбрать кошелёк списания для каждого актива. По умолчанию выбран кошелёк с максимальным балансом.'
            : 'Вы можете изменить количество единиц по каждому активу.'}
        </p>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-4 py-2 text-left font-medium text-gray-700">Актив</th>
                {showWalletColumn && (
                  <th className="px-4 py-2 text-left font-medium text-gray-700">Кошелёк</th>
                )}
                <th className="px-4 py-2 text-right font-medium text-gray-700">
                  {showWalletColumn ? 'Доступно' : 'Всего'}
                </th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">К выводу</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Сумма ($)</th>
              </tr>
            </thead>
            <tbody>
              {proposal?.map((a) => {
                const walletId = walletBySymbol[a.symbol] ?? null
                const cap = availableUnits(a.symbol, walletId, a.units_current)
                const units = editedUnits[a.symbol] ?? a.units_to_sell
                const ratio = a.units_to_sell > 0 ? units / a.units_to_sell : 0
                const value = a.value_usd * ratio
                // Кандидаты-кошельки: только те, на которых реально есть актив.
                // Если ни на одном нет (например, рассинхрон) — показываем все,
                // чтобы пользователь хотя бы мог выбрать.
                const candidates = (() => {
                  const withUnits = wallets.filter(
                    (w) => unitsOnWallet(w, a.symbol) > 0
                  )
                  return withUnits.length > 0 ? withUnits : wallets
                })()
                return (
                  <tr key={a.symbol} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-2">
                      <span className="font-medium text-gray-900">{a.symbol}</span>
                      <span className="text-gray-500 ml-1">({a.name})</span>
                    </td>
                    {showWalletColumn && (
                      <td className="px-4 py-2">
                        <select
                          value={walletId !== null ? String(walletId) : ''}
                          onChange={(e) => handleWalletChange(a.symbol, e.target.value)}
                          className="w-full px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-primary-500 text-sm"
                        >
                          {candidates.length === 0 && (
                            <option value="">— нет кошельков —</option>
                          )}
                          {candidates.map((w) => {
                            const u = unitsOnWallet(w, a.symbol)
                            return (
                              <option key={w.id} value={w.id}>
                                {w.name}
                                {w.is_default ? ' (по умолчанию)' : ''}
                                {u > 0 ? ` — ${u.toFixed(8)}` : ' — 0'}
                              </option>
                            )
                          })}
                        </select>
                      </td>
                    )}
                    <td className="px-4 py-2 text-right text-gray-600">
                      {cap.toFixed(8)}
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        min="0"
                        max={cap}
                        step="0.00000001"
                        value={editedUnits[a.symbol] ?? a.units_to_sell}
                        onChange={(e) => handleUnitsChange(a.symbol, e.target.value, cap)}
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
