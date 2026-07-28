// No auth yet, so we hardcode the demo user id.
export const DEMO_USER_ID = 1

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
