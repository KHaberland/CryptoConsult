'use client'

import { useEffect, useMemo } from 'react'
import { Wallet as WalletIcon } from 'lucide-react'
import type { Wallet } from '@/services/api'

export interface WalletSelectorProps {
  /** Полный список кошельков из portfolioStore. */
  wallets: Wallet[]
  /** Выбранный wallet_id. `null` — ещё не выбран. */
  value: number | null
  /** Вызывается при ручном выборе и при авто-выборе единственного кандидата. */
  onChange: (walletId: number) => void
  /** Подпись над селектом. По умолчанию — «Кошелёк». */
  label?: string
  /** Заблокировать селект (например, во время сабмита). */
  disabled?: boolean
  /**
   * Фильтр кандидатов. Используется в swap/withdraw, чтобы показывать только
   * кошельки, на которых есть нужный актив.
   */
  filterPredicate?: (wallet: Wallet) => boolean
  /**
   * Дополнительный текст справа от названия кошелька в опции. Например,
   * «— доступно 0.42 BTC».
   */
  getOptionSuffix?: (wallet: Wallet) => string | null | undefined
  /**
   * Если `true` (по умолчанию) и после фильтрации остался ровно один кошелёк —
   * UI скрыт, но `onChange` вызывается автоматически.
   */
  hideWhenSingle?: boolean
  /** Текст-подсказка под селектом. */
  hint?: string | null
  /** Сообщение, если после фильтрации не осталось ни одного кандидата. */
  emptyMessage?: string
  /** Дополнительные классы для обёртки. */
  className?: string
  /** id поля (если нужно связать с label извне). */
  id?: string
}

const SELECT_CLASSES =
  'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm disabled:bg-gray-50 disabled:text-gray-500'

function sortCandidates(wallets: Wallet[]): Wallet[] {
  return [...wallets].sort((a, b) => {
    if (a.is_default !== b.is_default) {
      return a.is_default ? -1 : 1
    }
    return a.name.localeCompare(b.name)
  })
}

/**
 * Переиспользуемый селектор кошелька для contribute / swap / withdraw.
 *
 * Поведение:
 *  - 0 кандидатов  → рендерится `emptyMessage` (если задан), `onChange` не вызывается;
 *  - 1 кандидат и `hideWhenSingle` (по умолчанию) → UI скрыт, `value` авто-выставляется;
 *  - >1 кандидат   → обычный `<select>`.
 */
export function WalletSelector({
  wallets,
  value,
  onChange,
  label = 'Кошелёк',
  disabled = false,
  filterPredicate,
  getOptionSuffix,
  hideWhenSingle = true,
  hint,
  emptyMessage,
  className,
  id,
}: WalletSelectorProps) {
  const candidates = useMemo(() => {
    const filtered = filterPredicate ? wallets.filter(filterPredicate) : wallets
    return sortCandidates(filtered)
  }, [wallets, filterPredicate])

  // Автосинхронизация value с набором кандидатов:
  //   - выбранный кошелёк выпал из фильтра  → сбрасываем на единственного, если он один,
  //     иначе оставляем «не выбрано» — пусть пользователь выберет вручную;
  //   - кандидат ровно один и value другой/пустой → выставляем его.
  useEffect(() => {
    if (candidates.length === 0) return

    const currentIsValid =
      value !== null && candidates.some((w) => w.id === value)

    if (candidates.length === 1) {
      if (!currentIsValid || value !== candidates[0].id) {
        onChange(candidates[0].id)
      }
      return
    }

    if (value !== null && !currentIsValid) {
      // Не выбираем «случайного» — пусть пользователь решит сам.
      // Но чтобы не блокировать сабмит «-1» / устаревшим id, переключаемся
      // на дефолтный кошелёк, если он есть в кандидатах.
      const defaultCandidate = candidates.find((w) => w.is_default)
      if (defaultCandidate) {
        onChange(defaultCandidate.id)
      }
    }
  }, [candidates, value, onChange])

  // Без кандидатов — компактный hint (или ничего, если сообщение не задано).
  if (candidates.length === 0) {
    if (!emptyMessage) return null
    return (
      <div className={className}>
        {label && (
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {label}
          </label>
        )}
        <div className="flex items-start gap-2 text-xs text-gray-500 px-3 py-2 border border-dashed border-gray-200 rounded-lg bg-gray-50">
          <WalletIcon className="w-4 h-4 mt-0.5 shrink-0 text-gray-400" />
          <span>{emptyMessage}</span>
        </div>
      </div>
    )
  }

  // Один кандидат и `hideWhenSingle` — UI скрываем (см. PLAN06 F9).
  if (candidates.length === 1 && hideWhenSingle) {
    return null
  }

  const selectValue = value !== null && candidates.some((w) => w.id === value)
    ? String(value)
    : ''

  return (
    <div className={className}>
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          {label}
        </label>
      )}
      <select
        id={id}
        value={selectValue}
        onChange={(e) => {
          const next = e.target.value
          if (!next) return
          const parsed = Number(next)
          if (Number.isFinite(parsed)) {
            onChange(parsed)
          }
        }}
        disabled={disabled}
        className={SELECT_CLASSES}
      >
        {selectValue === '' && <option value="">— выбрать кошелёк —</option>}
        {candidates.map((w) => {
          const suffix = getOptionSuffix?.(w)
          return (
            <option key={w.id} value={w.id}>
              {w.name}
              {w.is_default ? ' (по умолчанию)' : ''}
              {suffix ? ` ${suffix}` : ''}
            </option>
          )
        })}
      </select>
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  )
}

export default WalletSelector
