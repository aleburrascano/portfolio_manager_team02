import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AssetList from './AssetList'
import type { Asset } from '../api'

const AAPL: Asset = {
  symbol: 'AAPL', name: 'Apple Inc.', currentPrice: 150, change: 1.5,
  changePercent: 1.0, dayLow: 148, dayHigh: 152,
}

describe('AssetList', () => {
  it('shows a loading indicator', () => {
    render(<AssetList title="Most Active Stocks" assets={[]} assetType="stock" loading />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('shows an empty state when there are no assets', () => {
    render(<AssetList title="Most Active Stocks" assets={[]} assetType="stock" />)
    expect(screen.getByText('No results')).toBeInTheDocument()
  })

  it('renders each asset with its price and change', () => {
    render(<AssetList title="Most Active Stocks" assets={[AAPL]} assetType="stock" />)
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('$150.00')).toBeInTheDocument()
    expect(screen.getByText('▲ 1.00%')).toBeInTheDocument()
  })

  it('calls onSelect with the ticker when a row is clicked', async () => {
    const onSelect = vi.fn()
    const typer = userEvent.setup()
    render(<AssetList title="Most Active Stocks" assets={[AAPL]} assetType="stock" onSelect={onSelect} />)

    await typer.click(screen.getByRole('button', { name: /Apple Inc\./ }))
    expect(onSelect).toHaveBeenCalledWith('AAPL')
  })

  it('does not mark rows as buttons when there is no onSelect', () => {
    render(<AssetList title="Most Active Stocks" assets={[AAPL]} assetType="stock" />)
    expect(screen.queryByRole('button', { name: /Apple Inc\./ })).not.toBeInTheDocument()
  })
})
