import { useEffect, useState } from 'react'
import Dashboard from './pages/Dashboard'
import TradeAssets from './pages/TradeAssets'
import TransactionHistory from './pages/TransactionHistory'
import Account from './pages/Account'
import FillToasts from './components/FillToasts'
import Header from './components/Header'
import Sidebar, { type Page } from './components/Sidebar'
import Login from './components/Login'
import { AssetTypesProvider } from './AssetTypesContext'
import { BalanceProvider } from './BalanceContext'
import { fetchCurrentUser, logout, type AssetType, type SessionResult, type User } from './api'
import './App.css'

function App() {
  // The server session is the only source of truth for who is logged in, so
  // it's asked once on load rather than trusting anything the client stored.
  const [session, setSession] = useState<SessionResult | null>(null)
  const [page, setPage] = useState<Page>('dashboard')
  // Set when the user opens an asset from somewhere other than the trade
  // screen - a holdings row, a watchlist tile - so that screen knows what
  // to show on arrival.
  const [openAsset, setOpenAsset] = useState<{ assetType: AssetType; symbol: string } | null>(null)
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
      setPage('dashboard')
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
      <BalanceProvider userId={user.userId}>
        <a className="skip-link" href="#app-page">
          Skip to main content
        </a>
        <div className="app-shell">
          <Header
            user={user}
            onOpenAccount={() => setPage('account')}
            onLogout={handleLogout}
          />
          <div className="app-body">
            <Sidebar page={page} onNavigate={setPage} />
            <main className="app-page" id="app-page" tabIndex={-1}>
              {page === 'dashboard' && (
                <Dashboard
                  user={user}
                  onBrowseAssets={() => {
                    setOpenAsset(null)
                    setPage('trade-assets')
                  }}
                  onSelectAsset={(assetType, symbol) => {
                    setOpenAsset({ assetType, symbol })
                    setPage('trade-assets')
                  }}
                />
              )}
              {page === 'trade-assets' && <TradeAssets user={user} openAsset={openAsset} />}
              {page === 'transaction-history' && <TransactionHistory user={user} />}
              {page === 'account' && <Account user={user} onUpdate={handleLogin} />}
            </main>
          </div>
        </div>
        {/* At the shell, because a conditional order can fill while the
            user is on any screen - including none of the ones that would
            otherwise show it. */}
        <FillToasts />
      </BalanceProvider>
    </AssetTypesProvider>
  )
}

export default App
