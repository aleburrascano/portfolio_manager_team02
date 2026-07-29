import { useState } from 'react'
import Home from './Home'
import Login from './components/Login'
import { BalanceProvider } from './BalanceContext'
import type { User } from './api'
import './App.css'

function App() {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })

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
      <Home user={user} onLogout={handleLogout} />
    </BalanceProvider>
  )
}

export default App
