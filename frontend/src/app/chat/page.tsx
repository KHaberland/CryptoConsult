'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { useChatStore, RebalanceSuggestion } from '@/store/chatStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { Header } from '@/components/layout/Header'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { PortfolioRebalanceModal } from '@/components/portfolio/PortfolioRebalanceModal'
import { formatDateTime } from '@/lib/utils'
import { portfolioApi } from '@/services/api'
import {
  Send,
  Trash2,
  Loader2,
  Bot,
  User,
  RefreshCw,
} from 'lucide-react'

const QUICK_COMMANDS = [
  {
    cmd: '/status',
    label: 'Статус',
    icon: '📊',
    tooltip: 'Текущее состояние вашего портфеля: стоимость, распределение активов и динамика. Позволяет быстро оценить общую картину инвестиций.',
  },
  {
    cmd: '/recommendation',
    label: 'Рекомендация',
    icon: '💡',
    tooltip: 'Персональные рекомендации консультанта на основе вашего профиля риска и рыночной ситуации. Помогает принять обоснованные решения.',
  },
  {
    cmd: '/risk',
    label: 'Риски',
    icon: '⚠️',
    tooltip: 'Анализ рисков вашего портфеля: волатильность, концентрация активов и потенциальные угрозы. Важно для понимания возможных потерь.',
  },
  {
    cmd: '/market',
    label: 'Рынок',
    icon: '📈',
    tooltip: 'Обзор рыночной ситуации: тренды, ключевые события и настроения. Контекст для принятия решений о покупке или продаже.',
  },
  {
    cmd: '/drawdown',
    label: 'Просадка',
    icon: '📉',
    tooltip: 'Анализ просадки портфеля — насколько упала стоимость от пика. Показывает максимальные потери и помогает оценить стресс-тест.',
  },
  {
    cmd: '/dca',
    label: 'DCA',
    icon: '💰',
    tooltip: 'Стратегия усреднения (Dollar Cost Averaging): планы регулярных покупок для снижения влияния волатильности на среднюю цену входа.',
  },
  {
    cmd: '/rebalance',
    label: 'Реструктуризация',
    icon: '🔄',
    tooltip: 'Рекомендации по приведению портфеля к целевому распределению. Помогает зафиксировать прибыль и перераспределить риски.',
  },
]

// Модульная переменная — сохраняется при remount в Strict Mode
let lastProcessedUrlCmd: string | null = null

