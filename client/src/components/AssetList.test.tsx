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
  it('shows row-shaped placeholders while loading, so nothing shifts on arrival', () => {
    const { container } = render(
      <AssetList title="Most Active Stocks" assets={[]} assetType="stock" loading />,
    )
    expect(container.querySelectorAll('.asset-row-skeleton')).toHaveLength(6)
  })

  it('shows the caller-supplied empty state when there are no assets', () => {
    render(
      <AssetList
        title="Search results"
        assets={[]}
        assetType="stock"
        emptyMessage="No stocks match &quot;zzz&quot;. Check the spelling."
      />,
    )
    expect(screen.getByText(/No stocks match/)).toBeInTheDocument()
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

  // Rows are the only route into the buy/sell ticket, so a keyboard user
  // who cannot activate them cannot trade at all.
  it('opens a row from the keyboard with Enter', async () => {
    const onSelect = vi.fn()
    const typer = userEvent.setup()
    render(<AssetList title="Most Active Stocks" assets={[AAPL]} assetType="stock" onSelect={onSelect} />)

    await typer.tab()
    expect(screen.getByRole('button', { name: /Apple Inc\./ })).toHaveFocus()

    await typer.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledWith('AAPL')
  })

  it('opens a row from the keyboard with Space', async () => {
    const onSelect = vi.fn()
    const typer = userEvent.setup()
    render(<AssetList title="Most Active Stocks" assets={[AAPL]} assetType="stock" onSelect={onSelect} />)

    await typer.tab()
    await typer.keyboard(' ')
    expect(onSelect).toHaveBeenCalledWith('AAPL')
  })

  it('keeps the full asset name reachable when the visible text is truncated', () => {
    render(<AssetList title="Most Active Stocks" assets={[AAPL]} assetType="stock" />)
    expect(screen.getByText('Apple Inc.')).toHaveAttribute('title', 'Apple Inc.')
  })

  it('does not mark rows as buttons when there is no onSelect', () => {
    render(<AssetList title="Most Active Stocks" assets={[AAPL]} assetType="stock" />)
    expect(screen.queryByRole('button', { name: /Apple Inc\./ })).not.toBeInTheDocument()
  })
})
