import { useEffect, useState } from 'react'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import {
  buyAsset,
  fetchAssetDetail,
  fetchAssetHistory,
  fetchHoldings,
  sellAsset,
  type AssetDetail as AssetDetailType,
  type AssetType,
  type PricePoint,
  type User,
} from '../api'
import { useBalance } from '../balance-context'
import { useLiveQuotes } from '../realtime'
import { useIdempotencyKey } from '../idempotency'
import { validateQuantityInput } from '../validation'
import { formatCurrency, formatNumber } from '../format'
import AssetLogo from './AssetLogo'
import './AssetDetail.css'

type Side = 'buy' | 'sell'

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
  const [status, setStatus] = useState('')
  const [submitting, setSubmitting] = useState(false)

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

  const live = useLiveQuotes(assetType, [symbol])
  // The pushed update carries only the fields that have a value, so it
  // refreshes the price without wiping the fields it doesn't cover.
  const quote = detail ? { ...detail, ...live[symbol] } : null

  const price = quote?.currentPrice ?? 0
  const isPositive = (quote?.change ?? 0) >= 0
  const parsedQuantity = Number(quantity)
  const maxQuantity =
    side === 'buy'
      ? price > 0 && balance !== null
        ? balance / price
        : 0
      : shares
  const total = Number.isFinite(parsedQuantity) ? parsedQuantity * price : 0

  function switchSide(next: Side) {
    setSide(next)
    setStatus('')
    setQuantity('1')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('')

    const quantityError = validateQuantityInput(quantity)
    if (quantityError) {
      setStatus(quantityError)
      return
    }
    if (parsedQuantity > maxQuantity) {
      setStatus(side === 'buy' ? 'Not enough cash!' : 'Not enough shares!')
      return
    }

    setSubmitting(true)
    try {
      const key = idempotency.keyFor(`${side}:${assetType}:${symbol}:${parsedQuantity}`)
      if (side === 'buy') {
        await buyAsset(user.userId, assetType, symbol, parsedQuantity, key)
      } else {
        await sellAsset(user.userId, assetType, symbol, parsedQuantity, key)
      }
      idempotency.reset()
      setShares(await fetchHoldings(user.userId, assetType, symbol))
      await refreshBalance()
      setQuantity('1')
      setStatus(side === 'buy' ? 'Purchase successful!' : 'Sale successful!')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Transaction failed.')
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
        <p className="asset-list-status">Loading…</p>
      ) : (
        <>
          <div className="asset-detail-title">
            <AssetLogo symbol={quote.symbol} assetType={assetType} />
            <div>
              <h1>{quote.name}</h1>
              <span className="asset-symbol">{quote.symbol}</span>
            </div>
          </div>

          <div className="asset-detail-grid">
            <div className="asset-detail-main">
              <div className="chart-card">
                <div className="trade-price">
                  {formatCurrency(price)}{' '}
                  <span className={isPositive ? 'positive' : 'negative'}>
                    {isPositive ? '▲' : '▼'} {formatNumber(Math.abs(quote.changePercent ?? 0), 2)}%
                    {' '}({formatCurrency(Math.abs(quote.change ?? 0))})
                  </span>
                </div>
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

              <div className="stats-grid">
                <div>
                  <span className="stats-label">Daily High</span>
                  <span>{quote.dayHigh != null ? formatCurrency(quote.dayHigh) : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">Daily Low</span>
                  <span>{quote.dayLow != null ? formatCurrency(quote.dayLow) : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">52 Week High</span>
                  <span>{quote.yearHigh != null ? formatCurrency(quote.yearHigh) : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">52 Week Low</span>
                  <span>{quote.yearLow != null ? formatCurrency(quote.yearLow) : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">Open</span>
                  <span>{quote.open != null ? formatCurrency(quote.open) : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">Volume</span>
                  <span>{quote.volume != null ? formatNumber(quote.volume) : '—'}</span>
                </div>
              </div>
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

                <form onSubmit={handleSubmit}>
                  <label htmlFor="quantity">
                    Quantity <span className="trade-max">max: {formatNumber(maxQuantity, 1)}</span>
                  </label>
                  <input
                    id="quantity"
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    required
                  />

                  <p className="trade-total">Total: {formatCurrency(total)}</p>

                  <button type="submit" className="submit-btn" disabled={submitting}>
                    {submitting ? 'Submitting...' : 'Submit'}
                  </button>
                </form>

                {status && (
                  <p className={`trade-status ${status.includes('successful') ? 'success' : 'error'}`}>
                    {status}
                  </p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default AssetDetail
