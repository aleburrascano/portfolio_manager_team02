import { useCallback, useEffect, useState } from 'react'
import {
  cancelLimitOrder,
  fetchLimitOrders,
  type AssetType,
  type LimitOrder,
  type OrderStatus,
  type User,
} from '../api'
import { useOrderFills } from '../realtime'
import { formatCurrency, formatNumber } from '../format'
import './OpenOrdersTab.css'

/** How much history to pull. Pending lists are short; resolved ones aren't. */
const HISTORY_LIMIT = 100

const FILTERS: { status: OrderStatus; label: string; empty: string }[] = [
  {
    status: 'pending',
    label: 'Open',
    empty: "You don't have any open orders. Place one from an asset's Trade panel and it'll show up here until it fills or you cancel it.",
  },
  {
    status: 'filled',
    label: 'Filled',
    empty: 'Nothing has filled yet. An order moves here the moment its trigger is crossed.',
  },
  {
    status: 'cancelled',
    label: 'Cancelled',
    empty: "You haven't cancelled any orders.",
  },
]

/**
 * Which side of the trigger this order is waiting for.
 *
 * A limit waits for a price at least as good as the trigger, a stop for one
 * at least as bad, so the same side reads the opposite way round and the
 * figure on its own would be ambiguous.
 */
function triggerLabel(order: LimitOrder): string {
  const waitsForFall = (order.orderType === 'limit') === (order.side === 'buy')
  return waitsForFall ? '≤' : '≥'
}

function formatPlaced(value: string) {
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * A user's GTC conditional orders for one asset type: open, filled, or
 * cancelled.
 *
 * Only open orders can be cancelled, so that column carries a resolution
 * date on the other two tabs instead of a button - a resolved order is a
 * record, and the one thing worth knowing about it is when it stopped
 * waiting.
 *
 * Scoped to whichever type the trade screen is showing; only the types the
 * server reports as supporting conditional orders ever get here.
 */
function OpenOrdersTab({ user, assetType }: { user: User; assetType: AssetType }) {
  const [status, setStatus] = useState<OrderStatus>('pending')
  const [cancellingId, setCancellingId] = useState<number | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const requestKey = `${user.userId}:${assetType}:${status}:${reloadKey}`
  const [state, setState] = useState<{ key: string; orders?: LimitOrder[]; error?: string }>({
    key: '',
  })

  const loadOrders = useCallback(
    () => fetchLimitOrders(user.userId, assetType, status, HISTORY_LIMIT),
    [user.userId, assetType, status],
  )

  useEffect(() => {
    let cancelled = false

    loadOrders()
      .then((rows) => {
        if (!cancelled) setState({ key: requestKey, orders: rows })
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            key: requestKey,
            error: err instanceof Error ? err.message : 'Failed to load orders.',
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [requestKey, loadOrders])

  useOrderFills(() => setReloadKey((current) => current + 1))

  async function handleCancel(order: LimitOrder) {
    setCancellingId(order.limitOrderId)
    try {
      await cancelLimitOrder(order)
      setState({ key: requestKey, orders: await loadOrders() })
    } catch (err) {
      setState({
        key: requestKey,
        error: err instanceof Error ? err.message : 'Failed to cancel order.',
      })
    } finally {
      setCancellingId(null)
    }
  }

  const loading = state.key !== requestKey
  const orders = state.orders ?? null
  const error = state.error ?? null
  const isPending = status === 'pending'
  const emptyMessage = FILTERS.find((f) => f.status === status)!.empty

  return (
    <section className="open-orders">
      <div className="open-orders-filters" role="group" aria-label="Order status">
        {FILTERS.map((filter) => (
          <button
            key={filter.status}
            type="button"
            className={status === filter.status ? 'active' : ''}
            aria-pressed={status === filter.status}
            onClick={() => setStatus(filter.status)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {error && <p className="asset-list-status">{error}</p>}

      {loading || orders === null ? (
        <div className="open-orders-loading" aria-busy="true">
          <span className="visually-hidden">Loading orders</span>
          {Array.from({ length: 3 }, (_, index) => (
            <span key={index} className="skeleton skeleton-holding" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <p className="open-orders-empty">{emptyMessage}</p>
      ) : (
        <div className="open-orders-scroll">
          <table className="open-orders-table">
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Side</th>
                <th scope="col">Type</th>
                <th scope="col" className="numeric">Quantity</th>
                <th scope="col" className="numeric">Trigger</th>
                <th scope="col">Placed</th>
                {isPending ? (
                  <th scope="col" aria-label="Cancel" />
                ) : (
                  <th scope="col">{status === 'filled' ? 'Filled' : 'Cancelled'}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.limitOrderId}>
                  <td data-label="Ticker" className="figure open-orders-ticker">{order.ticker}</td>
                  <td data-label="Side" className={`open-orders-side ${order.side}`}>{order.side}</td>
                  <td data-label="Type" className="open-orders-type">{order.orderType}</td>
                  <td data-label="Quantity" className="numeric figure">{formatNumber(order.quantity, 2)}</td>
                  <td data-label="Trigger" className="numeric figure">
                    {triggerLabel(order)} {formatCurrency(order.limitPrice)}
                  </td>
                  <td data-label="Placed">{formatPlaced(order.createdAt)}</td>
                  {isPending ? (
                    <td data-label="">
                      <button
                        type="button"
                        className="secondary-btn open-orders-cancel"
                        disabled={cancellingId === order.limitOrderId}
                        onClick={() => handleCancel(order)}
                      >
                        {cancellingId === order.limitOrderId ? 'Cancelling…' : 'Cancel'}
                      </button>
                    </td>
                  ) : (
                    <td data-label="Resolved">
                      {order.resolvedAt ? formatPlaced(order.resolvedAt) : '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default OpenOrdersTab