export default function ChatPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { initSession, isReady } = useSessionStore()
  const { hasProfile, fetchProfile, isLoading: profileLoading } = usePortfolioStore()
  const {
    messages,
    isLoading,
    isSending,
    error,
    alert,
    rebalanceSuggestion,
    fetchHistory,
    sendMessage,
    clearHistory,
    clearError,
    showRebalanceModal,
    hideRebalanceModal,
  } = useChatStore()
  
  const { portfolioValue, fetchPortfolioValue } = usePortfolioStore()
  
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const lastShownRebalanceMsgId = useRef<number | null>(null)
  
  // Инициализация сессии
  useEffect(() => {
    initSession()
  }, [initSession])
  
  // Загрузка профиля, портфеля и истории после инициализации
  useEffect(() => {
    if (isReady) {
      fetchProfile()
      fetchPortfolioValue()
      fetchHistory()
    }
  }, [isReady, fetchProfile, fetchPortfolioValue, fetchHistory])
  
  // Редирект если нет профиля
  useEffect(() => {
    if (isReady && !profileLoading && !hasProfile) {
      router.push('/questionnaire')
    }
  }, [isReady, profileLoading, hasProfile, router])
  
  // Обработка команды из URL (модульная переменная предотвращает двойной вызов в Strict Mode)
  useEffect(() => {
    const cmd = searchParams.get('cmd')
    if (!cmd || !isReady || !hasProfile || isSending) return
    if (lastProcessedUrlCmd === cmd) return

    lastProcessedUrlCmd = cmd
    sendMessage(`/${cmd}`)
    router.replace('/chat')
  }, [searchParams, isReady, hasProfile, isSending, sendMessage, router])

  // Сброс при уходе cmd из URL
  useEffect(() => {
    if (!searchParams.get('cmd')) {
      lastProcessedUrlCmd = null
    }
  }, [searchParams])
  
  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isSending) return
    
    sendMessage(input.trim())
    setInput('')
  }
  
  const handleQuickCommand = (cmd: string) => {
    if (isSending) return
    sendMessage(cmd)
  }
  
  const handleClearHistory = async () => {
    if (confirm('Вы уверены, что хотите очистить историю чата?')) {
      await clearHistory()
    }
  }
  
  // Обработка подтверждения реструктуризации
  const handleRebalanceConfirm = async () => {
    if (!rebalanceSuggestion) return
    
    await portfolioApi.rebalance(rebalanceSuggestion.newAssets)
    // Обновляем данные портфеля
    await fetchPortfolioValue(true)
  }
  
  // Парсинг сообщения AI на предмет предложения реструктуризации
  const parseRebalanceSuggestion = (content: string): RebalanceSuggestion | null => {
    const jsonMatch = content.match(/\[REBALANCE_SUGGESTION\]([\s\S]*?)\[\/REBALANCE_SUGGESTION\]/)
    if (jsonMatch) {
      try {
        const data = JSON.parse(jsonMatch[1])
        return {
          show: true,
          newAssets: data.newAssets || [],
          currentAssets: portfolioValue?.assets?.map(a => ({
            symbol: a.symbol,
            name: a.name,
            percentage: a.percentage,
          })) || [],
        }
      } catch {
        return null
      }
    }
    return null
  }

  // Убрать JSON-блок из текста для отображения
  const stripRebalanceBlock = (text: string): string => {
    return text.replace(/\[REBALANCE_SUGGESTION\][\s\S]*?\[\/REBALANCE_SUGGESTION\]/g, '').trim()
  }
  
  const lastAssistantMessage = messages.filter(m => m.role === 'assistant').slice(-1)[0]
  const hasSuggestionInLastMessage = lastAssistantMessage?.content?.includes('[REBALANCE_SUGGESTION]')
  
  // Автоматически показывать модалку реструктуризации после ответа AI
  useEffect(() => {
    if (!hasSuggestionInLastMessage || !lastAssistantMessage || rebalanceSuggestion) return
    if (lastShownRebalanceMsgId.current === lastAssistantMessage.id) return
    const suggestion = parseRebalanceSuggestion(lastAssistantMessage.content)
    if (suggestion && suggestion.newAssets.length > 0) {
      lastShownRebalanceMsgId.current = lastAssistantMessage.id
      showRebalanceModal(suggestion)
    }
  }, [hasSuggestionInLastMessage, lastAssistantMessage?.id, rebalanceSuggestion])
  
  const handleShowRebalanceFromMessage = () => {
    if (!lastAssistantMessage) return
    const suggestion = parseRebalanceSuggestion(lastAssistantMessage.content)
    if (suggestion) {
      showRebalanceModal(suggestion)
    }
  }
  
  if (!isReady || profileLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="flex items-center justify-center h-[calc(100vh-64px)]">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }
  
  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <Header />
      
      {/* Модальное окно реструктуризации */}
      {rebalanceSuggestion && (
        <PortfolioRebalanceModal
          isOpen={rebalanceSuggestion.show}
          onClose={hideRebalanceModal}
          currentAssets={rebalanceSuggestion.currentAssets}
          newAssets={rebalanceSuggestion.newAssets}
          onConfirm={handleRebalanceConfirm}
        />
      )}
      
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-4 flex flex-col overflow-hidden">
        {/* Alerts */}
        {error && (
          <Alert variant="error" className="mb-4">
            {error}
            <button
              onClick={clearError}
              className="ml-2 text-sm underline"
            >
              Закрыть
            </button>
          </Alert>
        )}
        
        {alert && alert.alert && (
          <Alert
            variant={alert.level === 'critical' ? 'error' : 'warning'}
            title={alert.level === 'critical' ? 'Критический уровень просадки!' : 'Предупреждение о просадке'}
            className="mb-4"
          >
            {alert.message}
          </Alert>
        )}
        
        {/* Quick Commands - всегда вверху */}
        <div className="flex flex-wrap gap-2 mb-4 flex-shrink-0 overflow-visible">
          {QUICK_COMMANDS.map(({ cmd, label, icon, tooltip }, index) => (
            <div key={cmd} className="relative group">
              <button
                onClick={() => handleQuickCommand(cmd)}
                disabled={isSending}
                className="flex items-center px-3 py-1.5 bg-white border rounded-full text-sm hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <span className="mr-1">{icon}</span>
                {label}
              </button>
              <div
                role="tooltip"
                className={`absolute top-full mt-2 px-3 py-2 w-64 bg-gray-800 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50 shadow-lg ${
                  index === 0 ? 'left-0' : 'left-1/2 -translate-x-1/2'
                }`}
              >
                {tooltip}
                <div className={`absolute -top-2 border-4 border-transparent border-b-gray-800 ${
                  index === 0 ? 'left-4' : 'left-1/2 -translate-x-1/2'
                }`} />
              </div>
            </div>
          ))}
          
          {messages.length > 0 && (
            <button
              onClick={handleClearHistory}
              className="flex items-center px-3 py-1.5 bg-white border rounded-full text-sm text-red-600 hover:bg-red-50 transition-colors ml-auto"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Очистить
            </button>
          )}
        </div>
        
        {/* Chat Messages - скроллируемая область */}
        <Card className="flex-1 flex flex-col min-h-0 overflow-hidden mb-0">
          <CardContent className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <Bot className="w-16 h-16 mb-4 text-primary-200" />
                <p className="text-lg font-medium">Начните диалог</p>
                <p className="text-sm">Задайте вопрос или используйте быстрые команды</p>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                        message.role === 'user'
                          ? 'bg-primary-600 text-white rounded-br-sm'
                          : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                      }`}
                    >
                      <div className="flex items-center mb-1">
                        {message.role === 'assistant' ? (
                          <Bot className="w-4 h-4 mr-1" />
                        ) : (
                          <User className="w-4 h-4 mr-1" />
                        )}
                        <span className="text-xs opacity-70">
                          {formatDateTime(message.created_at)}
                        </span>
                      </div>
                      <div className="whitespace-pre-wrap text-sm">
                        {message.role === 'assistant' ? stripRebalanceBlock(message.content) : message.content}
                      </div>
                    </div>
                  </div>
                ))}
                
                {isSending && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                      <div className="flex items-center space-x-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-sm text-gray-600">Консультант думает...</span>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Кнопка повторного открытия предложения реструктуризации */}
                {hasSuggestionInLastMessage && !isSending && !rebalanceSuggestion?.show && (
                  <div className="flex justify-center mt-4">
                    <Button
                      variant="secondary"
                      onClick={handleShowRebalanceFromMessage}
                      className="flex items-center"
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      Показать предложение реструктуризации
                    </Button>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </>
            )}
          </CardContent>
        </Card>
        
        {/* Input - всегда внизу */}
        <form onSubmit={handleSubmit} className="mt-4 flex-shrink-0 bg-gray-50 pb-2">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Задайте вопрос консультанту..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white"
              disabled={isSending}
            />
            <Button
              type="submit"
              disabled={!input.trim() || isSending}
              className="px-6"
            >
              {isSending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </Button>
          </div>
        </form>
      </main>
    </div>
  )
}
