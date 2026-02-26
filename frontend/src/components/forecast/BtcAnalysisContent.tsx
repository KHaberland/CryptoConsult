'use client'

import { TrendingUp, Bitcoin, ThumbsUp, Minus, ThumbsDown, User } from 'lucide-react'
import type { BtcAnalysisData } from './BtcAnalysisModal'

function ScenarioCard({
  emoji,
  title,
  scenario,
  extraKey,
}: {
  emoji: string
  title: string
  scenario: { probability?: number; description?: string; price_range?: string; conditions?: string; triggers?: string }
  extraKey: 'price_range' | 'conditions' | 'triggers'
}) {
  const sc = scenario || {}
  const extra = (sc[extraKey] as string) || ''
  const labels: Record<string, string> = {
    price_range: 'Ценовой диапазон',
    conditions: 'Условия реализации',
    triggers: 'Триггеры падения',
  }
  return (
    <div className="p-3 rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center gap-2 mb-1">
        <span>{emoji}</span>
        <span className="font-medium text-gray-900">{title}</span>
        <span className="text-sm text-gray-500">({sc.probability ?? 0}%)</span>
      </div>
      {sc.description && <p className="text-sm text-gray-700 mb-1">{sc.description}</p>}
      {extra && (
        <p className="text-xs text-gray-600 mt-1">
          <span className="font-medium">{labels[extraKey]}:</span> {extra}
        </p>
      )}
    </div>
  )
}

function ProfileCard({
  title,
  rec,
}: {
  title: string
  rec: { allocation?: string; description?: string }
}) {
  const r = rec || {}
  if (!r.allocation && !r.description) return null
  return (
    <div className="p-3 rounded-lg border border-gray-200 bg-white">
      <div className="font-medium text-gray-900 mb-1">{title}</div>
      {r.allocation && (
        <p className="text-sm text-gray-700 font-mono">{r.allocation}</p>
      )}
      {r.description && (
        <p className="text-xs text-gray-600 mt-1">{r.description}</p>
      )}
    </div>
  )
}

