import { useEffect, useMemo, useState } from 'react'
import './Dashboard.css'
import { fetchPortfolioBreakdown } from './api'
import PortfolioComposition from './components/PortfolioComposition'

function Dashboard() {
  const [data, setData] = useState<{ name: string; value: number }[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const user = useMemo(() => {
    const s = localStorage.getItem('user')
    return s ? JSON.parse(s) : null
  }, [])

  useEffect(() => {
    async function load() {
      if (!user?.userId) {
        setError('No user')
        setLoading(false)
        return
      }
      setLoading(true)
      try {
        const res = await fetchPortfolioBreakdown(user.userId)
        const chartData = [
          { name: 'Cash', value: res.cash },
          { name: 'Stocks', value: res.stock },
          { name: 'Crypto', value: res.crypto },
        ]
        setData(chartData)
      } catch (e: any) {
        setError(e?.message || 'Failed to load portfolio')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [user])

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
