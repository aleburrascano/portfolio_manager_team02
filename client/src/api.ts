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

export type Stock = {
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

export async function fetchPopularStocks(): Promise<Stock[]> {
  const res = await fetch('/stocks/popular')
  if (!res.ok) throw new Error('Failed to fetch popular stocks')
  const data = await res.json()
  return data.results
}

export async function searchStocks(query: string): Promise<Stock[]> {
  const res = await fetch(`/stocks/search?q=${encodeURIComponent(query)}`)
  if (!res.ok) throw new Error('Failed to search stocks')
  const data = await res.json()
  return data.results
}

export type StockDetail = Stock & {
  open?: number
  yearLow?: number
  yearHigh?: number
  volume?: number
}

export async function fetchStockDetail(symbol: string): Promise<StockDetail> {
  const res = await fetch(`/stocks/${encodeURIComponent(symbol)}`)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Failed to fetch stock')
  return data
}

export type PricePoint = { date: string; close: number }

export async function fetchStockHistory(symbol: string): Promise<PricePoint[]> {
  const res = await fetch(`/stocks/${encodeURIComponent(symbol)}/history`)
  if (!res.ok) throw new Error('Failed to fetch stock history')
  const data = await res.json()
  return data.history
}

export async function fetchHoldings(userId: number, symbol: string): Promise<number> {
  const res = await fetch(`/users/${userId}/stocks/${encodeURIComponent(symbol)}/holdings`)
  if (!res.ok) throw new Error('Failed to fetch holdings')
  const data = await res.json()
  return data.shares
}

export async function buyStock(userId: number, symbol: string, quantity: number): Promise<void> {
  const res = await fetch(`/users/${userId}/stocks/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker: symbol, quantity }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Stock purchase failed')
}

export async function sellStock(userId: number, symbol: string, quantity: number): Promise<void> {
  const res = await fetch(`/users/${userId}/stocks/sell`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker: symbol, quantity }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Stock sale failed')
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