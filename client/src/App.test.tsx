import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fetchCurrentUser, logout } from './api'

vi.mock('./api', () => ({
  fetchCurrentUser: vi.fn(),
  logout: vi.fn(),
  fetchBalance: vi.fn().mockResolvedValue(1000),
  fetchAssetTypes: vi.fn().mockResolvedValue([]),
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
    mockedFetchCurrentUser.mockResolvedValue({ status: 'anonymous' })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  // A server that couldn't answer must not be reported as "you're logged
  // out": the user still has a session and retrying is the right advice.
  it('offers a retry rather than the login form when the session check fails', async () => {
    mockedFetchCurrentUser.mockResolvedValue({ status: 'unavailable', message: 'Server exploded' })
    render(<App />)

    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByText('Server exploded')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Welcome back' })).not.toBeInTheDocument()
  })

  it('re-checks the session when the retry is clicked', async () => {
    mockedFetchCurrentUser.mockResolvedValueOnce({ status: 'unavailable', message: 'Server exploded' })
    mockedFetchCurrentUser.mockResolvedValueOnce({ status: 'authenticated', user })
    const typer = userEvent.setup()

    render(<App />)
    await typer.click(await screen.findByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('button', { name: /Ada Lovelace/ })).toBeInTheDocument()
  })

  it('shows the app shell for a restored session', async () => {
    mockedFetchCurrentUser.mockResolvedValue({ status: 'authenticated', user })
    render(<App />)
    expect(await screen.findByRole('button', { name: /Ada Lovelace/ })).toBeInTheDocument()
    expect(screen.getByText('Dashboard page')).toBeInTheDocument()
  })

  it('returns to the login form after logging out', async () => {
    mockedFetchCurrentUser.mockResolvedValue({ status: 'authenticated', user })
    mockedLogout.mockResolvedValue(undefined)
    const typer = userEvent.setup()

    render(<App />)
    await screen.findByRole('button', { name: /Ada Lovelace/ })

    // Account menu -> Log Out -> confirm.
    await typer.click(screen.getByRole('button', { name: /Ada Lovelace/ }))
    await typer.click(screen.getByRole('menuitem', { name: 'Log Out' }))
    await typer.click(screen.getByRole('alertdialog').querySelector('.danger-btn') as HTMLElement)

    await waitFor(() => expect(mockedLogout).toHaveBeenCalledOnce())
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })
})
