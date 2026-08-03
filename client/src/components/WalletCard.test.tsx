import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WalletCard from './WalletCard'
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

/** A book worth $1,000 that is up $20 today. */
const TOTALS = {
  positions: 2,
  value: 1000,
  costBasis: 800,
  gainLoss: 200,
  gainLossPercent: 25,
  dayChange: 20,
  dayChangePercent: 2.04,
}

/** Open the dialog and get as far as the review step. */
async function reachReview(typer: ReturnType<typeof userEvent.setup>, action: string, amount: string) {
  await typer.click(screen.getByRole('button', { name: action }))
  await typer.type(screen.getByLabelText('Amount'), amount)
  await typer.click(screen.getByRole('button', { name: 'Continue' }))
}

beforeEach(() => {
  mockedSubmit.mockReset()
  mockedUseBalance.mockReturnValue({ balance: 500, refreshBalance: vi.fn().mockResolvedValue(undefined) })
})

describe('WalletCard', () => {
  it('shows the whole portfolio, not just the cash', () => {
    const { container } = render(<WalletCard user={user} totals={TOTALS} />)
    expect(container.querySelector('.wallet-balance')).toHaveTextContent('$1,500.00')
  })

  it('breaks the total into cash and invested', () => {
    const { container } = render(<WalletCard user={user} totals={TOTALS} />)
    const split = container.querySelector('.wallet-split')
    expect(split).toHaveTextContent('Cash $500.00')
    expect(split).toHaveTextContent('Invested $1,000.00')
  })

  it("shows today's move with a direction glyph, not colour alone", () => {
    render(<WalletCard user={user} totals={TOTALS} />)
    expect(screen.getByText(/▲ \$20.00 \(2.04%\)/)).toBeInTheDocument()
  })

  it('shows a down glyph on a losing day', () => {
    render(
      <WalletCard user={user} totals={{ ...TOTALS, dayChange: -35.5, dayChangePercent: -3.4 }} />,
    )
    expect(screen.getByText(/▼ \$35.50 \(3.40%\)/)).toBeInTheDocument()
  })

  it("omits today's move for an account holding nothing", () => {
    render(<WalletCard user={user} totals={{ ...TOTALS, positions: 0, value: 0 }} />)
    expect(screen.queryByText('today')).not.toBeInTheDocument()
  })

  it('announces that the value is loading rather than showing a placeholder figure', () => {
    mockedUseBalance.mockReturnValue({ balance: null, refreshBalance: vi.fn() })
    render(<WalletCard user={user} totals={TOTALS} />)
    expect(screen.getByText('Loading your portfolio value')).toBeInTheDocument()
  })

  it('waits for the book before claiming a total', () => {
    render(<WalletCard user={user} totals={null} />)
    expect(screen.getByText('Loading your portfolio value')).toBeInTheDocument()
  })

  it('opens the deposit dialog with the current balance shown', async () => {
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await typer.click(screen.getByRole('button', { name: 'Deposit' }))
    expect(screen.getByRole('heading', { name: 'Deposit funds' })).toBeInTheDocument()
    expect(screen.getByText('Current balance: $500.00')).toBeInTheDocument()
  })

  it('does not call the API until the deposit is confirmed', async () => {
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await reachReview(typer, 'Deposit', '100')

    expect(screen.getByRole('heading', { name: 'Review deposit' })).toBeInTheDocument()
    expect(screen.getByText('Balance after')).toBeInTheDocument()
    expect(screen.getByText('$600.00')).toBeInTheDocument()
    expect(mockedSubmit).not.toHaveBeenCalled()
  })

  it('submits the deposit once confirmed and reports the result', async () => {
    mockedSubmit.mockResolvedValue({ message: 'ok' })
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await reachReview(typer, 'Deposit', '100')
    await typer.click(screen.getByRole('button', { name: 'Deposit $100.00' }))

    expect(await screen.findByText('Deposit submitted successfully.')).toBeInTheDocument()
    expect(mockedSubmit).toHaveBeenCalledWith(1, 'deposit', 100, 'deposit:100')
  })

  it('leaves the success message on screen until the user dismisses it', async () => {
    mockedSubmit.mockResolvedValue({ message: 'ok' })
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await reachReview(typer, 'Deposit', '100')
    await typer.click(screen.getByRole('button', { name: 'Deposit $100.00' }))
    await screen.findByText('Deposit submitted successfully.')

    await typer.click(screen.getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('can step back from the review to change the amount', async () => {
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await reachReview(typer, 'Deposit', '100')
    await typer.click(screen.getByRole('button', { name: 'Back' }))

    expect(screen.getByLabelText('Amount')).toHaveValue(100)
    expect(mockedSubmit).not.toHaveBeenCalled()
  })

  it('blocks a withdrawal larger than the balance without calling the API', async () => {
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await typer.click(screen.getByRole('button', { name: 'Withdraw' }))
    await typer.type(screen.getByLabelText('Amount'), '600')
    await typer.click(screen.getByRole('button', { name: 'Continue' }))

    expect(
      await screen.findByText('Withdrawal amount exceeds current balance of $500.00.'),
    ).toBeInTheDocument()
    expect(mockedSubmit).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Amount')).toBeInTheDocument()
  })

  it('shows the server error message on a failed transaction', async () => {
    mockedSubmit.mockRejectedValue(new Error('Insufficient funds'))
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await reachReview(typer, 'Deposit', '100')
    await typer.click(screen.getByRole('button', { name: 'Deposit $100.00' }))

    expect(await screen.findByText('Insufficient funds')).toBeInTheDocument()
  })

  it('closes the dialog on cancel', async () => {
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await typer.click(screen.getByRole('button', { name: 'Deposit' }))
    await typer.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('closes the dialog on Escape', async () => {
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    await typer.click(screen.getByRole('button', { name: 'Deposit' }))
    await typer.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('returns focus to the button that opened the dialog', async () => {
    const typer = userEvent.setup()
    render(<WalletCard user={user} totals={TOTALS} />)

    const depositButton = screen.getByRole('button', { name: 'Deposit' })
    await typer.click(depositButton)
    await typer.keyboard('{Escape}')

    await waitFor(() => expect(depositButton).toHaveFocus())
  })
})

