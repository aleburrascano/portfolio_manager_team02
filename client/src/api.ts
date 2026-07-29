export type User = {
  userId: number
  firstName: string
  lastName: string
}

export async function login(firstName: string, lastName: string): Promise<User> {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ firstName, lastName }),
  })
  if (!res.ok) throw new Error('Login failed')
  return res.json()
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

export async function fetchBalance(userId: number): Promise<number> {
  const res = await fetch(`/users/${userId}/balance`)
  if (!res.ok) throw new Error('Failed to fetch balance')
  const data = await res.json()
  return data.balance
}

export async function fetchPopularAssets(assetType: AssetType): Promise<Asset[]> {
  const res = await fetch(`/assets/${assetType}/popular`)
  if (!res.ok) throw new Error('Failed to fetch popular assets')
  const data = await res.json()
  return data.results
}

export async function searchAssets(assetType: AssetType, query: string): Promise<Asset[]> {
  const res = await fetch(`/assets/${assetType}/search?q=${encodeURIComponent(query)}`)
  if (!res.ok) throw new Error('Failed to search assets')
  const data = await res.json()
  return data.results
}

export type AssetDetail = Asset & {
  open?: number
  yearLow?: number
  yearHigh?: number
  volume?: number
}

export async function fetchAssetDetail(assetType: AssetType, symbol: string): Promise<AssetDetail> {
  const res = await fetch(`/assets/${assetType}/${encodeURIComponent(symbol)}`)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Failed to fetch asset')
  return data
}

export type PricePoint = { date: string; close: number }

export async function fetchAssetHistory(assetType: AssetType, symbol: string): Promise<PricePoint[]> {
  const res = await fetch(`/assets/${assetType}/${encodeURIComponent(symbol)}/history`)
  if (!res.ok) throw new Error('Failed to fetch asset history')
  const data = await res.json()
  return data.history
}

export async function fetchHoldings(userId: number, assetType: AssetType, symbol: string): Promise<number> {
  const res = await fetch(`/users/${userId}/assets/${assetType}/${encodeURIComponent(symbol)}/holdings`)
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
  const res = await fetch(`/users/${userId}/assets/${assetType}/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker: symbol, quantity }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Purchase failed')
}

export async function sellAsset(
  userId: number,
  assetType: AssetType,
  symbol: string,
  quantity: number,
): Promise<void> {
  const res = await fetch(`/users/${userId}/assets/${assetType}/sell`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker: symbol, quantity }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Sale failed')
}

export type TransactionType = 'deposit' | 'withdraw'
export async function submitCashTransaction(
  userId: number,
  type: TransactionType,
  amount: number,
): Promise<{ message: string }> {
  const res = await fetch(`/users/${userId}/${type}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount }),
  })

  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    throw new Error(data.error || `Unable to ${type} funds!`)
  }

  return data
}
