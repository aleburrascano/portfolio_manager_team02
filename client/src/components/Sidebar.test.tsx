import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Sidebar from './Sidebar'

describe('Sidebar', () => {
  it('marks the current page as active', () => {
    render(<Sidebar page="trade-assets" onNavigate={vi.fn()} onLogout={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Trade Assets/ })).toHaveClass('active')
    expect(screen.getByRole('button', { name: /Dashboard/ })).not.toHaveClass('active')
  })

  it('navigates when a nav item is clicked', async () => {
    const onNavigate = vi.fn()
    const typer = userEvent.setup()
    render(<Sidebar page="dashboard" onNavigate={onNavigate} onLogout={vi.fn()} />)

    await typer.click(screen.getByRole('button', { name: /Transaction History/ }))
    expect(onNavigate).toHaveBeenCalledWith('transaction-history')
  })

  it('requires confirmation before logging out', async () => {
    const onLogout = vi.fn()
    const typer = userEvent.setup()
    render(<Sidebar page="dashboard" onNavigate={vi.fn()} onLogout={onLogout} />)

    await typer.click(screen.getByRole('button', { name: /Log Out/ }))
    expect(onLogout).not.toHaveBeenCalled()

    const dialogLogoutButtons = screen.getAllByRole('button', { name: 'Log Out' })
    await typer.click(dialogLogoutButtons[dialogLogoutButtons.length - 1])
    expect(onLogout).toHaveBeenCalledOnce()
  })

  it('dismisses the confirmation without logging out on cancel', async () => {
    const onLogout = vi.fn()
    const typer = userEvent.setup()
    render(<Sidebar page="dashboard" onNavigate={vi.fn()} onLogout={onLogout} />)

    await typer.click(screen.getByRole('button', { name: /Log Out/ }))
    await typer.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onLogout).not.toHaveBeenCalled()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })
})
