import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TransactionHistory from './TransactionHistory'
import { fetchTransactions, type Transaction } from '../api'

vi.mock('../api', () => ({
  fetchTransactions: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchTransactions)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

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
    mockedFetch.mockResolvedValue([])
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
    const transactions: Transaction[] = [
      {
        transactionId: 1, type: 'cash', transactionType: 'deposit',
        transactionDate: '2024-01-01T00:00:00Z', signedAmount: 100,
      },
      {
        transactionId: 2, type: 'stock', transactionType: 'buy',
        transactionDate: '2024-01-02T00:00:00Z', signedAmount: -50, ticker: 'AAPL', qty: 5, price: 10,
      },
    ]
    mockedFetch.mockResolvedValue(transactions)
    render(<TransactionHistory user={user} />)

    // Both rows read as something that happened, in the same tense.
    expect(await screen.findByText('Deposited cash')).toBeInTheDocument()
    expect(screen.getByText('+$100.00')).toBeInTheDocument()
    expect(screen.getByText('Bought 5.00 AAPL')).toBeInTheDocument()
    expect(screen.getByText('-$50.00')).toBeInTheDocument()
  })

  it('lists the newest transaction first and can reverse the order', async () => {
    const transactions: Transaction[] = [
      {
        transactionId: 1, type: 'cash', transactionType: 'deposit',
        transactionDate: '2024-01-01T00:00:00Z', signedAmount: 100,
      },
      {
        transactionId: 2, type: 'stock', transactionType: 'buy',
        transactionDate: '2024-01-02T00:00:00Z', signedAmount: -50, ticker: 'AAPL', qty: 5, price: 10,
      },
    ]
    mockedFetch.mockResolvedValue(transactions)
    const typer = userEvent.setup()
    render(<TransactionHistory user={user} />)

    const descriptionOrder = () =>
      screen.getAllByRole('cell')
        .map((cell) => cell.textContent)
        .filter((text) => text === 'Deposited cash' || text === 'Bought 5.00 AAPL')

    await screen.findByText('Deposited cash')
    expect(descriptionOrder()).toEqual(['Bought 5.00 AAPL', 'Deposited cash'])

    await typer.click(screen.getByRole('button', { name: 'Newest first' }))
    expect(descriptionOrder()).toEqual(['Deposited cash', 'Bought 5.00 AAPL'])
  })
})
