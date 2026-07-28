import { useEffect, useState } from 'react'
import { DEMO_USER_ID, fetchBalance, submitCashTransaction, 
         type TransactionType } from '../api'
import './Header.css'

function Header() {
  const [balance, setBalance] = useState<number | null>(null)
  const [isPopupOpen, setIsPopupOpen] = useState(false)
  const [transactionType, setTransactionType] = useState<TransactionType>('deposit')
  const [amount, setAmount] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function loadBalance() {
      try {
        setBalance(await fetchBalance(DEMO_USER_ID))
      } catch {
        setBalance(null)
      }
    }
  
  useEffect(() => {
    loadBalance()
  }, [])

  function openPopup(type: TransactionType) {
    setTransactionType(type)
    setAmount('')
    setStatusMessage('')
    setIsPopupOpen(true)
  }

  async function handleSubmit() {

    const parsedAmount = Number(amount)
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setStatusMessage('Please enter a positive amount.')
      return
    }

    setIsSubmitting(true)
    setStatusMessage('')

    try {
      await submitCashTransaction(DEMO_USER_ID, transactionType, parsedAmount)
      await loadBalance()
      setStatusMessage(`${transactionType === 'deposit' ? 'Deposit' : 'Withdrawal'} submitted successfully.`)
      setAmount('')
      setTimeout(() => setIsPopupOpen(false), 500)
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Transaction failed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
    <header className="app-header">
      <h1>Hello, User Name</h1>
      <div className="app-header-actions">
        <button type="button" className="deposit-btn" onClick={() => openPopup('deposit')}>
          Deposit
        </button>
        <button type="button" className="withdraw-btn" onClick={() => openPopup('withdraw')}>
          Withdraw
        </button>
        <span className="balance">
          {balance !== null ? `$${balance.toFixed(2)}` : '...'}
        </span>
      </div>
    </header>

     {isPopupOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{transactionType === 'deposit' ? 'Deposit Funds' : 'Withdraw Funds'}</h2>
            <p className="modal-balance">
              Current Balance: {balance !== null ? `$${balance.toFixed(2)}` : '...'}
            </p>

            <form onSubmit={handleSubmit}>
              <label className="modal-label" htmlFor="transaction-amount">
                Amount
              </label>
              <input
                id="transaction-amount"
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="0.00"
                required
              />

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={() => setIsPopupOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="submit-btn" disabled={isSubmitting}>
                  {isSubmitting ? 'Submitting...' : 'Submit Transaction'}
                </button>
              </div>
            </form>

            {statusMessage && (
              <p className={`modal-status ${statusMessage.includes('success') ? 'success' : 'error'}`}>
                {statusMessage}
              </p>
            )}
            
          </div>
        </div>
      )}
    </>
  )
}

export default Header
