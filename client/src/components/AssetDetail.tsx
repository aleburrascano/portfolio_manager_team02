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
import AssetLogo from './AssetLogo'
import './AssetDetail.css'

type Side = 'buy' | 'sell'

// Crypto trades around the clock and moves faster, so it's worth polling
// more often than stocks.
const POLL_INTERVAL_MS: Record<AssetType, number> = {
  stock: 5000,
  crypto: 3000,
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

    async function pollPrice() {
      // Only the price/holdings tick live; the year of history behind the
      // chart doesn't change second to second, so there's no point refetching it.
      try {
        const d = await fetchAssetDetail(assetType, symbol)
        if (!cancelled) setDetail(d)
      } catch {
        // keep showing the last good price rather than blanking the page
      }
      try {
        const s = await fetchHoldings(user.userId, assetType, symbol)
        if (!cancelled) setShares(s)
      } catch {
        // keep showing the last known holdings
      }
    }

    loadInitial()
    const interval = setInterval(pollPrice, POLL_INTERVAL_MS[assetType])

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [assetType, symbol, user.userId])

  const price = detail?.currentPrice ?? 0
  const isPositive = (detail?.change ?? 0) >= 0
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

    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setStatus('Enter a valid quantity.')
      return
    }
    if (parsedQuantity > maxQuantity) {
      setStatus(side === 'buy' ? 'Not enough cash!' : 'Not enough shares!')
      return
    }

    setSubmitting(true)
    try {
      if (side === 'buy') {
        await buyAsset(user.userId, assetType, symbol, parsedQuantity)
      } else {
        await sellAsset(user.userId, assetType, symbol, parsedQuantity)
      }
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
      ) : !detail ? (
        <p className="asset-list-status">Loading…</p>
      ) : (
        <>
          <div className="asset-detail-title">
            <AssetLogo symbol={detail.symbol} assetType={assetType} />
            <div>
              <h1>{detail.name}</h1>
              <span className="asset-symbol">{detail.symbol}</span>
            </div>
          </div>

          <div className="asset-detail-grid">
            <div className="asset-detail-main">
              <div className="chart-card">
                <div className="trade-price">
                  ${price.toFixed(2)}{' '}
                  <span className={isPositive ? 'positive' : 'negative'}>
                    {isPositive ? '▲' : '▼'} {Math.abs(detail.changePercent ?? 0).toFixed(2)}%
                    {' '}(${Math.abs(detail.change ?? 0).toFixed(2)})
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
                      tickFormatter={(value) => `$${Number(value).toLocaleString()}`}
                      tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                      axisLine={false}
                      tickLine={false}
                      width={64}
                    />
                    <Tooltip
                      formatter={(value) => [`$${Number(value).toFixed(2)}`, 'Close']}
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
                  <span>{detail.dayHigh !== undefined ? `$${detail.dayHigh.toFixed(2)}` : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">Daily Low</span>
                  <span>{detail.dayLow !== undefined ? `$${detail.dayLow.toFixed(2)}` : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">52 Week High</span>
                  <span>{detail.yearHigh !== undefined ? `$${detail.yearHigh.toFixed(2)}` : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">52 Week Low</span>
                  <span>{detail.yearLow !== undefined ? `$${detail.yearLow.toFixed(2)}` : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">Open</span>
                  <span>{detail.open !== undefined ? `$${detail.open.toFixed(2)}` : '—'}</span>
                </div>
                <div>
                  <span className="stats-label">Volume</span>
                  <span>{detail.volume !== undefined ? detail.volume.toLocaleString() : '—'}</span>
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
                    Quantity <span className="trade-max">max: {maxQuantity.toFixed(1)}</span>
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

                  <p className="trade-total">Total: ${total.toFixed(2)}</p>

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
