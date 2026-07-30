const API_BASE = '/api/v1'

type ApiErrorBody = { error?: { message?: string } | string }

function errorMessage(data: ApiErrorBody, fallback: string): string {
  if (typeof data.error === 'string') return data.error
  return data.error?.message || fallback
}

export type User = {
  userId: number
  firstName: string
  lastName: string
}

export async function login(firstName: string, lastName: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ firstName, lastName }),
  })
  if (!res.ok) throw new Error('Login failed')
  return res.json()
}

export type AssetType = 'stock' | 'crypto' | 'bond'

export type Asset = {
  symbol: string
  name: string
  currentPrice?: number
  volume?: number | null
  change?: number | null
  changePercent?: number | null
  dayLow?: number | null
  dayHigh?: number | null
}

export async function fetchUser(userId: number): Promise<User> {
  const res = await fetch(`${API_BASE}/users/${userId}`)
  if (!res.ok) throw new Error(res.status === 404 ? 'User not found' : 'Failed to fetch user')
  return res.json()
}

export async function fetchPortfolioBreakdown(userId: number): Promise<{ cash: number; stock: number; crypto: number; bond: number }> {
  const res = await fetch(`${API_BASE}/users/${userId}/portfolio`)
  if (!res.ok) throw new Error('Failed to fetch portfolio breakdown')
  const data = await res.json()
  return { cash: data.cash || 0, stock: data.stock || 0, crypto: data.crypto || 0, bond: data.bond || 0 }
}

export async function fetchBalance(userId: number): Promise<number> {
  const res = await fetch(`${API_BASE}/users/${userId}/balance`)
  if (!res.ok) throw new Error('Failed to fetch balance')
  const data = await res.json()
  return data.balance
}

export async function fetchPopularAssets(assetType: AssetType): Promise<Asset[]> {
  const res = await fetch(`${API_BASE}/assets/${assetType}/popular`)
  if (!res.ok) throw new Error('Failed to fetch popular assets')
  const data = await res.json()
  return data.results
}

export async function searchAssets(assetType: AssetType, query: string): Promise<Asset[]> {
  const res = await fetch(`${API_BASE}/assets/${assetType}/search?q=${encodeURIComponent(query)}`)
  if (!res.ok) throw new Error('Failed to search assets')
  const data = await res.json()
  return data.results
}

export type AssetDetail = Asset & {
  open?: number | null
  yearLow?: number | null
  yearHigh?: number | null
}

export async function fetchAssetDetail(assetType: AssetType, symbol: string): Promise<AssetDetail> {
  const res = await fetch(`${API_BASE}/assets/${assetType}/${encodeURIComponent(symbol)}`)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(errorMessage(data, 'Failed to fetch asset'))
  return data
}

export type PricePoint = { date: string; close: number }

export async function fetchAssetHistory(assetType: AssetType, symbol: string): Promise<PricePoint[]> {
  const res = await fetch(`${API_BASE}/assets/${assetType}/${encodeURIComponent(symbol)}/history`)
  if (!res.ok) throw new Error('Failed to fetch asset history')
  const data = await res.json()
  return data.history
}

export async function fetchHoldings(userId: number, assetType: AssetType, symbol: string): Promise<number> {
  const res = await fetch(`${API_BASE}/users/${userId}/assets/${assetType}/${encodeURIComponent(symbol)}/holdings`)
  if (!res.ok) throw new Error('Failed to fetch holdings')
  const data = await res.json()
  return data.shares
}

export async function buyAsset(
  userId: number,
  assetType: AssetType,
  symbol: string,
  quantity: number,
): Promise<void> {
  const res = await fetch(`${API_BASE}/users/${userId}/assets/${assetType}/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker: symbol, quantity }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(errorMessage(data, 'Purchase failed'))
}

export async function sellAsset(
  userId: number,
  assetType: AssetType,
  symbol: string,
  quantity: number,
): Promise<void> {
  const res = await fetch(`${API_BASE}/users/${userId}/assets/${assetType}/sell`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker: symbol, quantity }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(errorMessage(data, 'Sale failed'))
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
  const res = await fetch(`${API_BASE}/users/${userId}/transactions`)
  if (!res.ok) throw new Error('Failed to fetch transaction history')
  const data = await res.json()
  return data.transactions
}

export type TransactionType = 'deposit' | 'withdraw'
export async function submitCashTransaction(
  userId: number,
  type: TransactionType,
  amount: number,
): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/users/${userId}/${type}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount }),
  })

  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    throw new Error(errorMessage(data, `Unable to ${type} funds!`))
  }

  return data
}
