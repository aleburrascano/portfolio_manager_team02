import { useEffect, useState } from 'react'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import {
  buyAsset,
  fetchAssetDetail,
  fetchAssetHistory,
  fetchHoldings,
  placeLimitOrder,
  sellAsset,
  type AssetDetail as AssetDetailType,
  type AssetType,
  type PricePoint,
  type User,
} from '../api'
import { useBalance } from '../balance-context'
import { useLiveFeed, usePriceDirection, useQuoteConnection } from '../realtime'
import { useIdempotencyKey } from '../idempotency'
import { validateAmountInput, validateQuantityInput } from '../validation'
import { formatCurrency, formatNumber } from '../format'
import AssetLogo from './AssetLogo'
import AnalystRatings from './AnalystRatings'
import ConfirmDialog from './ConfirmDialog'
import LiveIndicator from './LiveIndicator'
import WatchButton from './WatchButton'
import './AssetDetail.css'

type Side = 'buy' | 'sell'
type OrderType = 'market' | 'limit'
type Status = { kind: 'success' | 'error'; text: string }

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function AssetDetail({
  assetType,
  symbol,
  user,
  onBack,
}: {
  assetType: AssetType
  symbol: string
  user: User
  onBack: () => void
}) {
  const { balance, refreshBalance } = useBalance()
  const idempotency = useIdempotencyKey()
  const [detail, setDetail] = useState<AssetDetailType | null>(null)
  const [detailError, setDetailError] = useState('')
  const [history, setHistory] = useState<PricePoint[]>([])
  const [shares, setShares] = useState(0)
  const [side, setSide] = useState<Side>('buy')
  const [quantity, setQuantity] = useState('1')
  const [orderType, setOrderType] = useState<OrderType>('market')
  const [limitPrice, setLimitPrice] = useState('')
  const [status, setStatus] = useState<Status | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    let cancelled = false

    // One-off: the live price arrives over the socket from here on, and the
    // year of history behind the chart doesn't change second to second.
    // Holdings only move when this user trades, which refetches them below.
    async function loadInitial() {
      setDetail(null)
      setDetailError('')
      setHistory([])

      try {
        const d = await fetchAssetDetail(assetType, symbol)
        if (!cancelled) setDetail(d)
      } catch (error) {
        if (!cancelled) setDetailError(error instanceof Error ? error.message : 'Failed to load asset.')
      }
      try {
        const h = await fetchAssetHistory(assetType, symbol)
        if (!cancelled) setHistory(h)
      } catch {
        // history is a nice-to-have for the chart; leave it empty on failure
      }
      try {
        const s = await fetchHoldings(user.userId, assetType, symbol)
        if (!cancelled) setShares(s)
      } catch {
        // holdings default to 0 already
      }
    }

    loadInitial()

    return () => {
      cancelled = true
    }
  }, [assetType, symbol, user.userId])

  const { quotes: live, lastUpdate } = useLiveFeed(assetType, [symbol])
  // The pushed update carries only the fields that have a value, so it
  // refreshes the price without wiping the fields it doesn't cover.
  const quote = detail ? { ...detail, ...live[symbol] } : null

  const price = quote?.currentPrice ?? 0
  const isPositive = (quote?.change ?? 0) >= 0
  const connected = useQuoteConnection()
  const tick = usePriceDirection(quote?.currentPrice)
  const parsedQuantity = Number(quantity)
  const isLimit = orderType === 'limit'
  const parsedLimitPrice = Number(limitPrice)
  // A limit order won't fill at the current price - that's the point of it -
  // so once one is being entered, every downstream figure (max quantity,
  // total, cash after) is computed off the price the user typed instead.
  const effectivePrice = isLimit ? (Number.isFinite(parsedLimitPrice) ? parsedLimitPrice : 0) : price
  const maxQuantity =
    side === 'buy'
      ? effectivePrice > 0 && balance !== null
        ? balance / effectivePrice
        : 0
      : shares
  const total = Number.isFinite(parsedQuantity) ? parsedQuantity * effectivePrice : 0
  const isBuy = side === 'buy'
  const cashAfter = balance !== null ? (isBuy ? balance - total : balance + total) : null
  const sharesAfter = isBuy ? shares + parsedQuantity : shares - parsedQuantity

  function switchSide(next: Side) {
    setSide(next)
    setStatus(null)
    setQuantity('1')
    setOrderType('market')
    setLimitPrice('')
  }

  /** Validates and opens the review. Nothing is sent from here. */
  function handleReview(e: React.FormEvent) {
    e.preventDefault()
    setStatus(null)

    const quantityError = validateQuantityInput(quantity)
    if (quantityError) {
      setStatus({ kind: 'error', text: quantityError })
      return
    }
    if (isLimit) {
      const limitPriceError = validateAmountInput(limitPrice)
      if (limitPriceError) {
        setStatus({ kind: 'error', text: limitPriceError })
        return
      }
    }
    if (parsedQuantity > maxQuantity) {
      setStatus({
        kind: 'error',
        text: isBuy
          ? `${formatCurrency(total)} is more than your ${formatCurrency(balance ?? 0)} cash balance. The most you can buy at this price is ${formatNumber(maxQuantity, 2)}.`
          : `You hold ${formatNumber(shares, 2)} ${symbol}, so you can't sell ${formatNumber(parsedQuantity, 2)}.`,
      })
      return
    }

    setConfirming(true)
  }

  async function handleConfirm() {
    setConfirming(false)
    setSubmitting(true)

    try {
      if (isLimit) {
        const key = idempotency.keyFor(
          `limit:${side}:${assetType}:${symbol}:${parsedQuantity}:${parsedLimitPrice}`,
        )
        await placeLimitOrder(user.userId, assetType, symbol, side, parsedQuantity, parsedLimitPrice, key)
        idempotency.reset()
        // Nothing has settled yet - a limit order just sits pending until
        // its price is crossed - so balance and holdings are left alone.
        setQuantity('1')
        setLimitPrice('')
        setOrderType('market')
        setStatus({
          kind: 'success',
          text: `Limit order placed: ${isBuy ? 'buy' : 'sell'} ${formatNumber(parsedQuantity, 2)} ${symbol} at ${formatCurrency(parsedLimitPrice)} or better.`,
        })
        return
      }

      const key = idempotency.keyFor(`${side}:${assetType}:${symbol}:${parsedQuantity}`)
      if (isBuy) {
        await buyAsset(user.userId, assetType, symbol, parsedQuantity, key)
      } else {
        await sellAsset(user.userId, assetType, symbol, parsedQuantity, key)
      }
      idempotency.reset()
      setShares(await fetchHoldings(user.userId, assetType, symbol))
      await refreshBalance()
      setQuantity('1')
      setStatus({
        kind: 'success',
        text: `${isBuy ? 'Bought' : 'Sold'} ${formatNumber(parsedQuantity, 2)} ${symbol} for ${formatCurrency(total)}.`,
      })
    } catch (error) {
      setStatus({
        kind: 'error',
        text: error instanceof Error ? error.message : 'Transaction failed.',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="asset-detail">
      <button type="button" className="back-btn" onClick={onBack}>
        ← Back
      </button>

      {detailError ? (
        <p className="asset-list-status">{detailError}</p>
      ) : !quote ? (
        <div className="asset-detail-loading" aria-busy="true">
          <span className="visually-hidden">Loading {symbol}</span>
          <span className="skeleton skeleton-title" />
          <span className="skeleton skeleton-chart" />
        </div>
      ) : (
        <>
          <div className="asset-detail-title">
            <AssetLogo symbol={quote.symbol} assetType={assetType} />
            <div>
              <h1>{quote.name}</h1>
              <span className="asset-symbol">{quote.symbol}</span>
            </div>
            <WatchButton user={user} assetType={assetType} symbol={symbol} />
          </div>

          <div className="asset-detail-grid">
            <div className="asset-detail-main">
              <div className="chart-card">
                {/* tick-* flashes for ~700ms in the direction the price moved,
                    so a quote that changes while you are reading it says so. */}
                <div className={`trade-price${tick ? ` tick-${tick}` : ''}`}>
                  {formatCurrency(price)}{' '}
                  <span className={isPositive ? 'positive' : 'negative'}>
                    {isPositive ? '▲' : '▼'} {formatNumber(Math.abs(quote.changePercent ?? 0), 2)}%
                    {' '}({formatCurrency(Math.abs(quote.change ?? 0))})
                  </span>
                </div>
                {/* Bonds are repriced on a schedule rather than streamed,
                    so claiming a live feed for one would be a lie. */}
                {assetType !== 'bond' && (
                  <div className="quote-feed">
                    <LiveIndicator connected={connected} lastUpdate={lastUpdate} />
                  </div>
                )}
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={history} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="assetChartFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatDate}
                      tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                      axisLine={{ stroke: 'var(--border)' }}
                      tickLine={false}
                      minTickGap={40}
                    />
                    <YAxis
                      domain={['auto', 'auto']}
                      tickFormatter={(value) => formatCurrency(Number(value), 0)}
                      tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                      axisLine={false}
                      tickLine={false}
                      width={64}
                    />
                    <Tooltip
                      formatter={(value) => [formatCurrency(Number(value)), 'Close']}
                      labelFormatter={(label) => formatDate(String(label))}
                      contentStyle={{
                        background: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 8,
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="close"
                      stroke="var(--accent)"
                      strokeWidth={2}
                      fill="url(#assetChartFill)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Six figures split into the two questions they answer -
                  what happened today, and where today sits in the year -
                  rather than one flat grid of unrelated numbers. */}
              <div className="stats-card">
                <section className="stats-group">
                  <h3 className="stats-heading">Today</h3>
                  <dl className="stats-list">
                    <dt>Open</dt>
                    <dd className="figure">{quote.open != null ? formatCurrency(quote.open) : '—'}</dd>
                    <dt>High</dt>
                    <dd className="figure">{quote.dayHigh != null ? formatCurrency(quote.dayHigh) : '—'}</dd>
                    <dt>Low</dt>
                    <dd className="figure">{quote.dayLow != null ? formatCurrency(quote.dayLow) : '—'}</dd>
                    <dt>Volume</dt>
                    <dd className="figure">{quote.volume != null ? formatNumber(quote.volume) : '—'}</dd>
                  </dl>
                </section>

                <section className="stats-group">
                  <h3 className="stats-heading">Past 52 weeks</h3>
                  <dl className="stats-list">
                    <dt>High</dt>
                    <dd className="figure">{quote.yearHigh != null ? formatCurrency(quote.yearHigh) : '—'}</dd>
                    <dt>Low</dt>
                    <dd className="figure">{quote.yearLow != null ? formatCurrency(quote.yearLow) : '—'}</dd>
                  </dl>
                </section>
              </div>

              <AnalystRatings assetType={assetType} symbol={symbol} price={price || null} />
            </div>

            <div className="asset-detail-side">
              <div className="trade-card">
                <div className="trade-tabs">
                  <button
                    type="button"
                    className={side === 'buy' ? 'active' : ''}
                    onClick={() => switchSide('buy')}
                  >
                    Buy
                  </button>
                  <button
                    type="button"
                    className={side === 'sell' ? 'active' : ''}
                    onClick={() => switchSide('sell')}
                  >
                    Sell
                  </button>
                </div>

                {/* Limit orders are stocks-only for now, so the toggle only
                    shows up where placing one is actually possible. */}
                {assetType === 'stock' && (
                  <div className="order-type-tabs">
                    <button
                      type="button"
                      className={orderType === 'market' ? 'active' : ''}
                      onClick={() => setOrderType('market')}
                    >
                      Market
                    </button>
                    <button
                      type="button"
                      className={orderType === 'limit' ? 'active' : ''}
                      onClick={() => setOrderType('limit')}
                    >
                      Limit
                    </button>
                  </div>
                )}

                <form onSubmit={handleReview}>
                  <div className="trade-label-row">
                    <label htmlFor="quantity">Quantity</label>
                    <span className="figure trade-max">
                      max {formatNumber(maxQuantity, 2)}
                    </span>
                  </div>
                  <input
                    id="quantity"
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    required
                  />

                  {isLimit && (
                    <>
                      <label htmlFor="limit-price">Limit price</label>
                      <input
                        id="limit-price"
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={limitPrice}
                        onChange={(e) => setLimitPrice(e.target.value)}
                        required
                      />
                    </>
                  )}

                  {/* The wallet lives here rather than only in the header:
                      "can I afford this" is the question being asked at
                      this exact moment, and the answer is the line the
                      order total is subtracted from. */}
                  <dl className="trade-summary">
                    <dt>{isBuy ? 'Order total' : 'Proceeds'}</dt>
                    <dd className="figure">{formatCurrency(total)}</dd>

                    <dt>Cash available</dt>
                    <dd className="figure">
                      {balance !== null ? formatCurrency(balance) : '—'}
                    </dd>

                    <dt className="trade-summary-after">Cash after</dt>
                    <dd
                      className={`figure trade-summary-after${
                        cashAfter !== null && cashAfter < 0 ? ' short' : ''
                      }`}
                    >
                      {cashAfter !== null ? formatCurrency(cashAfter) : '—'}
                    </dd>
                  </dl>

                  <button type="submit" className="submit-btn" disabled={submitting}>
                    {submitting ? 'Submitting…' : isLimit ? `Review ${side} order` : `Review ${side}`}
                  </button>
                </form>

                {status && (
                  <p className={`trade-status ${status.kind}`} role="status">
                    {status.text}
                  </p>
                )}
              </div>
            </div>
          </div>

          {confirming && isLimit && (
            <ConfirmDialog
              title={`Place ${side} order for ${formatNumber(parsedQuantity, 2)} ${symbol}?`}
              confirmLabel="Place order"
              cancelLabel="Back"
              onConfirm={handleConfirm}
              onCancel={() => setConfirming(false)}
              message={
                <dl className="confirm-summary">
                  <dt>{isBuy ? 'Buy' : 'Sell'}</dt>
                  <dd className="figure">
                    {formatNumber(parsedQuantity, 2)} {symbol} at {formatCurrency(parsedLimitPrice)} or better
                  </dd>
                  <dt className="confirm-summary-total">Status</dt>
                  <dd className="figure confirm-summary-total">
                    Pending until the price is met — nothing is charged yet
                  </dd>
                </dl>
              }
            />
          )}

          {confirming && !isLimit && (
            <ConfirmDialog
              title={`${isBuy ? 'Buy' : 'Sell'} ${formatNumber(parsedQuantity, 2)} ${symbol}?`}
              confirmLabel={`${isBuy ? 'Buy' : 'Sell'} ${formatNumber(parsedQuantity, 2)} ${symbol}`}
              cancelLabel="Back"
              onConfirm={handleConfirm}
              onCancel={() => setConfirming(false)}
              message={
                <dl className="confirm-summary">
                  <dt>{isBuy ? 'Buying' : 'Selling'}</dt>
                  <dd className="figure">
                    {formatNumber(parsedQuantity, 2)} at {formatCurrency(price)}
                  </dd>
                  <dt>{isBuy ? 'Cost' : 'Proceeds'}</dt>
                  <dd className="figure">{formatCurrency(total)}</dd>
                  <dt>{symbol} after</dt>
                  <dd className="figure">{formatNumber(sharesAfter, 2)}</dd>
                  <dt className="confirm-summary-total">Cash after</dt>
                  <dd className="figure confirm-summary-total">
                    {cashAfter !== null ? formatCurrency(cashAfter) : '—'}
                  </dd>
                </dl>
              }
            />
          )}
        </>
      )}
    </div>
  )
}

export default AssetDetail
