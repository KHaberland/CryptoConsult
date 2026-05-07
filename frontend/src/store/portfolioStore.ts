import { create } from 'zustand'
import {
  portfolioApi,
  profileApi,
  walletApi,
  type Wallet,
  type WalletCreateInput,
  type WalletUpdateInput,
  type WalletTransferInput,
  type HoldingAdjustInput,
} from '@/services/api'

/** Преобразование ошибок валидации API в читаемую строку */
function formatApiError(error: any, fallback: string): string {
  const data = error?.response?.data
  if (!data) return fallback
  if (typeof data.detail === 'string') return data.detail
  // Ошибки валидации: { field: ['msg1', 'msg2'], ... }
  if (typeof data === 'object' && !Array.isArray(data)) {
    const messages: string[] = []
    for (const [field, msgs] of Object.entries(data)) {
      if (Array.isArray(msgs)) {
        messages.push(...msgs.map((m: unknown) => String(m)))
      } else if (typeof msgs === 'string') {
        messages.push(msgs)
      }
    }
    if (messages.length > 0) return messages.join('. ')
  }
  return fallback
}

interface Asset {
  symbol: string
  name: string
  percentage: number
  units: number
  initial_value: number
  current_value: number
  current_price: number
  change_24h: number
  profit_loss: number
  profit_loss_percent: number
  is_recommended?: boolean
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
  has_existing_portfolio?: boolean
}

interface PortfolioState {
  profile: InvestorProfile | null
  portfolioValue: PortfolioValue | null
  wallets: Wallet[]
  walletsLoaded: boolean
  hasProfile: boolean
  hasPortfolio: boolean
  isLoading: boolean
  error: string | null
  lastFetchTime: number  // Время последнего запроса для debounce
  
  // Actions
  fetchProfile: () => Promise<void>
  createProfile: (data: Omit<InvestorProfile, 'id'>) => Promise<void>
  fetchPortfolioValue: (force?: boolean) => Promise<void>
  createPortfolio: (data: { name: string; initial_amount: number; target_years: number; experience_level?: string; needs_liquidity?: boolean }) => Promise<void>
  contribute: (amount: number) => Promise<void>
  contributeByUnits: (
    items: Array<{
      symbol: string
      units: number
      purchase_price?: number
      purchased_at?: string
    }>,
    walletId?: number | null
  ) => Promise<void>
  withdraw: (
    assets: Array<{
      symbol: string
      units_to_sell: number
      wallet_id?: number | null
    }>
  ) => Promise<void>
  swap: (
    data: {
      from_symbol: string
      from_units: number
      to_symbol: string
      to_units: number
      note?: string
    },
    walletId?: number | null
  ) => Promise<void>
  // Wallet actions
  fetchWallets: () => Promise<void>
  createWallet: (data: WalletCreateInput) => Promise<Wallet>
  updateWallet: (id: number, data: WalletUpdateInput) => Promise<Wallet>
  deleteWallet: (id: number) => Promise<void>
  transferBetweenWallets: (data: WalletTransferInput) => Promise<void>
  adjustHolding: (
    walletId: number,
    symbol: string,
    data: HoldingAdjustInput
  ) => Promise<void>
  clearError: () => void
}

// Минимальный интервал между запросами (30 секунд)
const MIN_FETCH_INTERVAL = 30000

