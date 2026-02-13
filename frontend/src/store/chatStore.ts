import { create } from 'zustand'
import { chatApi } from '@/services/api'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

interface Alert {
  alert: boolean
  level?: 'warning' | 'critical'
  message: string
  current_drawdown?: number
  max_drawdown?: number
}

// Интерфейс для предложения реструктуризации
export interface RebalanceSuggestion {
  show: boolean
  newAssets: Array<{
    symbol: string
    name: string
    percentage: number
  }>
  currentAssets: Array<{
    symbol: string
    name: string
    percentage: number
  }>
}

interface ChatState {
  messages: Message[]
  isLoading: boolean
  isSending: boolean
  error: string | null
  alert: Alert | null
  hasMore: boolean
  total: number
  rebalanceSuggestion: RebalanceSuggestion | null
  
  // Actions
  fetchHistory: () => Promise<void>
  sendMessage: (message: string) => Promise<void>
  clearHistory: () => Promise<void>
  clearError: () => void
  showRebalanceModal: (suggestion: RebalanceSuggestion) => void
  hideRebalanceModal: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  isSending: false,
  error: null,
  alert: null,
  hasMore: false,
  total: 0,
  rebalanceSuggestion: null,
  
  fetchHistory: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await chatApi.getHistory(50, 0)
      set({
        messages: response.messages,
        total: response.total,
        hasMore: response.has_more,
        isLoading: false,
      })
    } catch (error: any) {
      set({ error: 'Ошибка загрузки истории', isLoading: false })
    }
  },
  
  sendMessage: async (message: string) => {
    set({ isSending: true, error: null })
    
    // Оптимистично добавляем сообщение пользователя
    const tempUserMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    }
    
    set((state) => ({
      messages: [...state.messages, tempUserMessage],
    }))
    
    try {
      const response = await chatApi.sendMessage(message)
      
      // Заменяем временное сообщение на реальное и добавляем ответ
      set((state) => ({
        messages: [
          ...state.messages.filter((m) => m.id !== tempUserMessage.id),
          response.user_message,
          response.assistant_message,
        ],
        alert: response.alert || null,
        isSending: false,
      }))
    } catch (error: any) {
      // Удаляем временное сообщение при ошибке
      set((state) => ({
        messages: state.messages.filter((m) => m.id !== tempUserMessage.id),
        error: error.response?.data?.detail || 'Ошибка отправки сообщения',
        isSending: false,
      }))
    }
  },
  
  clearHistory: async () => {
    set({ isLoading: true, error: null })
    try {
      await chatApi.clearHistory()
      set({ messages: [], total: 0, hasMore: false, isLoading: false })
    } catch (error: any) {
      set({ error: 'Ошибка очистки истории', isLoading: false })
    }
  },
  
  clearError: () => set({ error: null }),
  
  showRebalanceModal: (suggestion: RebalanceSuggestion) => {
    set({ rebalanceSuggestion: suggestion })
  },
  
  hideRebalanceModal: () => {
    set({ rebalanceSuggestion: null })
  },
}))
