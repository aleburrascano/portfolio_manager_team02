import { useState } from 'react'
import { submitCashTransaction, type TransactionType, type User } from '../api'
import { useBalance } from '../balance-context'
import { validateAmountInput } from '../validation'
import './Modal.css'
import './Header.css'

function formatCurrency(value: number) {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function Header({ user }: { user: User }) {
  const { balance, refreshBalance } = useBalance()
  const [isPopupOpen, setIsPopupOpen] = useState(false)
  const [transactionType, setTransactionType] = useState<TransactionType>('deposit')
  const [amount, setAmount] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function openPopup(type: TransactionType) {
    setTransactionType(type)
    setAmount('')
    setStatusMessage('')
    setIsPopupOpen(true)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const amountError = validateAmountInput(amount)
    if (amountError) {
      setStatusMessage(amountError)
      return
    }
    const parsedAmount = Number(amount)

    if (transactionType === 'withdraw' && balance !== null && parsedAmount > balance) {
      setStatusMessage(`Withdrawal amount exceeds current balance of ${formatCurrency(balance)}.`)
      return
    }

    setIsSubmitting(true)
    setStatusMessage('')

    try {
      await submitCashTransaction(user.userId, transactionType, parsedAmount)
      await refreshBalance()
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
      <h1>Hello, {user.firstName}</h1>
      <div className="app-header-actions">
        <button type="button" className="deposit-btn" onClick={() => openPopup('deposit')}>
          Deposit
        </button>
        <button type="button" className="withdraw-btn" onClick={() => openPopup('withdraw')}>
          Withdraw
        </button>
        <span className="balance">
          {balance !== null ? formatCurrency(balance) : '...'}
        </span>
      </div>
    </header>

     {isPopupOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{transactionType === 'deposit' ? 'Deposit Funds' : 'Withdraw Funds'}</h2>
            <p className="modal-balance">
              Current Balance: {balance !== null ? formatCurrency(balance) : '...'}
            </p>

            <form onSubmit={handleSubmit}>
              <label className="modal-label" htmlFor="transaction-amount">
                Amount
              </label>
              <input
                id="transaction-amount"
                type="number"
                min="0.01"
                max={transactionType === 'withdraw' && balance !== null ? balance : undefined}
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
