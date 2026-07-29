import { useState } from 'react'
import Dashboard from './Dashboard'
import Home from './Home'
import Header from './components/Header'
import Sidebar, { type Page } from './components/Sidebar'
import Login from './components/Login'
import { BalanceProvider } from './BalanceContext'
import type { User } from './api'
import './App.css'

function App() {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })
  const [page, setPage] = useState<Page>('dashboard')

  function handleLogin(user: User) {
    localStorage.setItem('user', JSON.stringify(user))
    setUser(user)
  }

  function handleLogout() {
    localStorage.removeItem('user')
    setUser(null)
  }

  if (!user) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <BalanceProvider userId={user.userId}>
      <div className="app-shell">
        <Header user={user} onLogout={handleLogout} />
        <div className="app-body">
          <Sidebar page={page} onNavigate={setPage} />
          <main className="app-page">
            {page === 'dashboard' ? <Dashboard /> : <Home user={user} />}
          </main>
        </div>
      </div>
    </BalanceProvider>
  )
}

export default App
