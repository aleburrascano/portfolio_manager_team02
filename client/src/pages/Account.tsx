import { useState } from 'react'
import { updateUser, type User } from '../api'
import { validateName, validatePassword, validateUsername } from '../validation'
import './Account.css'

function Account({ user, onUpdate }: { user: User; onUpdate: (user: User) => void }) {
  const [username, setUsername] = useState(user.username)
  const [firstName, setFirstName] = useState(user.firstName)
  const [lastName, setLastName] = useState(user.lastName)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function validate(): string | null {
    const usernameError = validateUsername(username)
    if (usernameError) return usernameError
    const firstNameError = validateName(firstName, 'First name')
    if (firstNameError) return firstNameError
    const lastNameError = validateName(lastName, 'Last name')
    if (lastNameError) return lastNameError

    const changingPassword = currentPassword || newPassword || confirmPassword
    if (changingPassword) {
      if (!currentPassword) return 'Enter your current password.'
      const passwordError = validatePassword(newPassword)
      if (passwordError) return passwordError
      if (newPassword !== confirmPassword) return 'New passwords do not match.'
    }
    return null
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const validationError = validate()
    if (validationError) {
      setStatusMessage(validationError)
      return
    }

    setIsSubmitting(true)
    setStatusMessage('')

    try {
      const updated = await updateUser(user.userId, {
        username: username.trim(),
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        ...(newPassword && { currentPassword, newPassword }),
      })
      onUpdate(updated)
      setStatusMessage('Account updated successfully.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Failed to update account.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section id="account-content">
      <div className="account-card">
        <h2>Account</h2>
        <form onSubmit={handleSubmit}>
          <label className="account-label" htmlFor="account-username">
            Username
          </label>
          <input
            id="account-username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />

          <label className="account-label" htmlFor="account-first-name">
            First Name
          </label>
          <input
            id="account-first-name"
            type="text"
            autoComplete="given-name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
          />

          <label className="account-label" htmlFor="account-last-name">
            Last Name
          </label>
          <input
            id="account-last-name"
            type="text"
            autoComplete="family-name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
          />

          <h3 className="account-subheading">Change Password</h3>
          <p className="account-hint">Leave these blank to keep your current password.</p>

          <label className="account-label" htmlFor="account-current-password">
            Current Password
          </label>
          <input
            id="account-current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />

          <label className="account-label" htmlFor="account-new-password">
            New Password
          </label>
          <input
            id="account-new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />

          <label className="account-label" htmlFor="account-confirm-password">
            Confirm New Password
          </label>
          <input
            id="account-confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />

          <button type="submit" className="submit-btn" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : 'Save Changes'}
          </button>
        </form>

        {statusMessage && (
          <p className={`account-status ${statusMessage.includes('success') ? 'success' : 'error'}`}>
            {statusMessage}
          </p>
        )}
      </div>
    </section>
  )
}

export default Account
