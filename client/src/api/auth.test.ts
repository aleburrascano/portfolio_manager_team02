import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./client', async () => {
  const actual = await vi.importActual<typeof import('./client')>('./client')
  return {
    ApiError: actual.ApiError,
    apiFetch: vi.fn(),
    post: vi.fn((body: unknown) => ({ method: 'POST', body })),
  }
})

import { ApiError, apiFetch } from './client'
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
    await expect(fetchCurrentUser()).resolves.toEqual({ status: 'authenticated', user })
  })

  it('reports anonymous instead of throwing when there is no session', async () => {
    mockedApiFetch.mockRejectedValue(new ApiError('Authentication required', 401))
    await expect(fetchCurrentUser()).resolves.toEqual({ status: 'anonymous' })
  })

  it('reports unavailable when the server fails for any other reason', async () => {
    mockedApiFetch.mockRejectedValue(new ApiError('Internal server error', 500))
    await expect(fetchCurrentUser()).resolves.toEqual({
      status: 'unavailable',
      message: 'Internal server error',
    })
  })

  it('reports unavailable when the request never reaches the server', async () => {
    mockedApiFetch.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(fetchCurrentUser()).resolves.toEqual({
      status: 'unavailable',
      message: 'Failed to fetch',
    })
  })
})

describe('logout', () => {
  it('posts to the logout endpoint', async () => {
    mockedApiFetch.mockResolvedValue({ message: 'Logged out.' })
    await logout()
    expect(mockedApiFetch).toHaveBeenCalledWith('/auth/logout', 'Logout failed', expect.anything())
  })
})
