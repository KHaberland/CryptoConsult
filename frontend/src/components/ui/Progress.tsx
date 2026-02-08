'use client'

import { cn } from '@/lib/utils'

interface ProgressProps {
  value: number
  max?: number
  className?: string
  showLabel?: boolean
}

export function Progress({ value, max = 100, className, showLabel = false }: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)
  
  return (
    <div className={cn('w-full', className)}>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-primary-600 rounded-full transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <p className="text-sm text-gray-600 mt-1 text-right">{percentage.toFixed(0)}%</p>
      )}
    </div>
  )
}
