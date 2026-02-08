'use client'

import { cn } from '@/lib/utils'

interface SliderProps {
  label?: string
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step?: number
  showValue?: boolean
  valuePrefix?: string
  valueSuffix?: string
  className?: string
}

export function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  showValue = true,
  valuePrefix = '',
  valueSuffix = '',
  className,
}: SliderProps) {
  const percentage = ((value - min) / (max - min)) * 100
  
  return (
    <div className={cn('w-full', className)}>
      {(label || showValue) && (
        <div className="flex justify-between items-center mb-2">
          {label && (
            <label className="text-sm font-medium text-gray-700">{label}</label>
          )}
          {showValue && (
            <span className="text-sm font-semibold text-primary-600">
              {valuePrefix}{value}{valueSuffix}
            </span>
          )}
        </div>
      )}
      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-full appearance-none cursor-pointer
                     [&::-webkit-slider-thumb]:appearance-none
                     [&::-webkit-slider-thumb]:w-5
                     [&::-webkit-slider-thumb]:h-5
                     [&::-webkit-slider-thumb]:bg-primary-600
                     [&::-webkit-slider-thumb]:rounded-full
                     [&::-webkit-slider-thumb]:cursor-pointer
                     [&::-webkit-slider-thumb]:shadow-md
                     [&::-webkit-slider-thumb]:transition-transform
                     [&::-webkit-slider-thumb]:hover:scale-110"
          style={{
            background: `linear-gradient(to right, #0284c7 0%, #0284c7 ${percentage}%, #e5e7eb ${percentage}%, #e5e7eb 100%)`,
          }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>{valuePrefix}{min}{valueSuffix}</span>
        <span>{valuePrefix}{max}{valueSuffix}</span>
      </div>
    </div>
  )
}
