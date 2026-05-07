'use client'

import { Pencil, Trash2, Wallet as WalletIcon } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { cn, formatCurrency, formatUnits } from '@/lib/utils'
import type { Wallet, WalletHolding, WalletType } from '@/services/api'

interface WalletCardProps {
  wallet: Wallet
  onEdit?: (wallet: Wallet) => void
  onDelete?: (wallet: Wallet) => void
  onAdjustHolding?: (wallet: Wallet, holding: WalletHolding) => void
  className?: string
}

const TYPE_LABELS: Record<WalletType, string> = {
  exchange: 'Биржа',
  hot: 'Горячий',
  cold: 'Холодный',
  bank: 'Банк',
  other: 'Другое',
}

const TYPE_BADGE_CLASSES: Record<WalletType, string> = {
  exchange: 'bg-blue-100 text-blue-700',
  hot: 'bg-orange-100 text-orange-700',
  cold: 'bg-slate-100 text-slate-700',
  bank: 'bg-emerald-100 text-emerald-700',
  other: 'bg-gray-100 text-gray-700',
}

function toNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined) return 0
  const n = typeof value === 'number' ? value : parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

export function WalletCard({
  wallet,
  onEdit,
  onDelete,
  onAdjustHolding,
  className,
}: WalletCardProps) {
  const holdings = wallet.holdings ?? []
  const totalUsd = toNumber(wallet.total_value_usd)
  const canDelete = !wallet.is_default

  return (
    <Card className={cn('p-5', className)}>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className="shrink-0 w-10 h-10 rounded-lg bg-primary-50 text-primary-600 flex items-center justify-center">
            <WalletIcon className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-lg font-semibold text-gray-900 truncate">
                {wallet.name}
              </h3>
              {wallet.is_default && (
                <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-primary-100 text-primary-700">
                  По умолчанию
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <span
                className={cn(
                  'inline-block px-2 py-0.5 text-xs font-medium rounded-full',
                  TYPE_BADGE_CLASSES[wallet.type]
                )}
              >
                {TYPE_LABELS[wallet.type]}
              </span>
              {wallet.note && (
                <span className="text-xs text-gray-500 truncate">
                  {wallet.note}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {onEdit && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onEdit(wallet)}
              aria-label="Редактировать кошелёк"
            >
              <Pencil className="w-4 h-4 mr-1" />
              Редактировать
            </Button>
          )}
          {canDelete && onDelete && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => onDelete(wallet)}
              aria-label="Удалить кошелёк"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Удалить
            </Button>
          )}
        </div>
      </div>

      {holdings.length === 0 ? (
        <div className="text-sm text-gray-500 py-3 border-t border-gray-100">
          Активов пока нет
        </div>
      ) : (
        <div className="border-t border-gray-100 pt-3">
          <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 uppercase tracking-wide pb-2">
            <div className="col-span-4">Актив</div>
            <div className="col-span-4 text-right">Кол-во</div>
            <div className="col-span-4 text-right">USD</div>
          </div>
          <ul className="divide-y divide-gray-100">
            {holdings.map((h) => {
              const units = toNumber(h.units)
              const valueUsd = toNumber(h.value_usd)
              return (
                <li
                  key={h.id}
                  className="grid grid-cols-12 gap-2 py-2 items-center text-sm"
                >
                  <div className="col-span-4 font-medium text-gray-900">
                    {h.symbol}
                  </div>
                  <div className="col-span-4 text-right text-gray-700 tabular-nums">
                    {formatUnits(units)}
                  </div>
                  <div className="col-span-3 text-right text-gray-700 tabular-nums">
                    {formatCurrency(valueUsd)}
                  </div>
                  <div className="col-span-1 flex justify-end">
                    {onAdjustHolding && (
                      <button
                        type="button"
                        onClick={() => onAdjustHolding(wallet, h)}
                        className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700"
                        aria-label={`Скорректировать ${h.symbol}`}
                        title="Скорректировать баланс"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
        <span className="text-sm text-gray-500">Всего</span>
        <span className="text-lg font-semibold text-gray-900 tabular-nums">
          {formatCurrency(totalUsd)}
        </span>
      </div>
    </Card>
  )
}

export default WalletCard
