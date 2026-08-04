import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PortfolioPerformance from './PortfolioPerformance'
import {
  fetchPopularAssets,
  fetchPortfolioPerformance,
  searchAssets,
  type PortfolioPerformance as Performance,
} from '../../api'

vi.mock('../../api', () => ({
  fetchPortfolioPerformance: vi.fn(),
  fetchPopularAssets: vi.fn(),
  searchAssets: vi.fn(),
}))

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => null,
  Line: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}))

const mockedFetch = vi.mocked(fetchPortfolioPerformance)
const mockedPopular = vi.mocked(fetchPopularAssets)
const mockedSearch = vi.mocked(searchAssets)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

/** What the chart compares against until the user picks something else. */
const SP500 = { assetType: 'stock', ticker: 'SPY', label: 'S&P 500' }

function performance(overrides: Partial<Performance> = {}): Performance {
  return {
    series: [
      { date: '2026-01-01', portfolioValue: 1000, investedValue: 500, cash: 500, netDeposits: 1000 },
      { date: '2026-01-02', portfolioValue: 1500, investedValue: 1000, cash: 500, netDeposits: 1000 },
    ],
    summary: {
      startValue: 1000,
      currentValue: 1500,
      netDeposits: 1000,
      gainLoss: 500,
      gainLossPercent: 50,
    },
    byAssetType: [
      { assetType: 'stock', value: 1000, costBasis: 500, gainLoss: 500, gainLossPercent: 100 },
    ],
    benchmark: { assetType: 'stock', ticker: 'SPY' },
    ...overrides,
  }
}

/** The same series, with the index comparison the server attaches. */
function withBenchmark(portfolioEnd: number, benchmarkEnd: number): Partial<Performance> {
  return {
    series: [
      {
        date: '2026-01-01', portfolioValue: 1000, investedValue: 500,
        cash: 500, netDeposits: 1000, benchmarkValue: 1000,
      },
      {
        date: '2026-01-02', portfolioValue: portfolioEnd, investedValue: 1000,
        cash: 500, netDeposits: 1000, benchmarkValue: benchmarkEnd,
      },
    ],
  }
}

beforeEach(() => {
  mockedFetch.mockReset()
  mockedFetch.mockResolvedValue(performance())
  mockedPopular.mockReset()
  mockedPopular.mockResolvedValue([{ symbol: 'BTC-USD', name: 'Bitcoin', currentPrice: 60000 }])
  mockedSearch.mockReset()
  mockedSearch.mockResolvedValue([])
})

describe('PortfolioPerformance', () => {
  it('announces that it is loading before the series arrives', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))
    render(<PortfolioPerformance user={user} balance={100} />)
    expect(screen.getByText('Loading portfolio performance')).toBeInTheDocument()
  })

  it('shows the gain against what was paid in, not the portfolio value', async () => {
    render(<PortfolioPerformance user={user} balance={100} />)

    expect(await screen.findByText(/▲ \$500.00 \(50.00%\)/)).toBeInTheDocument()
    expect(screen.getByText(/against \$1,000.00 paid in/)).toBeInTheDocument()
    expect(screen.queryByText('$1,500.00')).not.toBeInTheDocument()
  })

  it('shows a loss with a down glyph', async () => {
    mockedFetch.mockResolvedValue(
      performance({
        summary: {
          startValue: 1000,
          currentValue: 800,
          netDeposits: 1000,
          gainLoss: -200,
          gainLossPercent: -20,
        },
      }),
    )
    render(<PortfolioPerformance user={user} balance={100} />)
    expect(await screen.findByText(/▼ \$200.00 \(20.00%\)/)).toBeInTheDocument()
  })

  it('defaults to a one-year window against the S&P 500', async () => {
    render(<PortfolioPerformance user={user} balance={100} />)
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledWith(1, 365, SP500))
    expect(screen.getByRole('button', { name: '1Y' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('refetches for the range the user picks', async () => {
    const typer = userEvent.setup()
    render(<PortfolioPerformance user={user} balance={100} />)
    await screen.findByText(/against \$1,000.00 paid in/)

    await typer.click(screen.getByRole('button', { name: '1M' }))
    await waitFor(() => expect(mockedFetch).toHaveBeenLastCalledWith(1, 30, SP500))
  })

  it('breaks the gain down by asset class', async () => {
    render(<PortfolioPerformance user={user} balance={100} />)
    expect(await screen.findByText('Stocks')).toBeInTheDocument()
  })

  it('explains that there is not enough history yet', async () => {
    mockedFetch.mockResolvedValue(performance({ series: [] }))
    render(<PortfolioPerformance user={user} balance={100} />)
    expect(await screen.findByText(/isn't enough history to chart yet/)).toBeInTheDocument()
  })

  it('surfaces a failure instead of an empty frame', async () => {
    mockedFetch.mockRejectedValue(new Error('Performance service is down'))
    render(<PortfolioPerformance user={user} balance={100} />)
    expect(await screen.findByText(/Performance service is down/)).toBeInTheDocument()
  })

  it('says how far ahead of the benchmark the portfolio is', async () => {
    mockedFetch.mockResolvedValue(performance(withBenchmark(1500, 1200)))
    render(<PortfolioPerformance user={user} balance={100} />)

    expect(await screen.findByText('ahead of S&P 500 by $300.00')).toBeInTheDocument()
  })

  it('says so when the portfolio is behind the benchmark', async () => {
    mockedFetch.mockResolvedValue(performance(withBenchmark(1100, 1400)))
    render(<PortfolioPerformance user={user} balance={100} />)

    expect(await screen.findByText('behind S&P 500 by $300.00')).toBeInTheDocument()
  })

  it('leaves the comparison out when the index could not be priced', async () => {
    render(<PortfolioPerformance user={user} balance={100} />)

    await screen.findByText(/against \$1,000.00 paid in/)
    expect(screen.queryByText(/S&P 500 by/)).not.toBeInTheDocument()
    expect(screen.getByText(/S&P 500 couldn't be priced/)).toBeInTheDocument()
  })

  it('drops the comparison when the toggle is switched off, without refetching', async () => {
    const typer = userEvent.setup()
    mockedFetch.mockResolvedValue(performance(withBenchmark(1500, 1200)))
    render(<PortfolioPerformance user={user} balance={100} />)
    await screen.findByText('ahead of S&P 500 by $300.00')

    await typer.click(screen.getByRole('checkbox', { name: 'Compare against' }))

    expect(screen.queryByText('ahead of S&P 500 by $300.00')).not.toBeInTheDocument()
    expect(mockedFetch).toHaveBeenCalledTimes(1)
  })

  it('compares against any asset the user searches for', async () => {
    const typer = userEvent.setup()
    render(<PortfolioPerformance user={user} balance={100} />)
    await screen.findByText(/against \$1,000.00 paid in/)

    await typer.click(screen.getByRole('button', { name: 'S&P 500' }))
    await typer.selectOptions(screen.getByLabelText('Asset type'), 'crypto')
    await typer.click(await screen.findByRole('button', { name: /Bitcoin/ }))

    await waitFor(() =>
      expect(mockedFetch).toHaveBeenLastCalledWith(1, 365, {
        assetType: 'crypto',
        ticker: 'BTC-USD',
        label: 'Bitcoin',
      }),
    )
    expect(screen.getByRole('button', { name: 'Bitcoin' })).toBeInTheDocument()
  })
})
