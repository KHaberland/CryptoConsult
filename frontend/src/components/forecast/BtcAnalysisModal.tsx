'use client'

import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { BtcAnalysisContent } from './BtcAnalysisContent'

export interface BtcAnalysisSection {
  title: string
  content: string
}

export interface ScenarioItem {
  probability: number
  description: string
  price_range?: string
  conditions?: string
  triggers?: string
}

export interface ScenarioForecast {
  base: ScenarioItem
  bullish: ScenarioItem
  negative: ScenarioItem
}

export interface ProfileAllocation {
  allocation: string
  description: string
}

export interface ProfileRecommendations {
  conservative: ProfileAllocation
  moderate: ProfileAllocation
  aggressive: ProfileAllocation
  user_profile_type?: string
  user_recommendation?: string
}

export interface BtcAnalysisData {
  error?: string
  sections: BtcAnalysisSection[]
  scenario_forecast?: ScenarioForecast | null
  profile_recommendations?: ProfileRecommendations | null
  forecast_6months: string
  buy_recommendation: string
  signal?: 'BUY' | 'HOLD' | 'REDUCE'
  signal_score?: number
  signal_blocks?: Record<string, number>
}

interface BtcAnalysisModalProps {
  isOpen: boolean
  onClose: () => void
  data: BtcAnalysisData | null
  isLoading: boolean
  error: string | null
}

export function BtcAnalysisModal({
  isOpen,
  onClose,
  data,
  isLoading,
  error,
}: BtcAnalysisModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Анализ BTC"
      size="xl"
      className="max-w-2xl max-h-[85vh] flex flex-col"
    >
      <div className="flex flex-col max-h-[70vh] min-h-[120px] -mx-6 -mb-4">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-12 px-6">
            <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-primary-600" />
            <p className="mt-3 text-gray-600 text-center">
              Происходит многофакторный анализ, который занимает много времени, пожалуйста подождите.
            </p>
          </div>
        ) : error || data?.error ? (
          <div className="py-6 px-6 text-center">
            <p className="text-red-600">{error || data?.error}</p>
            <Button variant="secondary" className="mt-4" onClick={onClose}>
              Закрыть
            </Button>
          </div>
        ) : data ? (
          <>
            <div className="overflow-y-auto flex-1 min-h-0 px-6 pb-4">
              <BtcAnalysisContent data={data} />
            </div>
            <div className="shrink-0 pt-4 mt-4 border-t px-6 pb-6 flex justify-end">
              <Button variant="primary" onClick={onClose}>
                Закрыть
              </Button>
            </div>
          </>
        ) : (
          <div className="py-6 px-6 text-center text-gray-500">
            Нет данных для отображения
          </div>
        )}
      </div>
    </Modal>
  )
}
