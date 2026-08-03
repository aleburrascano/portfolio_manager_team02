import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Login from './Login'
import { login, register } from '../api'

vi.mock('../api', () => ({
  login: vi.fn(),
  register: vi.fn(),
}))

const mockedLogin = vi.mocked(login)
const mockedRegister = vi.mocked(register)

beforeEach(() => {
  mockedLogin.mockReset()
  mockedRegister.mockReset()
})

describe('Login', () => {
  it('logs in with the entered credentials', async () => {
    const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }
    mockedLogin.mockResolvedValue(user)
    const onLogin = vi.fn()
    const typer = userEvent.setup()

    render(<Login onLogin={onLogin} />)
    await typer.type(screen.getByPlaceholderText('Username'), 'ada')
    await typer.type(screen.getByPlaceholderText('Password'), 'password1')
    await typer.click(screen.getByRole('button', { name: 'Log In' }))

    await waitFor(() => expect(onLogin).toHaveBeenCalledWith(user))
    expect(mockedLogin).toHaveBeenCalledWith('ada', 'password1')
  })

  it('shows the server error message on failed login', async () => {
    mockedLogin.mockRejectedValue(new Error('Incorrect username or password'))
    const typer = userEvent.setup()

    render(<Login onLogin={vi.fn()} />)
    await typer.type(screen.getByPlaceholderText('Username'), 'ada')
    await typer.type(screen.getByPlaceholderText('Password'), 'password1')
    await typer.click(screen.getByRole('button', { name: 'Log In' }))

    expect(await screen.findByText('Incorrect username or password')).toBeInTheDocument()
  })

  it('blocks submission client-side without calling the API', async () => {
    const typer = userEvent.setup()
    render(<Login onLogin={vi.fn()} />)
    await typer.type(screen.getByPlaceholderText('Username'), ' ')
    await typer.type(screen.getByPlaceholderText('Password'), ' ')
    await typer.click(screen.getByRole('button', { name: 'Log In' }))

    expect(await screen.findByText('Username is required.')).toBeInTheDocument()
    expect(mockedLogin).not.toHaveBeenCalled()
  })

  it('switches to registration mode and validates its extra fields', async () => {
    const typer = userEvent.setup()
    render(<Login onLogin={vi.fn()} />)

    await typer.click(screen.getByRole('button', { name: 'Need an account? Sign up' }))
    expect(screen.getByRole('heading', { name: 'Create an account' })).toBeInTheDocument()

    await typer.type(screen.getByPlaceholderText('Username'), 'ada')
    await typer.type(screen.getByPlaceholderText('Password'), 'short')
    await typer.type(screen.getByPlaceholderText('First Name'), 'Ada')
    await typer.type(screen.getByPlaceholderText('Last Name'), 'Lovelace')
    await typer.click(screen.getByRole('button', { name: 'Sign Up' }))

    expect(await screen.findByText('Password must be at least 8 characters.')).toBeInTheDocument()
    expect(mockedRegister).not.toHaveBeenCalled()
  })

  it('registers with all four fields', async () => {
    const user = { userId: 2, username: 'grace', firstName: 'Grace', lastName: 'Hopper' }
    mockedRegister.mockResolvedValue(user)
    const onLogin = vi.fn()
    const typer = userEvent.setup()

    render(<Login onLogin={onLogin} />)
    await typer.click(screen.getByRole('button', { name: 'Need an account? Sign up' }))
    await typer.type(screen.getByPlaceholderText('Username'), 'grace')
    await typer.type(screen.getByPlaceholderText('Password'), 'password1')
    await typer.type(screen.getByPlaceholderText('First Name'), 'Grace')
    await typer.type(screen.getByPlaceholderText('Last Name'), 'Hopper')
    await typer.click(screen.getByRole('button', { name: 'Sign Up' }))

    await waitFor(() => expect(onLogin).toHaveBeenCalledWith(user))
    expect(mockedRegister).toHaveBeenCalledWith('grace', 'password1', 'Grace', 'Hopper')
  })
})
