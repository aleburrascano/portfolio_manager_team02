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
import PortfolioComposition from '../components/portfolio/PortfolioComposition'
import HoldingsTable from '../components/portfolio/HoldingsTable'
import Watchlist from '../components/portfolio/Watchlist'
import WalletCard from '../components/portfolio/WalletCard'
import { useAssetTypes } from '../context/asset-types'
import { useBalance } from '../context/balance-context'

const PortfolioPerformance = lazy(() => import('../components/portfolio/PortfolioPerformance'))

function ChartFallback() {
  return (
    <section className="card performance-card" aria-busy="true">
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
  const onSelectAsset = (assetType: AssetType, symbol: string) =>
    navigate(`/trade/${assetType}/${encodeURIComponent(symbol)}`)

  const { balance } = useBalance()
  const { types } = useAssetTypes()
  const [data, setData] = useState<{ name: string; value: number }[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

    async function loadHoldings() {
      try {
        const result = await fetchPortfolioHoldings(user.userId)
        if (!cancelled) setBook({ key: holdingsKey, data: result })
      } catch (e) {
        if (!cancelled) {
          setBook({
            key: holdingsKey,
            error: e instanceof Error ? e.message : 'Failed to load holdings.',
          })
        }
      }
    }

    void loadHoldings()

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

      <Watchlist user={user} onSelectAsset={onSelectAsset} />

      <div className="dashboard-row">
        <Suspense fallback={<ChartFallback />}>
          <PortfolioPerformance user={user} balance={balance} />
        </Suspense>

        {loading ? (
          <section className="card" aria-busy="true">
            <h3 className="section-title">Portfolio composition</h3>
            <span className="visually-hidden">Loading your portfolio</span>
            <div className="composition-skeleton">
              <span className="skeleton skeleton-donut" />
              <span className="skeleton skeleton-legend" />
            </div>
          </section>
        ) : error || !data ? (
          <section className="card">
            <h3 className="section-title">Portfolio composition</h3>
            <p className="dashboard-empty-body">
              {error ?? 'We could not load your portfolio just now.'} Refresh the page to try
              again.
            </p>
          </section>
        ) : total === 0 ? (
          <section className="card dashboard-empty">
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
