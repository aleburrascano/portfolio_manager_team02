import { useEffect, useRef, useState } from 'react'
import SearchBar from './components/SearchBar'
import AssetList from './components/AssetList'
import AssetDetail from './components/AssetDetail'
import { fetchPopularAssets, searchAssets, type Asset, type AssetType, type User } from './api'
import './Home.css'

const ASSET_TYPES: { type: AssetType; label: string }[] = [
  { type: 'stock', label: 'Stocks' },
  { type: 'crypto', label: 'Crypto' },
]

const POPULAR_POLL_INTERVAL_MS: Record<AssetType, number> = {
  stock: 10000,
  crypto: 5000,
}

function Home({ user }: { user: User }) {
  const [assetType, setAssetType] = useState<AssetType>('stock')
  const [query, setQuery] = useState('')
  const [popularAssets, setPopularAssets] = useState<Asset[]>([])
  const [popularLoading, setPopularLoading] = useState(true)
  const [searchResults, setSearchResults] = useState<Asset[]>([])
  const [searching, setSearching] = useState(false)
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

  useEffect(() => {
    let cancelled = false

    const interval = setInterval(() => {
      fetchPopularAssets(assetType)
        .then((assets) => {
          if (cancelled) return
          popularCache.current[assetType] = assets
          setPopularAssets(assets)
        })
        .catch(() => {})
    }, POPULAR_POLL_INTERVAL_MS[assetType])

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [assetType])

  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      setSearchResults([])
      return
    }

    setSearching(true)
    const timeout = setTimeout(async () => {
      try {
        setSearchResults(await searchAssets(assetType, trimmed))
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 300)

    return () => clearTimeout(timeout)
  }, [assetType, query])

  function switchAssetType(next: AssetType) {
    if (popularLoading || next === assetType) return
    setAssetType(next)
    setQuery('')
    setSelectedSymbol(null)
  }

  const isSearching = query.trim().length > 0

  return (
    <section id="home-content">
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
                : `Most Active ${assetType === 'stock' ? 'Stocks' : 'Crypto'}`
            }
            assetType={assetType}
            assets={isSearching ? searchResults : popularAssets}
            loading={isSearching ? searching : popularLoading}
            onSelect={setSelectedSymbol}
          />
        </>
      )}
    </section>
  )
}

export default Home
