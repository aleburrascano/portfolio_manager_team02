import { apiFetch, del, post } from './client'
import type { AssetType } from './assets'

export type OrderSide = 'buy' | 'sell'
export type OrderStatus = 'pending' | 'filled' | 'cancelled'

export type LimitOrder = {
  limitOrderId: number
  ticker: string
  side: OrderSide
  quantity: number
  limitPrice: number
  status: OrderStatus
  createdAt: string
  resolvedAt: string | null
  assetTransactionId: number | null
}

export async function placeLimitOrder(
  userId: number,
  assetType: AssetType,
  ticker: string,
  side: OrderSide,
  quantity: number,
  limitPrice: number,
  idempotencyKey?: string,
): Promise<LimitOrder> {
  const data = await apiFetch<{ order: LimitOrder }>(
    `/users/${userId}/assets/${assetType}/limit-orders`,
    'Failed to place order',
    post({ ticker, side, quantity, limitPrice }, idempotencyKey),
  )
  return data.order
}

export async function fetchLimitOrders(
  userId: number,
  assetType: AssetType,
  status?: OrderStatus,
): Promise<LimitOrder[]> {
  const query = status ? `?status=${status}` : ''
  const data = await apiFetch<{ orders: LimitOrder[] }>(
    `/users/${userId}/assets/${assetType}/limit-orders${query}`,
    'Failed to fetch orders',
  )
  return data.orders
}

export async function cancelLimitOrder(userId: number, limitOrderId: number): Promise<void> {
  await apiFetch(`/users/${userId}/limit-orders/${limitOrderId}`, 'Failed to cancel order', del())
}
