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
import { useAssetTypes } from '../asset-types'
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
/** What the panel offers, which is the two conditional kinds plus market. */
type PanelOrderType = 'market' | 'limit' | 'stop'
type Status = { kind: 'success' | 'error'; text: string }

const ORDER_TABS: { type: PanelOrderType; label: string }[] = [
  { type: 'market', label: 'Market' },
  { type: 'limit', label: 'Limit' },
  { type: 'stop', label: 'Stop' },
]

/**
 * What each conditional kind waits for, said in the direction the user is
 * trading. A stop and a limit on the same side are opposites, and the price
 * box alone doesn't say which way round this one runs.
 */
function triggerHint(orderType: PanelOrderType, isBuy: boolean): string | null {
  if (orderType === 'limit') {
    return isBuy ? 'Buys if the price falls to this or lower.' : 'Sells if the price rises to this or higher.'
  }
  if (orderType === 'stop') {
    return isBuy ? 'Buys if the price rises to this or higher.' : 'Sells if the price falls to this or lower.'
  }
  return null
}

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
  const { byType } = useAssetTypes()
  const capabilities = byType[assetType]
  const idempotency = useIdempotencyKey()
  const [detail, setDetail] = useState<AssetDetailType | null>(null)
  const [detailError, setDetailError] = useState('')
  const [history, setHistory] = useState<PricePoint[]>([])
  const [shares, setShares] = useState(0)
  const [side, setSide] = useState<Side>('buy')
  const [quantity, setQuantity] = useState('1')
  const [orderType, setOrderType] = useState<PanelOrderType>('market')
  const [limitPrice, setLimitPrice] = useState('')
  const [status, setStatus] = useState<Status | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    let cancelled = false

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
        if (!cancelled) setHistory([])
      }
      try {
        const s = await fetchHoldings(user.userId, assetType, symbol)
        if (!cancelled) setShares(s)
      } catch {
        if (!cancelled) setShares(0)
      }
    }

    loadInitial()

    return () => {
      cancelled = true
    }
  }, [assetType, symbol, user.userId])

  const { quotes: live, lastUpdate } = useLiveFeed(assetType, [symbol])
  const quote = detail ? { ...detail, ...live[symbol] } : null

  const price = quote?.currentPrice ?? 0
  const isPositive = (quote?.change ?? 0) >= 0
  const connected = useQuoteConnection()
  const tick = usePriceDirection(quote?.currentPrice)
  const parsedQuantity = Number(quantity)
  const isConditional = orderType !== 'market'
  const parsedLimitPrice = Number(limitPrice)
  const effectivePrice = isConditional
    ? (Number.isFinite(parsedLimitPrice) ? parsedLimitPrice : 0)
    : price
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
  const waitsForFall = (orderType === 'limit') === isBuy
  const triggerDirection = waitsForFall ? 'falls to or below' : 'rises to or above'

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
    if (isConditional) {
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
      if (isConditional) {
        const key = idempotency.keyFor(
          `${orderType}:${side}:${assetType}:${symbol}:${parsedQuantity}:${parsedLimitPrice}`,
        )
        await placeLimitOrder(
          user.userId, assetType, symbol, side, parsedQuantity, parsedLimitPrice, orderType, key,
        )
        idempotency.reset()
        setQuantity('1')
        setLimitPrice('')
        setOrderType('market')
        setStatus({
          kind: 'success',
          text: `${orderType === 'stop' ? 'Stop' : 'Limit'} order placed: ${isBuy ? 'buy' : 'sell'} ${formatNumber(parsedQuantity, 2)} ${symbol} if the price ${triggerDirection} ${formatCurrency(parsedLimitPrice)}.`,
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
                <div className={`trade-price${tick ? ` tick-${tick}` : ''}`}>
                  {formatCurrency(price)}{' '}
                  <span className={isPositive ? 'positive' : 'negative'}>
                    {isPositive ? '▲' : '▼'} {formatNumber(Math.abs(quote.changePercent ?? 0), 2)}%
                    {' '}({formatCurrency(Math.abs(quote.change ?? 0))})
                  </span>
                </div>
                {capabilities?.streams && (
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

                {capabilities?.supportsLimitOrders && (
                  <div className="order-type-tabs">
                    {ORDER_TABS.map(({ type, label }) => (
                      <button
                        key={type}
                        type="button"
                        className={orderType === type ? 'active' : ''}
                        aria-pressed={orderType === type}
                        onClick={() => setOrderType(type)}
                      >
                        {label}
                      </button>
                    ))}
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

                  {isConditional && (
                    <>
                      <label htmlFor="limit-price">
                        {orderType === 'stop' ? 'Stop price' : 'Limit price'}
                      </label>
                      <input
                        id="limit-price"
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={limitPrice}
                        onChange={(e) => setLimitPrice(e.target.value)}
                        aria-describedby="trigger-hint"
                        required
                      />
                      <p id="trigger-hint" className="trade-hint">
                        {triggerHint(orderType, isBuy)}
                      </p>
                    </>
                  )}

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
                    {submitting
                      ? 'Submitting…'
                      : isConditional
                        ? `Review ${orderType} ${side}`
                        : `Review ${side}`}
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

          {confirming && isConditional && (
            <ConfirmDialog
              title={`Place ${orderType} ${side} for ${formatNumber(parsedQuantity, 2)} ${symbol}?`}
              confirmLabel="Place order"
              cancelLabel="Back"
              onConfirm={handleConfirm}
              onCancel={() => setConfirming(false)}
              message={
                <dl className="confirm-summary">
                  <dt>{isBuy ? 'Buy' : 'Sell'}</dt>
                  <dd className="figure">
                    {formatNumber(parsedQuantity, 2)} {symbol} if the price {triggerDirection}{' '}
                    {formatCurrency(parsedLimitPrice)}
                  </dd>
                  <dt>Fills at</dt>
                  <dd className="figure">The market price when it triggers</dd>
                  <dt className="confirm-summary-total">Status</dt>
                  <dd className="figure confirm-summary-total">
                    Pending until the price is met — nothing is charged yet
                  </dd>
                </dl>
              }
            />
          )}

          {confirming && !isConditional && (
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
