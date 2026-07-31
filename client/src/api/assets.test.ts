import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
  post: vi.fn((body: unknown, idempotencyKey?: string) => ({ method: 'POST', body, idempotencyKey })),
}))

import { apiFetch } from './client'
import { buyAsset, fetchHoldings, fetchPopularAssets, searchAssets, sellAsset } from './assets'

const mockedApiFetch = vi.mocked(apiFetch)

beforeEach(() => {
  mockedApiFetch.mockReset()
})

describe('fetchPopularAssets', () => {
  it('unwraps the results field', async () => {
    const results = [{ symbol: 'AAPL', name: 'Apple Inc.' }]
    mockedApiFetch.mockResolvedValue({ results })
    await expect(fetchPopularAssets('stock')).resolves.toBe(results)
    expect(mockedApiFetch).toHaveBeenCalledWith('/assets/stock/popular', expect.any(String))
  })
})

describe('searchAssets', () => {
  it('url-encodes the query', async () => {
    mockedApiFetch.mockResolvedValue({ results: [] })
    await searchAssets('crypto', 'bit coin')
    expect(mockedApiFetch).toHaveBeenCalledWith('/assets/crypto/search?q=bit%20coin', expect.any(String))
  })
})

describe('fetchHoldings', () => {
  it('unwraps the shares field', async () => {
    mockedApiFetch.mockResolvedValue({ shares: 4.5 })
    await expect(fetchHoldings(1, 'stock', 'AAPL')).resolves.toBe(4.5)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/assets/stock/AAPL/holdings',
      expect.any(String),
    )
  })
})

describe('buyAsset', () => {
  it('posts the ticker and quantity', async () => {
    mockedApiFetch.mockResolvedValue(undefined)
    await buyAsset(1, 'stock', 'AAPL', 5, 'key-1')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/assets/stock/buy',
      expect.any(String),
      { method: 'POST', body: { ticker: 'AAPL', quantity: 5 }, idempotencyKey: 'key-1' },
    )
  })
})

describe('sellAsset', () => {
  it('posts the ticker and quantity', async () => {
    mockedApiFetch.mockResolvedValue(undefined)
    await sellAsset(1, 'stock', 'AAPL', 2)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/assets/stock/sell',
      expect.any(String),
      { method: 'POST', body: { ticker: 'AAPL', quantity: 2 }, idempotencyKey: undefined },
    )
  })
})
