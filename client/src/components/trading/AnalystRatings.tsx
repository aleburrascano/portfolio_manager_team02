import { useEffect, useState } from 'react'
import { fetchAssetRatings, type AnalystRatings as Ratings, type AssetType } from '../../api'
import { formatCurrency, formatNumber } from '../../lib/format'
import './AnalystRatings.css'

/** The feed's consensus word, in the register the rest of the app uses. */
const CONSENSUS_LABELS: Record<string, string> = {
  strong_buy: 'Strong buy',
  buy: 'Buy',
  outperform: 'Outperform',
  hold: 'Hold',
  underperform: 'Underperform',
  sell: 'Sell',
  strong_sell: 'Strong sell',
}

/** Bullish buckets read green, bearish red, hold stays neutral. */
const BUCKET_TONE: Record<string, string> = {
  'Strong buy': 'bullish',
  Buy: 'bullish',
  Hold: 'neutral',
  Sell: 'bearish',
  'Strong sell': 'bearish',
}

function consensusTone(score: number | null) {
  if (score == null) return 'neutral'
  if (score <= 2.5) return 'bullish'
  if (score >= 3.5) return 'bearish'
  return 'neutral'
}

/**
 * Where the current price sits between the low and high targets, 0-100.
 * Clamped, because a price can and does run past either end.
 */
function targetPosition(ratings: Ratings, price: number | null) {
  const { targetLow, targetHigh } = ratings
  if (targetLow == null || targetHigh == null || price == null) return null
  const span = targetHigh - targetLow
  if (span <= 0) return null
  return Math.min(100, Math.max(0, ((price - targetLow) / span) * 100))
}

function AnalystRatings({
  assetType,
  symbol,
  price,
}: {
  assetType: AssetType
  symbol: string
  price: number | null
}) {
  const requestKey = `${assetType}:${symbol}`
  const [state, setState] = useState<{ key: string; ratings?: Ratings | null; failed?: boolean }>({
    key: '',
  })

  useEffect(() => {
    let cancelled = false

    async function loadRatings() {
      try {
        const ratings = await fetchAssetRatings(assetType, symbol)
        if (!cancelled) setState({ key: requestKey, ratings })
      } catch {
        if (!cancelled) setState({ key: requestKey, failed: true })
      }
    }

    void loadRatings()

    return () => {
      cancelled = true
    }
  }, [assetType, symbol, requestKey])

  const loading = state.key !== requestKey

  if (loading) {
    return (
      <div className="ratings-card" aria-busy="true">
        <h3 className="stats-heading">Analyst ratings</h3>
        <span className="visually-hidden">Loading analyst ratings</span>
        <span className="skeleton skeleton-ratings" />
      </div>
    )
  }

  if (state.failed || !state.ratings) return null

  const ratings = state.ratings
  const total = ratings.distribution.reduce((sum, bucket) => sum + bucket.count, 0)
  const marker = targetPosition(ratings, price ?? ratings.currentPrice)
  const consensus = ratings.consensus ? CONSENSUS_LABELS[ratings.consensus] ?? ratings.consensus : null

  return (
    <div className="ratings-card">
      {/*
        * The two counts here are different populations and are labelled as
        * such: the bars are every rating on file, while the targets come
        * only from the analysts who published a price. Shown as one number
        * they never reconciled - "14 analysts" above bars totalling 63.
        */}
      <div className="ratings-header">
        <h3 className="stats-heading">Analyst ratings</h3>
        {total > 0 && (
          <span className="ratings-count">
            {total} {total === 1 ? 'rating' : 'ratings'}
          </span>
        )}
      </div>

      {consensus && (
        <p className={`ratings-consensus ${consensusTone(ratings.score)}`}>
          {consensus}
          {ratings.score != null && (
            <span className="ratings-score figure">{formatNumber(ratings.score, 2)} / 5</span>
          )}
        </p>
      )}

      {total > 0 && (
        <ul className="ratings-bars">
          {ratings.distribution.map((bucket) => (
            <li key={bucket.label}>
              <span className="ratings-bar-label">{bucket.label}</span>
              <span className="ratings-bar-track">
                <span
                  className={`ratings-bar-fill ${BUCKET_TONE[bucket.label] ?? 'neutral'}`}
                  style={{ width: `${(bucket.count / total) * 100}%` }}
                />
              </span>
              <span className="figure ratings-bar-count">{bucket.count}</span>
            </li>
          ))}
        </ul>
      )}

      {ratings.targetMean != null && (
        <div className="ratings-targets">
          <p className="ratings-target-headline">
            <span>
              12-month target
              {ratings.analystCount != null && (
                <span className="ratings-target-source">
                  from {ratings.analystCount} {ratings.analystCount === 1 ? 'analyst' : 'analysts'}
                </span>
              )}
            </span>
            <span className="figure">{formatCurrency(ratings.targetMean)}</span>
          </p>

          {marker != null && (
            <>
              <span className="ratings-scale" aria-hidden="true">
                <span className="ratings-scale-marker" style={{ left: `${marker}%` }} />
              </span>
              <p className="ratings-scale-labels">
                <span className="figure">{formatCurrency(ratings.targetLow!)}</span>
                <span className="ratings-scale-caption">low · high</span>
                <span className="figure">{formatCurrency(ratings.targetHigh!)}</span>
              </p>
            </>
          )}
        </div>
      )}

      <p className="ratings-source">Consensus of Wall Street analysts, via Yahoo Finance.</p>
    </div>
  )
}

export default AnalystRatings
