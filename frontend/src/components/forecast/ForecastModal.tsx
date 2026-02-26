'use client'

import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export interface ForecastScenario {
  description: string
  probability: number
}

export interface ForecastData {
  days: number
  positive: ForecastScenario
  negative: ForecastScenario
  base: ForecastScenario
  portfolio_outlook?: {
    most_likely_scenario: string
    description: string
  }
}

interface ForecastModalProps {
  isOpen: boolean
  onClose: () => void
  forecast: ForecastData | null
  isLoading: boolean
  error: string | null
}

export function ForecastModal({
  isOpen,
  onClose,
  forecast,
  isLoading,
  error,
}: ForecastModalProps) {
  const periodLabel =
    forecast?.days === 30
      ? '30 дней'
      : forecast?.days === 90
        ? '90 дней'
        : forecast?.days
          ? `${forecast.days} дней`
          : ''

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={forecast ? `Прогноз на ${periodLabel}` : 'Прогноз рынка'}
      size="xl"
    >
      <div className="flex flex-col max-h-[60vh] min-h-[120px]">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-primary-600" />
            <p className="mt-3 text-gray-600">Анализ рынка криптоконсультантом...</p>
          </div>
        ) : error ? (
          <div className="py-6 text-center">
            <p className="text-red-600">{error}</p>
            <Button variant="secondary" className="mt-4" onClick={onClose}>
              Закрыть
            </Button>
          </div>
        ) : forecast ? (
          <>
            <div className="overflow-y-auto flex-1 min-h-0 pr-1 -mr-1 space-y-4">
            <div className="p-4 rounded-lg border-2 border-green-200 bg-green-50">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-5 h-5 text-green-600" />
                <span className="font-semibold text-green-800">Позитивный сценарий</span>
                <span className="ml-auto text-sm font-medium text-green-700 bg-green-200 px-2 py-0.5 rounded">
                  {forecast.positive.probability}%
                </span>
              </div>
              <p className="text-sm text-gray-700">{forecast.positive.description}</p>
            </div>
            <div className="p-4 rounded-lg border-2 border-red-200 bg-red-50">
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown className="w-5 h-5 text-red-600" />
                <span className="font-semibold text-red-800">Негативный сценарий</span>
                <span className="ml-auto text-sm font-medium text-red-700 bg-red-200 px-2 py-0.5 rounded">
                  {forecast.negative.probability}%
                </span>
              </div>
              <p className="text-sm text-gray-700">{forecast.negative.description}</p>
            </div>
            <div className="p-4 rounded-lg border-2 border-gray-200 bg-gray-50">
              <div className="flex items-center gap-2 mb-2">
                <Minus className="w-5 h-5 text-gray-600" />
                <span className="font-semibold text-gray-800">Базовый сценарий</span>
                <span className="ml-auto text-sm font-medium text-gray-700 bg-gray-200 px-2 py-0.5 rounded">
                  {forecast.base.probability}%
                </span>
              </div>
              <p className="text-sm text-gray-700">{forecast.base.description}</p>
            </div>
            {forecast.portfolio_outlook && (
              <div className="p-4 rounded-lg border-2 border-primary-200 bg-primary-50">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold text-primary-800">
                    Портфель через {periodLabel}
                  </span>
                  <span className="ml-auto text-xs text-primary-600">
                    при{' '}
                    {forecast.portfolio_outlook.most_likely_scenario === 'positive'
                      ? 'позитивном'
                      : forecast.portfolio_outlook.most_likely_scenario === 'negative'
                        ? 'негативном'
                        : 'базовом'}{' '}
                    сценарии
                  </span>
                </div>
                <p className="text-sm text-gray-700 whitespace-pre-line">
                  {forecast.portfolio_outlook.description}
                </p>
              </div>
            )}
            </div>
            <div className="shrink-0 pt-4 mt-4 border-t flex justify-end">
              <Button variant="primary" onClick={onClose}>
                Закрыть
              </Button>
            </div>
          </>
        ) : (
          <div className="py-6 text-center text-gray-500">
            Нет данных для отображения
          </div>
        )}
      </div>
    </Modal>
  )
}
