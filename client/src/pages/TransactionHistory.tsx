import { useEffect, useState } from 'react'
import {
  fetchTransactions,
  transactionsExportUrl,
  type RealizedGain,
  type Transaction,
  type TransactionSort,
  type User,
} from '../api'
import { formatCurrency, formatNumber } from '../format'
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

  // Tagged with the request it answers, so flipping the sort shows a
  // skeleton rather than the old order without a separate loading flag that
  // could drift out of step with what is held.
  const requestKey = `${user.userId}:${sort}`
  const [page, setPage] = useState<{ key: string; transactions: Transaction[]; total: number }>({
    key: '',
    transactions: [],
    total: 0,
  })

  useEffect(() => {
    let cancelled = false

    fetchTransactions(user.userId, PAGE_SIZE, 0, sort)
      .then((result) => {
        if (!cancelled) {
          setPage({ key: requestKey, transactions: result.transactions, total: result.total })
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to fetch transaction history')
      })

    return () => {
      cancelled = true
    }
  }, [requestKey, user.userId, sort])

  // Appends rather than replaces, and the offset comes from what is already
  // held - so a row that arrives between two pages can't cause one to be
  // skipped, only repeated at worst.
  async function loadMore() {
    setLoadingMore(true)
    try {
      const next = await fetchTransactions(user.userId, PAGE_SIZE, page.transactions.length, sort)
      setPage((current) => ({
        key: current.key,
        transactions: [...current.transactions, ...next.transactions],
        total: next.total,
      }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch more transactions')
    } finally {
      setLoadingMore(false)
    }
  }

  // The database sorts and pages against an index. Flipping the order
  // refetches rather than reversing what is held, which would only reorder
  // the rows this page happens to have - a different list entirely.
  const loading = page.key !== requestKey
  const transactions = page.transactions
  const total = page.total
  const hasMore = transactions.length < total

  return (
    <section id="transaction-history-content">
      <div className="history-header">
        <h1 className="section-title">Transaction history</h1>
        {transactions.length > 0 && (
          <div className="history-actions">
            <button
              type="button"
              className="secondary-btn"
              onClick={() => setSort((current) => (current === 'newest' ? 'oldest' : 'newest'))}
            >
              {sort === 'newest' ? 'Newest first' : 'Oldest first'}
            </button>
            {/* A plain link, not a fetch: the browser has to navigate to it
                itself to get a file rather than a string in memory. Same
                origin, so the session cookie goes with it. */}
            <a
              className="secondary-btn"
              href={transactionsExportUrl(user.userId)}
              download="transactions.csv"
            >
              Export CSV
            </a>
          </div>
        )}
      </div>

      {/* Error first: a request that failed never tags the page with its
          key, so testing "still loading" ahead of it would leave a skeleton
          up forever instead of saying what went wrong. */}
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
          {/* The wrapper is the floor: if the table ever exceeds its column it
              scrolls inside this box rather than dragging the whole page
              sideways, which .app-page's overflow-y would otherwise allow. */}
          <div className="transaction-history-scroll">
            <table className="transaction-history-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Description</th>
                  <th scope="col">Amount</th>
                  {/* The unrealised side of this is on the dashboard for
                      every open position; this is the only place a closed
                      one says whether it was a good trade. */}
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
                          // An em dash, not a zero: this row didn't realise
                          // nothing, it isn't the kind of event that can.
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
