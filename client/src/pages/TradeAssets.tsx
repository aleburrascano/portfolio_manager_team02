import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import SearchBar from '../components/SearchBar'
import AssetList from '../components/AssetList'
import Icon, { type IconName } from './../components/Icon'
import OpenOrdersTab from '../components/OpenOrdersTab'
import { fetchPopularAssets, searchAssets, type Asset, type AssetType, type User } from '../api'
import { useAssetTypes } from '../asset-types'
import { useLiveQuotes } from '../realtime'
import './TradeAssets.css'

const AssetDetail = lazy(() => import('../components/AssetDetail'))

const ICONS: Partial<Record<AssetType, IconName>> = {
  stock: 'stock',
  crypto: 'crypto',
  bond: 'bond',
}
const FALLBACK_ICON: IconName = 'stock'

/**
 * Browse, search, and open one asset type - or that type's orders.
 *
 * The asset type, the selected symbol, and whether the orders view is
 * showing are all read from the address rather than held here, so every one
 * of them is a place: shareable, bookmarkable, and reachable with the
 * browser's back button.
 */
function TradeAssets({ user, showOrders = false }: { user: User; showOrders?: boolean }) {
  const { types, byType } = useAssetTypes()
  const navigate = useNavigate()
  const params = useParams<{ assetType: string; symbol: string }>()

  const assetType = params.assetType as AssetType
  const selectedSymbol = params.symbol ?? null
  const capabilities = byType[assetType]

  const [query, setQuery] = useState('')
  const [popularAssets, setPopularAssets] = useState<Asset[]>([])
  const [popularLoading, setPopularLoading] = useState(true)
  const [search, setSearch] = useState<{ key: string; assets: Asset[] }>({ key: '', assets: [] })
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

  const listed = isSearching ? search.assets : popularAssets
  const live = useLiveQuotes(assetType, listed.map((asset) => asset.symbol))
  const assets = listed.map((asset) => ({ ...asset, ...live[asset.symbol] }))
  const typeLabel = capabilities?.label ?? assetType

  if (types.length > 0 && !capabilities) {
    return <Navigate to={`/trade/${types[0].assetType}`} replace />
  }

  function switchAssetType(next: AssetType) {
    if (next === assetType) return
    setQuery('')
    navigate(`/trade/${next}`)
  }

  return (
    <section id="trade-assets-content">
      {showOrders ? (
        <>
          <Link className="back-btn" to={`/trade/${assetType}`}>
            ← Back
          </Link>
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
            onBack={() => navigate(`/trade/${assetType}`)}
          />
        </Suspense>
      ) : (
        <>
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
                  <Icon name={ICONS[type] ?? FALLBACK_ICON} />
                  {label}
                </button>
              ))}
            </div>
            {capabilities?.supportsLimitOrders && (
              <Link className="secondary-btn open-orders-toggle" to={`/orders/${assetType}`}>
                Orders
              </Link>
            )}
            <SearchBar value={query} onChange={setQuery} />
          </div>
          <AssetList
            title={isSearching ? 'Search results' : `Most active ${typeLabel.toLowerCase()}`}
            assetType={assetType}
            assets={assets}
            loading={isSearching ? searchLoading : popularLoading}
            emptyMessage={
              isSearching
                ? `No ${typeLabel.toLowerCase()} match "${trimmedQuery}". Check the spelling, or try another asset type above.`
                : `No ${typeLabel.toLowerCase()} are available right now.`
            }
            onSelect={(symbol) => navigate(`/trade/${assetType}/${encodeURIComponent(symbol)}`)}
          />
        </>
      )}
    </section>
  )
}

export default TradeAssets
