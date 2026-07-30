// Shared HTTP plumbing for the API modules in this folder. Nothing here
// knows about any particular resource.

const API_BASE = '/api/v1'

type ApiErrorBody = { error?: { message?: string } | string }

function errorMessage(data: ApiErrorBody, fallback: string): string {
  if (typeof data.error === 'string') return data.error
  return data.error?.message || fallback
}

/**
 * Call the API and unwrap its JSON, throwing the server's own error
 * message on failure.
 *
 * The session lives in an httpOnly cookie the server sets on login, so
 * every call sends credentials - there is no token for the client to hold.
 */
export async function apiFetch<T>(path: string, fallbackError: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...init })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(errorMessage(data, fallbackError))
  return data as T
}

/**
 * Build the RequestInit for a JSON POST.
 *
 * An idempotencyKey makes the request safe to retry: the server does the
 * work for whichever request claims the key first and replays that same
 * response to any repeat.
 */
export function post(body?: unknown, idempotencyKey?: string): RequestInit {
  return {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(idempotencyKey && { 'Idempotency-Key': idempotencyKey }),
    },
    body: JSON.stringify(body ?? {}),
  }
}
