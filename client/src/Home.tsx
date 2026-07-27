import { useEffect, useState } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import StockList from './components/StockList'
import { fetchPopularStocks, searchStocks, type Stock } from './api'

function Home() {
  const [query, setQuery] = useState('')
  const [popularStocks, setPopularStocks] = useState<Stock[]>([])
  const [searchResults, setSearchResults] = useState<Stock[]>([])
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    async function loadPopularStocks() {
      try {
        setPopularStocks(await fetchPopularStocks())
      } catch {
        setPopularStocks([])
      }
    }

    loadPopularStocks()
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
        setSearchResults(await searchStocks(trimmed))
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
      <Header />
      <section id="home-content">
        <SearchBar value={query} onChange={setQuery} />
        <StockList
          title={isSearching ? 'Search Results' : 'Most Active Stocks'}
          stocks={isSearching ? searchResults : popularStocks}
          loading={isSearching && searching}
        />
      </section>
    </>
  )
}

export default Home
