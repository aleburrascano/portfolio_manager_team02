import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
  post: vi.fn((body: unknown, idempotencyKey?: string) => ({ method: 'POST', body, idempotencyKey })),
  del: vi.fn(() => ({ method: 'DELETE' })),
}))

import { apiFetch } from './client'
import { cancelLimitOrder, fetchLimitOrders, placeLimitOrder } from './orders'

const mockedApiFetch = vi.mocked(apiFetch)

beforeEach(() => {
  mockedApiFetch.mockReset()
})

describe('placeLimitOrder', () => {
  it('posts the order fields and idempotency key, and unwraps the order', async () => {
    const order = { limitOrderId: 1, ticker: 'AAPL', side: 'buy', quantity: 5, limitPrice: 8, status: 'pending', createdAt: '2026-01-01T00:00:00', resolvedAt: null, assetTransactionId: null }
    mockedApiFetch.mockResolvedValue({ order })

    await expect(placeLimitOrder(1, 'stock', 'AAPL', 'buy', 5, 8, 'key-1')).resolves.toBe(order)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/assets/stock/limit-orders',
      expect.any(String),
      { method: 'POST', body: { ticker: 'AAPL', side: 'buy', quantity: 5, limitPrice: 8 }, idempotencyKey: 'key-1' },
    )
  })
})

describe('fetchLimitOrders', () => {
  it('omits the status query param when not given', async () => {
    mockedApiFetch.mockResolvedValue({ orders: [] })
    await fetchLimitOrders(1, 'stock')
    expect(mockedApiFetch).toHaveBeenCalledWith('/users/1/assets/stock/limit-orders', expect.any(String))
  })

  it('appends the status query param when given', async () => {
    mockedApiFetch.mockResolvedValue({ orders: [] })
    await fetchLimitOrders(1, 'stock', 'pending')
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/assets/stock/limit-orders?status=pending',
      expect.any(String),
    )
  })

  it('unwraps the orders field', async () => {
    const orders = [{ limitOrderId: 1 }]
    mockedApiFetch.mockResolvedValue({ orders })
    await expect(fetchLimitOrders(1, 'stock')).resolves.toBe(orders)
  })
})

describe('cancelLimitOrder', () => {
  it('issues a DELETE to the order-scoped route', async () => {
    mockedApiFetch.mockResolvedValue({ status: 'cancelled' })
    await cancelLimitOrder(1, 42)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/users/1/limit-orders/42',
      expect.any(String),
      { method: 'DELETE' },
    )
  })
})
