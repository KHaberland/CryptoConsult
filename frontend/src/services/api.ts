import axios, { InternalAxiosRequestConfig } from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

/**
 * Генерация UUID v4 для session_id
 */
const generateSessionId = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

/**
 * Получение или создание session_id
 */
const getOrCreateSessionId = (): string => {
  if (typeof window === 'undefined') {
    return ''
  }
  
  let sessionId = localStorage.getItem('session_id')
  
  if (!sessionId) {
    sessionId = generateSessionId()
    localStorage.setItem('session_id', sessionId)
  }
  
  return sessionId
}

// Создаём экземпляр axios
export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Интерцептор для добавления session_id
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const sessionId = getOrCreateSessionId()
    
    if (sessionId && config.headers) {
      config.headers['X-Session-ID'] = sessionId
    }
    
    return config
  },
  (error) => Promise.reject(error)
)

// ============ Profile API ============

export const profileApi = {
  get: async () => {
    const response = await api.get('/profile/')
    return response.data
  },
  
  lookup: async (name: string) => {
    const response = await api.get('/profile/lookup/', { params: { name } })
    return response.data
  },
  
  create: async (data: {
    name: string
    investment_horizon: number
    investment_amount: number
    max_drawdown: number
    needs_liquidity: boolean
    experience_level: string
    use_dca: boolean
    dca_parts?: number
    use_default_portfolio: boolean
  }) => {
    const response = await api.post('/profile/', data)
    return response.data
  },
  
  update: async (data: Partial<{
    investment_horizon: number
    investment_amount: number
    max_drawdown: number
    needs_liquidity: boolean
    experience_level: string
    use_dca: boolean
    dca_parts: number
    use_default_portfolio: boolean
  }>) => {
    const response = await api.patch('/profile/', data)
    return response.data
  },
}

// ============ Portfolio API ============

export const portfolioApi = {
  list: async () => {
    const response = await api.get('/portfolio/')
    return response.data
  },
  
  create: async (data: {
    name: string
    initial_amount: number
    target_years: number
    use_default_assets?: boolean
    custom_assets?: Array<{ symbol: string; name: string; percentage: number }>
    experience_level?: string
  }) => {
    const response = await api.post('/portfolio/', data)
    return response.data
  },
  
  getActive: async () => {
    const response = await api.get('/portfolio/active/')
    return response.data
  },
  
  getValue: async () => {
    const response = await api.get('/portfolio/value/')
    return response.data
  },
  
  getDetail: async (id: number) => {
    const response = await api.get(`/portfolio/${id}/`)
    return response.data
  },
  
  deactivate: async (id: number) => {
    const response = await api.delete(`/portfolio/${id}/`)
    return response.data
  },
  
  rebalance: async (assets: Array<{ symbol: string; name: string; percentage: number }>) => {
    const response = await api.post('/portfolio/rebalance/', { assets })
    return response.data
  },

  contribute: async (amount: number) => {
    const response = await api.post('/portfolio/contribute/', { amount })
    return response.data
  },

  getWithdrawProposal: async (amount: number) => {
    const response = await api.get('/portfolio/withdraw/proposal/', { params: { amount } })
    return response.data
  },

  withdraw: async (assets: Array<{ symbol: string; units_to_sell: number }>) => {
    const response = await api.post('/portfolio/withdraw/', { assets })
    return response.data
  },
}

// ============ Prices API ============

export const pricesApi = {
  getPrices: async (symbols?: string[]) => {
    const params = symbols ? { symbols: symbols.join(',') } : {}
    const response = await api.get('/portfolio/prices/', { params })
    return response.data
  },
  
  getPricesWithChanges: async (symbols?: string[]) => {
    const params = symbols ? { symbols: symbols.join(',') } : {}
    const response = await api.get('/portfolio/prices/changes/', { params })
    return response.data
  },
  
  getMarketData: async (symbols?: string[]) => {
    const params = symbols ? { symbols: symbols.join(',') } : {}
    const response = await api.get('/portfolio/prices/market/', { params })
    return response.data
  },
  
  getHistory: async (symbol: string, days?: number) => {
    const params = days ? { days } : {}
    const response = await api.get(`/portfolio/prices/history/${symbol}/`, { params })
    return response.data
  },
  
  getSupported: async () => {
    const response = await api.get('/portfolio/prices/supported/')
    return response.data
  },
}

// ============ Chat API ============

export const chatApi = {
  sendMessage: async (message: string) => {
    const response = await api.post('/chat/', { message })
    return response.data
  },
  
  getHistory: async (limit?: number, offset?: number) => {
    const params = { limit: limit || 50, offset: offset || 0 }
    const response = await api.get('/chat/history/', { params })
    return response.data
  },
  
  clearHistory: async () => {
    const response = await api.delete('/chat/history/')
    return response.data
  },
  
  getSummary: async () => {
    const response = await api.get('/chat/summary/')
    return response.data
  },
  
  getRiskAnalysis: async () => {
    const response = await api.get('/chat/risk/')
    return response.data
  },
  
  getDrawdownAlert: async () => {
    const response = await api.get('/chat/alert/')
    return response.data
  },
  
  getCommands: async () => {
    const response = await api.get('/chat/commands/')
    return response.data
  },
  
  getMarketForecast: async () => {
    const response = await api.get('/chat/forecast/')
    return response.data
  },
}
