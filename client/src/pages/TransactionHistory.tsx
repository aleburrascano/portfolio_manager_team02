import { useEffect, useState } from 'react'
import {
  fetchTransactions,
  transactionsExportUrl,
  type RealizedGain,
  type Transaction,
  type TransactionPage,
  type TransactionSort,
  type User,
} from '../api'
import { formatCurrency, formatNumber } from '../lib/format'
import './TransactionHistory.css'

/** One screenful and a bit, so the first page always overflows into a scroll. */
const PAGE_SIZE = 50

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

function describe(transaction: Transaction): string {
  if (transaction.type === 'cash') {
    return transaction.transactionType === 'deposit' ? 'Deposited cash' : 'Withdrew cash'
  }
  const action = transaction.transactionType === 'buy' ? 'Bought' : 'Sold'
  const qty = transaction.qty != null ? formatNumber(Math.abs(transaction.qty), 2) : undefined
  return `${action}${qty != null ? ` ${qty}` : ''} ${transaction.ticker ?? ''}`.trim()
}

/** A sale's outcome: what it made, and what that was as a percentage. */
function Realized({ value }: { value: RealizedGain }) {
  const tone = value.gainLoss > 0 ? 'positive' : value.gainLoss < 0 ? 'negative' : 'flat'
  const sign = value.gainLoss > 0 ? '+' : value.gainLoss < 0 ? '-' : ''
  return (
    <span className={tone}>
      {sign}{formatCurrency(Math.abs(value.gainLoss))}{' '}
      <span className="history-realized-pct">
        ({formatNumber(Math.abs(value.gainLossPercent), 2)}%)
      </span>
    </span>
  )
}

function TransactionHistory({ user }: { user: User }) {
  const [sort, setSort] = useState<TransactionSort>('newest')
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requestKey = `${user.userId}:${sort}`
  const [page, setPage] = useState<{ key: string; result: TransactionPage | null }>({
    key: '',
    result: null,
  })

  useEffect(() => {
    let cancelled = false

    async function loadPage() {
      try {
        const result = await fetchTransactions(user.userId, PAGE_SIZE, 0, sort)
        if (!cancelled) setPage({ key: requestKey, result })
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to fetch transaction history')
      }
    }

    void loadPage()

    return () => {
      cancelled = true
    }
  }, [requestKey, user.userId, sort])

  async function loadMore() {
    const held = page.result?.transactions.length ?? 0
    setLoadingMore(true)
    try {
      const next = await fetchTransactions(user.userId, PAGE_SIZE, held, sort)
      setPage((current) => ({
        key: current.key,
        result: {
          ...next,
          transactions: [...(current.result?.transactions ?? []), ...next.transactions],
        },
      }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch more transactions')
    } finally {
      setLoadingMore(false)
    }
  }

  const loading = page.key !== requestKey
  const transactions = page.result?.transactions ?? []
  const total = page.result?.total ?? 0
  const hasMore = transactions.length < total

  return (
    <section id="transaction-history-content">
      <div className="history-header">
        <h1 className="section-title">Transaction history</h1>
        {transactions.length > 0 && page.result && (
          <div className="history-actions">
            <button
              type="button"
              className="secondary-btn"
              onClick={() => setSort((current) => (current === 'newest' ? 'oldest' : 'newest'))}
            >
              {sort === 'newest' ? 'Newest first' : 'Oldest first'}
            </button>
            <a
              className="secondary-btn"
              href={transactionsExportUrl(page.result)}
              download="transactions.csv"
            >
              Export CSV
            </a>
          </div>
        )}
      </div>

      {error ? (
        <p className="transaction-history-placeholder">{error}</p>
      ) : loading ? (
        <div className="transaction-history-loading" aria-busy="true">
          <span className="visually-hidden">Loading your transactions</span>
          {Array.from({ length: 5 }, (_, index) => (
            <span key={index} className="skeleton skeleton-row" />
          ))}
        </div>
      ) : transactions.length === 0 ? (
        <p className="transaction-history-placeholder">
          Every deposit, withdrawal, buy, and sell you make will be listed here.
        </p>
      ) : (
        <>
          <div className="transaction-history-scroll">
            <table className="transaction-history-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Description</th>
                  <th scope="col">Amount</th>
                  <th scope="col">Realized</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => {
                  const isPositive = transaction.signedAmount >= 0
                  return (
                    <tr key={`${transaction.type}-${transaction.transactionId}`}>
                      <td data-label="Date">{formatDate(transaction.transactionDate)}</td>
                      <td data-label="Description">{describe(transaction)}</td>
                      <td data-label="Amount" className={isPositive ? 'positive' : 'negative'}>
                        {isPositive ? '+' : '-'}{formatCurrency(Math.abs(transaction.signedAmount))}
                      </td>
                      <td data-label="Realized" className="history-realized">
                        {transaction.realized ? (
                          <Realized value={transaction.realized} />
                        ) : (
                          <span aria-hidden="true">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="history-footer">
            <p className="history-count">
              Showing {transactions.length} of {total}
            </p>
            {hasMore && (
              <button
                type="button"
                className="secondary-btn"
                disabled={loadingMore}
                onClick={loadMore}
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  )
}

export default TransactionHistory
