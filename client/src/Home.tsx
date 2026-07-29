import { useEffect, useState } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import AssetList from './components/AssetList'
import AssetDetail from './components/AssetDetail'
import { fetchPopularAssets, searchAssets, type Asset, type User } from './api'

const ASSET_TYPE = 'stock'

function Home({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [query, setQuery] = useState('')
  const [popularAssets, setPopularAssets] = useState<Asset[]>([])
  const [searchResults, setSearchResults] = useState<Asset[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [balanceRefreshKey, setBalanceRefreshKey] = useState(0)

  useEffect(() => {
    async function loadPopularAssets() {
      try {
        setPopularAssets(await fetchPopularAssets(ASSET_TYPE))
      } catch {
        setPopularAssets([])
      }
    }

    loadPopularAssets()
  }, [])

  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      setSearchResults([])
      return
    }

    setSearching(true)
    const timeout = setTimeout(async () => {
      try {
        setSearchResults(await searchAssets(ASSET_TYPE, trimmed))
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 300)

    return () => clearTimeout(timeout)
  }, [query])

  const isSearching = query.trim().length > 0

  return (
    <>
      <Header user={user} onLogout={onLogout} refreshKey={balanceRefreshKey} />
      <section id="home-content">
        {selectedSymbol ? (
          <AssetDetail
            assetType={ASSET_TYPE}
            symbol={selectedSymbol}
            user={user}
            onBack={() => setSelectedSymbol(null)}
            onTraded={() => setBalanceRefreshKey((key) => key + 1)}
          />
        ) : (
          <>
            <SearchBar value={query} onChange={setQuery} />
            <AssetList
              title={isSearching ? 'Search Results' : 'Most Active Stocks'}
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
