import { useEffect, useState } from 'react'
import Modal from '../ui/Modal'
import SearchBar from '../ui/SearchBar'
import AssetList from '../trading/AssetList'
import {
  fetchPopularAssets,
  searchAssets,
  type Asset,
  type AssetType,
  type Benchmark,
} from '../../api'
import { useAssetTypes } from '../../context/asset-types'
import './BenchmarkPicker.css'

const SEARCH_DEBOUNCE_MS = 300

/**
 * Pick what the portfolio is measured against.
 *
 * Searches the same catalog the trade screen does rather than offering a
 * fixed list of indices: the interesting question is often "what if I had
 * just bought Bitcoin instead", and anything the app can price it can
 * compare against.
 */
function BenchmarkPicker({
  current,
  onPick,
  onClose,
}: {
  current: Benchmark
  onPick: (benchmark: Benchmark) => void
  onClose: () => void
}) {
  const { types, byType } = useAssetTypes()
  const [assetType, setAssetType] = useState<AssetType>(current.assetType)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<{ key: string; assets: Asset[] }>({ key: '', assets: [] })

  const trimmedQuery = query.trim()
  const resultsKey = `${assetType}:${trimmedQuery}`
  const loading = results.key !== resultsKey

  useEffect(() => {
    let cancelled = false

    // Debounced while typing, immediate when the field is empty: the
    // popular list is what the modal opens on, and waiting 300ms to show
    // it reads as a broken dialog.
    const timeout = setTimeout(
      async () => {
        let assets: Asset[]
        try {
          assets = trimmedQuery
            ? await searchAssets(assetType, trimmedQuery)
            : await fetchPopularAssets(assetType)
        } catch {
          assets = []
        }
        if (!cancelled) setResults({ key: resultsKey, assets })
      },
      trimmedQuery ? SEARCH_DEBOUNCE_MS : 0,
    )

    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [assetType, trimmedQuery, resultsKey])

  const typeLabel = (byType[assetType]?.label ?? assetType).toLowerCase()

  function pick(symbol: string) {
    const asset = results.assets.find((candidate) => candidate.symbol === symbol)
    onPick({ assetType, ticker: symbol, label: asset?.name || symbol })
  }

  return (
    <Modal title="Compare against" onClose={onClose} className="benchmark-picker">
      <div className="benchmark-picker-controls">
        <select
          aria-label="Asset type"
          value={assetType}
          onChange={(event) => {
            setAssetType(event.target.value as AssetType)
            setQuery('')
          }}
        >
          {types.map(({ assetType: type, label }) => (
            <option key={type} value={type}>
              {label}
            </option>
          ))}
        </select>
        <SearchBar value={query} onChange={setQuery} />
      </div>

      <AssetList
        title={trimmedQuery ? 'Search results' : `Popular ${typeLabel}`}
        assetType={assetType}
        assets={results.assets}
        loading={loading}
        emptyMessage={
          trimmedQuery
            ? `No ${typeLabel} match "${trimmedQuery}". Check the spelling, or try another type above.`
            : `No ${typeLabel} are available right now.`
        }
        onSelect={pick}
      />
    </Modal>
  )
}

export default BenchmarkPicker
