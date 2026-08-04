import { useState } from 'react'
import {
  useBondRedemptions,
  useOrderCancellations,
  useOrderFills,
  type BondRedemption,
  type OrderCancellation,
  type OrderFill,
} from '../../hooks/realtime'
import { formatCurrency, formatNumber } from '../../lib/format'
import './FillToasts.css'

/** Long enough to read a sentence, short enough not to sit in the way. */
const DISMISS_AFTER_MS = 9000

type Notice = { id: string; title: string; body: string; subject: string }

function fillNotice(fill: OrderFill): Notice {
  return {
    id: `fill:${fill.limitOrderId}`,
    title: `${fill.orderType === 'stop' ? 'Stop' : 'Limit'} order filled`,
    body: `${fill.side === 'buy' ? 'Bought' : 'Sold'} ${formatNumber(fill.quantity, 2)} ${fill.ticker} at ${formatCurrency(fill.price)}.`,
    subject: fill.ticker,
  }
}

function cancellationNotice(cancellation: OrderCancellation): Notice {
  return {
    id: `cancelled:${cancellation.limitOrderId}`,
    title: `${cancellation.orderType === 'stop' ? 'Stop' : 'Limit'} order cancelled`,
    body: `You no longer hold any ${cancellation.ticker}, so the order to sell ${formatNumber(cancellation.quantity, 2)} of it was dropped.`,
    subject: cancellation.ticker,
  }
}

function redemptionNotice(payout: BondRedemption): Notice {
  return {
    id: `bond:${payout.ticker}`,
    title: 'Bond matured',
    body: `${payout.ticker} paid out ${formatCurrency(payout.proceeds)} at face value.`,
    subject: payout.ticker,
  }
}

/**
 * Announces the things that move someone's money without them doing
 * anything: a conditional order filling, and a bond reaching maturity.
 *
 * Both happen on the server's own schedule and can land on any screen, so
 * they are announced at the shell rather than on the pages that would
 * otherwise show them - which are exactly the ones the user is least likely
 * to be looking at when it happens.
 *
 * role="status" rather than "alert": worth knowing and not worth
 * interrupting for, so a screen reader announces it at the next pause.
 */
function FillToasts() {
  const [notices, setNotices] = useState<Notice[]>([])

  function announce(notice: Notice) {
    setNotices((current) => [...current, notice])
    setTimeout(
      () => setNotices((current) => current.filter((n) => n.id !== notice.id)),
      DISMISS_AFTER_MS,
    )
  }

  useOrderFills((fill) => announce(fillNotice(fill)))
  useBondRedemptions((payout) => announce(redemptionNotice(payout)))
  useOrderCancellations((cancellation) => announce(cancellationNotice(cancellation)))

  function dismiss(id: string) {
    setNotices((current) => current.filter((n) => n.id !== id))
  }

  if (notices.length === 0) return null

  return (
    <div className="fill-toasts" role="status" aria-live="polite">
      {notices.map((notice) => (
        <div key={notice.id} className="fill-toast">
          <div>
            <p className="fill-toast-title">{notice.title}</p>
            <p className="fill-toast-body">{notice.body}</p>
          </div>
          <button
            type="button"
            className="fill-toast-close"
            aria-label={`Dismiss ${notice.subject} notice`}
            onClick={() => dismiss(notice.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

export default FillToasts
