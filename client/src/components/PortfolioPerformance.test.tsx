import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PortfolioPerformance from './PortfolioPerformance'
import { fetchPortfolioPerformance, type PortfolioPerformance as Performance } from '../api'

vi.mock('../api', () => ({
  fetchPortfolioPerformance: vi.fn(),
}))

// Recharts measures its container, which jsdom reports as 0x0, so the SVG
// never renders. These tests cover the parts around it: the headline, the
// range control, and the states where no chart is drawn at all.
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
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

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
    benchmark: { ticker: 'SPY', label: 'S&P 500' },
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
})

describe('PortfolioPerformance', () => {
  it('announces that it is loading before the series arrives', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))
    render(<PortfolioPerformance user={user} balance={100} />)
    expect(screen.getByText('Loading portfolio performance')).toBeInTheDocument()
  })

  // The statement head owns "what am I worth"; this card reports change,
  // so it must not repeat a level that two fetches could disagree on.
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

  it('defaults to a one-year window', async () => {
    render(<PortfolioPerformance user={user} balance={100} />)
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledWith(1, 365))
    expect(screen.getByRole('button', { name: '1Y' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('refetches for the range the user picks', async () => {
    const typer = userEvent.setup()
    render(<PortfolioPerformance user={user} balance={100} />)
    await screen.findByText(/against \$1,000.00 paid in/)

    await typer.click(screen.getByRole('button', { name: '1M' }))
    await waitFor(() => expect(mockedFetch).toHaveBeenLastCalledWith(1, 30))
  })

  it('breaks the gain down by asset class', async () => {
    render(<PortfolioPerformance user={user} balance={100} />)
    expect(await screen.findByText('Stocks')).toBeInTheDocument()
  })

  // A single point is a dot, not a trend; saying so beats an empty frame.
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

  // Beating your own deposits only means you didn't lose money. This is the
  // comparison that says whether the picking was worth doing.
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

  // The index is priced best-effort like everything else here: no
  // comparison rather than no chart.
  it('leaves the comparison out when the index could not be priced', async () => {
    render(<PortfolioPerformance user={user} balance={100} />)

    await screen.findByText(/against \$1,000.00 paid in/)
    expect(screen.queryByText(/S&P 500 by/)).not.toBeInTheDocument()
  })
})
