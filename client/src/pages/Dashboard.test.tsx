import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'
import { fetchPortfolioBreakdown } from '../api'
import { useBalance } from '../balance-context'

vi.mock('../api', () => ({
  fetchPortfolioBreakdown: vi.fn(),
  fetchPortfolioHoldings: vi.fn().mockResolvedValue({
    holdings: [],
    totals: {
      positions: 0,
      value: 0,
      costBasis: 0,
      gainLoss: 0,
      gainLossPercent: 0,
      dayChange: 0,
      dayChangePercent: 0,
    },
  }),
}))

vi.mock('../balance-context', () => ({
  useBalance: vi.fn(),
}))

vi.mock('../components/PortfolioComposition', () => ({
  default: ({ data }: { data: { name: string; value: number }[] }) => (
    <div data-testid="portfolio-composition">{JSON.stringify(data)}</div>
  ),
}))

vi.mock('../components/WalletCard', () => ({
  default: () => <div data-testid="wallet-card" />,
}))

vi.mock('../components/Watchlist', () => ({
  default: () => <div data-testid="watchlist" />,
}))

vi.mock('../components/PortfolioPerformance', () => ({
  default: () => <div data-testid="portfolio-performance" />,
}))

vi.mock('../components/HoldingsTable', () => ({
  default: () => <div data-testid="holdings-table" />,
}))

const mockedFetch = vi.mocked(fetchPortfolioBreakdown)
const mockedUseBalance = vi.mocked(useBalance)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

beforeEach(() => {
  mockedFetch.mockReset()
  mockedUseBalance.mockReturnValue({ balance: 500, refreshBalance: vi.fn().mockResolvedValue(undefined) })
})

const onBrowseAssets = vi.fn()

describe('Dashboard', () => {
  it('shows a loading state before the portfolio resolves', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))
    render(<Dashboard user={user} onBrowseAssets={onBrowseAssets} onSelectAsset={vi.fn()} />)
    expect(screen.getByText('Loading your portfolio')).toBeInTheDocument()
  })

  // The first screen a new account sees. It has to say what the panel is
  // for and offer the next step, not just report an absence.
  it('teaches the panel and offers a next step when the portfolio is empty', async () => {
    mockedFetch.mockResolvedValue({ cash: 0, stock: 0, crypto: 0, bond: 0 })
    mockedUseBalance.mockReturnValue({ balance: 0, refreshBalance: vi.fn() })
    const typer = userEvent.setup()
    render(<Dashboard user={user} onBrowseAssets={onBrowseAssets} onSelectAsset={vi.fn()} />)

    expect(await screen.findByText(/Deposit some cash above to get started/)).toBeInTheDocument()

    await typer.click(screen.getByRole('button', { name: 'Browse assets' }))
    expect(onBrowseAssets).toHaveBeenCalled()
  })

  it('tells a funded but unheld account what to do next', async () => {
    mockedFetch.mockResolvedValue({ cash: 0, stock: 0, crypto: 0, bond: 0 })
    render(<Dashboard user={user} onBrowseAssets={onBrowseAssets} onSelectAsset={vi.fn()} />)
    expect(await screen.findByText(/Once you buy your first stock/)).toBeInTheDocument()
  })

  it('renders the composition chart once data resolves', async () => {
    mockedFetch.mockResolvedValue({ cash: 100, stock: 50, crypto: 0, bond: 0 })
    render(<Dashboard user={user} onBrowseAssets={onBrowseAssets} onSelectAsset={vi.fn()} />)
    expect(await screen.findByTestId('portfolio-composition')).toBeInTheDocument()
  })

  it('shows every panel on one screen', async () => {
    mockedFetch.mockResolvedValue({ cash: 100, stock: 50, crypto: 0, bond: 0 })
    render(<Dashboard user={user} onBrowseAssets={onBrowseAssets} onSelectAsset={vi.fn()} />)

    expect(await screen.findByTestId('portfolio-composition')).toBeInTheDocument()
    // The chart is code-split, so it resolves a tick after the rest.
    expect(await screen.findByTestId('portfolio-performance')).toBeInTheDocument()
    expect(screen.getByTestId('holdings-table')).toBeInTheDocument()
    expect(screen.getByTestId('watchlist')).toBeInTheDocument()
  })

  it('shows the error message on failure', async () => {
    mockedFetch.mockRejectedValue(new Error('Failed to fetch portfolio breakdown'))
    render(<Dashboard user={user} onBrowseAssets={onBrowseAssets} onSelectAsset={vi.fn()} />)
    expect(await screen.findByText(/Failed to fetch portfolio breakdown/)).toBeInTheDocument()
  })
})

