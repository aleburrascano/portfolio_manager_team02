import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FillToasts from './FillToasts'
import {
  useBondRedemptions,
  useOrderFills,
  type BondRedemption,
  type OrderFill,
} from '../../hooks/realtime'

vi.mock('../../hooks/realtime', () => ({ useOrderFills: vi.fn(), useBondRedemptions: vi.fn() }))

const mockedUseOrderFills = vi.mocked(useOrderFills)
const mockedUseRedemptions = vi.mocked(useBondRedemptions)

/** The handlers the component registered, so a test can push events at it. */
let announce: (fill: OrderFill) => void
let announceRedemption: (payout: BondRedemption) => void

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
  mockedUseRedemptions.mockImplementation((onRedeem) => {
    announceRedemption = onRedeem
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

    await typer.click(screen.getByRole('button', { name: 'Dismiss AAPL notice' }))
    expect(screen.queryByText(/order filled/)).not.toBeInTheDocument()
  })

  it('announces a bond paying out at maturity', () => {
    render(<FillToasts />)
    act(() =>
      announceRedemption({ ticker: 'UST2Y', quantity: 2, price: 1000, proceeds: 2000 }),
    )

    expect(screen.getByText('Bond matured')).toBeInTheDocument()
    expect(screen.getByText('UST2Y paid out $2,000.00 at face value.')).toBeInTheDocument()
  })

  it('keeps a fill and a redemption apart', () => {
    render(<FillToasts />)
    act(() => announce(fill()))
    act(() =>
      announceRedemption({ ticker: 'UST2Y', quantity: 1, price: 1000, proceeds: 1000 }),
    )

    expect(screen.getByText('Limit order filled')).toBeInTheDocument()
    expect(screen.getByText('Bond matured')).toBeInTheDocument()
  })

  it('clears itself after a while', () => {
    vi.useFakeTimers()
    render(<FillToasts />)
    act(() => announce(fill()))

    expect(screen.getByText(/order filled/)).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(10_000))
    expect(screen.queryByText(/order filled/)).not.toBeInTheDocument()
  })

  it('announces politely rather than as an alert', () => {
    render(<FillToasts />)
    act(() => announce(fill()))

    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })
})
