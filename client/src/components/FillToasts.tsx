import { useState } from 'react'
import { useOrderFills, type OrderFill } from '../realtime'
import { formatCurrency, formatNumber } from '../format'
import './FillToasts.css'

/** Long enough to read a sentence, short enough not to sit in the way. */
const DISMISS_AFTER_MS = 9000

/**
 * Announces conditional orders as they fill.
 *
 * A fill is the one thing in this app that moves someone's money without
 * them doing anything, and it can land on any screen - so it is announced
 * at the shell level rather than on the orders tab, which is exactly the
 * place they are least likely to be looking when it happens.
 *
 * role="status" rather than "alert": it is worth knowing and not worth
 * interrupting for, so a screen reader announces it at the next pause.
 */
function FillToasts() {
  const [fills, setFills] = useState<OrderFill[]>([])

  useOrderFills((fill) => {
    setFills((current) => [...current, fill])
    setTimeout(
      () => setFills((current) => current.filter((f) => f.limitOrderId !== fill.limitOrderId)),
      DISMISS_AFTER_MS,
    )
  })

  function dismiss(limitOrderId: number) {
    setFills((current) => current.filter((f) => f.limitOrderId !== limitOrderId))
  }

  if (fills.length === 0) return null

  return (
    <div className="fill-toasts" role="status" aria-live="polite">
      {fills.map((fill) => (
        <div key={fill.limitOrderId} className="fill-toast">
          <div>
            <p className="fill-toast-title">
              {fill.orderType === 'stop' ? 'Stop' : 'Limit'} order filled
            </p>
            {/* The executed price, not the trigger: for a stop especially,
                those are different numbers and only one of them is what
                the user actually paid. */}
            <p className="fill-toast-body">
              {fill.side === 'buy' ? 'Bought' : 'Sold'} {formatNumber(fill.quantity, 2)}{' '}
              {fill.ticker} at {formatCurrency(fill.price)}.
            </p>
          </div>
          <button
            type="button"
            className="fill-toast-close"
            aria-label={`Dismiss ${fill.ticker} fill`}
            onClick={() => dismiss(fill.limitOrderId)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

export default FillToasts
