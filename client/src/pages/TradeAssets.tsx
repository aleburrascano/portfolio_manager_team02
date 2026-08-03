import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import SearchBar from '../components/SearchBar'
import AssetList from '../components/AssetList'
import Icon, { type IconName } from './../components/Icon'
import OpenOrdersTab from '../components/OpenOrdersTab'
import { fetchPopularAssets, searchAssets, type Asset, type AssetType, type User } from '../api'
import { useAssetTypes } from '../asset-types'
import { useLiveQuotes } from '../realtime'
import './TradeAssets.css'

// Carries the price chart, so it is fetched when someone opens an asset
// rather than being paid for by everyone who only browses the list.
const AssetDetail = lazy(() => import('../components/AssetDetail'))

// The tabs, their order, and their labels all come from the server's
// provider registry; only the icon is a client-side decision, and a type
// with no icon of its own gets a neutral one rather than no tab.
const ICONS: Partial<Record<AssetType, IconName>> = {
  stock: 'stock',
  crypto: 'crypto',
  bond: 'bond',
}

function TradeAssets({
  user,
  openAsset,
}: {
  user: User
  /** An asset picked elsewhere - a holdings row, a watchlist tile. */
  openAsset?: { assetType: AssetType; symbol: string } | null
}) {
  const { types, byType } = useAssetTypes()
  const [assetType, setAssetType] = useState<AssetType>(openAsset?.assetType ?? 'stock')
  const [query, setQuery] = useState('')
  const [popularAssets, setPopularAssets] = useState<Asset[]>([])
  const [popularLoading, setPopularLoading] = useState(true)
  // Results are tagged with the search they answer, so "still loading" is
  // derived from what we hold rather than tracked in a separate flag that
  // could drift out of sync with it.
  const [search, setSearch] = useState<{ key: string; assets: Asset[] }>({ key: '', assets: [] })
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(openAsset?.symbol ?? null)
  // Only shown for a type that takes conditional orders - switching away
  // drops back to browsing rather than leaving a dead-end view up for an
  // asset type that doesn't support them.
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
  const typeLabel = byType[assetType]?.label ?? assetType

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
          <OpenOrdersTab user={user} assetType={assetType} />
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
              {types.map(({ assetType: type, label }) => (
                <button
                  key={type}
                  type="button"
                  className={assetType === type ? 'active' : ''}
                  aria-pressed={assetType === type}
                  onClick={() => switchAssetType(type)}
                >
                  <Icon name={ICONS[type] ?? 'stock'} />
                  {label}
                </button>
              ))}
            </div>
            {byType[assetType]?.supportsLimitOrders && (
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
                : `Most active ${typeLabel.toLowerCase()}`
            }
            assetType={assetType}
            assets={assets}
            loading={isSearching ? searchLoading : popularLoading}
            emptyMessage={
              isSearching
                ? `No ${typeLabel.toLowerCase()} match "${trimmedQuery}". Check the spelling, or try another asset type above.`
                : `No ${typeLabel.toLowerCase()} are available right now.`
            }
            onSelect={setSelectedSymbol}
          />
        </>
      )}
    </section>
  )
}

export default TradeAssets
