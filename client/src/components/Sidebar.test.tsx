import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Sidebar from './Sidebar'

describe('Sidebar', () => {
  it('marks the current page as active', () => {
    render(<Sidebar page="trade-assets" onNavigate={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Trade/ })).toHaveClass('active')
    expect(screen.getByRole('button', { name: /Dashboard/ })).not.toHaveClass('active')
  })

  it('tells assistive tech which page is current', () => {
    render(<Sidebar page="trade-assets" onNavigate={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Trade/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: /Dashboard/ })).not.toHaveAttribute('aria-current')
  })

  it('navigates when a nav item is clicked', async () => {
    const onNavigate = vi.fn()
    const typer = userEvent.setup()
    render(<Sidebar page="dashboard" onNavigate={onNavigate} />)

    await typer.click(screen.getByRole('button', { name: /History/ }))
    expect(onNavigate).toHaveBeenCalledWith('transaction-history')
  })

  // Account settings and logging out live in the header's account menu, so
  // the rail carries only the three places you navigate between.
  it('carries only the navigation destinations', () => {
    render(<Sidebar page="dashboard" onNavigate={vi.fn()} />)

    expect(screen.getAllByRole('button')).toHaveLength(3)
    expect(screen.queryByRole('button', { name: /Log Out/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Account/ })).not.toBeInTheDocument()
  })
})
