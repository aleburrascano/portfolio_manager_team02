import { useState } from 'react'
import { submitCashTransaction, type HoldingsTotals, type TransactionType, type User } from '../api'
import { useBalance } from '../balance-context'
import { useIdempotencyKey } from '../idempotency'
import { validateAmountInput } from '../validation'
import { formatCurrency, formatNumber } from '../format'
import Icon from './Icon'
import Modal from './Modal'
import './WalletCard.css'

/** Enter an amount, check it over, then commit. Money never moves on one click. */
type Step = 'amount' | 'review' | 'done'

/** Direction is carried by a glyph as well as colour, never colour alone. */
const tone = (value: number) => (value > 0 ? 'positive' : value < 0 ? 'negative' : 'flat')
const glyph = (value: number) => (value > 0 ? '▲' : value < 0 ? '▼' : '—')

/**
 * The head of the statement, and the one place the app answers "what am I
 * worth". Everything below it reports change or composition, so no two
 * panels can show a different level and appear to disagree.
 */
function WalletCard({ user, totals }: { user: User; totals: HoldingsTotals | null }) {
  const { balance, refreshBalance } = useBalance()
  const idempotency = useIdempotencyKey()
  const [isPopupOpen, setIsPopupOpen] = useState(false)
  const [step, setStep] = useState<Step>('amount')
  const [transactionType, setTransactionType] = useState<TransactionType>('deposit')
  const [amount, setAmount] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isDeposit = transactionType === 'deposit'
  const actionNoun = isDeposit ? 'Deposit' : 'Withdrawal'
  const parsedAmount = Number(amount)
  const balanceAfter =
    balance !== null && Number.isFinite(parsedAmount)
      ? isDeposit
        ? balance + parsedAmount
        : balance - parsedAmount
      : null

  function openPopup(type: TransactionType) {
    setTransactionType(type)
    setAmount('')
    setErrorMessage('')
    setStep('amount')
    setIsPopupOpen(true)
  }

  function handleReview(e: React.FormEvent) {
    e.preventDefault()

    const amountError = validateAmountInput(amount)
    if (amountError) {
      setErrorMessage(amountError)
      return
    }

    if (!isDeposit && balance !== null && parsedAmount > balance) {
      setErrorMessage(`Withdrawal amount exceeds current balance of ${formatCurrency(balance)}.`)
      return
    }

    setErrorMessage('')
    setStep('review')
  }

  async function handleConfirm() {
    setIsSubmitting(true)
    setErrorMessage('')

    try {
      await submitCashTransaction(
        user.userId,
        transactionType,
        parsedAmount,
        idempotency.keyFor(`${transactionType}:${parsedAmount}`),
      )
      idempotency.reset()
      await refreshBalance()
      setStep('done')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Transaction failed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      {/* The top rule of a statement: label, figure, and the actions that
          change it. No card, no fill - the typography carries the weight. */}
      <section className="wallet-statement" aria-labelledby="wallet-balance-label">
        <div className="wallet-heading">
          <h2 id="wallet-balance-label" className="wallet-label">
            Portfolio value
          </h2>
          <div className="wallet-actions">
            <button type="button" className="wallet-btn" onClick={() => openPopup('deposit')}>
              <Icon name="deposit" />
              Deposit
            </button>
            <button type="button" className="wallet-btn" onClick={() => openPopup('withdraw')}>
              <Icon name="withdraw" />
              Withdraw
            </button>
          </div>
        </div>

        {balance !== null && totals ? (
          <>
            <p className="figure wallet-balance">{formatCurrency(balance + totals.value)}</p>

            {totals.positions > 0 && (
              <p className={`wallet-day ${tone(totals.dayChange)}`}>
                <span className="figure">
                  {glyph(totals.dayChange)} {formatCurrency(Math.abs(totals.dayChange))} (
                  {formatNumber(Math.abs(totals.dayChangePercent), 2)}%)
                </span>
                <span className="wallet-day-label">today</span>
              </p>
            )}

            <p className="wallet-split">
              <span>
                Cash <span className="figure">{formatCurrency(balance)}</span>
              </span>
              <span aria-hidden="true">·</span>
              <span>
                Invested <span className="figure">{formatCurrency(totals.value)}</span>
              </span>
            </p>
          </>
        ) : (
          <p className="wallet-balance">
            <span className="skeleton wallet-balance-skeleton" />
            <span className="visually-hidden">Loading your portfolio value</span>
          </p>
        )}
      </section>

      {isPopupOpen && (
        <Modal
          title={
            step === 'done'
              ? `${actionNoun} complete`
              : step === 'review'
                ? `Review ${actionNoun.toLowerCase()}`
                : isDeposit
                  ? 'Deposit funds'
                  : 'Withdraw funds'
          }
          focusKey={step}
          onClose={() => setIsPopupOpen(false)}
        >
          {step === 'amount' && (
            <form onSubmit={handleReview}>
              <p className="modal-balance">
                Current balance: {balance !== null ? formatCurrency(balance) : '—'}
              </p>

              <label className="modal-label" htmlFor="transaction-amount">
                Amount
              </label>
              {/* No `max`: the browser would block submission with its own
                  bubble ("Value must be less than or equal to 50") and our
                  message - which names the actual balance - would never
                  fire. One error vocabulary beats two. */}
              <input
                id="transaction-amount"
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="0.00"
                required
                data-autofocus
              />

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={() => setIsPopupOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="submit-btn">
                  Continue
                </button>
              </div>
            </form>
          )}

          {step === 'review' && (
            <>
              <dl className="confirm-summary">
                <dt>{isDeposit ? 'Depositing' : 'Withdrawing'}</dt>
                <dd className="figure">{formatCurrency(parsedAmount)}</dd>
                <dt>Current balance</dt>
                <dd className="figure">{balance !== null ? formatCurrency(balance) : '—'}</dd>
                <dt className="confirm-summary-total">Balance after</dt>
                <dd className="figure confirm-summary-total">
                  {balanceAfter !== null ? formatCurrency(balanceAfter) : '—'}
                </dd>
              </dl>

              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setStep('amount')}
                  disabled={isSubmitting}
                >
                  Back
                </button>
                <button
                  type="button"
                  className="submit-btn"
                  onClick={handleConfirm}
                  disabled={isSubmitting}
                  data-autofocus
                >
                  {isSubmitting
                    ? 'Submitting…'
                    : `${isDeposit ? 'Deposit' : 'Withdraw'} ${formatCurrency(parsedAmount)}`}
                </button>
              </div>
            </>
          )}

          {step === 'done' && (
            <>
              <dl className="confirm-summary">
                <dt>{isDeposit ? 'Deposited' : 'Withdrawn'}</dt>
                <dd className="figure">{formatCurrency(parsedAmount)}</dd>
                <dt className="confirm-summary-total">New balance</dt>
                <dd className="figure confirm-summary-total">
                  {balance !== null ? formatCurrency(balance) : '—'}
                </dd>
              </dl>

              <p className="modal-status success" role="status">
                {actionNoun} submitted successfully.
              </p>

              <div className="modal-actions">
                <button
                  type="button"
                  className="submit-btn"
                  onClick={() => setIsPopupOpen(false)}
                  data-autofocus
                >
                  Done
                </button>
              </div>
            </>
          )}

          {/* One live region for the dialog, so a screen reader hears the
              validation or server error without hunting for it. */}
          <p className="modal-status error" role="alert">
            {errorMessage}
          </p>
        </Modal>
      )}
    </>
  )
}

export default WalletCard
