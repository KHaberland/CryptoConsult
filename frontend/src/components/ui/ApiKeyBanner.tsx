'use client'

import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { ChevronDown, ChevronUp } from 'lucide-react'

const ENV_TEMPLATE = `# OpenRouter API (обязательно для ИИ-консультанта)
OPENROUTER_API_KEY=

# Coinglass API — требуется ПЛАТНЫЙ ключ (от $29/мес). ETF, ликвидации в блоках Деривативы и Институциональный фактор.
# COINGLASS_API_KEY=your_key

# Glassnode API (опционально — для MVRV, SOPR, exchange flow, LTH в блоке Он-чейн)
# GLASSNODE_API_KEY=your_key

# FRED API (опционально — для ФРС, DXY, 10Y Treasury, S&P500 в блоке Макроэкономика)
# Бесплатный ключ: https://fredaccount.stlouisfed.org/apikeys
FRED_API_KEY=

# CryptoPanic API (бесплатный DEVELOPER) — новости в блоке Институциональный фактор.
# Ограничения: News Delay 24ч, 20 новостей, 2 запроса/сек, 100 запросов/мес, только Title+Description.
CRYPTOPANIC_API_KEY=

OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=`

interface ApiKeyBannerProps {
  variant?: 'chat' | 'dashboard'
  className?: string
}

export function ApiKeyBanner({ variant = 'chat', className }: ApiKeyBannerProps) {
  const [expanded, setExpanded] = useState(false)

  const hint =
    variant === 'chat'
      ? 'Без ключа ИИ‑консультант не будет работать.'
      : 'Без ключа прогнозы и анализ BTC не будут работать.'

  return (
    <Alert variant="warning" className={className}>
      <div>
        <strong>Введите свой API‑ключ в настройках.</strong> Создайте файл backend/.env и добавьте ключи. {hint}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-2 flex items-center gap-1 text-sm font-medium text-yellow-800 underline hover:no-underline"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-4 h-4" />
              Скрыть шаблон .env
            </>
          ) : (
            <>
              <ChevronDown className="w-4 h-4" />
              Показать шаблон .env
            </>
          )}
        </button>
        {expanded && (
          <pre className="mt-3 p-4 bg-yellow-100/50 border border-yellow-300 rounded text-xs overflow-x-auto text-yellow-900 font-mono whitespace-pre">
            {ENV_TEMPLATE}
          </pre>
        )}
      </div>
    </Alert>
  )
}
