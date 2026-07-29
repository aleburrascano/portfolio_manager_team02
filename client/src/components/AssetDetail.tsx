import { useEffect, useState } from 'react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts'
import {
  buyAsset,
  fetchAssetDetail,
  fetchAssetHistory,
  fetchBalance,
  fetchHoldings,
  sellAsset,
  type AssetDetail as AssetDetailType,
  type AssetType,
  type PricePoint,
  type User,
} from '../api'
import StockLogo from './StockLogo'
import './AssetDetail.css'

type Side = 'buy' | 'sell'

function AssetDetail({
  assetType,
  symbol,
  user,
  onBack,
  onTraded,
}: {
  assetType: AssetType
  symbol: string
  user: User
  onBack: () => void
  onTraded: () => void
}) {
  const [detail, setDetail] = useState<AssetDetailType | null>(null)
  const [detailError, setDetailError] = useState('')
  const [history, setHistory] = useState<PricePoint[]>([])
  const [shares, setShares] = useState(0)
  const [balance, setBalance] = useState<number | null>(null)
  const [side, setSide] = useState<Side>('buy')
  const [quantity, setQuantity] = useState('1')
  const [status, setStatus] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setDetail(null)
    setDetailError('')
    fetchAssetDetail(assetType, symbol)
      .then(setDetail)
      .catch((error) =>
        setDetailError(error instanceof Error ? error.message : 'Failed to load asset.')
      )
    fetchAssetHistory(assetType, symbol).then(setHistory).catch(() => setHistory([]))
    fetchHoldings(user.userId, assetType, symbol).then(setShares).catch(() => setShares(0))
    fetchBalance(user.userId).then(setBalance).catch(() => setBalance(null))
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
      setBalance(await fetchBalance(user.userId))
      setQuantity('1')
      setStatus(side === 'buy' ? 'Purchase successful!' : 'Sale successful!')
      onTraded()
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
            <StockLogo symbol={detail.symbol} />
            <div>
              <h1>{detail.name}</h1>
              <span className="asset-symbol">{detail.symbol}</span>
            </div>
          </div>

          <div className="chart-card">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={history}>
                <XAxis dataKey="date" hide />
                <YAxis domain={['auto', 'auto']} hide />
                <Tooltip
                  formatter={(value) => [`$${Number(value).toFixed(2)}`, 'Close']}
                  labelFormatter={(label) => label}
                />
                <Line
                  type="monotone"
                  dataKey="close"
                  stroke={isPositive ? 'var(--positive)' : 'var(--negative)'}
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

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

            <div className="trade-price">
              ${price.toFixed(2)}{' '}
              <span className={isPositive ? 'positive' : 'negative'}>
                {isPositive ? '▲' : '▼'} {Math.abs(detail.changePercent ?? 0).toFixed(2)}%
                {' '}(${Math.abs(detail.change ?? 0).toFixed(2)})
              </span>
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
        </>
      )}
    </div>
  )
}

export default AssetDetail
