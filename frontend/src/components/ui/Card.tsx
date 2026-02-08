'use client'

import { cn } from '@/lib/utils'

interface CardProps {
  className?: string
  children: React.ReactNode
}

export function Card({ className, children }: CardProps) {
  return (
    <div className={cn('bg-white rounded-xl shadow-lg p-6', className)}>
      {children}
    </div>
  )
}

export function CardHeader({ className, children }: CardProps) {
  return (
    <div className={cn('mb-4', className)}>
      {children}
    </div>
  )
}

export function CardTitle({ className, children }: CardProps) {
  return (
    <h3 className={cn('text-xl font-semibold text-gray-900', className)}>
      {children}
    </h3>
  )
}

export function CardContent({ className, children }: CardProps) {
  return (
    <div className={cn('', className)}>
      {children}
    </div>
  )
}
