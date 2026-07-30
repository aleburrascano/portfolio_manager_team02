import { useEffect, useState } from 'react'
import './Dashboard.css'
import { fetchPortfolioBreakdown, type User } from '../api'
import PortfolioComposition from '../components/PortfolioComposition'

function Dashboard({ user }: { user: User }) {
  const [data, setData] = useState<{ name: string; value: number }[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const res = await fetchPortfolioBreakdown(user.userId)
        const chartData = [
          { name: 'Cash', value: res.cash },
          { name: 'Stocks', value: res.stock },
          { name: 'Crypto', value: res.crypto },
        ]
        setData(chartData)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load portfolio')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [user.userId])

  if (loading) {
    return (
      <section id="dashboard-content">
        <p>Loading portfolio...</p>
      </section>
    )
  }

  if (error || !data) {
    return (
      <section id="dashboard-content">
        <p className="dashboard-placeholder">{error || 'No portfolio data available.'}</p>
      </section>
    )
  }

  const total = data.reduce((s, d) => s + (d.value || 0), 0)
  if (total === 0) {
    return (
      <section id="dashboard-content">
        <p className="dashboard-placeholder">No holdings to display.</p>
      </section>
    )
  }

  return (
    <section id="dashboard-content">
      <div className="dashboard-grid">
        <PortfolioComposition data={data} />
      </div>
    </section>
  )
}

export default Dashboard
