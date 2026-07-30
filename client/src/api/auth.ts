import { apiFetch, post } from './client'

export type User = {
  userId: number
  username: string
  firstName: string
  lastName: string
}

export async function login(username: string, password: string): Promise<User> {
  return apiFetch('/auth/login', 'Login failed', post({ username, password }))
}

export async function register(
  username: string,
  password: string,
  firstName: string,
  lastName: string,
): Promise<User> {
  return apiFetch('/auth/register', 'Registration failed', post({ username, password, firstName, lastName }))
}

/** The user owning the current session, or null if there isn't one. */
export async function fetchCurrentUser(): Promise<User | null> {
  try {
    return await apiFetch<User>('/auth/me', 'Failed to fetch session')
  } catch {
    return null
  }
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', 'Logout failed', post())
}
