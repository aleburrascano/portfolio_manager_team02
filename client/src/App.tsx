import { useEffect, useState } from 'react'
import Dashboard from './Dashboard'
import TradeAssets from './TradeAssets'
import TransactionHistory from './TransactionHistory'
import Header from './components/Header'
import Sidebar, { type Page } from './components/Sidebar'
import Login from './components/Login'
import { BalanceProvider } from './BalanceContext'
import { fetchUser, type User } from './api'
import './App.css'

function App() {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })
  const [validating, setValidating] = useState(() => localStorage.getItem('user') !== null)
  const [page, setPage] = useState<Page>('dashboard')

  useEffect(() => {
    if (!user) return

    let cancelled = false
    fetchUser(user.userId).catch((err) => {
      if (cancelled) return
      if (err instanceof Error && err.message === 'User not found') {
        handleLogout()
      }
    }).finally(() => {
      if (!cancelled) setValidating(false)
    })

    return () => {
      cancelled = true
    }
    // Only re-validate when a different user logs in, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.userId])

  function handleLogin(user: User) {
    localStorage.setItem('user', JSON.stringify(user))
    setUser(user)
  }

  function handleLogout() {
    localStorage.removeItem('user')
    setUser(null)
  }

  if (validating) {
    return null
  }

  if (!user) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <BalanceProvider userId={user.userId}>
      <div className="app-shell">
        <Header user={user} />
        <div className="app-body">
          <Sidebar page={page} onNavigate={setPage} onLogout={handleLogout} />
          <main className="app-page">
            {page === 'dashboard' && <Dashboard />}
            {page === 'trade-assets' && <TradeAssets user={user} />}
            {page === 'transaction-history' && <TransactionHistory user={user} />}
          </main>
        </div>
      </div>
    </BalanceProvider>
  )
}

export default App
