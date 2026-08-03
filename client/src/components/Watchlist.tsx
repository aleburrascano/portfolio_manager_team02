import { useEffect, useState } from 'react'
import {
  fetchPopularAssets,
  fetchWatchlist,
  type AssetType,
  type User,
  type WatchlistEntry,
} from '../api'
import { useAssetTypes } from '../asset-types'
import { useLiveFeeds, useQuoteConnection } from '../realtime'
import { formatCurrency, formatNumber } from '../format'
import AssetLogo from './AssetLogo'
import LiveIndicator from './LiveIndicator'
import './Watchlist.css'

/** Below this, a move is noise. Painting it green or red would be a lie. */
const FLAT_THRESHOLD = 0.05
/** How many most-active stocks stand in before anything has been saved. */
const SUGGESTION_COUNT = 6

function direction(changePercent: number): 'up' | 'down' | 'flat' {
  if (Math.abs(changePercent) < FLAT_THRESHOLD) return 'flat'
  return changePercent > 0 ? 'up' : 'down'
}

const GLYPHS = { up: '▲', down: '▼', flat: '—' } as const

type Tile = {
  symbol: string
  assetType: AssetType
  currentPrice: number | null
  changePercent: number | null
}

function Watchlist({
  user,
  onSelectAsset,
}: {
  user: User
  /** Opens the asset in the trade screen, so a tile is a way in. */
  onSelectAsset?: (assetType: AssetType, symbol: string) => void
}) {
  const { types } = useAssetTypes()
  const [saved, setSaved] = useState<WatchlistEntry[] | null>(null)
  const [suggested, setSuggested] = useState<Tile[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    fetchWatchlist(user.userId)
      .then(async (entries) => {
        if (cancelled) return
        setSaved(entries)

        if (entries.length === 0) {
          try {
            const popular = await fetchPopularAssets('stock')
            if (!cancelled) {
              setSuggested(
                popular.slice(0, SUGGESTION_COUNT).map((asset) => ({
                  symbol: asset.symbol,
                  assetType: 'stock' as AssetType,
                  currentPrice: asset.currentPrice ?? null,
                  changePercent: asset.changePercent ?? null,
                })),
              )
            }
          } catch {
            if (!cancelled) setSuggested([])
          }
        }
      })
      .catch(() => {
        if (!cancelled) setSaved([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [user.userId])

  const showingSuggestions = (saved?.length ?? 0) === 0
  const tiles: Tile[] = showingSuggestions
    ? suggested
    : (saved ?? []).map((entry) => ({
        symbol: entry.symbol,
        assetType: entry.assetType,
        currentPrice: entry.currentPrice,
        changePercent: entry.changePercent,
      }))

  const streamedTypes = types.filter((info) => info.streams).map((info) => info.assetType)
  const symbolsByType = Object.fromEntries(
    streamedTypes.map((type) => [type, tiles.filter((t) => t.assetType === type).map((t) => t.symbol)]),
  ) as Record<AssetType, string[]>
  const feeds = useLiveFeeds(symbolsByType)
  const streamed = tiles.filter((tile) => streamedTypes.includes(tile.assetType))
  const connected = useQuoteConnection()

  const items = tiles.map((tile) => {
    const update = feeds.quotes[tile.symbol]
    return {
      ...tile,
      currentPrice: update?.currentPrice ?? tile.currentPrice,
      changePercent: update?.changePercent ?? tile.changePercent,
    }
  })

  return (
    <section className="dashboard-card watchlist-card" aria-labelledby="watchlist-title">
      <div className="watchlist-header">
        <div className="watchlist-heading">
          <h3 id="watchlist-title" className="section-title">
            {showingSuggestions ? 'Most active today' : 'Watchlist'}
          </h3>
          {showingSuggestions && !loading && (
            <p className="watchlist-hint">
              Nothing saved yet — open any asset and choose <strong>Save for later</strong> to
              build your own list.
            </p>
          )}
        </div>
        {items.length > 0 && streamed.length > 0 && (
          <LiveIndicator connected={connected} lastUpdate={feeds.lastUpdate} />
        )}
      </div>

      {loading ? (
        <div className="tile-grid" aria-hidden="true">
          {Array.from({ length: SUGGESTION_COUNT }, (_, index) => (
            <span key={index} className="skeleton skeleton-tile" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="watchlist-status">
          Prices are unavailable right now. They'll appear here once the market feed reconnects.
        </p>
      ) : (
        <ul className="tile-grid">
          {items.map((item) => {
            const changePercent = item.changePercent ?? 0
            const trend = direction(changePercent)
            const body = (
              <>
                <span className="tile-top">
                  <AssetLogo symbol={item.symbol} assetType={item.assetType} />
                  <span className="tile-sym figure">{item.symbol}</span>
                </span>
                <span className="figure tile-price">
                  {item.currentPrice != null ? formatCurrency(item.currentPrice) : '—'}
                </span>
                <span className={`figure tile-chg ${trend}`}>
                  {GLYPHS[trend]} {formatNumber(Math.abs(changePercent), 2)}%
                </span>
              </>
            )

            return (
              <li key={`${item.assetType}:${item.symbol}`}>
                {onSelectAsset ? (
                  <button
                    type="button"
                    className={`watch-tile ${trend}`}
                    onClick={() => onSelectAsset(item.assetType, item.symbol)}
                  >
                    {body}
                  </button>
                ) : (
                  <span className={`watch-tile ${trend}`}>{body}</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export default Watchlist
