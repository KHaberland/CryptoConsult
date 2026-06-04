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

// ============ Version API ============

export interface VersionResponse {
  version: string
  api_key_configured: boolean
}

export const versionApi = {
  get: async (): Promise<string> => {
    const response = await api.get<VersionResponse>('/version/')
    return response.data.version
  },
  getFull: async (): Promise<VersionResponse> => {
    const response = await api.get<VersionResponse>('/version/')
    return response.data
  },
}

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
    has_existing_portfolio?: boolean
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
    has_existing_portfolio: boolean
  }>) => {
    const response = await api.patch('/profile/', data)
    return response.data
  },
}

// ============ Portfolio API ============

// --- PLAN11: фиатный учёт (FiatCashFlow + base_currency + P&L по фиату) ---

/** Базовая валюта портфеля / валюта фиатной операции (PLAN11). */
export type FiatCurrency = 'USD' | 'EUR'

/** Тип фиатного движения средств: внесение или вывод (PLAN11). */
export type FiatCashFlowKind = 'deposit' | 'withdrawal'

/**
 * Фиатное движение средств по портфелю (PLAN11 — A1/A5).
 *
 * Хранится отдельно от `Portfolio.initial_amount` / `PortfolioContribution` /
 * `PortfolioWithdrawal`: эта подсистема используется ТОЛЬКО для расчёта
 * P&L на dashboard и не привязана к конкретному `Wallet`.
 *
 * Числовые поля бэк отдаёт как Decimal-строки или числа в зависимости от
 * сериализатора, поэтому допускаем оба варианта.
 */
export interface FiatCashFlow {
  id: number
  kind: FiatCashFlowKind
  amount: number | string
  currency: FiatCurrency
  fx_rate_to_base: number | string
  amount_in_base: number
  occurred_on: string
  note: string
  created_at: string
}

/**
 * Расчёт P&L портфеля по фиатному учёту (PLAN11 — A4/A6).
 *
 * Все суммы — в `currency`. `no_cash_in === true` означает, что у пользователя
 * ещё нет ни одного депозита — на dashboard в этом случае показываем CTA,
 * а не нули. `fx_stale === true` сигнализирует о том, что FX USD↔EUR не
 * удалось получить и расчёт сделан по курсу 1.0 (см. PLAN11 §A4).
 */
export interface FiatPnl {
  currency: FiatCurrency
  cash_in_total: number
  cash_out_total: number
  net_cash_in: number
  current_value: number
  profit_loss: number
  profit_loss_percent: number
  no_cash_in: boolean
  fx_stale: boolean
}

/** Актив портфеля в ответе `GET /api/portfolio/value/`. */
export interface PortfolioValueAsset {
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

/** Запись истории взносов (`PortfolioContribution`). */
export interface PortfolioValueContribution {
  id: number
  amount: number
  contributed_at: string
}

/** Запись истории выводов (`PortfolioWithdrawal`). */
export interface PortfolioValueWithdrawal {
  id: number
  amount: number
  withdrawn_at: string
}

/**
 * Ответ `GET /api/portfolio/value/[?currency=USD|EUR]` (PLAN11 — A6).
 *
 * Старые поля (`total_value`, `initial_value`, `profit_loss`,
 * `profit_loss_percent`) сохранены для обратной совместимости — это
 * legacy-расчёт от `Portfolio.initial_amount + Σ contributions`. Новый блок
 * `fiat_pnl` считается по `FiatCashFlow` и должен использоваться в новом
 * dashboard-блоке «Финансы по фиату».
 */
export interface PortfolioValue {
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
  assets: PortfolioValueAsset[]
  contributions?: PortfolioValueContribution[]
  withdrawals?: PortfolioValueWithdrawal[]
  fiat_pnl?: FiatPnl
  base_currency?: FiatCurrency
  manual_usd_eur_rate?: number | string | null
}

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
    needs_liquidity?: boolean
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

  contributeByUnits: async (
    items: Array<{
      symbol: string
      units: number
      purchase_price?: number
      purchased_at?: string
    }>,
    options?: { wallet_id?: number | null }
  ) => {
    const payload: Record<string, unknown> = { items }
    if (options?.wallet_id != null) {
      payload.wallet_id = options.wallet_id
    }
    const response = await api.post('/portfolio/contribute/', payload)
    return response.data
  },

  getSwapQuote: async (
    params: {
      from_symbol: string
      to_symbol: string
      from_units: number
    },
    options?: { wallet_id?: number | null }
  ) => {
    const query: Record<string, unknown> = { ...params }
    if (options?.wallet_id != null) {
      query.wallet_id = options.wallet_id
    }
    const response = await api.get('/portfolio/swap/quote/', { params: query })
    return response.data as {
      from_symbol: string
      from_units: number
      from_price: number
      to_symbol: string
      to_units_expected: number
      to_price: number
      value_usd: number
      units_available?: number
      wallet_id?: number
      wallet_name?: string
    }
  },