function SignalBadge({ signal, score }: { signal: string; score?: number }) {
  const config = {
    BUY: { icon: ThumbsUp, bg: 'bg-green-100', border: 'border-green-300', text: 'text-green-800', label: 'Покупка' },
    HOLD: { icon: Minus, bg: 'bg-amber-100', border: 'border-amber-300', text: 'text-amber-800', label: 'Удержание' },
    REDUCE: { icon: ThumbsDown, bg: 'bg-red-100', border: 'border-red-300', text: 'text-red-800', label: 'Снижение' },
  }
  const c = config[signal as keyof typeof config] || config.HOLD
  const Icon = c.icon
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border-2 ${c.bg} ${c.border} ${c.text}`}>
      <Icon className="w-5 h-5" />
      <span className="font-semibold">{c.label}</span>
      {score != null && <span className="text-sm opacity-80">({score})</span>}
    </div>
  )
}

interface BtcAnalysisContentProps {
  data: BtcAnalysisData
  /** Компактный режим: меньше разделов, без полного списка sections */
  compact?: boolean
}

export function BtcAnalysisContent({ data, compact = false }: BtcAnalysisContentProps) {
  return (
    <div className="space-y-4">
      {data.signal && (
        <div className="flex items-center justify-between gap-4 p-4 rounded-lg border-2 border-primary-200 bg-primary-50">
          <div>
            <p className="text-sm font-medium text-primary-800 mb-1">Сигнал по алгоритму</p>
            <p className="text-xs text-primary-600">
              {data.signal_blocks && Object.keys(data.signal_blocks).length > 0
                ? `Блоки: A=${data.signal_blocks.A ?? '-'} B=${data.signal_blocks.B ?? '-'} C=${data.signal_blocks.C ?? '-'} D=${data.signal_blocks.D ?? '-'} E=${data.signal_blocks.E ?? '-'}`
                : 'Структура, импульс, деривативы, он-чейн, макро'}
            </p>
          </div>
          <SignalBadge signal={data.signal} score={data.signal_score} />
        </div>
      )}

      {!compact && data.sections
        ?.filter(
          (s) =>
            (!data.scenario_forecast || !s.title.includes('9. Сценарный')) &&
            (!data.profile_recommendations || !s.title.includes('10. Инвестиционные'))
        )
        .map((section, idx) => (
          <div
            key={idx}
            className="p-4 rounded-lg border border-gray-200 bg-gray-50/50"
          >
            <h3 className="font-semibold text-gray-900 mb-2">{section.title}</h3>
            <p className="text-sm text-gray-700 whitespace-pre-line">{section.content}</p>
          </div>
        ))}

      {data.scenario_forecast && (
        <div className="p-4 rounded-lg border-2 border-primary-200 bg-primary-50/50 space-y-3">
          <h3 className="font-semibold text-primary-900 mb-3">9. Сценарный прогноз</h3>
          <div className="grid gap-3 sm:grid-cols-1">
            <ScenarioCard
              emoji="🟢"
              title="Базовый"
              scenario={data.scenario_forecast.base}
              extraKey="price_range"
            />
            <ScenarioCard
              emoji="🟡"
              title="Альтернативный бычий"
              scenario={data.scenario_forecast.bullish}
              extraKey="conditions"
            />
            <ScenarioCard
              emoji="🔴"
              title="Негативный"
              scenario={data.scenario_forecast.negative}
              extraKey="triggers"
            />
          </div>
        </div>
      )}

      {data.profile_recommendations && (
        <div className="p-4 rounded-lg border-2 border-emerald-200 bg-emerald-50/50 space-y-3">
          <h3 className="font-semibold text-emerald-900 mb-3">
            10. Инвестиционные рекомендации по профилю
          </h3>
          <div className="grid gap-3 sm:grid-cols-1">
            <ProfileCard
              title="Консервативный"
              rec={data.profile_recommendations.conservative}
            />
            <ProfileCard
              title="Умеренный"
              rec={data.profile_recommendations.moderate}
            />
            <ProfileCard
              title="Агрессивный"
              rec={data.profile_recommendations.aggressive}
            />
          </div>
          {data.profile_recommendations.user_recommendation && (
            <div className="mt-3 p-3 rounded-lg border-2 border-emerald-300 bg-emerald-100/80">
              <div className="flex items-center gap-2 mb-1">
                <User className="w-4 h-4 text-emerald-700" />
                <span className="font-medium text-emerald-900">
                  Рекомендация для вас
                  {data.profile_recommendations.user_profile_type && (
                    <span className="text-emerald-700 font-normal">
                      {' '}
                      ({data.profile_recommendations.user_profile_type})
                    </span>
                  )}
                </span>
              </div>
              <p className="text-sm text-emerald-800 whitespace-pre-line">
                {data.profile_recommendations.user_recommendation}
              </p>
            </div>
          )}
        </div>
      )}

      {data.forecast_6months && (
        <div className="p-4 rounded-lg border-2 border-primary-200 bg-primary-50">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-primary-600" />
            <span className="font-semibold text-primary-800">Прогноз на 6 месяцев</span>
          </div>
          <p className="text-sm text-gray-700 whitespace-pre-line">
            {data.forecast_6months}
          </p>
        </div>
      )}

      {data.buy_recommendation && (
        <div className="p-4 rounded-lg border-2 border-amber-200 bg-amber-50">
          <div className="flex items-center gap-2 mb-2">
            <Bitcoin className="w-5 h-5 text-amber-600" />
            <span className="font-semibold text-amber-800">
              Рекомендация: стоит ли покупать BTC
            </span>
          </div>
          <p className="text-sm text-gray-700 whitespace-pre-line">
            {data.buy_recommendation}
          </p>
        </div>
      )}
    </div>
  )
}
