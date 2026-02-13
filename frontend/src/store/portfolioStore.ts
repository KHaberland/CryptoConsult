import { create } from 'zustand'
import { portfolioApi, profileApi } from '@/services/api'

interface Asset {
  symbol: string
  name: string
  percentage: number
  initial_value: number
  current_value: number
  current_price: number
  change_24h: number
  profit_loss: number
  profit_loss_percent: number
}

interface Contribution {
  id: number
  amount: number
  contributed_at: string
}

interface Withdrawal {
  id: number
  amount: number
  withdrawn_at: string
}

interface PortfolioValue {
  portfolio_id: number
  portfolio_name: string
  total_value: number
  initial_value: number
  profit_loss: number
  profit_loss_percent: number
  start_date: string
  target_date: string
  target_years: number
  days_active: number
  days_remaining: number
  assets: Asset[]
  contributions?: Contribution[]
  withdrawals?: Withdrawal[]
}

interface InvestorProfile {
  id: number
  name: string
  investment_horizon: number
  investment_amount: number
  max_drawdown: number
  needs_liquidity: boolean
  experience_level: string
  use_dca: boolean
  dca_parts: number | null
  use_default_portfolio: boolean
}

interface PortfolioState {
  profile: InvestorProfile | null
  portfolioValue: PortfolioValue | null
  hasProfile: boolean
  hasPortfolio: boolean
  isLoading: boolean
  error: string | null
  lastFetchTime: number  // Время последнего запроса для debounce
  
  // Actions
  fetchProfile: () => Promise<void>
  createProfile: (data: Omit<InvestorProfile, 'id'>) => Promise<void>
  fetchPortfolioValue: (force?: boolean) => Promise<void>
  createPortfolio: (data: { name: string; initial_amount: number; target_years: number; experience_level?: string }) => Promise<void>
  contribute: (amount: number) => Promise<void>
  withdraw: (assets: Array<{ symbol: string; units_to_sell: number }>) => Promise<void>
  clearError: () => void
}

// Минимальный интервал между запросами (30 секунд)
const MIN_FETCH_INTERVAL = 30000

// Флаги для предотвращения параллельных запросов
let isFetchingProfile = false
let isFetchingPortfolio = false

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
  profile: null,
  portfolioValue: null,
  hasProfile: false,
  hasPortfolio: false,
  isLoading: false,
  error: null,
  lastFetchTime: 0,
  
  fetchProfile: async () => {
    // Защита от параллельных запросов
    if (isFetchingProfile) {
      console.log('fetchProfile: уже выполняется запрос, пропускаем')
      return
    }
    
    // Если профиль уже загружен, не загружаем повторно
    const state = get()
    if (state.hasProfile && state.profile) {
      console.log('fetchProfile: профиль уже загружен')
      return
    }
    
    isFetchingProfile = true
    set({ isLoading: true, error: null })
    
    try {
      const profile = await profileApi.get()
      set({ profile, hasProfile: true, isLoading: false })
    } catch (error: any) {
      if (error.response?.status === 404) {
        set({ hasProfile: false, isLoading: false })
      } else {
        set({ error: 'Ошибка загрузки профиля', isLoading: false })
      }
    } finally {
      isFetchingProfile = false
    }
  },
  
  createProfile: async (data) => {
    set({ isLoading: true, error: null })
    try {
      const profile = await profileApi.create(data)
      set({ profile, hasProfile: true, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Ошибка создания профиля'
      set({ error: message, isLoading: false })
      throw error
    }
  },
  
  fetchPortfolioValue: async (force = false) => {
    // Защита от параллельных запросов
    if (isFetchingPortfolio) {
      console.log('fetchPortfolioValue: уже выполняется запрос, пропускаем')
      return
    }
    
    // Debounce: не запрашиваем чаще чем раз в 30 секунд (если не force)
    const state = get()
    const now = Date.now()
    if (!force && state.lastFetchTime && (now - state.lastFetchTime) < MIN_FETCH_INTERVAL) {
      console.log('fetchPortfolioValue: слишком частый запрос, пропускаем')
      return
    }
    
    isFetchingPortfolio = true
    set({ isLoading: true, error: null, lastFetchTime: now })
    
    try {
      const value = await portfolioApi.getValue()
      set({ portfolioValue: value, hasPortfolio: true, isLoading: false })
    } catch (error: any) {
      if (error.response?.status === 404) {
        set({ hasPortfolio: false, isLoading: false })
      } else {
        set({ error: 'Ошибка загрузки портфеля', isLoading: false })
      }
    } finally {
      isFetchingPortfolio = false
    }
  },
  
  createPortfolio: async (data) => {
    set({ isLoading: true, error: null })
    try {
      await portfolioApi.create({ ...data, use_default_assets: true, experience_level: data.experience_level })
      const value = await portfolioApi.getValue()
      set({ portfolioValue: value, hasPortfolio: true, isLoading: false, lastFetchTime: Date.now() })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Ошибка создания портфеля'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  contribute: async (amount: number) => {
    set({ isLoading: true, error: null })
    try {
      await portfolioApi.contribute(amount)
      const value = await portfolioApi.getValue()
      set({ portfolioValue: value, isLoading: false, lastFetchTime: Date.now() })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Ошибка внесения взноса'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  withdraw: async (assets: Array<{ symbol: string; units_to_sell: number }>) => {
    set({ isLoading: true, error: null })
    try {
      await portfolioApi.withdraw(assets)
      const value = await portfolioApi.getValue()
      set({ portfolioValue: value, isLoading: false, lastFetchTime: Date.now() })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Ошибка вывода средств'
      set({ error: message, isLoading: false })
      throw error
    }
  },
  
  clearError: () => set({ error: null }),
}))