  executeSwap: async (
    data: {
      from_symbol: string
      from_units: number
      to_symbol: string
      to_units: number
      note?: string
    },
    options?: { wallet_id?: number | null }
  ) => {
    const payload: Record<string, unknown> = { ...data }
    if (options?.wallet_id != null) {
      payload.wallet_id = options.wallet_id
    }
    const response = await api.post('/portfolio/swap/', payload)
    return response.data
  },

  getTradableAssets: async () => {
    const response = await api.get('/portfolio/tradable-assets/')
    return response.data as {
      assets: Array<{
        symbol: string
        name: string
        current_price: number
        is_recommended: boolean
        in_portfolio: boolean
        is_stable: boolean
      }>
      count: number
    }
  },

  getWithdrawProposal: async (amount: number) => {
    const response = await api.get('/portfolio/withdraw/proposal/', { params: { amount } })
    return response.data
  },

  withdraw: async (
    assets: Array<{
      symbol: string
      units_to_sell: number
      wallet_id?: number | null
    }>
  ) => {
    // Бэкенд принимает wallet_id per item; null/undefined → backend сам
    // выберет кошелёк (по стратегии max-units, см. PLAN06 — Агент 13).
    const payload = {
      assets: assets.map(({ symbol, units_to_sell, wallet_id }) => {
        const item: Record<string, unknown> = { symbol, units_to_sell }
        if (wallet_id != null) item.wallet_id = wallet_id
        return item
      }),
    }
    const response = await api.post('/portfolio/withdraw/', payload)
    return response.data
  },

  getTop10: async () => {
    const response = await api.get('/portfolio/top10/')
    return response.data as {
      top10: Array<{
        symbol: string
        name: string
        current_price: number
        market_cap: number
      }>
      count: number
    }
  },

  import: async (data: {
    name?: string
    target_years: number
    assets: Array<{
      symbol: string
      name?: string
      units?: number
      value_usd?: number
      purchase_price?: number
      purchased_at?: string
    }>
  }) => {
    const response = await api.post('/portfolio/import/', data)
    return response.data as {
      success: boolean
      portfolio: {
        id: number
        name: string
        initial_amount: number | string
        target_years: number
        is_imported: boolean
        assets: Array<{
          id: number
          symbol: string
          name: string
          percentage: number | string
          initial_price: number | string | null
          units: number | string | null
          is_recommended: boolean
          purchased_at: string | null
        }>
      }
      non_recommended: Array<{ symbol: string; name: string; message: string }>
      warnings: Array<{ symbol: string; message: string }>
      summary: {
        total_initial: number
        total_current: number
        profit_loss: number
        profit_loss_percent: number
      }
    }
  },

  // --- PLAN11: FiatCashFlow + base_currency + типизированный getValue ---

  /**
   * Типизированный `GET /api/portfolio/value/[?currency=USD|EUR]`.
   *
   * Если `currency` не передан — бэкенд использует `portfolio.base_currency`.
   * Старые поля (`total_value`, `initial_value`, `profit_loss`,
   * `profit_loss_percent`) остаются для обратной совместимости; новый блок
   * `fiat_pnl` считается по `FiatCashFlow`.
   */
  getPortfolioValue: async (
    currency?: FiatCurrency
  ): Promise<PortfolioValue> => {
    const params = currency ? { currency } : undefined
    const response = await api.get<PortfolioValue>('/portfolio/value/', { params })
    return response.data
  },

  /**
   * `GET /api/portfolio/cash-flows/[?kind=...&currency=...]`.
   *
   * Пагинации нет (PLAN11 — A5): эндпоинт всегда отдаёт полный список
   * cash-flow'ов активного портфеля в виде `{items, count}`.
   */
  listFiatCashFlows: async (params?: {
    kind?: FiatCashFlowKind
    currency?: FiatCurrency
  }): Promise<{ items: FiatCashFlow[] }> => {
    const response = await api.get<{ items: FiatCashFlow[]; count?: number }>(
      '/portfolio/cash-flows/',
      { params }
    )
    return { items: response.data.items }
  },

  /**
   * `POST /api/portfolio/cash-flows/`.
   *
   * `fx_rate_to_base` рассчитывается на сервере. Если внешний FX-источник
   * недоступен, в ответе придёт `fx_stale: true` — это нужно показать
   * пользователю как маленькое предупреждение (PLAN11 — A5/A8).
   */
  createFiatCashFlow: async (input: {
    kind: FiatCashFlowKind
    amount: number
    currency: FiatCurrency
    occurred_on?: string
    note?: string
  }): Promise<FiatCashFlow & { fx_stale?: boolean }> => {
    const response = await api.post<FiatCashFlow & { fx_stale?: boolean }>(
      '/portfolio/cash-flows/',
      input
    )
    return response.data
  },

