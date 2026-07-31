import { useEffect, useMemo, useState } from 'react'
import { fetchTransactions, type Transaction, type User } from '../api'
import { formatCurrency, formatNumber } from '../format'
import './TransactionHistory.css'

/** Full date for the table; the stacked mobile layout uses the same string. */
function formatDate(value: string) {
  return new Date(value).toLocaleString('en-US', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
}

// Every row reads as something that happened, in the same tense, so the
// column scans as one list rather than two kinds of entry side by side.
function describe(transaction: Transaction): string {
  if (transaction.type === 'cash') {
    return transaction.transactionType === 'deposit' ? 'Deposited cash' : 'Withdrew cash'
  }
  const action = transaction.transactionType === 'buy' ? 'Bought' : 'Sold'
  const qty = transaction.qty != null ? formatNumber(Math.abs(transaction.qty), 2) : undefined
  return `${action}${qty != null ? ` ${qty}` : ''} ${transaction.ticker ?? ''}`.trim()
}

function TransactionHistory({ user }: { user: User }) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newestFirst, setNewestFirst] = useState(true)

  useEffect(() => {
    let cancelled = false

    // No loading/error reset up here: both already start in the right
    // state, and the user can't change without this page unmounting.
    fetchTransactions(user.userId)
      .then((data) => {
        if (!cancelled) setTransactions(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to fetch transaction history')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [user.userId])

  const ordered = useMemo(() => {
    const byDate = [...transactions].sort(
      (a, b) => Date.parse(a.transactionDate) - Date.parse(b.transactionDate),
    )
    return newestFirst ? byDate.reverse() : byDate
  }, [transactions, newestFirst])

  return (
    <section id="transaction-history-content">
      <div className="history-header">
        <h1 className="section-title">Transaction history</h1>
        {ordered.length > 0 && (
          <button
            type="button"
            className="secondary-btn"
            onClick={() => setNewestFirst((current) => !current)}
          >
            {newestFirst ? 'Newest first' : 'Oldest first'}
          </button>
        )}
      </div>

      {loading ? (
        <div className="transaction-history-loading" aria-busy="true">
          <span className="visually-hidden">Loading your transactions</span>
          {Array.from({ length: 5 }, (_, index) => (
            <span key={index} className="skeleton skeleton-row" />
          ))}
        </div>
      ) : error ? (
        <p className="transaction-history-placeholder">{error}</p>
      ) : ordered.length === 0 ? (
        <p className="transaction-history-placeholder">
          Every deposit, withdrawal, buy, and sell you make will be listed here.
        </p>
      ) : (
        // The wrapper is the floor: if the table ever exceeds its column it
        // scrolls inside this box rather than dragging the whole page
        // sideways, which .app-page's overflow-y would otherwise allow.
        <div className="transaction-history-scroll">
          <table className="transaction-history-table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Description</th>
                <th scope="col">Amount</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((transaction) => {
                const isPositive = transaction.signedAmount >= 0
                return (
                  <tr key={`${transaction.type}-${transaction.transactionId}`}>
                    <td data-label="Date">{formatDate(transaction.transactionDate)}</td>
                    <td data-label="Description">{describe(transaction)}</td>
                    <td data-label="Amount" className={isPositive ? 'positive' : 'negative'}>
                      {isPositive ? '+' : '-'}{formatCurrency(Math.abs(transaction.signedAmount))}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default TransactionHistory
