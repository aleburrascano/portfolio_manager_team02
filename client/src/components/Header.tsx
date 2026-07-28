import { useEffect, useState } from 'react'
import { fetchBalance, type User } from '../api'
import './Header.css'

function Header({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [balance, setBalance] = useState<number | null>(null)

  useEffect(() => {
    async function loadBalance() {
      try {
        setBalance(await fetchBalance(user.userId))
      } catch {
        setBalance(null)
      }
    }

    loadBalance()
  }, [user.userId])

  return (
    <header className="app-header">
      <h1>Hello, {user.firstName}</h1>
      <div className="app-header-actions">
        <button type="button" className="deposit-btn">
          Deposit
        </button>
        <button type="button" className="withdraw-btn">
          Withdraw
        </button>
        <span className="balance">
          {balance !== null ? `$${balance.toFixed(2)}` : '...'}
        </span>
        <button type="button" className="logout-btn" onClick={onLogout}>
          Log out
        </button>
      </div>
    </header>
  )
}

export default Header
