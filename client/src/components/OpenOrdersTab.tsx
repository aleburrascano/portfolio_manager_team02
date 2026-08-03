import { useCallback, useEffect, useState } from 'react'
import {
  cancelLimitOrder,
  fetchLimitOrders,
  type AssetType,
  type LimitOrder,
  type User,
} from '../api'
import { formatCurrency, formatNumber } from '../format'
import './OpenOrdersTab.css'

function formatPlaced(value: string) {
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Pending GTC limit orders for one asset type, with a cancel action per row.
 *
 * Scoped to whichever type the trade screen is showing; only the types the
 * server reports as supporting conditional orders ever get here.
 */
function OpenOrdersTab({ user, assetType }: { user: User; assetType: AssetType }) {
  const [orders, setOrders] = useState<LimitOrder[] | null>(null)
  const [error, setError] = useState('')
  const [cancellingId, setCancellingId] = useState<number | null>(null)

  // Fetching and storing are kept apart so the effect can drop a response
  // that arrives after the user has moved on, while the cancel handler -
  // which is always acting on the screen in front of someone - just takes
  // the result. Reaching for state inside the effect body is what the
  // hooks lint objects to.
  const loadOrders = useCallback(
    () => fetchLimitOrders(user.userId, assetType, 'pending'),
    [user.userId, assetType],
  )

  useEffect(() => {
    let cancelled = false

    loadOrders()
      .then((rows) => {
        if (!cancelled) setOrders(rows)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load open orders.')
        }
      })

    return () => {
      cancelled = true
    }
  }, [loadOrders])

  async function handleCancel(orderId: number) {
    setCancellingId(orderId)
    try {
      await cancelLimitOrder(user.userId, orderId)
      setOrders(await loadOrders())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel order.')
    } finally {
      setCancellingId(null)
    }
  }

  return (
    <section className="open-orders">
      {error && <p className="asset-list-status">{error}</p>}

      {orders === null ? (
        <div className="open-orders-loading" aria-busy="true">
          <span className="visually-hidden">Loading open orders</span>
          {Array.from({ length: 3 }, (_, index) => (
            <span key={index} className="skeleton skeleton-holding" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <p className="open-orders-empty">
          You don't have any open limit orders. Place one from a stock's Trade panel and it'll
          show up here until it fills or you cancel it.
        </p>
      ) : (
        <div className="open-orders-scroll">
          <table className="open-orders-table">
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Side</th>
                <th scope="col" className="numeric">Quantity</th>
                <th scope="col" className="numeric">Limit price</th>
                <th scope="col">Placed</th>
                <th scope="col" aria-label="Cancel" />
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.limitOrderId}>
                  <td data-label="Ticker" className="figure open-orders-ticker">{order.ticker}</td>
                  <td data-label="Side" className={`open-orders-side ${order.side}`}>{order.side}</td>
                  <td data-label="Quantity" className="numeric figure">{formatNumber(order.quantity, 2)}</td>
                  <td data-label="Limit price" className="numeric figure">
                    {formatCurrency(order.limitPrice)}
                  </td>
                  <td data-label="Placed">{formatPlaced(order.createdAt)}</td>
                  <td data-label="">
                    <button
                      type="button"
                      className="secondary-btn open-orders-cancel"
                      disabled={cancellingId === order.limitOrderId}
                      onClick={() => handleCancel(order.limitOrderId)}
                    >
                      {cancellingId === order.limitOrderId ? 'Cancelling…' : 'Cancel'}
                    </button>
                  </td>
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
