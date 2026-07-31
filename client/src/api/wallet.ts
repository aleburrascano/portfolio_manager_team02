import { apiFetch, post } from './client'
import type { AssetType } from './assets'

export type PortfolioBreakdown = { cash: number; stock: number; crypto: number; bond: number }

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

export type TransactionType = 'deposit' | 'withdraw'

/** One day of the portfolio's history. */
export type PerformancePoint = {
  date: string
  portfolioValue: number
  investedValue: number
  cash: number
  netDeposits: number
}

export type PerformanceSummary = {
  startValue: number
  currentValue: number
  netDeposits: number
  gainLoss: number
  gainLossPercent: number
}

export type AssetTypePerformance = {
  assetType: AssetType
  value: number
  costBasis: number
  gainLoss: number
  gainLossPercent: number
}

export type PortfolioPerformance = {
  series: PerformancePoint[]
  summary: PerformanceSummary
  byAssetType: AssetTypePerformance[]
}

export type Holding = {
  ticker: string
  assetType: AssetType
  quantity: number
  currentPrice: number
  averageCost: number
  value: number
  costBasis: number
  gainLoss: number
  gainLossPercent: number
  dayChange: number
  acquiredAt: string | null
}

export type HoldingsTotals = {
  positions: number
  value: number
  costBasis: number
  gainLoss: number
  gainLossPercent: number
  /** Today's move on the whole book, against what it opened at. */
  dayChange: number
  dayChangePercent: number
}

export type HoldingsResult = {
  holdings: Holding[]
  totals: HoldingsTotals
}

export async function fetchBalance(userId: number): Promise<number> {
  const data = await apiFetch<{ balance: number }>(`/users/${userId}/balance`, 'Failed to fetch balance')
  return data.balance
}

export async function fetchPortfolioBreakdown(userId: number): Promise<PortfolioBreakdown> {
  const data = await apiFetch<Partial<PortfolioBreakdown>>(
    `/users/${userId}/portfolio`,
    'Failed to fetch portfolio breakdown',
  )
  return { cash: data.cash || 0, stock: data.stock || 0, crypto: data.crypto || 0, bond: data.bond || 0 }
}

export async function fetchPortfolioPerformance(
  userId: number,
  days = 365,
): Promise<PortfolioPerformance> {
  return apiFetch(
    `/users/${userId}/portfolio/performance?days=${days}`,
    'Failed to fetch portfolio performance',
  )
}

/**
 * Open positions, largest first. Re-sorting happens in the component: the
 * rows are bounded by how many assets one person holds, every sortable
 * field is already in this payload, and a round trip per column click
 * would re-price every ticker upstream for data we already have.
 */
export async function fetchPortfolioHoldings(userId: number): Promise<HoldingsResult> {
  return apiFetch(`/users/${userId}/portfolio/holdings`, 'Failed to fetch holdings')
}

export async function fetchTransactions(userId: number): Promise<Transaction[]> {
  const data = await apiFetch<{ transactions: Transaction[] }>(
    `/users/${userId}/transactions`,
    'Failed to fetch transaction history',
  )
  return data.transactions
}

export async function submitCashTransaction(
  userId: number,
  type: TransactionType,
  amount: number,
  idempotencyKey?: string,
): Promise<{ message: string }> {
  return apiFetch(
    `/users/${userId}/${type}`,
    `Unable to ${type} funds!`,
    post({ amount }, idempotencyKey),
  )
}
