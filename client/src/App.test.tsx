import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fetchCurrentUser, logout } from './api'

vi.mock('./api', () => ({
  fetchCurrentUser: vi.fn(),
  logout: vi.fn(),
  fetchBalance: vi.fn().mockResolvedValue(1000),
  login: vi.fn(),
  register: vi.fn(),
}))

vi.mock('./pages/Dashboard', () => ({ default: () => <div>Dashboard page</div> }))
vi.mock('./pages/TradeAssets', () => ({ default: () => <div>Trade assets page</div> }))
vi.mock('./pages/TransactionHistory', () => ({ default: () => <div>Transaction history page</div> }))

const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser)
const mockedLogout = vi.mocked(logout)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

beforeEach(() => {
  mockedFetchCurrentUser.mockReset()
  mockedLogout.mockReset()
})

describe('App', () => {
  it('shows the login form when there is no active session', async () => {
    mockedFetchCurrentUser.mockResolvedValue(null)
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('shows the app shell for a restored session', async () => {
    mockedFetchCurrentUser.mockResolvedValue(user)
    render(<App />)
    expect(await screen.findByText('Hello, Ada')).toBeInTheDocument()
    expect(screen.getByText('Dashboard page')).toBeInTheDocument()
  })

  it('returns to the login form after logging out', async () => {
    mockedFetchCurrentUser.mockResolvedValue(user)
    mockedLogout.mockResolvedValue(undefined)
    const typer = userEvent.setup()

    render(<App />)
    await screen.findByText('Hello, Ada')

    await typer.click(screen.getByRole('button', { name: /Log Out/ }))
    const confirmButtons = screen.getAllByRole('button', { name: 'Log Out' })
    await typer.click(confirmButtons[confirmButtons.length - 1])

    await waitFor(() => expect(mockedLogout).toHaveBeenCalledOnce())
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })
})
