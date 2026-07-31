import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
  post: vi.fn((body: unknown) => ({ method: 'POST', body })),
}))

import { apiFetch } from './client'
import { fetchCurrentUser, login, logout, register } from './auth'

const mockedApiFetch = vi.mocked(apiFetch)

beforeEach(() => {
  mockedApiFetch.mockReset()
})

describe('login', () => {
  it('posts credentials and returns the user', async () => {
    const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }
    mockedApiFetch.mockResolvedValue(user)

    await expect(login('ada', 'password1')).resolves.toEqual(user)
    expect(mockedApiFetch).toHaveBeenCalledWith('/auth/login', 'Login failed', expect.anything())
  })
})

describe('register', () => {
  it('posts the new account fields', async () => {
    const user = { userId: 2, username: 'grace', firstName: 'Grace', lastName: 'Hopper' }
    mockedApiFetch.mockResolvedValue(user)

    await expect(register('grace', 'password1', 'Grace', 'Hopper')).resolves.toEqual(user)
    expect(mockedApiFetch).toHaveBeenCalledWith('/auth/register', 'Registration failed', expect.anything())
  })
})

describe('fetchCurrentUser', () => {
  it('returns the user when a session exists', async () => {
    const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }
    mockedApiFetch.mockResolvedValue(user)
    await expect(fetchCurrentUser()).resolves.toEqual(user)
  })

  it('returns null instead of throwing when there is no session', async () => {
    mockedApiFetch.mockRejectedValue(new Error('Authentication required'))
    await expect(fetchCurrentUser()).resolves.toBeNull()
  })
})

describe('logout', () => {
  it('posts to the logout endpoint', async () => {
    mockedApiFetch.mockResolvedValue({ message: 'Logged out.' })
    await logout()
    expect(mockedApiFetch).toHaveBeenCalledWith('/auth/logout', 'Logout failed', expect.anything())
  })
})
