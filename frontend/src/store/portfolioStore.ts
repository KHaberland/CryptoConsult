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
  type FiatCashFlow,
  type FiatCashFlowKind,
  type FiatCurrency,
  type FiatPnl,
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
  /** PLAN11 — A6: новый блок P&L по фиатному учёту `FiatCashFlow`. */
  fiat_pnl?: FiatPnl
  /** PLAN11 — A6: базовая валюта портфеля (`USD`/`EUR`). */
  base_currency?: FiatCurrency
  /** Ручной курс USD→EUR для пересчета фиатного P&L. */
  manual_usd_eur_rate?: number | string | null
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

  // --- PLAN11 (A8): фиатный учёт ---
  /** Текущая базовая валюта портфеля на фронте (зеркало `portfolio.base_currency`). */
  baseCurrency: FiatCurrency
  /** Последний загруженный блок P&L по фиату (`null`, пока не запросили). */
  fiatPnl: FiatPnl | null
  /** Признак, что курс USD↔EUR на бэке протух (для иконки-warning). */
  fxStale: boolean
  /** Ручной курс USD→EUR, если пользователь задал его для портфеля. */
  manualUsdEurRate: number | null
  /** Список cash-flow'ов активного портфеля. */
  fiatCashFlows: FiatCashFlow[]
  
  // Actions
  fetchProfile: () => Promise<void>
  createProfile: (data: Omit<InvestorProfile, 'id'>) => Promise<void>
  fetchPortfolioValue: (force?: boolean, currency?: FiatCurrency) => Promise<void>
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
  // --- PLAN11 (A8): cash-flow + смена базовой валюты ---
  /** Перезагружает список фиатных операций активного портфеля. */
  fetchFiatCashFlows: () => Promise<void>
  /**
   * Создаёт `FiatCashFlow` через API и обновляет
   * `fiatCashFlows` + `portfolioValue.fiat_pnl` в одном проходе.
   * Возвращает созданную запись (с возможным `fx_stale` от бэка).
   */
  createFiatCashFlow: (input: {
    kind: FiatCashFlowKind
    amount: number
    currency: FiatCurrency
    occurred_on?: string
    note?: string
  }) => Promise<FiatCashFlow & { fx_stale?: boolean }>
  /** Удаляет cash-flow и пересчитывает блок «Финансы по фиату». */
  deleteFiatCashFlow: (id: number) => Promise<void>
  /**
   * Меняет базовую валюту портфеля и сразу обновляет dashboard:
   * бэкенд внутри транзакции пересчитывает `fx_rate_to_base` у всех
   * существующих cash-flow'ов (PLAN11 — A6).
   */
  setBaseCurrency: (
    currency: FiatCurrency,
    manualUsdEurRate?: number | null
  ) => Promise<void>
  /** Сохраняет ручной курс USD→EUR через тот же endpoint currency/. */
  setManualUsdEurRate: (rate: number | null) => Promise<void>
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

  // PLAN11 (A8): фиатный учёт
  baseCurrency: 'USD',
  fiatPnl: null,
  fxStale: false,
  manualUsdEurRate: null,
  fiatCashFlows: [],
  
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
  
  fetchPortfolioValue: async (force = false, currency?: FiatCurrency) => {
    // Защита от параллельных запросов
    if (isFetchingPortfolio) {
      console.log('fetchPortfolioValue: уже выполняется запрос, пропускаем')
      return
    }
    
    // Debounce: не запрашиваем чаще чем раз в 30 секунд (если не force).
    // Смена валюты — это «принудительная» операция, она тоже выставит
    // force=true в вызывающем коде (см. `setBaseCurrency` и переключатель
    // USD/EUR на dashboard'е).
    const state = get()
    const now = Date.now()
    if (!force && state.lastFetchTime && (now - state.lastFetchTime) < MIN_FETCH_INTERVAL) {
      console.log('fetchPortfolioValue: слишком частый запрос, пропускаем')
      return
    }
    
    isFetchingPortfolio = true
    set({ isLoading: true, error: null, lastFetchTime: now })

    try {
      // Используем типизированный `getPortfolioValue` из PLAN11 — он
      // умеет принимать `?currency=` и возвращает `fiat_pnl` + `base_currency`.
      const value = await portfolioApi.getPortfolioValue(currency)
      set({
        portfolioValue: value as unknown as PortfolioValue,
        hasPortfolio: true,
        isLoading: false,
        fiatPnl: value.fiat_pnl ?? null,
        baseCurrency: value.base_currency ?? get().baseCurrency,
        fxStale: Boolean(value.fiat_pnl?.fx_stale),
        manualUsdEurRate:
          value.manual_usd_eur_rate == null
            ? null
            : Number(value.manual_usd_eur_rate),
      })
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

  // --- PLAN11 (A8): cash-flow + base_currency ---

  fetchFiatCashFlows: async () => {
    try {
      const { items } = await portfolioApi.listFiatCashFlows()
      set({ fiatCashFlows: items })
    } catch (error: any) {
      // 404 = нет активного портфеля; пустой список — норма.
      if (error?.response?.status === 404) {
        set({ fiatCashFlows: [] })
        return
      }
      const message = formatApiError(error, 'Ошибка загрузки фиатных операций')
      set({ error: message })
    }
  },

  createFiatCashFlow: async (input) => {
    set({ error: null })
    try {
      const created = await portfolioApi.createFiatCashFlow(input)
      const currency = get().baseCurrency
      // После создания cash-flow обновляем и список, и блок P&L: бэк
      // пересчитал `fiat_pnl.cash_in_total` / `current_value`, фронту
      // нельзя считать это самому (нужны актуальные крипто-цены).
      const [list, value] = await Promise.all([
        portfolioApi.listFiatCashFlows().catch(() => ({ items: get().fiatCashFlows })),
        portfolioApi
          .getPortfolioValue(currency)
          .catch(() => null),
      ])
      set({
        fiatCashFlows: list.items,
        portfolioValue:
          value ? (value as unknown as PortfolioValue) : get().portfolioValue,
        fiatPnl: value?.fiat_pnl ?? get().fiatPnl,
        baseCurrency: value?.base_currency ?? get().baseCurrency,
        fxStale: Boolean(value?.fiat_pnl?.fx_stale ?? get().fxStale),
        manualUsdEurRate: value
          ? value.manual_usd_eur_rate == null
            ? null
            : Number(value.manual_usd_eur_rate)
          : get().manualUsdEurRate,
        lastFetchTime: Date.now(),
      })
      return created
    } catch (error: any) {
      const message = formatApiError(error, 'Не удалось сохранить фиатную операцию')
      set({ error: message })
      throw error
    }
  },

  deleteFiatCashFlow: async (id: number) => {
    set({ error: null })
    try {
      await portfolioApi.deleteFiatCashFlow(id)
      const currency = get().baseCurrency
      const [list, value] = await Promise.all([
        portfolioApi.listFiatCashFlows().catch(() => ({ items: get().fiatCashFlows.filter((f) => f.id !== id) })),
        portfolioApi
          .getPortfolioValue(currency)
          .catch(() => null),
      ])
      set({
        fiatCashFlows: list.items,
        portfolioValue:
          value ? (value as unknown as PortfolioValue) : get().portfolioValue,
        fiatPnl: value?.fiat_pnl ?? get().fiatPnl,
        baseCurrency: value?.base_currency ?? get().baseCurrency,
        fxStale: Boolean(value?.fiat_pnl?.fx_stale ?? get().fxStale),
        manualUsdEurRate: value
          ? value.manual_usd_eur_rate == null
            ? null
            : Number(value.manual_usd_eur_rate)
          : get().manualUsdEurRate,
        lastFetchTime: Date.now(),
      })
    } catch (error: any) {
      const message = formatApiError(error, 'Не удалось удалить операцию')
      set({ error: message })
      throw error
    }
  },

  setBaseCurrency: async (currency: FiatCurrency, manualUsdEurRate?: number | null) => {
    const prev = get().baseCurrency
    if (prev === currency && manualUsdEurRate === undefined) return
    set({ error: null })
    try {
      const portfolioId = get().portfolioValue?.portfolio_id
      if (!portfolioId) {
        throw new Error('Нет активного портфеля для смены базовой валюты')
      }
      const resp = await portfolioApi.setBaseCurrency(
        portfolioId,
        currency,
        manualUsdEurRate
      )
      // После PATCH `currency/` нужно перетянуть value с новой валютой,
      // чтобы блок «Финансы по фиату» сразу пересчитался.
      const value = await portfolioApi
        .getPortfolioValue(resp.base_currency)
        .catch(() => null)
      set({
        baseCurrency: resp.base_currency,
        fxStale: Boolean(resp.fx_stale || value?.fiat_pnl?.fx_stale),
        portfolioValue:
          value ? (value as unknown as PortfolioValue) : get().portfolioValue,
        fiatPnl: value?.fiat_pnl ?? get().fiatPnl,
        manualUsdEurRate: resp.manual_usd_eur_rate,
        lastFetchTime: Date.now(),
      })
      // FX у cash-flow'ов изменился — обновим и список.
      await get().fetchFiatCashFlows()
    } catch (error: any) {
      const message = formatApiError(error, 'Не удалось сменить базовую валюту')
      set({ error: message })
      throw error
    }
  },

  setManualUsdEurRate: async (rate: number | null) => {
    await get().setBaseCurrency(get().baseCurrency, rate)
  },

  clearError: () => set({ error: null }),
}))
