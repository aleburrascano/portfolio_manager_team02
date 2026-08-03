import { Suspense, lazy, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './Dashboard.css'
import {
  fetchPortfolioBreakdown,
  fetchPortfolioHoldings,
  type AssetType,
  type HoldingsResult,
  type User,
} from '../api'
import PortfolioComposition from '../components/PortfolioComposition'
import HoldingsTable from '../components/HoldingsTable'
import Watchlist from '../components/Watchlist'
import WalletCard from '../components/WalletCard'
import { useAssetTypes } from '../asset-types'
import { useBalance } from '../balance-context'

// Charting is the single largest thing the client ships, and nothing above
// the fold needs it. Split out, it loads alongside the data it draws
// rather than blocking the first paint of the whole app.
const PortfolioPerformance = lazy(() => import('../components/PortfolioPerformance'))

function ChartFallback() {
  return (
    <section className="dashboard-card performance-card" aria-busy="true">
      <h3 className="section-title">Portfolio performance</h3>
      <span className="visually-hidden">Loading portfolio performance</span>
      <div className="performance-body">
        <span className="skeleton skeleton-performance" />
      </div>
    </section>
  )
}

function Dashboard({ user }: { user: User }) {
  const navigate = useNavigate()
  // Opening an asset is navigation, so it goes to that asset's address
  // rather than being handed up as a callback and held as state.
  const onSelectAsset = (assetType: AssetType, symbol: string) =>
    navigate(`/trade/${assetType}/${encodeURIComponent(symbol)}`)

  const { balance } = useBalance()
  const { types } = useAssetTypes()
  const [data, setData] = useState<{ name: string; value: number }[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Holdings are fetched once, here, and handed to both the statement head
  // and the table. Fetching them twice would price the book at two
  // different instants and show two different totals on one screen.
  const holdingsKey = `${user.userId}:${balance}`
  const [book, setBook] = useState<{ key: string; data?: HoldingsResult; error?: string }>({
    key: '',
  })

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const res = await fetchPortfolioBreakdown(user.userId)
        if (cancelled) return
        // Cash first, then a slice per asset type the server reports, so
        // the donut gains a slice when the server gains a provider.
        setData([
          { name: 'Cash', value: res.cash },
          ...types.map(({ assetType, label }) => ({
            name: label,
            value: res[assetType] ?? 0,
          })),
        ])
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load portfolio')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [user.userId, balance, types])

  useEffect(() => {
    let cancelled = false

    fetchPortfolioHoldings(user.userId)
      .then((result) => {
        if (!cancelled) setBook({ key: holdingsKey, data: result })
      })
      .catch((e) => {
        if (!cancelled) {
          setBook({
            key: holdingsKey,
            error: e instanceof Error ? e.message : 'Failed to load holdings.',
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [user.userId, holdingsKey])

  const total = data?.reduce((sum, entry) => sum + (entry.value || 0), 0) ?? 0
  const hasCash = (balance ?? 0) > 0
  const bookLoading = book.key !== holdingsKey

  return (
    <section id="dashboard-content">
      <WalletCard user={user} totals={bookLoading ? null : book.data?.totals ?? null} />

      {/* The watchlist sits high and spans the width, so it shows as many
          tiles as the screen allows rather than being squeezed into a
          column. Below it: performance beside composition, then the book. */}
      <Watchlist user={user} onSelectAsset={onSelectAsset} />

      <div className="dashboard-row">
        <Suspense fallback={<ChartFallback />}>
          <PortfolioPerformance user={user} balance={balance} />
        </Suspense>

        {loading ? (
          <section className="dashboard-card" aria-busy="true">
            <h3 className="section-title">Portfolio composition</h3>
            <span className="visually-hidden">Loading your portfolio</span>
            <div className="composition-skeleton">
              <span className="skeleton skeleton-donut" />
              <span className="skeleton skeleton-legend" />
            </div>
          </section>
        ) : error || !data ? (
          <section className="dashboard-card">
            <h3 className="section-title">Portfolio composition</h3>
            <p className="dashboard-empty-body">
              {error ?? 'We could not load your portfolio just now.'} Refresh the page to try
              again.
            </p>
          </section>
        ) : total === 0 ? (
          // The first panel a new account ever sees. It says what this is
          // for and hands over the next step, rather than reporting an
          // absence and stopping there.
          <section className="dashboard-card dashboard-empty">
            <h3 className="section-title">Portfolio composition</h3>
            <p className="dashboard-empty-body">
              {hasCash
                ? 'Once you buy your first stock, crypto, or bond, this is where the split across them will appear.'
                : 'This is where the split of your money across cash, stocks, crypto, and bonds will appear. Deposit some cash above to get started.'}
            </p>
            <button type="button" className="secondary-btn" onClick={() => navigate('/trade')}>
              Browse assets
            </button>
          </section>
        ) : (
          <PortfolioComposition data={data} />
        )}
      </div>

      <HoldingsTable
        data={book.data ?? null}
        loading={bookLoading}
        error={book.error ?? null}
        onSelectAsset={onSelectAsset}
      />
    </section>
  )
}

export default Dashboard
