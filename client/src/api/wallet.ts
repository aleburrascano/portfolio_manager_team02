import { API_BASE, apiFetch, post } from './client'
import type { AssetType } from './assets'

/**
 * How much of the portfolio sits in cash and in each asset type.
 *
 * Open-ended rather than a fixed set of keys: the server builds these
 * buckets from its provider registry, so a new asset type appears here on
 * its own and a client that enumerated three of them would silently drop it.
 */
export type PortfolioBreakdown = { cash: number } & Partial<Record<AssetType, number>>

/** What a sale made against the average cost of what it came out of. */
export type RealizedGain = {
  costBasis: number
  proceeds: number
  gainLoss: number
  gainLossPercent: number
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
  /**
   * Present on sells only. Absent - not zero - on everything else, because
   * a buy realising nothing is a different statement from one that made
   * nothing.
   */
  realized?: RealizedGain
}

export type TransactionType = 'deposit' | 'withdraw'

/** One day of the portfolio's history. */
export type PerformancePoint = {
  date: string
  portfolioValue: number
  investedValue: number
  cash: number
  netDeposits: number
  /**
   * What the same deposits, made on the same days, would be worth in the
   * benchmark instead. Absent when the index couldn't be priced.
   */
  benchmarkValue?: number
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
  /** What the comparison line is, so the chart can name it. */
  benchmark: { ticker: string; label: string }
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
  return { ...data, cash: data.cash || 0 }
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

export type TransactionPage = {
  transactions: Transaction[]
  /** The count before paging, so a caller knows whether more exist. */
  total: number
}

/**
 * One page of history, newest first.
 *
 * Paged in the database against an index rather than fetched whole and
 * sorted here: a seeded account is already a couple of hundred rows and
 * only grows.
 */
export type TransactionSort = 'newest' | 'oldest'

export async function fetchTransactions(
  userId: number,
  limit?: number,
  offset = 0,
  sort: TransactionSort = 'newest',
): Promise<TransactionPage> {
  const params = new URLSearchParams()
  if (limit != null) params.set('limit', String(limit))
  if (offset) params.set('offset', String(offset))
  if (sort !== 'newest') params.set('sort', sort)
  const query = params.size > 0 ? `?${params}` : ''

  return apiFetch(`/users/${userId}/transactions${query}`, 'Failed to fetch transaction history')
}

/** Where the browser should point to download the whole history as CSV. */
export function transactionsExportUrl(userId: number): string {
  return `${API_BASE}/users/${userId}/transactions/export`
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
