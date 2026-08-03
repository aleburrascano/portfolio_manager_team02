import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Dashboard from './Dashboard'
import { fetchPortfolioBreakdown } from '../api'
import { useBalance } from '../context/balance-context'

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

vi.mock('../context/balance-context', () => ({
  useBalance: vi.fn(),
}))

vi.mock('../components/portfolio/PortfolioComposition', () => ({
  default: ({ data }: { data: { name: string; value: number }[] }) => (
    <div data-testid="portfolio-composition">{JSON.stringify(data)}</div>
  ),
}))

vi.mock('../components/portfolio/WalletCard', () => ({
  default: () => <div data-testid="wallet-card" />,
}))

vi.mock('../components/portfolio/Watchlist', () => ({
  default: () => <div data-testid="watchlist" />,
}))

vi.mock('../components/portfolio/PortfolioPerformance', () => ({
  default: () => <div data-testid="portfolio-performance" />,
}))

vi.mock('../components/portfolio/HoldingsTable', () => ({
  default: () => <div data-testid="holdings-table" />,
}))

const mockedFetch = vi.mocked(fetchPortfolioBreakdown)
const mockedUseBalance = vi.mocked(useBalance)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

beforeEach(() => {
  mockedFetch.mockReset()
  mockedUseBalance.mockReturnValue({ balance: 500, settled: true, refreshBalance: vi.fn().mockResolvedValue(undefined) })
})

/**
 * Rendered inside a router, since opening an asset is now navigation
 * rather than a callback. The stub route reports where it landed, which is
 * what the old onBrowseAssets spy was standing in for.
 */
function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<Dashboard user={user} />} />
        <Route path="/trade" element={<div>Trade screen</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Dashboard', () => {
  it('shows a loading state before the portfolio resolves', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))
    renderDashboard()
    expect(screen.getByText('Loading your portfolio')).toBeInTheDocument()
  })

  it('teaches the panel and offers a next step when the portfolio is empty', async () => {
    mockedFetch.mockResolvedValue({ cash: 0, stock: 0, crypto: 0, bond: 0 })
    mockedUseBalance.mockReturnValue({ balance: 0, settled: true, refreshBalance: vi.fn() })
    const typer = userEvent.setup()
    renderDashboard()

    expect(await screen.findByText(/Deposit some cash above to get started/)).toBeInTheDocument()

    await typer.click(screen.getByRole('button', { name: 'Browse assets' }))
    expect(await screen.findByText('Trade screen')).toBeInTheDocument()
  })

  it('tells a funded but unheld account what to do next', async () => {
    mockedFetch.mockResolvedValue({ cash: 0, stock: 0, crypto: 0, bond: 0 })
    renderDashboard()
    expect(await screen.findByText(/Once you buy your first stock/)).toBeInTheDocument()
  })

  it('renders the composition chart once data resolves', async () => {
    mockedFetch.mockResolvedValue({ cash: 100, stock: 50, crypto: 0, bond: 0 })
    renderDashboard()
    expect(await screen.findByTestId('portfolio-composition')).toBeInTheDocument()
  })

  it('shows every panel on one screen', async () => {
    mockedFetch.mockResolvedValue({ cash: 100, stock: 50, crypto: 0, bond: 0 })
    renderDashboard()

    expect(await screen.findByTestId('portfolio-composition')).toBeInTheDocument()
    expect(await screen.findByTestId('portfolio-performance')).toBeInTheDocument()
    expect(screen.getByTestId('holdings-table')).toBeInTheDocument()
    expect(screen.getByTestId('watchlist')).toBeInTheDocument()
  })

  it('shows the error message on failure', async () => {
    mockedFetch.mockRejectedValue(new Error('Failed to fetch portfolio breakdown'))
    renderDashboard()
    expect(await screen.findByText(/Failed to fetch portfolio breakdown/)).toBeInTheDocument()
  })
})

