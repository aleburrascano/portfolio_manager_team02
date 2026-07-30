import { useState } from 'react'
import { login, type User } from '../api'
import { validateName } from '../validation'
import './Login.css'

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const firstNameError = validateName(firstName, 'First name')
    const lastNameError = validateName(lastName, 'Last name')
    if (firstNameError || lastNameError) {
      setError(firstNameError || lastNameError || '')
      return
    }

    setError('')
    try {
      onLogin(await login(firstName.trim(), lastName.trim()))
    } catch {
      setError('Login failed. Please try again.')
    }
  }

  return (
    <div className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Welcome</h1>
        <input
          type="text"
          placeholder="First Name"
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          required
        />
        <input
          type="text"
          placeholder="Last Name"
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          required
        />
        {error && <p className="login-error">{error}</p>}
        <button type="submit">Continue</button>
      </form>
    </div>
  )
}

export default Login
