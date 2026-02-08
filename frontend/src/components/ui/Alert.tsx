'use client'

import { cn } from '@/lib/utils'
import { AlertCircle, CheckCircle, Info, XCircle } from 'lucide-react'

interface AlertProps {
  variant?: 'info' | 'success' | 'warning' | 'error'
  title?: string
  children: React.ReactNode
  className?: string
}

export function Alert({ variant = 'info', title, children, className }: AlertProps) {
  const variants = {
    info: {
      container: 'bg-blue-50 border-blue-200 text-blue-800',
      icon: Info,
    },
    success: {
      container: 'bg-green-50 border-green-200 text-green-800',
      icon: CheckCircle,
    },
    warning: {
      container: 'bg-yellow-50 border-yellow-200 text-yellow-800',
      icon: AlertCircle,
    },
    error: {
      container: 'bg-red-50 border-red-200 text-red-800',
      icon: XCircle,
    },
  }
  
  const { container, icon: Icon } = variants[variant]
  
  return (
    <div className={cn('border rounded-lg p-4', container, className)}>
      <div className="flex">
        <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
        <div>
          {title && <h4 className="font-medium mb-1">{title}</h4>}
          <div className="text-sm">{children}</div>
        </div>
      </div>
    </div>
  )
}
