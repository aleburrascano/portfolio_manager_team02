import { ApiError, apiFetch, patch, post } from './client'

export type User = {
  userId: number
  username: string
  firstName: string
  lastName: string
}

export type UpdateUserInput = {
  username?: string
  firstName?: string
  lastName?: string
  currentPassword?: string
  newPassword?: string
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

export type SessionResult =
  | { status: 'authenticated'; user: User }
  | { status: 'anonymous' }
  | { status: 'unavailable'; message: string }

/**
 * Who owns the current session, or why we couldn't find out.
 *
 * The three answers are deliberately distinct. Collapsing them into
 * `User | null` makes a 500 look exactly like a signed-out visitor, which
 * silently drops a logged-in user at the login screen with no explanation
 * and no hint that retrying might work.
 */
export async function fetchCurrentUser(): Promise<SessionResult> {
  try {
    return { status: 'authenticated', user: await apiFetch<User>('/auth/me', 'Failed to fetch session') }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return { status: 'anonymous' }
    return {
      status: 'unavailable',
      message: error instanceof Error ? error.message : 'Could not reach the server.',
    }
  }
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', 'Logout failed', post())
}

export async function updateUser(userId: number, input: UpdateUserInput): Promise<User> {
  return apiFetch(`/users/${userId}`, 'Failed to update account', patch(input))
}
