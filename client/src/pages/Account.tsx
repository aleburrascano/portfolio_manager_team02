import { useState } from 'react'
import { updateUser, type User } from '../api'
import { validateName, validatePassword, validateUsername } from '../validation'
import './Account.css'

type Status = { kind: 'success' | 'error'; text: string }

function Account({ user, onUpdate }: { user: User; onUpdate: (user: User) => void }) {
  const [username, setUsername] = useState(user.username)
  const [firstName, setFirstName] = useState(user.firstName)
  const [lastName, setLastName] = useState(user.lastName)
  const [changingPassword, setChangingPassword] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [status, setStatus] = useState<Status | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function validate(): string | null {
    const usernameError = validateUsername(username)
    if (usernameError) return usernameError
    const firstNameError = validateName(firstName, 'First name')
    if (firstNameError) return firstNameError
    const lastNameError = validateName(lastName, 'Last name')
    if (lastNameError) return lastNameError

    if (changingPassword) {
      if (!currentPassword) return 'Enter your current password.'
      const passwordError = validatePassword(newPassword)
      if (passwordError) return passwordError
      if (newPassword !== confirmPassword) return 'New passwords do not match.'
    }
    return null
  }

  function cancelPasswordChange() {
    setChangingPassword(false)
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const validationError = validate()
    if (validationError) {
      setStatus({ kind: 'error', text: validationError })
      return
    }

    setIsSubmitting(true)
    setStatus(null)

    try {
      const updated = await updateUser(user.userId, {
        username: username.trim(),
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        ...(changingPassword && newPassword && { currentPassword, newPassword }),
      })
      onUpdate(updated)
      setStatus({
        kind: 'success',
        text: changingPassword ? 'Account and password updated.' : 'Account updated.',
      })
      cancelPasswordChange()
    } catch (error) {
      setStatus({
        kind: 'error',
        text: error instanceof Error ? error.message : 'Failed to update account.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section id="account-content">
      <div className="account-card">
        <h1 className="account-title">Account</h1>

        <form onSubmit={handleSubmit}>
          <fieldset className="account-group">
            <legend className="account-legend">Your details</legend>

            <div className="account-field">
              <label htmlFor="account-username">Username</label>
              <input
                id="account-username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            <div className="account-row">
              <div className="account-field">
                <label htmlFor="account-first-name">First name</label>
                <input
                  id="account-first-name"
                  type="text"
                  autoComplete="given-name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                />
              </div>

              <div className="account-field">
                <label htmlFor="account-last-name">Last name</label>
                <input
                  id="account-last-name"
                  type="text"
                  autoComplete="family-name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="account-group">
            <legend className="account-legend">Password</legend>

            {changingPassword ? (
              <>
                <div className="account-field">
                  <label htmlFor="account-current-password">Current password</label>
                  <input
                    id="account-current-password"
                    type="password"
                    autoComplete="current-password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    autoFocus
                  />
                </div>

                <div className="account-field">
                  <label htmlFor="account-new-password">New password</label>
                  <input
                    id="account-new-password"
                    type="password"
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                </div>

                <div className="account-field">
                  <label htmlFor="account-confirm-password">Confirm new password</label>
                  <input
                    id="account-confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </div>

                <button type="button" className="account-link-btn" onClick={cancelPasswordChange}>
                  Keep my current password
                </button>
              </>
            ) : (
              <button
                type="button"
                className="secondary-btn"
                onClick={() => setChangingPassword(true)}
              >
                Change password
              </button>
            )}
          </fieldset>

          <button type="submit" className="submit-btn" disabled={isSubmitting}>
            {isSubmitting ? 'Saving…' : 'Save changes'}
          </button>
        </form>

        <p className={`account-status ${status?.kind ?? ''}`} role="status">
          {status?.text}
        </p>
      </div>
    </section>
  )
}

export default Account
