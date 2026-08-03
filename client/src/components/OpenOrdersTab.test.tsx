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
    _links: { cancel: '/api/v1/users/1/limit-orders/1' },
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

    expect(await screen.findByText(/don't have any open orders/)).toBeInTheDocument()
  })

  it('opens on the pending orders', async () => {
    mockedFetch.mockResolvedValue([])
    render(<OpenOrdersTab user={user} assetType="stock" />)

    await screen.findByText(/don't have any open orders/)
    expect(mockedFetch).toHaveBeenCalledWith(1, 'stock', 'pending', expect.any(Number))
  })

  it('switches to filled orders and shows when each resolved', async () => {
    const typer = userEvent.setup()
    mockedFetch.mockResolvedValueOnce([])
    render(<OpenOrdersTab user={user} assetType="stock" />)
    await screen.findByText(/don't have any open orders/)

    mockedFetch.mockResolvedValueOnce([
      order({ status: 'filled', resolvedAt: '2026-02-03T09:30:00' }),
    ])
    await typer.click(screen.getByRole('button', { name: 'Filled' }))

    expect(mockedFetch).toHaveBeenLastCalledWith(1, 'stock', 'filled', expect.any(Number))
    const row = within(await screen.findByRole('row', { name: /AAPL/ }))
    expect(row.getByText('Feb 3, 2026')).toBeInTheDocument()
    expect(row.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
  })

  it('switches to cancelled orders', async () => {
    const typer = userEvent.setup()
    mockedFetch.mockResolvedValueOnce([])
    render(<OpenOrdersTab user={user} assetType="stock" />)
    await screen.findByText(/don't have any open orders/)

    mockedFetch.mockResolvedValueOnce([])
    await typer.click(screen.getByRole('button', { name: 'Cancelled' }))

    expect(mockedFetch).toHaveBeenLastCalledWith(1, 'stock', 'cancelled', expect.any(Number))
    expect(await screen.findByText(/haven't cancelled any orders/)).toBeInTheDocument()
  })

  it('lists a pending order', async () => {
    mockedFetch.mockResolvedValue([order()])
    render(<OpenOrdersTab user={user} assetType="stock" />)

    const row = within(await screen.findByRole('row', { name: /AAPL/ }))
    expect(row.getByText('buy')).toBeInTheDocument()
    expect(row.getByText('limit')).toBeInTheDocument()
    expect(row.getByText('5.00')).toBeInTheDocument()
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

    expect(mockedCancel).toHaveBeenCalledWith(expect.objectContaining({ limitOrderId: 1 }))
    await waitFor(() => expect(screen.getByText(/don't have any open orders/)).toBeInTheDocument())
  })

  it('surfaces a failure instead of a silently empty list', async () => {
    mockedFetch.mockRejectedValue(new Error('Orders service is down'))
    render(<OpenOrdersTab user={user} assetType="stock" />)

    expect(await screen.findByText('Orders service is down')).toBeInTheDocument()
  })
})
