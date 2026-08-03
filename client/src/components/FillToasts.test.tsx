import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FillToasts from './FillToasts'
import { useOrderFills, type OrderFill } from '../realtime'

vi.mock('../realtime', () => ({ useOrderFills: vi.fn() }))

const mockedUseOrderFills = vi.mocked(useOrderFills)

/** The handler the component registered, so a test can push a fill at it. */
let announce: (fill: OrderFill) => void

function fill(overrides: Partial<OrderFill> = {}): OrderFill {
  return {
    limitOrderId: 1,
    ticker: 'AAPL',
    side: 'buy',
    orderType: 'limit',
    quantity: 5,
    price: 9.5,
    assetTransactionId: 1,
    ...overrides,
  }
}

beforeEach(() => {
  mockedUseOrderFills.mockImplementation((onFill) => {
    announce = onFill
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('FillToasts', () => {
  it('shows nothing until something fills', () => {
    const { container } = render(<FillToasts />)
    expect(container).toBeEmptyDOMElement()
  })

  // The executed price, not the trigger: for a stop those differ, and only
  // one of them is what the user actually paid.
  it('reports what filled at the price it executed at', () => {
    render(<FillToasts />)
    act(() => announce(fill({ price: 9.5 })))

    expect(screen.getByText('Limit order filled')).toBeInTheDocument()
    expect(screen.getByText('Bought 5.00 AAPL at $9.50.')).toBeInTheDocument()
  })

  it('names a stop as a stop', () => {
    render(<FillToasts />)
    act(() => announce(fill({ orderType: 'stop', side: 'sell' })))

    expect(screen.getByText('Stop order filled')).toBeInTheDocument()
    expect(screen.getByText(/^Sold/)).toBeInTheDocument()
  })

  it('stacks several fills', () => {
    render(<FillToasts />)
    act(() => announce(fill({ limitOrderId: 1, ticker: 'AAPL' })))
    act(() => announce(fill({ limitOrderId: 2, ticker: 'MSFT' })))

    expect(screen.getAllByText(/order filled/)).toHaveLength(2)
  })

  it('can be dismissed by hand', async () => {
    const typer = userEvent.setup()
    render(<FillToasts />)
    act(() => announce(fill()))

    await typer.click(screen.getByRole('button', { name: 'Dismiss AAPL fill' }))
    expect(screen.queryByText(/order filled/)).not.toBeInTheDocument()
  })

  it('clears itself after a while', () => {
    vi.useFakeTimers()
    render(<FillToasts />)
    act(() => announce(fill()))

    expect(screen.getByText(/order filled/)).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(10_000))
    expect(screen.queryByText(/order filled/)).not.toBeInTheDocument()
  })

  // Worth knowing, not worth interrupting for.
  it('announces politely rather than as an alert', () => {
    render(<FillToasts />)
    act(() => announce(fill()))

    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })
})
