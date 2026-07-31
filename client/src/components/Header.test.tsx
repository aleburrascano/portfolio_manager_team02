import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Header from './Header'

const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

function renderHeader(overrides: Partial<Parameters<typeof Header>[0]> = {}) {
  const props = {
    user,
    onOpenAccount: vi.fn(),
    onLogout: vi.fn(),
    ...overrides,
  }
  render(<Header {...props} />)
  return props
}

describe('Header', () => {
  it('shows the wordmark', () => {
    renderHeader()
    expect(
      screen.getByText((_, element) => element?.classList.contains('wordmark-text') === true),
    ).toHaveTextContent('TreeTop Trading')
  })

  it('shows the signed-in user in the account control', () => {
    renderHeader()
    expect(screen.getByRole('button', { name: /Ada Lovelace/ })).toBeInTheDocument()
    expect(screen.getByText('AL')).toBeInTheDocument()
  })

  // The corner used to be a greeting and an avatar that looked interactive
  // and did nothing; it is now the account menu people reach for there.
  it('opens a menu with the account actions', async () => {
    const typer = userEvent.setup()
    renderHeader()

    const trigger = screen.getByRole('button', { name: /Ada Lovelace/ })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await typer.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('menuitem', { name: 'Account settings' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Log Out' })).toBeInTheDocument()
    expect(screen.getByText('ada')).toBeInTheDocument()
  })

  it('navigates to the account page from the menu', async () => {
    const typer = userEvent.setup()
    const props = renderHeader()

    await typer.click(screen.getByRole('button', { name: /Ada Lovelace/ }))
    await typer.click(screen.getByRole('menuitem', { name: 'Account settings' }))

    expect(props.onOpenAccount).toHaveBeenCalledOnce()
  })

  it('confirms before logging out', async () => {
    const typer = userEvent.setup()
    const props = renderHeader()

    await typer.click(screen.getByRole('button', { name: /Ada Lovelace/ }))
    await typer.click(screen.getByRole('menuitem', { name: 'Log Out' }))
    expect(props.onLogout).not.toHaveBeenCalled()

    await typer.click(
      screen.getByRole('alertdialog').querySelector('.danger-btn') as HTMLElement,
    )
    expect(props.onLogout).toHaveBeenCalledOnce()
  })

  it('closes the menu on Escape', async () => {
    const typer = userEvent.setup()
    renderHeader()

    await typer.click(screen.getByRole('button', { name: /Ada Lovelace/ }))
    await typer.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument())
  })
})
