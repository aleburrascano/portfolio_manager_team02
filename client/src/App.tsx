import { useEffect, useState } from 'react'
import Dashboard from './pages/Dashboard'
import TradeAssets from './pages/TradeAssets'
import TransactionHistory from './pages/TransactionHistory'
import Header from './components/Header'
import Sidebar, { type Page } from './components/Sidebar'
import Login from './components/Login'
import { BalanceProvider } from './BalanceContext'
import { fetchCurrentUser, logout, type User } from './api'
import './App.css'

function App() {
  // The server session is the only source of truth for who is logged in, so
  // it's asked once on load rather than trusting anything the client stored.
  const [user, setUser] = useState<User | null>(null)
  const [restoring, setRestoring] = useState(true)
  const [page, setPage] = useState<Page>('dashboard')

  useEffect(() => {
    let cancelled = false

    fetchCurrentUser().then((current) => {
      if (cancelled) return
      setUser(current)
      setRestoring(false)
    })

    return () => {
      cancelled = true
    }
  }, [])

  async function handleLogout() {
    // Cleared either way: if the request fails there's nothing useful the
    // user can do about it, and leaving them on the dashboard would make
    // the button look broken.
    try {
      await logout()
    } finally {
      setUser(null)
      setPage('dashboard')
    }
  }

  if (restoring) {
    return null
  }

  if (!user) {
    return <Login onLogin={setUser} />
  }

  return (
    <BalanceProvider userId={user.userId}>
      <div className="app-shell">
        <Header user={user} />
        <div className="app-body">
          <Sidebar page={page} onNavigate={setPage} onLogout={handleLogout} />
          <main className="app-page">
            {page === 'dashboard' && <Dashboard user={user} />}
            {page === 'trade-assets' && <TradeAssets user={user} />}
            {page === 'transaction-history' && <TransactionHistory user={user} />}
          </main>
        </div>
      </div>
    </BalanceProvider>
  )
}

export default App
