import { useState } from 'react'
import { login, register, type User } from '../api'
import { validateName, validatePassword, validateUsername } from '../validation'
import treetopIcon from '../assets/treetop-icon.svg'
import './Login.css'

type Mode = 'login' | 'register'

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState('')

  function switchMode(next: Mode) {
    setMode(next)
    setError('')
    setPassword('')
  }

  function validate(): string | null {
    const usernameError = validateUsername(username)
    if (usernameError) return usernameError
    if (mode === 'login') return null

    return (
      validatePassword(password) ||
      validateName(firstName, 'First name') ||
      validateName(lastName, 'Last name')
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setError('')
    try {
      onLogin(
        mode === 'login'
          ? await login(username.trim(), password)
          : await register(username.trim(), password, firstName.trim(), lastName.trim()),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    }
  }

  return (
    <div className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <div className="login-brand">
          <img src={treetopIcon} alt="" width="32" height="32" />
          <span>TreeTop Trading</span>
        </div>
        <h1>{mode === 'login' ? 'Welcome back' : 'Create an account'}</h1>
        <input
          type="text"
          placeholder="Username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {mode === 'register' && (
          <>
            <input
              type="text"
              placeholder="First Name"
              autoComplete="given-name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
            />
            <input
              type="text"
              placeholder="Last Name"
              autoComplete="family-name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
            />
          </>
        )}
        <p className="login-error" role="alert">
          {error}
        </p>
        <button type="submit">{mode === 'login' ? 'Log In' : 'Sign Up'}</button>
        <button
          type="button"
          className="login-switch"
          onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
        >
          {mode === 'login' ? 'Need an account? Sign up' : 'Already have an account? Log in'}
        </button>
      </form>
    </div>
  )
}

export default Login