  /** `DELETE /api/portfolio/cash-flows/<id>/` — жёсткое удаление операции. */
  deleteFiatCashFlow: async (id: number): Promise<void> => {
    await api.delete(`/portfolio/cash-flows/${id}/`)
  },

  /**
   * `PATCH /api/portfolio/<id>/currency/` — смена базовой валюты портфеля.
   *
   * Бэкенд внутри транзакции пересчитывает `fx_rate_to_base` у всех
   * существующих `FiatCashFlow`. Если хотя бы один курс пришёл из
   * fallback'а — вернётся `fx_stale: true` (PLAN11 — A6).
   */
  setBaseCurrency: async (
    portfolioId: number,
    currency: FiatCurrency,
    manualUsdEurRate?: number | null
  ): Promise<{
    ok: true
    base_currency: FiatCurrency
    manual_usd_eur_rate: number | null
    fx_stale: boolean
  }> => {
    const payload: {
      base_currency: FiatCurrency
      manual_usd_eur_rate?: number | null
    } = { base_currency: currency }
    if (manualUsdEurRate !== undefined) {
      payload.manual_usd_eur_rate = manualUsdEurRate
    }
    const response = await api.patch<{
      ok: true
      base_currency: FiatCurrency
      manual_usd_eur_rate: number | null
      fx_stale: boolean
    }>(`/portfolio/${portfolioId}/currency/`, payload)
    return response.data
  },
}

// ============ Wallets API ============

export type WalletType = 'exchange' | 'hot' | 'cold' | 'bank' | 'other'

export interface WalletHolding {
  id: number
  wallet_id: number
  symbol: string
  units: number | string
  /** USD-стоимость holding'а на момент запроса; null, если цена недоступна. */
  value_usd?: number | string | null
  updated_at?: string
}

export interface Wallet {
  id: number
  portfolio_id: number
  name: string
  type: WalletType
  is_default: boolean
  note?: string | null
  created_at?: string
  updated_at?: string
  holdings?: WalletHolding[]
  /** Сумма value_usd по holdings; 0, если ни одной цены не получено. */
  total_value_usd?: number | string | null
}

export interface WalletTransfer {
  id: number
  portfolio_id?: number
  from_wallet_id: number
  from_wallet_name?: string
  to_wallet_id: number
  to_wallet_name?: string
  symbol: string
  from_units: number | string
  to_units: number | string
  fee_units: number | string
  fee_usd: number | string
  occurred_on: string
  note?: string
  created_at?: string
}

export interface WalletCreateInput {
  name: string
  type: WalletType
  note?: string
  is_default?: boolean
}

export type WalletUpdateInput = Partial<WalletCreateInput>

export interface WalletTransferInput {
  from_wallet_id: number
  to_wallet_id: number
  symbol: string
  from_units: number | string
  to_units: number | string
  note?: string
}

export interface HoldingAdjustInput {
  units_after: number | string
  reason?:
    | 'network_fee'
    | 'exchange_fee'
    | 'reconciliation'
    | 'input_error'
    | 'other'
  note?: string
  occurred_on?: string
}

export const walletApi = {
  list: async (): Promise<Wallet[]> => {
    const response = await api.get<Wallet[]>('/portfolio/wallets/')
    return response.data
  },

  create: async (data: WalletCreateInput): Promise<Wallet> => {
    const response = await api.post<Wallet>('/portfolio/wallets/', data)
    return response.data
  },

  update: async (
    id: number,
    data: WalletUpdateInput
  ): Promise<Wallet> => {
    const response = await api.patch<Wallet>(
      `/portfolio/wallets/${id}/`,
      data
    )
    return response.data
  },

  delete: async (id: number): Promise<{ success: boolean } | void> => {
    const response = await api.delete(`/portfolio/wallets/${id}/`)
    return response.data
  },

  transfer: async (data: WalletTransferInput) => {
    const response = await api.post('/portfolio/wallets/transfer/', data)
    return response.data as {
      success: boolean
      message: string
      transfer: WalletTransfer
    }
  },

  adjustHolding: async (
    walletId: number,
    symbol: string,
    data: HoldingAdjustInput
  ) => {
    const response = await api.post(
      `/portfolio/wallets/${walletId}/holdings/${symbol}/adjust/`,
      data
    )
    return response.data as {
      success: boolean
      message?: string
      adjustment: {
        id: number
        wallet_id: number
        symbol: string
        units_before: number | string
        units_after: number | string
        delta: number | string
        value_delta_usd: number | string
        reason: string
        note?: string
        occurred_on: string
      }
    }
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
  
  getMarketForecast: async (days?: number) => {
    const params = days ? { days } : {}
    const response = await api.get('/chat/forecast/', { params })
    return response.data
  },

  getBtcAnalysis: async () => {
    const response = await api.get('/chat/btc-analysis/')
    return response.data
  },
}
