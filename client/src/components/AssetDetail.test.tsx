import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssetDetail from './AssetDetail'
import { BalanceContext } from '../balance-context'
import {
  buyAsset,
  fetchAssetDetail,
  fetchAssetHistory,
  fetchAssetRatings,
  fetchHoldings,
  isWatched,
  placeLimitOrder,
  sellAsset,
  setWatched,
  type User,
} from '../api'

vi.mock('../api', () => ({
  fetchAssetDetail: vi.fn(),
  fetchAssetHistory: vi.fn(),
  fetchHoldings: vi.fn(),
  fetchAssetRatings: vi.fn(),
  isWatched: vi.fn(),
  setWatched: vi.fn(),
  buyAsset: vi.fn(),
  sellAsset: vi.fn(),
  placeLimitOrder: vi.fn(),
}))

// Recharts measures its container, which jsdom reports as 0x0, so the SVG
// never renders. These tests don't cover the chart itself.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}))

const mockedFetchDetail = vi.mocked(fetchAssetDetail)
const mockedFetchHistory = vi.mocked(fetchAssetHistory)
const mockedFetchHoldings = vi.mocked(fetchHoldings)
const mockedFetchRatings = vi.mocked(fetchAssetRatings)
const mockedIsWatched = vi.mocked(isWatched)
const mockedSetWatched = vi.mocked(setWatched)
const mockedBuyAsset = vi.mocked(buyAsset)
const mockedSellAsset = vi.mocked(sellAsset)
const mockedPlaceLimitOrder = vi.mocked(placeLimitOrder)

const user: User = { userId: 1, username: 'alice', firstName: 'Alice', lastName: 'Anderson' }

function renderDetail(balance = 1000) {
  return render(
    <BalanceContext.Provider value={{ balance, refreshBalance: vi.fn() }}>
      <AssetDetail assetType="stock" symbol="AAPL" user={user} onBack={vi.fn()} />
    </BalanceContext.Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedFetchDetail.mockResolvedValue({
    symbol: 'AAPL',
    name: 'Apple Inc.',
    currentPrice: 10,
    change: 0.5,
    changePercent: 5,
    dayLow: 9,
    dayHigh: 11,
    open: 9.5,
    yearLow: 5,
    yearHigh: 15,
    volume: 1000,
  })
  mockedFetchHistory.mockResolvedValue([])
  mockedFetchHoldings.mockResolvedValue(0)
  mockedFetchRatings.mockResolvedValue(null)
  mockedIsWatched.mockResolvedValue(false)
  mockedSetWatched.mockResolvedValue(undefined)
})

describe('AssetDetail order type', () => {
  it('defaults to a market order with no limit-price field', async () => {
    renderDetail()
    await screen.findByText('AAPL', { selector: '.asset-symbol' })

    expect(screen.queryByLabelText('Limit price')).not.toBeInTheDocument()
  })

  it('shows a limit-price field once Limit is selected', async () => {
    const typer = userEvent.setup()
    renderDetail()
    await screen.findByText('AAPL', { selector: '.asset-symbol' })

    await typer.click(screen.getByRole('button', { name: 'Limit' }))
    expect(screen.getByLabelText('Limit price')).toBeInTheDocument()
  })

  it('blocks review with an empty limit price', async () => {
    // The input's own min="0.01" stops the browser from ever firing a
    // submit with 0 or a blank value, so this exercises the same guard
    // validateAmountInput backs up rather than the JS branch directly.
    const typer = userEvent.setup()
    renderDetail()
    await screen.findByText('AAPL', { selector: '.asset-symbol' })

    await typer.click(screen.getByRole('button', { name: 'Limit' }))
    await typer.click(screen.getByRole('button', { name: /Review buy order/ }))

    expect(screen.queryByRole('heading', { name: /Place buy order/ })).not.toBeInTheDocument()
  })

  it('places a limit order without touching balance or holdings, and leaves the market path untouched', async () => {
    const typer = userEvent.setup()
    renderDetail()
    await screen.findByText('AAPL', { selector: '.asset-symbol' })

    await typer.click(screen.getByRole('button', { name: 'Limit' }))
    await typer.clear(screen.getByLabelText('Quantity'))
    await typer.type(screen.getByLabelText('Quantity'), '5')
    await typer.type(screen.getByLabelText('Limit price'), '8')
    await typer.click(screen.getByRole('button', { name: /Review buy order/ }))

    expect(await screen.findByRole('heading', { name: /Place buy order for 5.00 AAPL/ })).toBeInTheDocument()
    expect(screen.getByText(/Pending until the price is met/)).toBeInTheDocument()

    await typer.click(screen.getByRole('button', { name: 'Place order' }))

    expect(mockedPlaceLimitOrder).toHaveBeenCalledWith(1, 'stock', 'AAPL', 'buy', 5, 8, expect.any(String))
    expect(mockedBuyAsset).not.toHaveBeenCalled()
    expect(mockedFetchHoldings).toHaveBeenCalledTimes(1) // only the initial load, not a post-order refresh
    expect(await screen.findByText(/Limit order placed/)).toBeInTheDocument()
  })

  it('still places a market order the normal way when Market is selected', async () => {
    const typer = userEvent.setup()
    mockedSellAsset.mockResolvedValue(undefined)
    renderDetail()
    await screen.findByText('AAPL', { selector: '.asset-symbol' })

    await typer.clear(screen.getByLabelText('Quantity'))
    await typer.type(screen.getByLabelText('Quantity'), '1')
    await typer.click(screen.getByRole('button', { name: /Review buy/ }))
    await typer.click(await screen.findByRole('button', { name: /^Buy 1.00 AAPL$/ }))

    expect(mockedBuyAsset).toHaveBeenCalledWith(1, 'stock', 'AAPL', 1, expect.any(String))
    expect(mockedPlaceLimitOrder).not.toHaveBeenCalled()
  })
})
