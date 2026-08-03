import { apiFetch, del, followLink, post } from './client'
import type { AssetType } from './assets'

export type OrderSide = 'buy' | 'sell'
export type OrderStatus = 'pending' | 'filled' | 'cancelled'

/**
 * Which way an order's trigger runs.
 *
 * 'limit' waits for a price at least as good as limitPrice - at or below to
 * buy, at or above to sell. 'stop' is the exact mirror, waiting for the
 * price to move against the position: a stop loss, or a breakout entry.
 */
export type OrderType = 'limit' | 'stop'

export type LimitOrder = {
  limitOrderId: number
  ticker: string
  side: OrderSide
  orderType: OrderType
  quantity: number
  /** The trigger, not the price it fills at. */
  limitPrice: number
  status: OrderStatus
  createdAt: string
  /** When it filled or was cancelled; null while it is still pending. */
  resolvedAt: string | null
  /** The trade a fill produced; null unless this order filled. */
  assetTransactionId: number | null
  /** What can be done with this order, as the server describes it. */
  _links: { cancel: string }
}

export async function placeLimitOrder(
  userId: number,
  assetType: AssetType,
  ticker: string,
  side: OrderSide,
  quantity: number,
  limitPrice: number,
  orderType: OrderType = 'limit',
  idempotencyKey?: string,
): Promise<LimitOrder> {
  const data = await apiFetch<{ order: LimitOrder }>(
    `/users/${userId}/assets/${assetType}/limit-orders`,
    'Failed to place order',
    post({ ticker, side, quantity, limitPrice, orderType }, idempotencyKey),
  )
  return data.order
}

export async function fetchLimitOrders(
  userId: number,
  assetType: AssetType,
  status?: OrderStatus,
  limit?: number,
): Promise<LimitOrder[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (limit != null) params.set('limit', String(limit))
  const query = params.size > 0 ? `?${params}` : ''

  const data = await apiFetch<{ orders: LimitOrder[] }>(
    `/users/${userId}/assets/${assetType}/limit-orders${query}`,
    'Failed to fetch orders',
  )
  return data.orders
}

/**
 * Cancel an order by following the `cancel` link it came with.
 *
 * The route shape isn't repeated here: the server said where the action
 * lives when it handed the order over, which is what the `_links` on every
 * response are for.
 */
export async function cancelLimitOrder(order: LimitOrder): Promise<void> {
  await followLink(order._links.cancel, 'Failed to cancel order', del())
}
