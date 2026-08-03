import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes, useNavigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import TradeAssets from './pages/TradeAssets'
import TransactionHistory from './pages/TransactionHistory'
import Account from './pages/Account'
import FillToasts from './components/FillToasts'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import Login from './components/Login'
import { AssetTypesProvider } from './AssetTypesContext'
import { BalanceProvider } from './BalanceContext'
import { fetchCurrentUser, logout, type SessionResult, type User } from './api'
import './App.css'

/**
 * The chrome every signed-in page sits inside, with the page itself in the
 * outlet.
 *
 * Split out from App so that the header, the rail and the toast layer are
 * mounted once for the whole session rather than per route - remounting
 * them on every navigation would drop the socket subscriptions and any
 * notice currently on screen.
 */
function AppShell({
  user,
  onLogout,
}: {
  user: User
  onLogout: () => void
}) {
  const navigate = useNavigate()

  return (
    <BalanceProvider userId={user.userId}>
      <a className="skip-link" href="#app-page">
        Skip to main content
      </a>
      <div className="app-shell">
        <Header user={user} onOpenAccount={() => navigate('/account')} onLogout={onLogout} />
        <div className="app-body">
          <Sidebar />
          <main className="app-page" id="app-page" tabIndex={-1}>
            <Outlet />
          </main>
        </div>
      </div>
      <FillToasts />
    </BalanceProvider>
  )
}

function App() {
  const [session, setSession] = useState<SessionResult | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false

    fetchCurrentUser().then((result) => {
      if (!cancelled) setSession(result)
    })

    return () => {
      cancelled = true
    }
  }, [attempt])

  function retry() {
    setSession(null)
    setAttempt((current) => current + 1)
  }

  async function handleLogout() {
    try {
      await logout()
    } finally {
      setSession({ status: 'anonymous' })
    }
  }

  function handleLogin(user: User) {
    setSession({ status: 'authenticated', user })
  }

  if (session === null) {
    return (
      <div className="app-boot" role="status">
        <span className="visually-hidden">Signing you in</span>
        <span className="skeleton app-boot-bar" />
      </div>
    )
  }

  if (session.status === 'unavailable') {
    return (
      <div className="app-boot">
        <div className="app-boot-error" role="alert">
          <h1>We couldn't reach TreeTop Trading</h1>
          <p>{session.message}</p>
          <p className="app-boot-hint">Your session is still active. This is a problem on our end.</p>
          <button type="button" className="submit-btn" onClick={retry}>
            Try again
          </button>
        </div>
      </div>
    )
  }

  if (session.status === 'anonymous') {
    return <Login onLogin={handleLogin} />
  }

  const user = session.user

  return (
    <AssetTypesProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell user={user} onLogout={handleLogout} />}>
            <Route index element={<Dashboard user={user} />} />
            <Route path="trade" element={<Navigate to="/trade/stock" replace />} />
            <Route path="trade/:assetType" element={<TradeAssets user={user} />} />
            <Route path="trade/:assetType/:symbol" element={<TradeAssets user={user} />} />
            <Route path="orders/:assetType" element={<TradeAssets user={user} showOrders />} />
            <Route path="history" element={<TransactionHistory user={user} />} />
            <Route path="account" element={<Account user={user} onUpdate={handleLogin} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AssetTypesProvider>
  )
}

export default App
