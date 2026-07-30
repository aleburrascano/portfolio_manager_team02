import { apiFetch, post } from './client'

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

export type AssetDetail = Asset & {
  open?: number
  yearLow?: number
  yearHigh?: number
  volume?: number
}

export type PricePoint = { date: string; close: number }

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
