import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Header from './Header'
import { submitCashTransaction } from '../api'
import { useBalance } from '../balance-context'

vi.mock('../api', () => ({
  submitCashTransaction: vi.fn(),
}))

vi.mock('../balance-context', () => ({
  useBalance: vi.fn(),
}))

vi.mock('../idempotency', () => ({
  useIdempotencyKey: () => ({ keyFor: (intent: string) => intent, reset: vi.fn() }),
}))

const mockedSubmit = vi.mocked(submitCashTransaction)
const mockedUseBalance = vi.mocked(useBalance)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

beforeEach(() => {
  mockedSubmit.mockReset()
  mockedUseBalance.mockReturnValue({ balance: 500, refreshBalance: vi.fn().mockResolvedValue(undefined) })
})

describe('Header', () => {
  it('shows the greeting and formatted balance', () => {
    render(<Header user={user} />)
    expect(screen.getByText('Hello, Ada')).toBeInTheDocument()
    expect(screen.getByText('$500.00')).toBeInTheDocument()
  })

  it('shows a placeholder while the balance is loading', () => {
    mockedUseBalance.mockReturnValue({ balance: null, refreshBalance: vi.fn() })
    render(<Header user={user} />)
    expect(screen.getByText('...')).toBeInTheDocument()
  })

  it('opens the deposit modal with the current balance shown', async () => {
    const typer = userEvent.setup()
    render(<Header user={user} />)

    await typer.click(screen.getByRole('button', { name: 'Deposit' }))
    expect(screen.getByRole('heading', { name: 'Deposit Funds' })).toBeInTheDocument()
    expect(screen.getByText('Current Balance: $500.00')).toBeInTheDocument()
  })

  it('submits a deposit and shows a success message', async () => {
    mockedSubmit.mockResolvedValue({ message: 'ok' })
    const typer = userEvent.setup()
    render(<Header user={user} />)

    await typer.click(screen.getByRole('button', { name: 'Deposit' }))
    await typer.type(screen.getByLabelText('Amount'), '100')
    await typer.click(screen.getByRole('button', { name: 'Submit Transaction' }))

    expect(await screen.findByText('Deposit submitted successfully.')).toBeInTheDocument()
    expect(mockedSubmit).toHaveBeenCalledWith(1, 'deposit', 100, 'deposit:100')
  })

  it('blocks a withdrawal larger than the balance without calling the API', async () => {
    const typer = userEvent.setup()
    render(<Header user={user} />)

    await typer.click(screen.getByRole('button', { name: 'Withdraw' }))
    await typer.type(screen.getByLabelText('Amount'), '600')
    // The amount input's native `max` (set to the balance) would otherwise
    // block a real click submission before React's own check ever runs.
    fireEvent.submit(screen.getByRole('button', { name: 'Submit Transaction' }).closest('form')!)

    expect(await screen.findByText('Withdrawal amount exceeds current balance of $500.00.')).toBeInTheDocument()
    expect(mockedSubmit).not.toHaveBeenCalled()
  })

  it('shows the server error message on a failed transaction', async () => {
    mockedSubmit.mockRejectedValue(new Error('Insufficient funds'))
    const typer = userEvent.setup()
    render(<Header user={user} />)

    await typer.click(screen.getByRole('button', { name: 'Deposit' }))
    await typer.type(screen.getByLabelText('Amount'), '100')
    await typer.click(screen.getByRole('button', { name: 'Submit Transaction' }))

    expect(await screen.findByText('Insufficient funds')).toBeInTheDocument()
  })

  it('closes the modal on cancel', async () => {
    const typer = userEvent.setup()
    render(<Header user={user} />)

    await typer.click(screen.getByRole('button', { name: 'Deposit' }))
    await typer.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
