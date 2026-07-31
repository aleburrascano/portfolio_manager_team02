import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import HoldingsTable from './HoldingsTable'
import type { Holding, HoldingsResult } from '../api'

vi.mock('./AssetLogo', () => ({ default: () => <span data-testid="logo" /> }))

/** The order tickers appear in the table body. */
function rowOrder() {
  return screen
    .getAllByRole('row')
    .map((row) => row.querySelector('.holdings-ticker')?.textContent)
    .filter(Boolean)
}

function holding(overrides: Partial<Holding> = {}): Holding {
  return {
    ticker: 'AAPL',
    assetType: 'stock',
    quantity: 10,
    currentPrice: 150,
    averageCost: 100,
    value: 1500,
    costBasis: 1000,
    gainLoss: 500,
    gainLossPercent: 50,
    dayChange: 0,
    acquiredAt: '2026-01-05T12:00:00',
    ...overrides,
  }
}

function book(holdings: Holding[]): HoldingsResult {
  const value = holdings.reduce((sum, row) => sum + row.value, 0)
  const costBasis = holdings.reduce((sum, row) => sum + row.costBasis, 0)
  const dayChange = holdings.reduce((sum, row) => sum + row.dayChange, 0)
  return {
    holdings,
    totals: {
      positions: holdings.length,
      value,
      costBasis,
      gainLoss: value - costBasis,
      gainLossPercent: costBasis ? ((value - costBasis) / costBasis) * 100 : 0,
      dayChange,
      dayChangePercent: 0,
    },
  }
}

function renderTable(data: HoldingsResult | null, overrides = {}) {
  return render(
    <HoldingsTable data={data} loading={false} error={null} {...overrides} />,
  )
}

describe('HoldingsTable', () => {
  it('shows row-shaped placeholders while loading', () => {
    const { container } = render(
      <HoldingsTable data={null} loading error={null} />,
    )
    expect(container.querySelectorAll('.skeleton-holding')).toHaveLength(4)
  })

  it('teaches the panel when nothing is held', () => {
    renderTable(book([]))
    expect(screen.getByText(/You don't hold any positions yet/)).toBeInTheDocument()
  })

  it('renders a position with its cost basis, value, and gain', () => {
    renderTable(book([holding()]))

    const row = within(screen.getByRole('row', { name: /AAPL/ }))
    expect(row.getByText('10.00')).toBeInTheDocument()
    expect(row.getByText('$100.00')).toBeInTheDocument()
    expect(row.getByText('$1,500.00')).toBeInTheDocument()
    expect(row.getByText(/▲ \$500.00/)).toBeInTheDocument()
  })

  it('shows a loss with a down glyph, not colour alone', () => {
    renderTable(
      book([holding({ value: 800, costBasis: 1000, gainLoss: -200, gainLossPercent: -20 })]),
    )

    // Scoped to the position: with one holding the totals row carries the
    // same figure, and an unscoped query would match both.
    const row = within(screen.getByRole('row', { name: /AAPL/ }))
    expect(row.getByText(/▼ \$200.00/)).toBeInTheDocument()
  })

  // Sorting is local: the payload is already here, so a column click must
  // reorder in place without any further data fetching.
  it('sorts in memory', async () => {
    const typer = userEvent.setup()
    renderTable(
      book([
        holding({ ticker: 'AAPL', value: 1500, gainLoss: 500, gainLossPercent: 50 }),
        holding({ ticker: 'MSFT', value: 900, gainLoss: 800, gainLossPercent: 400 }),
      ]),
    )

    expect(rowOrder()).toEqual(['AAPL', 'MSFT'])
    await typer.click(screen.getByRole('button', { name: /Gain \/ loss/ }))
    expect(rowOrder()).toEqual(['MSFT', 'AAPL'])
  })

  it('opens a text column ascending and a numeric one descending', async () => {
    const typer = userEvent.setup()
    renderTable(
      book([holding({ ticker: 'MSFT', value: 1500 }), holding({ ticker: 'AAPL', value: 900 })]),
    )

    // Names read A-Z on the first click...
    await typer.click(screen.getByRole('button', { name: /Asset/ }))
    expect(rowOrder()).toEqual(['AAPL', 'MSFT'])

    // ...money reads largest-first.
    await typer.click(screen.getByRole('button', { name: /Value/ }))
    expect(rowOrder()).toEqual(['MSFT', 'AAPL'])
  })

  it('reverses the order when the active column is clicked again', async () => {
    const typer = userEvent.setup()
    renderTable(
      book([holding({ ticker: 'MSFT', value: 1500 }), holding({ ticker: 'AAPL', value: 900 })]),
    )

    expect(rowOrder()).toEqual(['MSFT', 'AAPL'])
    await typer.click(screen.getByRole('button', { name: /Value/ }))
    expect(rowOrder()).toEqual(['AAPL', 'MSFT'])
  })

  it('sorts an unknown acquisition date to the end either way', async () => {
    const typer = userEvent.setup()
    renderTable(
      book([
        holding({ ticker: 'AAPL', acquiredAt: '2026-01-05T12:00:00' }),
        holding({ ticker: 'MSFT', acquiredAt: null }),
      ]),
    )

    await typer.click(screen.getByRole('button', { name: /Acquired/ }))
    expect(rowOrder()).toEqual(['AAPL', 'MSFT'])

    await typer.click(screen.getByRole('button', { name: /Acquired/ }))
    expect(rowOrder()).toEqual(['AAPL', 'MSFT'])
  })

  it('marks the sorted column for assistive tech', () => {
    renderTable(book([holding()]))

    expect(screen.getByRole('columnheader', { name: /Value/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
    expect(screen.getByRole('columnheader', { name: /Quantity/ })).toHaveAttribute(
      'aria-sort',
      'none',
    )
  })

  it('totals the book in a footer row', () => {
    renderTable(book([holding(), holding({ ticker: 'MSFT', value: 500, costBasis: 400 })]))

    expect(screen.getByText('2 positions')).toBeInTheDocument()
    const footer = within(screen.getByRole('row', { name: /Total/ }))
    expect(footer.getByText('$2,000.00')).toBeInTheDocument()
  })

  it('opens a position from its row', async () => {
    const onSelectAsset = vi.fn()
    const typer = userEvent.setup()
    renderTable(book([holding()]), { onSelectAsset })

    await typer.click(screen.getByRole('button', { name: /AAPL/ }))
    expect(onSelectAsset).toHaveBeenCalledWith('stock', 'AAPL')
  })

  it('surfaces a failure instead of an empty table', () => {
    render(
      <HoldingsTable data={null} loading={false} error="Holdings service is down" />,
    )
    expect(screen.getByText(/Holdings service is down/)).toBeInTheDocument()
  })
})
