import { apiFetch, post } from './client'

export type AssetType = 'stock' | 'crypto' | 'bond'

/**
 * What one asset type is called and what can be done with it.
 *
 * Comes from the server's provider registry rather than a list kept here,
 * so an asset type added there shows up in the tabs, the labels, and the
 * order-type toggles without a matching edit on this side.
 */
export type AssetTypeInfo = {
  assetType: AssetType
  label: string
  /** Whether prices for this type arrive over the quote feed. */
  streams: boolean
  supportsLimitOrders: boolean
}

export async function fetchAssetTypes(): Promise<AssetTypeInfo[]> {
  const data = await apiFetch<{ assetTypes: AssetTypeInfo[] }>(
    '/assets/types',
    'Failed to fetch asset types',
  )
  return data.assetTypes
}

export type Asset = {
  symbol: string
  name: string
  currentPrice?: number
  // Null, not absent, for fields an asset type doesn't have - a bond has
  // no volume or intraday range.
  volume?: number | null
  change?: number | null
  changePercent?: number | null
  dayLow?: number | null
  dayHigh?: number | null
}

export type AssetDetail = Asset & {
  open?: number | null
  yearLow?: number | null
  yearHigh?: number | null
}

export type PricePoint = { date: string; close: number }

export type RatingBucket = { label: string; count: number }

export type AnalystRatings = {
  /** The feed's own summary word, e.g. 'buy', 'strong_buy', 'hold'. */
  consensus: string | null
  /** 1.0 (strong buy) to 5.0 (strong sell). */
  score: number | null
  analystCount: number | null
  targetLow: number | null
  targetMean: number | null
  targetHigh: number | null
  currentPrice: number | null
  distribution: RatingBucket[]
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

export async function fetchAssetDetail(assetType: AssetType, symbol: string): Promise<AssetDetail> {
  return apiFetch(`/assets/${assetType}/${encodeURIComponent(symbol)}`, 'Failed to fetch asset')
}

export async function fetchAssetHistory(assetType: AssetType, symbol: string): Promise<PricePoint[]> {
  const data = await apiFetch<{ history: PricePoint[] }>(
    `/assets/${assetType}/${encodeURIComponent(symbol)}/history`,
    'Failed to fetch asset history',
  )
  return data.history
}

export type WatchlistEntry = {
  symbol: string
  assetType: AssetType
  addedAt: string | null
  name: string | null
  currentPrice: number | null
  change: number | null
  changePercent: number | null
}

export async function fetchWatchlist(userId: number): Promise<WatchlistEntry[]> {
  const data = await apiFetch<{ watchlist: WatchlistEntry[] }>(
    `/users/${userId}/watchlist`,
    'Failed to fetch watchlist',
  )
  return data.watchlist
}

export async function isWatched(
  userId: number,
  assetType: AssetType,
  symbol: string,
): Promise<boolean> {
  const data = await apiFetch<{ watched: boolean }>(
    `/users/${userId}/watchlist/${assetType}/${encodeURIComponent(symbol)}`,
    'Failed to check watchlist',
  )
  return data.watched
}

/** PUT to save, DELETE to unsave. Saving twice is the same one entry. */
export async function setWatched(
  userId: number,
  assetType: AssetType,
  symbol: string,
  watched: boolean,
): Promise<void> {
  await apiFetch(
    `/users/${userId}/watchlist/${assetType}/${encodeURIComponent(symbol)}`,
    watched ? 'Failed to save to watchlist' : 'Failed to remove from watchlist',
    { method: watched ? 'PUT' : 'DELETE' },
  )
}

/** Null when nobody covers this ticker - normal for bonds and crypto. */
export async function fetchAssetRatings(
  assetType: AssetType,
  symbol: string,
): Promise<AnalystRatings | null> {
  const data = await apiFetch<{ ratings: AnalystRatings | null }>(
    `/assets/${assetType}/${encodeURIComponent(symbol)}/ratings`,
    'Failed to fetch analyst ratings',
  )
  return data.ratings
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
  idempotencyKey?: string,
): Promise<void> {
  await apiFetch(
    `/users/${userId}/assets/${assetType}/buy`,
    'Purchase failed',
    post({ ticker: symbol, quantity }, idempotencyKey),
  )
}

export async function sellAsset(
  userId: number,
  assetType: AssetType,
  symbol: string,
  quantity: number,
  idempotencyKey?: string,
): Promise<void> {
  await apiFetch(
    `/users/${userId}/assets/${assetType}/sell`,
    'Sale failed',
    post({ ticker: symbol, quantity }, idempotencyKey),
  )
}
