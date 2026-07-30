import { useEffect, useRef, useState } from 'react'
import SearchBar from '../components/SearchBar'
import AssetList from '../components/AssetList'
import AssetDetail from '../components/AssetDetail'
import { fetchPopularAssets, searchAssets, type Asset, type AssetType, type User } from '../api'
import { useLiveQuotes } from '../realtime'
import './TradeAssets.css'

const ASSET_TYPES: { type: AssetType; label: string }[] = [
  { type: 'stock', label: 'Stocks' },
  { type: 'crypto', label: 'Crypto' },
  { type: 'bond', label: 'Bonds' },
]

// Derived from the tab list so a new asset type only has to be added once.
const ASSET_TYPE_LABELS = Object.fromEntries(
  ASSET_TYPES.map(({ type, label }) => [type, label]),
) as Record<AssetType, string>

function TradeAssets({ user }: { user: User }) {
  const [assetType, setAssetType] = useState<AssetType>('stock')
  const [query, setQuery] = useState('')
  const [popularAssets, setPopularAssets] = useState<Asset[]>([])
  const [popularLoading, setPopularLoading] = useState(true)
  // Results are tagged with the search they answer, so "still loading" is
  // derived from what we hold rather than tracked in a separate flag that
  // could drift out of sync with it.
  const [search, setSearch] = useState<{ key: string; assets: Asset[] }>({ key: '', assets: [] })
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
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
  // Bonds are repriced once a day rather than streamed, so there's nothing
  // for a subscription to deliver.
  const live = useLiveQuotes(assetType === 'bond' ? [] : listed.map((asset) => asset.symbol))
  const assets = listed.map((asset) => ({ ...asset, ...live[asset.symbol] }))

  function switchAssetType(next: AssetType) {
    if (popularLoading || next === assetType) return
    setAssetType(next)
    setQuery('')
    setSelectedSymbol(null)
  }

  return (
    <section id="trade-assets-content">
      {selectedSymbol ? (
        <AssetDetail
          assetType={assetType}
          symbol={selectedSymbol}
          user={user}
          onBack={() => setSelectedSymbol(null)}
        />
      ) : (
        <>
          <div className="asset-type-tabs">
            {ASSET_TYPES.map(({ type, label }) => (
              <button
                key={type}
                type="button"
                className={assetType === type ? 'active' : ''}
                disabled={popularLoading}
                onClick={() => switchAssetType(type)}
              >
                {label}
              </button>
            ))}
          </div>
          <SearchBar value={query} onChange={setQuery} />
          <AssetList
            title={
              isSearching
                ? 'Search Results'
                : `Most Active ${ASSET_TYPE_LABELS[assetType]}`
            }
            assetType={assetType}
            assets={assets}
            loading={isSearching ? searchLoading : popularLoading}
            onSelect={setSelectedSymbol}
          />
        </>
      )}
    </section>
  )
}

export default TradeAssets
