import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TransactionHistory from './TransactionHistory'
import { fetchTransactions, type Transaction } from '../api'

vi.mock('../api', () => ({
  fetchTransactions: vi.fn(),
  transactionsExportUrl: (userId: number) => `/api/v1/users/${userId}/transactions/export`,
}))

const mockedFetch = vi.mocked(fetchTransactions)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

const deposit: Transaction = {
  transactionId: 1, type: 'cash', transactionType: 'deposit',
  transactionDate: '2024-01-01T00:00:00Z', signedAmount: 100,
}
const purchase: Transaction = {
  transactionId: 2, type: 'stock', transactionType: 'buy',
  transactionDate: '2024-01-02T00:00:00Z', signedAmount: -50, ticker: 'AAPL', qty: 5, price: 10,
}

function page(transactions: Transaction[], total = transactions.length) {
  return { transactions, total }
}

beforeEach(() => {
  mockedFetch.mockReset()
})

describe('TransactionHistory', () => {
  it('shows a loading state before the history resolves', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))
    render(<TransactionHistory user={user} />)
    expect(screen.getByText('Loading your transactions')).toBeInTheDocument()
  })

  it('explains what will appear here when there is no history', async () => {
    mockedFetch.mockResolvedValue(page([]))
    render(<TransactionHistory user={user} />)
    expect(
      await screen.findByText(/Every deposit, withdrawal, buy, and sell you make will be listed here/),
    ).toBeInTheDocument()
  })

  it('shows the error message on failure', async () => {
    mockedFetch.mockRejectedValue(new Error('Failed to fetch transaction history'))
    render(<TransactionHistory user={user} />)
    expect(await screen.findByText('Failed to fetch transaction history')).toBeInTheDocument()
  })

  it('describes and formats cash and asset transactions', async () => {
    mockedFetch.mockResolvedValue(page([purchase, deposit]))
    render(<TransactionHistory user={user} />)

    // Both rows read as something that happened, in the same tense.
    expect(await screen.findByText('Deposited cash')).toBeInTheDocument()
    expect(screen.getByText('+$100.00')).toBeInTheDocument()
    expect(screen.getByText('Bought 5.00 AAPL')).toBeInTheDocument()
    expect(screen.getByText('-$50.00')).toBeInTheDocument()
  })

  it('asks for a page rather than the whole history', async () => {
    mockedFetch.mockResolvedValue(page([deposit]))
    render(<TransactionHistory user={user} />)

    await screen.findByText('Deposited cash')
    expect(mockedFetch).toHaveBeenCalledWith(1, expect.any(Number), 0, 'newest')
  })

  // Reversing the rows already fetched would only reorder that page, which
  // is a different list from the one the user asked to see.
  it('refetches in the other direction rather than reversing what it holds', async () => {
    const typer = userEvent.setup()
    mockedFetch.mockResolvedValue(page([purchase, deposit]))
    render(<TransactionHistory user={user} />)
    await screen.findByText('Deposited cash')

    mockedFetch.mockResolvedValue(page([deposit, purchase]))
    await typer.click(screen.getByRole('button', { name: 'Newest first' }))

    expect(mockedFetch).toHaveBeenLastCalledWith(1, expect.any(Number), 0, 'oldest')
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Oldest first' })).toBeInTheDocument(),
    )
  })

  it('says how much of the history is on screen', async () => {
    mockedFetch.mockResolvedValue(page([deposit], 214))
    render(<TransactionHistory user={user} />)

    expect(await screen.findByText('Showing 1 of 214')).toBeInTheDocument()
  })

  it('appends the next page rather than replacing the current one', async () => {
    const typer = userEvent.setup()
    mockedFetch.mockResolvedValue(page([deposit], 2))
    render(<TransactionHistory user={user} />)
    await screen.findByText('Deposited cash')

    mockedFetch.mockResolvedValue(page([purchase], 2))
    await typer.click(screen.getByRole('button', { name: 'Load more' }))

    expect(mockedFetch).toHaveBeenLastCalledWith(1, expect.any(Number), 1, 'newest')
    expect(await screen.findByText('Bought 5.00 AAPL')).toBeInTheDocument()
    expect(screen.getByText('Deposited cash')).toBeInTheDocument()
  })

  it('offers no Load more once everything is shown', async () => {
    mockedFetch.mockResolvedValue(page([deposit, purchase], 2))
    render(<TransactionHistory user={user} />)

    await screen.findByText('Deposited cash')
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
  })

  it('reports what a sale realised', async () => {
    const sale: Transaction = {
      transactionId: 3, type: 'stock', transactionType: 'sell',
      transactionDate: '2024-01-03T00:00:00Z', signedAmount: 60,
      ticker: 'AAPL', qty: -4, price: 15,
      realized: { costBasis: 40, proceeds: 60, gainLoss: 20, gainLossPercent: 50 },
    }
    mockedFetch.mockResolvedValue(page([sale]))
    render(<TransactionHistory user={user} />)

    expect(await screen.findByText('+$20.00')).toBeInTheDocument()
    expect(screen.getByText('(50.00%)')).toBeInTheDocument()
  })

  it('shows a loss on a sale as negative', async () => {
    const sale: Transaction = {
      transactionId: 3, type: 'stock', transactionType: 'sell',
      transactionDate: '2024-01-03T00:00:00Z', signedAmount: 30,
      ticker: 'AAPL', qty: -4, price: 7.5,
      realized: { costBasis: 40, proceeds: 30, gainLoss: -10, gainLossPercent: -25 },
    }
    mockedFetch.mockResolvedValue(page([sale]))
    render(<TransactionHistory user={user} />)

    const cell = await screen.findByText('-$10.00')
    expect(cell).toHaveClass('negative')
  })

  // A buy realises nothing; that is not the same as having made nothing.
  it('leaves the realized column blank on rows that cannot realise anything', async () => {
    mockedFetch.mockResolvedValue(page([deposit]))
    render(<TransactionHistory user={user} />)

    await screen.findByText('Deposited cash')
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('links to the CSV export as a download', async () => {
    mockedFetch.mockResolvedValue(page([deposit]))
    render(<TransactionHistory user={user} />)

    const link = await screen.findByRole('link', { name: 'Export CSV' })
    expect(link).toHaveAttribute('href', '/api/v1/users/1/transactions/export')
    expect(link).toHaveAttribute('download', 'transactions.csv')
  })
})
