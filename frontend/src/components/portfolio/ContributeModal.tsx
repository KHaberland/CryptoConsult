'use client'

import { useEffect, useMemo, useState } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { CheckCircle, DollarSign, Coins, Plus, Trash2 } from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import { portfolioApi, type Wallet } from '@/services/api'
import { WalletSelector } from '@/components/portfolio/WalletSelector'
import { parseApiError, type MirrorPairConflictInfo } from '@/lib/api-errors'

type Mode = 'usd' | 'units'

interface UnitsContributionItem {
  symbol: string
  units: number
  purchase_price?: number
  purchased_at?: string
}

interface TradableAsset {
  symbol: string
  name: string
  current_price: number
  is_recommended: boolean
  in_portfolio: boolean
  is_stable: boolean
}

interface PositionRow {
  id: string
  symbol: string
  units: string
  price: string
  useCurrentPrice: boolean
}

interface ContributeModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (amount: number) => Promise<void>
  onConfirmUnits?: (
    items: UnitsContributionItem[],
    walletId?: number | null
  ) => Promise<void>
  investedSoFar: number
  totalPlanned?: number
  suggestedAmount?: number
  /**
   * Список кошельков портфеля. Используется только в режиме «по монетам»
   * (USD-режим распределяет сумму по всем активам и не привязан к кошельку).
   * Если передан пустой массив (или 1 кошелёк) — селектор скрыт автоматически.
   */
  wallets?: Wallet[]
}

function makeId(): string {
  return Math.random().toString(36).slice(2, 10)
}

