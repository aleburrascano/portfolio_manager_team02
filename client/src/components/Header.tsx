import { useEffect, useState } from 'react'
import { DEMO_USER_ID, fetchBalance } from '../api'
import './Header.css'

function Header() {
  const [balance, setBalance] = useState<number | null>(null)

  useEffect(() => {
    async function loadBalance() {
      try {
        setBalance(await fetchBalance(DEMO_USER_ID))
      } catch {
        setBalance(null)
      }
    }

    loadBalance()
  }, [])

  return (
    <header className="app-header">
      <h1>Hello, User Name</h1>
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
      </div>
    </header>
  )
}

export default Header