// Флаги для предотвращения параллельных запросов
let isFetchingProfile = false
let isFetchingPortfolio = false
let isFetchingWallets = false

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
  profile: null,
  portfolioValue: null,
  wallets: [],
  walletsLoaded: false,
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
      const payload = { ...data, dca_parts: data.dca_parts ?? undefined }
      const profile = await profileApi.create(payload)
      set({ profile, hasProfile: true, isLoading: false })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка создания профиля')
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
      await portfolioApi.create({ ...data, use_default_assets: true, experience_level: data.experience_level, needs_liquidity: data.needs_liquidity })
      const value = await portfolioApi.getValue()
      set({ portfolioValue: value, hasPortfolio: true, isLoading: false, lastFetchTime: Date.now() })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка создания портфеля')
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
      const message = formatApiError(error, 'Ошибка внесения взноса')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  contributeByUnits: async (items, walletId) => {
    set({ isLoading: true, error: null })
    try {
      await portfolioApi.contributeByUnits(
        items,
        walletId != null ? { wallet_id: walletId } : undefined
      )
      // После contribute обновляем не только агрегатную стоимость портфеля,
      // но и список кошельков — изменился WalletHolding.units на выбранном
      // кошельке, и UI «Мои кошельки» должен отразить это сразу.
      const [value, wallets] = await Promise.all([
        portfolioApi.getValue(),
        walletApi.list().catch(() => get().wallets),
      ])
      set({
        portfolioValue: value,
        wallets,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка покупки монет')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  withdraw: async (assets) => {
    set({ isLoading: true, error: null })
    try {
      await portfolioApi.withdraw(assets)
      // После withdraw (см. PLAN06 — Агент 13) WalletHolding.units изменился
      // на конкретных кошельках. Обновляем и агрегатную стоимость портфеля,
      // и список кошельков, чтобы UI «Мои кошельки» сразу отразил списания.
      const [value, wallets] = await Promise.all([
        portfolioApi.getValue(),
        walletApi.list().catch(() => get().wallets),
      ])
      set({
        portfolioValue: value,
        wallets,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка вывода средств')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  swap: async (data, walletId) => {
    set({ isLoading: true, error: null })
    try {
      await portfolioApi.executeSwap(
        data,
        walletId != null ? { wallet_id: walletId } : undefined
      )
      // После swap (см. PLAN06 — Агент 12) WalletHolding.units изменился
      // на конкретном кошельке: списан from_symbol, зачислен to_symbol.
      // Обновляем и агрегатную стоимость портфеля, и список кошельков,
      // чтобы UI «Мои кошельки» сразу показал актуальные балансы.
      const [value, wallets] = await Promise.all([
        portfolioApi.getValue(),
        walletApi.list().catch(() => get().wallets),
      ])
      set({
        portfolioValue: value,
        wallets,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка обмена активов')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  fetchWallets: async () => {
    // Защита от параллельных запросов
    if (isFetchingWallets) {
      return
    }
    // Если кошельки уже загружены — повторно не запрашиваем при ремаунтах
    // (иначе возникал бесконечный цикл: fetchWallets → isLoading → ремаунт
    // секции → useEffect → fetchWallets ...).
    if (get().walletsLoaded) {
      return
    }
    isFetchingWallets = true
    // ВАЖНО: не трогаем глобальный isLoading — иначе на дашборде вновь
    // покажется лоадер, а WalletsSection размонтируется/смонтируется и
    // снова дёрнет fetchWallets из своего useEffect.
    set({ error: null })
    try {
      const wallets = await walletApi.list()
      set({ wallets, walletsLoaded: true })
    } catch (error: any) {
      // 404 — у пользователя ещё нет портфеля/кошельков, не считаем это ошибкой
      if (error?.response?.status === 404) {
        set({ wallets: [], walletsLoaded: true })
      } else {
        const message = formatApiError(error, 'Ошибка загрузки кошельков')
        set({ error: message })
      }
    } finally {
      isFetchingWallets = false
    }
  },

  createWallet: async (data) => {
    set({ isLoading: true, error: null })
    try {
      const wallet = await walletApi.create(data)
      // Обновляем список кошельков и стоимость портфеля
      const [wallets, value] = await Promise.all([
        walletApi.list().catch(() => get().wallets),
        portfolioApi.getValue().catch(() => get().portfolioValue),
      ])
      set({
        wallets,
        portfolioValue: value ?? get().portfolioValue,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
      return wallet
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка создания кошелька')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  updateWallet: async (id, data) => {
    set({ isLoading: true, error: null })
    try {
      const wallet = await walletApi.update(id, data)
      const [wallets, value] = await Promise.all([
        walletApi.list().catch(() => get().wallets),
        portfolioApi.getValue().catch(() => get().portfolioValue),
      ])
      set({
        wallets,
        portfolioValue: value ?? get().portfolioValue,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
      return wallet
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка обновления кошелька')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  deleteWallet: async (id) => {
    set({ isLoading: true, error: null })
    try {
      await walletApi.delete(id)
      const [wallets, value] = await Promise.all([
        walletApi.list().catch(() => get().wallets.filter((w) => w.id !== id)),
        portfolioApi.getValue().catch(() => get().portfolioValue),
      ])
      set({
        wallets,
        portfolioValue: value ?? get().portfolioValue,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка удаления кошелька')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  transferBetweenWallets: async (data) => {
    set({ isLoading: true, error: null })
    try {
      await walletApi.transfer(data)
      const [wallets, value] = await Promise.all([
        walletApi.list().catch(() => get().wallets),
        portfolioApi.getValue().catch(() => get().portfolioValue),
      ])
      set({
        wallets,
        portfolioValue: value ?? get().portfolioValue,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка перевода между кошельками')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  adjustHolding: async (walletId, symbol, data) => {
    set({ isLoading: true, error: null })
    try {
      await walletApi.adjustHolding(walletId, symbol, data)
      const [wallets, value] = await Promise.all([
        walletApi.list().catch(() => get().wallets),
        portfolioApi.getValue().catch(() => get().portfolioValue),
      ])
      set({
        wallets,
        portfolioValue: value ?? get().portfolioValue,
        isLoading: false,
        lastFetchTime: Date.now(),
      })
    } catch (error: any) {
      const message = formatApiError(error, 'Ошибка корректировки баланса')
      set({ error: message, isLoading: false })
      throw error
    }
  },

  clearError: () => set({ error: null }),
}))
