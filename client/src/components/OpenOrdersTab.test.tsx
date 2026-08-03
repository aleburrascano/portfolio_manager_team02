import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import OpenOrdersTab from './OpenOrdersTab'
import { cancelLimitOrder, fetchLimitOrders, type LimitOrder, type User } from '../api'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, fetchLimitOrders: vi.fn(), cancelLimitOrder: vi.fn() }
})

const mockedFetch = vi.mocked(fetchLimitOrders)
const mockedCancel = vi.mocked(cancelLimitOrder)

const user: User = { userId: 1, username: 'alice', firstName: 'Alice', lastName: 'Anderson' }

function order(overrides: Partial<LimitOrder> = {}): LimitOrder {
  return {
    limitOrderId: 1,
    ticker: 'AAPL',
    side: 'buy',
    orderType: 'limit',
    quantity: 5,
    limitPrice: 8,
    status: 'pending',
    createdAt: '2026-01-05T12:00:00',
    resolvedAt: null,
    assetTransactionId: null,
    ...overrides,
  }
}

beforeEach(() => {
  mockedFetch.mockReset()
  mockedCancel.mockReset()
})

describe('OpenOrdersTab', () => {
  it('teaches the panel when there are no open orders', async () => {
    mockedFetch.mockResolvedValue([])
    render(<OpenOrdersTab user={user} assetType="stock" />)

    expect(await screen.findByText(/don't have any open limit orders/)).toBeInTheDocument()
  })

  it('lists a pending order', async () => {
    mockedFetch.mockResolvedValue([order()])
    render(<OpenOrdersTab user={user} assetType="stock" />)

    const row = within(await screen.findByRole('row', { name: /AAPL/ }))
    expect(row.getByText('buy')).toBeInTheDocument()
    expect(row.getByText('limit')).toBeInTheDocument()
    expect(row.getByText('5.00')).toBeInTheDocument()
    // A limit buy waits for a fall, so the trigger reads as a ceiling.
    expect(row.getByText('≤ $8.00')).toBeInTheDocument()
  })

  it('reads a stop sell as waiting for a fall', async () => {
    mockedFetch.mockResolvedValue([order({ side: 'sell', orderType: 'stop' })])
    render(<OpenOrdersTab user={user} assetType="stock" />)

    const row = within(await screen.findByRole('row', { name: /AAPL/ }))
    expect(row.getByText('stop')).toBeInTheDocument()
    expect(row.getByText('≤ $8.00')).toBeInTheDocument()
  })

  it('reads a limit sell as waiting for a rise', async () => {
    mockedFetch.mockResolvedValue([order({ side: 'sell', orderType: 'limit' })])
    render(<OpenOrdersTab user={user} assetType="stock" />)

    const row = within(await screen.findByRole('row', { name: /AAPL/ }))
    expect(row.getByText('≥ $8.00')).toBeInTheDocument()
  })

  it('cancels an order and refetches the list', async () => {
    mockedFetch.mockResolvedValueOnce([order()])
    mockedCancel.mockResolvedValue(undefined)
    mockedFetch.mockResolvedValueOnce([])
    const typer = userEvent.setup()
    render(<OpenOrdersTab user={user} assetType="stock" />)

    await screen.findByRole('row', { name: /AAPL/ })
    await typer.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(mockedCancel).toHaveBeenCalledWith(1, 1)
    await waitFor(() => expect(screen.getByText(/don't have any open limit orders/)).toBeInTheDocument())
  })

  it('surfaces a failure instead of a silently empty list', async () => {
    mockedFetch.mockRejectedValue(new Error('Orders service is down'))
    render(<OpenOrdersTab user={user} assetType="stock" />)

    expect(await screen.findByText('Orders service is down')).toBeInTheDocument()
  })
})