export function ContributeModal({
  isOpen,
  onClose,
  onConfirm,
  onConfirmUnits,
  investedSoFar,
  totalPlanned = 0,
  suggestedAmount = 0,
  wallets = [],
}: ContributeModalProps) {
  const [mode, setMode] = useState<Mode>('usd')

  // USD-режим
  const [amount, setAmount] = useState(suggestedAmount > 0 ? String(suggestedAmount) : '')

  // Units-режим
  const [tradableAssets, setTradableAssets] = useState<TradableAsset[]>([])
  const [assetsLoading, setAssetsLoading] = useState(false)
  const [assetsError, setAssetsError] = useState<string | null>(null)
  const [positions, setPositions] = useState<PositionRow[]>([
    { id: makeId(), symbol: '', units: '', price: '', useCurrentPrice: true },
  ])

  // Кошелёк, на который зачисляем монеты в режиме «по монетам».
  // Изначально — default-кошелёк (если он есть среди переданных).
  // Если кошелёк один — WalletSelector сам авто-выберет его и скроется.
  const defaultWalletId = useMemo(() => {
    const def = wallets.find((w) => w.is_default)
    return def ? def.id : wallets[0]?.id ?? null
  }, [wallets])
  const [selectedWalletId, setSelectedWalletId] = useState<number | null>(
    defaultWalletId
  )

  const [isLoading, setIsLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mirrorConflict, setMirrorConflict] =
    useState<MirrorPairConflictInfo | null>(null)

  // Сброс формы при открытии модалки
  useEffect(() => {
    if (isOpen) {
      setMode('usd')
      setAmount(suggestedAmount > 0 ? String(suggestedAmount) : '')
      setPositions([
        { id: makeId(), symbol: '', units: '', price: '', useCurrentPrice: true },
      ])
      setSelectedWalletId(defaultWalletId)
      setError(null)
      setMirrorConflict(null)
      setShowSuccess(false)
    }
  }, [isOpen, suggestedAmount, defaultWalletId])

  // Загрузка списка доступных монет при первом переходе в режим units.
  // Важно: не включаем assetsLoading/tradableAssets.length в deps —
  // setState внутри эффекта вызвал бы cleanup и отменил бы in-flight запрос
  // (тогда «Загрузка списка монет…» зависал бы навсегда).
  useEffect(() => {
    if (!isOpen) return
    if (mode !== 'units') return
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
  }, [isOpen, mode])

  const priceBySymbol = useMemo(() => {
    const map: Record<string, number> = {}
    for (const a of tradableAssets) {
      map[a.symbol] = a.current_price
    }
    return map
  }, [tradableAssets])

  const totalUsdUnits = useMemo(() => {
    return positions.reduce((sum, p) => {
      const units = parseFloat((p.units || '').replace(',', '.'))
      if (isNaN(units) || units <= 0) return sum
      const customPrice = parseFloat((p.price || '').replace(',', '.'))
      const price = p.useCurrentPrice || isNaN(customPrice) || customPrice <= 0
        ? priceBySymbol[p.symbol] ?? 0
        : customPrice
      return sum + units * price
    }, 0)
  }, [positions, priceBySymbol])

  const handleConfirmUsd = async () => {
    const numAmount = parseFloat(amount.replace(',', '.'))
    if (isNaN(numAmount) || numAmount <= 0) {
      setError('Введите корректную сумму')
      return
    }

    setIsLoading(true)
    setError(null)
    setMirrorConflict(null)

    try {
      await onConfirm(numAmount)
      setShowSuccess(true)
    } catch (err: unknown) {
      const parsed = parseApiError(err, 'Ошибка при внесении взноса')
      setError(parsed.message)
      setMirrorConflict(parsed.mirrorConflict)
    } finally {
      setIsLoading(false)
    }
  }

  const handleConfirmUnits = async () => {
    if (!onConfirmUnits) {
      setError('Режим «по монетам» недоступен')
      return
    }

    const items: UnitsContributionItem[] = []
    for (const p of positions) {
      const symbol = p.symbol.trim().toUpperCase()
      const units = parseFloat((p.units || '').replace(',', '.'))
      if (!symbol) {
        setError('Выберите монету для каждой позиции')
        return
      }
      if (isNaN(units) || units <= 0) {
        setError('Количество должно быть больше нуля')
        return
      }

      const item: UnitsContributionItem = { symbol, units }
      if (!p.useCurrentPrice) {
        const customPrice = parseFloat((p.price || '').replace(',', '.'))
        if (isNaN(customPrice) || customPrice <= 0) {
          setError(`Введите корректную цену покупки для ${symbol}`)
          return
        }
        item.purchase_price = customPrice
      }
      items.push(item)
    }

    if (items.length === 0) {
      setError('Добавьте хотя бы одну монету')
      return
    }

    setIsLoading(true)
    setError(null)
    setMirrorConflict(null)

    try {
      await onConfirmUnits(items, selectedWalletId)
      setShowSuccess(true)
    } catch (err: unknown) {
      const parsed = parseApiError(err, 'Ошибка при покупке монет')
      setError(parsed.message)
      setMirrorConflict(parsed.mirrorConflict)
    } finally {
      setIsLoading(false)
    }
  }

  const handleConfirm = mode === 'usd' ? handleConfirmUsd : handleConfirmUnits

  const handleClose = () => {
    setMode('usd')
    setAmount(suggestedAmount > 0 ? String(suggestedAmount) : '')
    setPositions([
      { id: makeId(), symbol: '', units: '', price: '', useCurrentPrice: true },
    ])
    setSelectedWalletId(defaultWalletId)
    setShowSuccess(false)
    setError(null)
    onClose()
  }

  const updatePosition = (id: string, patch: Partial<PositionRow>) => {
    setPositions((prev) =>
      prev.map((p) => (p.id === id ? { ...p, ...patch } : p))
    )
  }

  const addPosition = () => {
    setPositions((prev) => [
      ...prev,
      { id: makeId(), symbol: '', units: '', price: '', useCurrentPrice: true },
    ])
  }

  const removePosition = (id: string) => {
    setPositions((prev) => (prev.length > 1 ? prev.filter((p) => p.id !== id) : prev))
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
            {mode === 'usd' ? 'Взнос внесён' : 'Покупка зафиксирована'}
          </h2>
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

  const showModeSwitcher = !!onConfirmUnits
  const modalSize = mode === 'units' ? 'xl' : 'md'

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Пополнить портфель" size={modalSize}>
      <div className="space-y-4">
        {showModeSwitcher && (
          <div className="grid grid-cols-2 gap-2 p-1 bg-gray-100 rounded-lg">
            <button
              type="button"
              onClick={() => {
                setMode('usd')
                setError(null)
              }}
              className={`flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === 'usd'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <DollarSign className="w-4 h-4" />
              По сумме $ (DCA)
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('units')
                setError(null)
              }}
              className={`flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === 'units'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Coins className="w-4 h-4" />
              По монетам
            </button>
          </div>
        )}

        {mode === 'usd' && (
          <>
            <p className="text-sm text-gray-600">
              Зафиксируйте внесённую сумму. Консультант будет учитывать её при
              рекомендациях.
            </p>
            {totalPlanned > 0 && (
              <p className="text-sm text-gray-500">
                Вложено: {formatCurrency(investedSoFar)} из {formatCurrency(totalPlanned)}
              </p>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Сумма ($)
              </label>
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
          </>
        )}

        {mode === 'units' && (
          <>
            <p className="text-sm text-gray-600">
              Укажите фактически купленное количество монет. Можно добавить
              несколько позиций. По умолчанию используется текущая рыночная цена.
            </p>

            <WalletSelector
              wallets={wallets}
              value={selectedWalletId}
              onChange={setSelectedWalletId}
              label="Кошелёк зачисления"
              disabled={isLoading}
              hint="Монеты будут добавлены на выбранный кошелёк."
            />

            {assetsLoading && (
              <p className="text-sm text-gray-500">Загрузка списка монет…</p>
            )}
            {assetsError && <Alert variant="error">{assetsError}</Alert>}

            {!assetsLoading && !assetsError && (
              <div className="space-y-3">
                {positions.map((p, idx) => {
                  const currentPrice = priceBySymbol[p.symbol] ?? 0
                  const customPrice = parseFloat((p.price || '').replace(',', '.'))
                  const effectivePrice =
                    p.useCurrentPrice || isNaN(customPrice) || customPrice <= 0
                      ? currentPrice
                      : customPrice
                  const unitsNum = parseFloat((p.units || '').replace(',', '.'))
                  const lineValue =
                    !isNaN(unitsNum) && unitsNum > 0 ? unitsNum * effectivePrice : 0

                  return (
                    <div
                      key={p.id}
                      className="rounded-lg border border-gray-200 p-3 bg-white"
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-xs font-medium text-gray-500">
                          Позиция {idx + 1}
                        </span>
                        {positions.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removePosition(p.id)}
                            className="p-1 rounded hover:bg-red-50 text-red-500"
                            title="Удалить позицию"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Монета
                          </label>
                          <select
                            value={p.symbol}
                            onChange={(e) =>
                              updatePosition(p.id, { symbol: e.target.value })
                            }
                            className="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                          >
                            <option value="">— выбрать —</option>
                            <optgroup label="В портфеле">
                              {tradableAssets
                                .filter((a) => a.in_portfolio)
                                .map((a) => (
                                  <option key={a.symbol} value={a.symbol}>
                                    {a.symbol} — {a.name}
                                  </option>
                                ))}
                            </optgroup>
                            <optgroup label="ТОП-10">
                              {tradableAssets
                                .filter((a) => !a.in_portfolio && a.is_recommended)
                                .map((a) => (
                                  <option key={a.symbol} value={a.symbol}>
                                    {a.symbol} — {a.name}
                                  </option>
                                ))}
                            </optgroup>
                            <optgroup label="Стейблкоины">
                              {tradableAssets
                                .filter(
                                  (a) =>
                                    !a.in_portfolio && !a.is_recommended && a.is_stable
                                )
                                .map((a) => (
                                  <option key={a.symbol} value={a.symbol}>
                                    {a.symbol} — {a.name}
                                  </option>
                                ))}
                            </optgroup>
                          </select>
                          {p.symbol && currentPrice > 0 && (
                            <p className="text-xs text-gray-500 mt-1">
                              Курс: {formatCurrency(currentPrice)}
                            </p>
                          )}
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Количество
                          </label>
                          <input
                            type="number"
                            min="0"
                            step="0.00000001"
                            value={p.units}
                            onChange={(e) =>
                              updatePosition(p.id, { units: e.target.value })
                            }
                            placeholder="0.00"
                            className="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Цена покупки ($)
                          </label>
                          <input
                            type="number"
                            min="0"
                            step="0.00000001"
                            value={p.useCurrentPrice ? '' : p.price}
                            disabled={p.useCurrentPrice}
                            onChange={(e) =>
                              updatePosition(p.id, { price: e.target.value })
                            }
                            placeholder={
                              p.useCurrentPrice && currentPrice > 0
                                ? currentPrice.toString()
                                : '0.00'
                            }
                            className="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm disabled:bg-gray-50 disabled:text-gray-500"
                          />
                          <label className="flex items-center gap-1.5 mt-1 text-xs text-gray-600 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={p.useCurrentPrice}
                              onChange={(e) =>
                                updatePosition(p.id, {
                                  useCurrentPrice: e.target.checked,
                                })
                              }
                              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                            />
                            По текущему курсу
                          </label>
                        </div>
                      </div>

                      {lineValue > 0 && (
                        <p className="text-xs text-gray-600 mt-2">
                          Стоимость позиции:{' '}
                          <span className="font-medium text-gray-900">
                            {formatCurrency(lineValue)}
                          </span>
                        </p>
                      )}
                    </div>
                  )
                })}

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={addPosition}
                  type="button"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Добавить ещё монету
                </Button>

                <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-sm">
                  <span className="text-gray-600">Всего к зачислению: </span>
                  <span className="font-semibold text-gray-900">
                    {formatCurrency(totalUsdUnits)}
                  </span>
                </div>
              </div>
            )}
          </>
        )}

        {mirrorConflict ? (
          <Alert
            variant="warning"
            title="Похоже, это та же операция, что и корректировка"
          >
            <p className="mb-1">{error}</p>
            <p className="text-xs opacity-80">
              {mirrorConflict.kind === 'contribution' ? 'Контрибьюшн' : 'Корректировка'}{' '}
              #{mirrorConflict.id} от {mirrorConflict.date} по {mirrorConflict.symbol}{' '}
              на ~{formatCurrency(mirrorConflict.value_usd)}.
            </p>
          </Alert>
        ) : (
          error && <Alert variant="error">{error}</Alert>
        )}
      </div>
      <ModalFooter>
        <Button variant="secondary" onClick={handleClose}>
          Отмена
        </Button>
        <Button
          variant="primary"
          onClick={handleConfirm}
          disabled={isLoading || (mode === 'units' && assetsLoading)}
        >
          {isLoading ? 'Сохранение...' : mode === 'usd' ? 'Внести' : 'Купить'}
        </Button>
      </ModalFooter>
    </Modal>
  )
}
