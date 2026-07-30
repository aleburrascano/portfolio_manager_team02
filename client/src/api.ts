const API_BASE = '/api/v1'

type ApiErrorBody = { error?: { message?: string } | string }

function errorMessage(data: ApiErrorBody, fallback: string): string {
  if (typeof data.error === 'string') return data.error
  return data.error?.message || fallback
}

// The session lives in an httpOnly cookie the server sets on login, so every
// call has to send credentials - there is no token for the client to hold.
async function apiFetch<T>(path: string, fallbackError: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...init })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(errorMessage(data, fallbackError))
  return data as T
}

function post(body?: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  }
}

export type User = {
  userId: number
  username: string
  firstName: string
  lastName: string
}

export async function login(username: string, password: string): Promise<User> {
  return apiFetch('/auth/login', 'Login failed', post({ username, password }))
}

export async function register(
  username: string,
  password: string,
  firstName: string,
  lastName: string,
): Promise<User> {
  return apiFetch('/auth/register', 'Registration failed', post({ username, password, firstName, lastName }))
}

/** The user owning the current session, or null if there isn't one. */
export async function fetchCurrentUser(): Promise<User | null> {
  try {
    return await apiFetch<User>('/auth/me', 'Failed to fetch session')
  } catch {
    return null
  }
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', 'Logout failed', post())
}

export type AssetType = 'stock' | 'crypto'

export type Asset = {
  symbol: string
  name: string
  currentPrice?: number
  volume?: number
  change?: number
  changePercent?: number
  dayLow?: number
  dayHigh?: number
}

export async function fetchPortfolioBreakdown(userId: number): Promise<{ cash: number; stock: number; crypto: number }> {
  const data = await apiFetch<{ cash?: number; stock?: number; crypto?: number }>(
    `/users/${userId}/portfolio`,
    'Failed to fetch portfolio breakdown',
  )
  return { cash: data.cash || 0, stock: data.stock || 0, crypto: data.crypto || 0 }
}

export async function fetchBalance(userId: number): Promise<number> {
  const data = await apiFetch<{ balance: number }>(`/users/${userId}/balance`, 'Failed to fetch balance')
  return data.balance
}

export async function fetchPopularAssets(assetType: AssetType): Promise<Asset[]> {
  const data = await apiFetch<{ results: Asset[] }>(
    `/assets/${assetType}/popular`,
    'Failed to fetch popular assets',
  )
  return data.results
}

export async function searchAssets(assetType: AssetType, query: string): Promise<Asset[]> {
  const data = await apiFetch<{ results: Asset[] }>(
    `/assets/${assetType}/search?q=${encodeURIComponent(query)}`,
    'Failed to search assets',
  )
  return data.results
}

export type AssetDetail = Asset & {
  open?: number
  yearLow?: number
  yearHigh?: number
  volume?: number
}

export async function fetchAssetDetail(assetType: AssetType, symbol: string): Promise<AssetDetail> {
  return apiFetch(`/assets/${assetType}/${encodeURIComponent(symbol)}`, 'Failed to fetch asset')
}

export type PricePoint = { date: string; close: number }

export async function fetchAssetHistory(assetType: AssetType, symbol: string): Promise<PricePoint[]> {
  const data = await apiFetch<{ history: PricePoint[] }>(
    `/assets/${assetType}/${encodeURIComponent(symbol)}/history`,
    'Failed to fetch asset history',
  )
  return data.history
}

export async function fetchHoldings(userId: number, assetType: AssetType, symbol: string): Promise<number> {
  const data = await apiFetch<{ shares: number }>(
    `/users/${userId}/assets/${assetType}/${encodeURIComponent(symbol)}/holdings`,
    'Failed to fetch holdings',
  )
  return data.shares
}

export async function buyAsset(
  userId: number,
  assetType: AssetType,
  symbol: string,
  quantity: number,
): Promise<void> {
  await apiFetch(
    `/users/${userId}/assets/${assetType}/buy`,
    'Purchase failed',
    post({ ticker: symbol, quantity }),
  )
}

export async function sellAsset(
  userId: number,
  assetType: AssetType,
  symbol: string,
  quantity: number,
): Promise<void> {
  await apiFetch(
    `/users/${userId}/assets/${assetType}/sell`,
    'Sale failed',
    post({ ticker: symbol, quantity }),
  )
}

export type Transaction = {
  transactionId: number
  type: 'cash' | AssetType
  transactionType: string
  transactionDate: string
  signedAmount: number
  ticker?: string
  qty?: number
  price?: number
}

export async function fetchTransactions(userId: number): Promise<Transaction[]> {
  const data = await apiFetch<{ transactions: Transaction[] }>(
    `/users/${userId}/transactions`,
    'Failed to fetch transaction history',
  )
  return data.transactions
}

export type TransactionType = 'deposit' | 'withdraw'
export async function submitCashTransaction(
  userId: number,
  type: TransactionType,
  amount: number,
): Promise<{ message: string }> {
  return apiFetch(`/users/${userId}/${type}`, `Unable to ${type} funds!`, post({ amount }))
}
