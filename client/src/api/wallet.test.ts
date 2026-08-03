import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
  post: vi.fn((body: unknown, idempotencyKey?: string) => ({ method: 'POST', body, idempotencyKey })),
}))

import { apiFetch } from './client'
import { fetchBalance, fetchPortfolioBreakdown, fetchTransactions, submitCashTransaction } from './wallet'

const mockedApiFetch = vi.mocked(apiFetch)

beforeEach(() => {
  mockedApiFetch.mockReset()
})

describe('fetchBalance', () => {
  it('unwraps the balance field', async () => {
    mockedApiFetch.mockResolvedValue({ balance: 123.45 })
    await expect(fetchBalance(1)).resolves.toBe(123.45)
    expect(mockedApiFetch).toHaveBeenCalledWith('/users/1/balance', expect.any(String))
  })
})

describe('fetchPortfolioBreakdown', () => {
  it('defaults a missing cash figure to zero', async () => {
    mockedApiFetch.mockResolvedValue({ stock: 50 })
    await expect(fetchPortfolioBreakdown(1)).resolves.toEqual({ cash: 0, stock: 50 })
  })

  it('passes through an asset type it does not know about', async () => {
    mockedApiFetch.mockResolvedValue({ cash: 100, commodity: 25 })
    await expect(fetchPortfolioBreakdown(1)).resolves.toEqual({ cash: 100, commodity: 25 })
  })
})

describe('fetchTransactions', () => {
  it('returns the page with its total', async () => {
    const page = { transactions: [{ transactionId: 1 }], total: 214 }
    mockedApiFetch.mockResolvedValue(page)
    await expect(fetchTransactions(1)).resolves.toBe(page)
  })

  it('asks for the whole history when given no paging', async () => {
    mockedApiFetch.mockResolvedValue({ transactions: [], total: 0 })
    await fetchTransactions(1)
    expect(mockedApiFetch).toHaveBeenCalledWith('/users/1/transactions', expect.any(String))
  })

  it('sends limit, offset and sort when they are asked for', async () => {
    mockedApiFetch.mockResolvedValue({ transactions: [], total: 0 })
    await fetchTransactions(1, 50, 100, 'oldest')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/transactions?limit=50&offset=100&sort=oldest',
      expect.any(String),
    )
  })

  it('leaves the default sort out of the query', async () => {
    mockedApiFetch.mockResolvedValue({ transactions: [], total: 0 })
    await fetchTransactions(1, 50)
    expect(mockedApiFetch).toHaveBeenCalledWith('/users/1/transactions?limit=50', expect.any(String))
  })
})

describe('submitCashTransaction', () => {
  it('posts to the deposit endpoint with the idempotency key', async () => {
    mockedApiFetch.mockResolvedValue({ message: 'ok' })
    await submitCashTransaction(1, 'deposit', 50, 'key-1')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/deposit',
      expect.any(String),
      { method: 'POST', body: { amount: 50 }, idempotencyKey: 'key-1' },
    )
  })

  it('posts to the withdraw endpoint', async () => {
    mockedApiFetch.mockResolvedValue({ message: 'ok' })
    await submitCashTransaction(1, 'withdraw', 50)
    expect(mockedApiFetch).toHaveBeenCalledWith('/users/1/withdraw', expect.any(String), expect.anything())
  })
})
