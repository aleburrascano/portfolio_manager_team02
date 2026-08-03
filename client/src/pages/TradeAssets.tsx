import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import SearchBar from '../components/SearchBar'
import AssetList from '../components/AssetList'
import Icon, { type IconName } from './../components/Icon'
import OpenOrdersTab from '../components/OpenOrdersTab'
import { fetchPopularAssets, searchAssets, type Asset, type AssetType, type User } from '../api'
import { useLiveQuotes } from '../realtime'
import './TradeAssets.css'

// Carries the price chart, so it is fetched when someone opens an asset
// rather than being paid for by everyone who only browses the list.
const AssetDetail = lazy(() => import('../components/AssetDetail'))

const ASSET_TYPES: { type: AssetType; label: string; icon: IconName }[] = [
  { type: 'stock', label: 'Stocks', icon: 'stock' },
  { type: 'crypto', label: 'Crypto', icon: 'crypto' },
  { type: 'bond', label: 'Bonds', icon: 'bond' },
]

// Derived from the tab list so a new asset type only has to be added once.
const ASSET_TYPE_LABELS = Object.fromEntries(
  ASSET_TYPES.map(({ type, label }) => [type, label]),
) as Record<AssetType, string>

function TradeAssets({
  user,
  openAsset,
}: {
  user: User
  /** An asset picked elsewhere - a holdings row, a watchlist tile. */
  openAsset?: { assetType: AssetType; symbol: string } | null
}) {
  const [assetType, setAssetType] = useState<AssetType>(openAsset?.assetType ?? 'stock')
  const [query, setQuery] = useState('')
  const [popularAssets, setPopularAssets] = useState<Asset[]>([])
  const [popularLoading, setPopularLoading] = useState(true)
  // Results are tagged with the search they answer, so "still loading" is
  // derived from what we hold rather than tracked in a separate flag that
  // could drift out of sync with it.
  const [search, setSearch] = useState<{ key: string; assets: Asset[] }>({ key: '', assets: [] })
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(openAsset?.symbol ?? null)
  // Limit orders are stocks-only, so this only ever shows for that tab -
  // switching away from Stocks drops back to browsing rather than leaving
  // a dead-end view up for an asset type that doesn't support it.
  const [showOpenOrders, setShowOpenOrders] = useState(false)
  const popularCache = useRef<Partial<Record<AssetType, Asset[]>>>({})

  useEffect(() => {
    const cached = popularCache.current[assetType]
    if (cached) {
      setPopularAssets(cached)
      setPopularLoading(false)
      return
    }

    let cancelled = false
    setPopularLoading(true)

    fetchPopularAssets(assetType)
      .then((assets) => {
        if (cancelled) return
        popularCache.current[assetType] = assets
        setPopularAssets(assets)
      })
      .catch(() => {
        if (!cancelled) setPopularAssets([])
      })
      .finally(() => {
        if (!cancelled) setPopularLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [assetType])

  const trimmedQuery = query.trim()
  const isSearching = trimmedQuery.length > 0
  const searchKey = `${assetType}:${trimmedQuery}`
  const searchLoading = isSearching && search.key !== searchKey

  useEffect(() => {
    if (!isSearching) return

    let cancelled = false
    const timeout = setTimeout(async () => {
      let assets: Asset[]
      try {
        assets = await searchAssets(assetType, trimmedQuery)
      } catch {
        assets = []
      }
      if (!cancelled) setSearch({ key: searchKey, assets })
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [assetType, trimmedQuery, isSearching, searchKey])

  // Only the rows actually on screen are subscribed to, so switching tabs
  // or searching moves the server's work with the user.
  const listed = isSearching ? search.assets : popularAssets
  const live = useLiveQuotes(assetType, listed.map((asset) => asset.symbol))
  const assets = listed.map((asset) => ({ ...asset, ...live[asset.symbol] }))

  function switchAssetType(next: AssetType) {
    if (next === assetType) return
    setAssetType(next)
    setQuery('')
    setSelectedSymbol(null)
    setShowOpenOrders(false)
  }

  return (
    <section id="trade-assets-content">
      {showOpenOrders ? (
        <>
          <button type="button" className="back-btn" onClick={() => setShowOpenOrders(false)}>
            ← Back
          </button>
          <OpenOrdersTab user={user} />
        </>
      ) : selectedSymbol ? (
        <Suspense
          fallback={
            <div className="asset-detail-loading" aria-busy="true">
              <span className="visually-hidden">Loading {selectedSymbol}</span>
              <span className="skeleton skeleton-title" />
              <span className="skeleton skeleton-chart" />
            </div>
          }
        >
          <AssetDetail
            assetType={assetType}
            symbol={selectedSymbol}
            user={user}
            onBack={() => setSelectedSymbol(null)}
          />
        </Suspense>
      ) : (
        <>
          {/* Not disabled while loading: switching tabs is a navigation
              decision the user has already made, and blocking it behind a
              network round-trip they did not ask to wait for is the wrong
              trade. The in-flight request for the old tab is cancelled. */}
          {/* Tabs and search share a row once there's width for it, so the
              list starts higher up the page instead of below two bands. */}
          <div className="trade-controls">
            <div className="asset-type-tabs">
              {ASSET_TYPES.map(({ type, label, icon }) => (
                <button
                  key={type}
                  type="button"
                  className={assetType === type ? 'active' : ''}
                  aria-pressed={assetType === type}
                  onClick={() => switchAssetType(type)}
                >
                  <Icon name={icon} />
                  {label}
                </button>
              ))}
            </div>
            {assetType === 'stock' && (
              <button
                type="button"
                className="secondary-btn open-orders-toggle"
                onClick={() => setShowOpenOrders(true)}
              >
                Open orders
              </button>
            )}
            <SearchBar value={query} onChange={setQuery} />
          </div>
          <AssetList
            title={
              isSearching
                ? 'Search results'
                : `Most active ${ASSET_TYPE_LABELS[assetType].toLowerCase()}`
            }
            assetType={assetType}
            assets={assets}
            loading={isSearching ? searchLoading : popularLoading}
            emptyMessage={
              isSearching
                ? `No ${ASSET_TYPE_LABELS[assetType].toLowerCase()} match "${trimmedQuery}". Check the spelling, or try another asset type above.`
                : `No ${ASSET_TYPE_LABELS[assetType].toLowerCase()} are available right now.`
            }
            onSelect={setSelectedSymbol}
          />
        </>
      )}
    </section>
  )
}

export default TradeAssets
