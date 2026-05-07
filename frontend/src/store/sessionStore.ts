import { create } from 'zustand'

interface SessionState {
  sessionId: string | null
  userName: string | null
  isReady: boolean
  hasCompletedOnboarding: boolean
  hasExistingPortfolio: boolean | null
  
  // Actions
  initSession: () => void
  getSessionId: () => string
  setOnboardingCompleted: (completed: boolean) => void
  setUserName: (name: string) => void
  setSessionFromLookup: (sessionId: string, name: string) => void
  startNewUserSession: (name: string) => void
  setHasExistingPortfolio: (value: boolean) => void
  resetSession: () => void
}

/**
 * Генерация UUID v4
 */
const generateSessionId = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

/**
 * Store для управления session_id.
 * Session ID используется для идентификации пользователя без авторизации.
 * Сохраняется в localStorage и передаётся на backend через заголовок X-Session-ID.
 */
export const useSessionStore = create<SessionState>((set, get) => ({
  sessionId: null,
  userName: null,
  isReady: false,
  hasCompletedOnboarding: false,
  hasExistingPortfolio: null,
  
  /**
   * Инициализация сессии.
   * Вызывается при загрузке приложения.
   * Читает session_id и onboarding_completed из localStorage.
   */
  initSession: () => {
    // Проверка на SSR
    if (typeof window === 'undefined') {
      return
    }
    
    let sessionId = localStorage.getItem('session_id')
    
    if (!sessionId) {
      sessionId = generateSessionId()
      localStorage.setItem('session_id', sessionId)
    }
    
    // Читаем состояние onboarding и имя
    const onboardingCompleted = localStorage.getItem('onboarding_completed') === 'true'
    const userName = localStorage.getItem('user_name')
    const hasExistingRaw = localStorage.getItem('has_existing_portfolio')
    const hasExistingPortfolio =
      hasExistingRaw === null ? null : hasExistingRaw === 'true'
    
    set({ 
      sessionId, 
      userName,
      isReady: true,
      hasCompletedOnboarding: onboardingCompleted,
      hasExistingPortfolio,
    })
  },
  
  /**
   * Получение session_id.
   * Если sessionId ещё не инициализирован в store — читает из localStorage.
   */
  getSessionId: (): string => {
    const state = get()
    
    // Если уже есть в store — возвращаем
    if (state.sessionId) {
      return state.sessionId
    }
    
    // Проверка на SSR
    if (typeof window === 'undefined') {
      return ''
    }
    
    // Читаем/генерируем из localStorage
    let sessionId = localStorage.getItem('session_id')
    
    if (!sessionId) {
      sessionId = generateSessionId()
      localStorage.setItem('session_id', sessionId)
    }
    
    return sessionId
  },
  
  /**
   * Установка статуса прохождения onboarding.
   */
  setOnboardingCompleted: (completed: boolean) => {
    if (typeof window !== 'undefined') {
      if (completed) {
        localStorage.setItem('onboarding_completed', 'true')
      } else {
        localStorage.removeItem('onboarding_completed')
      }
    }
    set({ hasCompletedOnboarding: completed })
  },
  
  /**
   * Установка имени пользователя (для нового пользователя).
   */
  setUserName: (name: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('user_name', name)
    }
    set({ userName: name })
  },
  
  /**
   * Установка сессии из lookup (для существующего пользователя).
   */
  setSessionFromLookup: (sessionId: string, name: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('session_id', sessionId)
      localStorage.setItem('user_name', name)
      localStorage.setItem('onboarding_completed', 'true')
    }
    set({ 
      sessionId, 
      userName: name, 
      hasCompletedOnboarding: true,
      isReady: true 
    })
  },
  
  /**
   * Начало новой сессии для нового пользователя.
   * Генерирует новый session_id, сбрасывает onboarding.
   */
  startNewUserSession: (name: string) => {
    if (typeof window !== 'undefined') {
      // Генерируем новый session_id
      const newSessionId = generateSessionId()
      localStorage.setItem('session_id', newSessionId)
      localStorage.setItem('user_name', name)
      localStorage.removeItem('onboarding_completed')
      localStorage.removeItem('has_existing_portfolio')
      
      set({
        sessionId: newSessionId,
        userName: name,
        hasCompletedOnboarding: false,
        hasExistingPortfolio: null,
        isReady: true
      })
    }
  },
  
  /**
   * Установка флага наличия существующего портфеля у пользователя.
   * Сохраняется в localStorage, чтобы повторный заход в анкету не сбрасывал ответ.
   */
  setHasExistingPortfolio: (value: boolean) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('has_existing_portfolio', String(value))
    }
    set({ hasExistingPortfolio: value })
  },
  
  /**
   * Сброс сессии (выход).
   */
  resetSession: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('session_id')
      localStorage.removeItem('user_name')
      localStorage.removeItem('onboarding_completed')
      localStorage.removeItem('has_existing_portfolio')
    }
    set({ 
      sessionId: null,
      userName: null,
      isReady: false,
      hasCompletedOnboarding: false,
      hasExistingPortfolio: null,
    })
  },
}))
