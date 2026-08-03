import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Watchlist from './Watchlist'
import { fetchPopularAssets, fetchWatchlist, type AssetType } from '../api'
import { useLiveFeeds } from '../realtime'

vi.mock('../api', () => ({
  fetchWatchlist: vi.fn(),
  fetchPopularAssets: vi.fn().mockResolvedValue([]),
}))

vi.mock('../realtime', () => ({
  useLiveFeeds: vi.fn(() => ({ quotes: {}, lastUpdate: null })),
  useQuoteConnection: vi.fn(() => true),
}))

const mockedWatchlist = vi.mocked(fetchWatchlist)
const mockedPopular = vi.mocked(fetchPopularAssets)
const mockedFeeds = vi.mocked(useLiveFeeds)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

function entry(symbol: string, assetType: AssetType) {
  return {
    symbol,
    assetType,
    addedAt: '2026-01-01T00:00:00',
    name: `${symbol} Inc.`,
    currentPrice: 100,
    change: 1,
    changePercent: 1,
  }
}

beforeEach(() => {
  mockedWatchlist.mockReset()
  mockedPopular.mockReset().mockResolvedValue([])
  mockedFeeds.mockClear().mockReturnValue({ quotes: {}, lastUpdate: null })
})

describe('Watchlist', () => {
  it('subscribes to every streaming type it is showing, not just stocks', async () => {
    mockedWatchlist.mockResolvedValue([entry('AAPL', 'stock'), entry('BTC-USD', 'crypto')])
    render(<Watchlist user={user} />)

    await screen.findByText('AAPL')
    expect(mockedFeeds).toHaveBeenLastCalledWith({ stock: ['AAPL'], crypto: ['BTC-USD'] })
  })

  it('subscribes to a crypto-only list', async () => {
    mockedWatchlist.mockResolvedValue([entry('BTC-USD', 'crypto')])
    render(<Watchlist user={user} />)

    await screen.findByText('BTC-USD')
    expect(mockedFeeds).toHaveBeenLastCalledWith({ stock: [], crypto: ['BTC-USD'] })
  })

  it('does not subscribe to bonds, which are repriced rather than quoted', async () => {
    mockedWatchlist.mockResolvedValue([entry('UST2Y', 'bond')])
    render(<Watchlist user={user} />)

    await screen.findByText('UST2Y')
    expect(mockedFeeds).toHaveBeenLastCalledWith({ stock: [], crypto: [] })
  })

  it('claims no live feed for a list of bonds alone', async () => {
    mockedWatchlist.mockResolvedValue([entry('UST2Y', 'bond')])
    render(<Watchlist user={user} />)

    await screen.findByText('UST2Y')
    expect(screen.queryByText(/Live/)).not.toBeInTheDocument()
  })

  it('prefers a pushed quote over the one the list arrived with', async () => {
    mockedWatchlist.mockResolvedValue([entry('AAPL', 'stock')])
    mockedFeeds.mockReturnValue({
      quotes: { AAPL: { symbol: 'AAPL', currentPrice: 250, changePercent: 4 } },
      lastUpdate: new Date(),
    })
    render(<Watchlist user={user} />)

    expect(await screen.findByText('$250.00')).toBeInTheDocument()
  })

  it('stands in suggestions when nothing is saved', async () => {
    mockedWatchlist.mockResolvedValue([])
    mockedPopular.mockResolvedValue([{ symbol: 'NVDA', name: 'Nvidia', currentPrice: 10 }])
    render(<Watchlist user={user} />)

    expect(await screen.findByText('Most active today')).toBeInTheDocument()
  })
})
