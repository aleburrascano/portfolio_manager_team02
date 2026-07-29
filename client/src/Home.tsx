import { useEffect, useState } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import AssetList from './components/AssetList'
import AssetDetail from './components/AssetDetail'
import { fetchPopularAssets, searchAssets, type Asset, type AssetType, type User } from './api'
import './Home.css'

const ASSET_TYPES: { type: AssetType; label: string }[] = [
  { type: 'stock', label: 'Stocks' },
  { type: 'crypto', label: 'Crypto' },
]

function Home({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [assetType, setAssetType] = useState<AssetType>('stock')
  const [query, setQuery] = useState('')
  const [popularAssets, setPopularAssets] = useState<Asset[]>([])
  const [searchResults, setSearchResults] = useState<Asset[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  useEffect(() => {
    async function loadPopularAssets() {
      try {
        setPopularAssets(await fetchPopularAssets(assetType))
      } catch {
        setPopularAssets([])
      }
    }

    loadPopularAssets()
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
    setAssetType(next)
    setQuery('')
    setSelectedSymbol(null)
  }

  const isSearching = query.trim().length > 0

  return (
    <>
      <Header user={user} onLogout={onLogout} />
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
              assets={isSearching ? searchResults : popularAssets}
              loading={isSearching && searching}
              onSelect={setSelectedSymbol}
            />
          </>
        )}
      </section>
    </>
  )
}

export default Home
