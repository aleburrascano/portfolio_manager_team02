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
      {/* At the shell, because a conditional order can fill - or a bond
          mature - while the user is on any screen, including none of the
          ones that would otherwise show it. */}
      <FillToasts />
    </BalanceProvider>
  )
}

function App() {
  // The server session is the only source of truth for who is logged in, so
  // it's asked once on load rather than trusting anything the client stored.
  const [session, setSession] = useState<SessionResult | null>(null)
  // Bumped by the retry button; the effect re-runs the session check when
  // it changes. The effect only reports the answer, so clearing back to the
  // loading state stays in the click handler where it belongs.
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
    // Cleared either way: if the request fails there's nothing useful the
    // user can do about it, and leaving them on the dashboard would make
    // the button look broken.
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

  // A server that couldn't answer is not the same as a signed-out visitor,
  // and saying so is the difference between "try again" and "log in again".
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
            {/* An asset type is part of the address, so a tab is a place -
                shareable, bookmarkable, and reachable with the back button.
                Bare /trade picks the first tab rather than showing nothing. */}
            <Route path="trade" element={<Navigate to="/trade/stock" replace />} />
            <Route path="trade/:assetType" element={<TradeAssets user={user} />} />
            <Route path="trade/:assetType/:symbol" element={<TradeAssets user={user} />} />
            {/* Its own path rather than a third segment under trade, which
                would be ambiguous with a ticker named "orders". */}
            <Route path="orders/:assetType" element={<TradeAssets user={user} showOrders />} />
            <Route path="history" element={<TransactionHistory user={user} />} />
            <Route path="account" element={<Account user={user} onUpdate={handleLogin} />} />
            {/* An address this app doesn't have is not worth an error page;
                the dashboard is where someone wanted to be anyway. */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AssetTypesProvider>
  )
}

export default App
