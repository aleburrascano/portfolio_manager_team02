import { useEffect, useState } from 'react'
import { fetchTransactions, type Transaction, type User } from '../api'
import { formatCurrency, formatNumber } from '../format'
import './TransactionHistory.css'

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

function describe(transaction: Transaction): string {
  if (transaction.type === 'cash') {
    return transaction.transactionType === 'deposit' ? 'Cash Deposit' : 'Cash Withdrawal'
  }
  const action = transaction.transactionType === 'buy' ? 'Bought' : 'Sold'
  const qty = transaction.qty != null ? formatNumber(Math.abs(transaction.qty), 2) : undefined
  return `${action}${qty != null ? ` ${qty}` : ''} ${transaction.ticker ?? ''}`.trim()
}

function TransactionHistory({ user }: { user: User }) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <section id="transaction-history-content">
      {loading ? (
        <p className="transaction-history-placeholder">Loading…</p>
      ) : error ? (
        <p className="transaction-history-placeholder">{error}</p>
      ) : transactions.length === 0 ? (
        <p className="transaction-history-placeholder">No transactions to display yet.</p>
      ) : (
        <table className="transaction-history-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((transaction) => {
              const isPositive = transaction.signedAmount >= 0
              return (
                <tr key={`${transaction.type}-${transaction.transactionId}`}>
                  <td>{formatDate(transaction.transactionDate)}</td>
                  <td>{describe(transaction)}</td>
                  <td className={isPositive ? 'positive' : 'negative'}>
                    {isPositive ? '+' : '-'}{formatCurrency(Math.abs(transaction.signedAmount))}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}

export default TransactionHistory
