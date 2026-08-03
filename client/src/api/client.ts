import { API_ORIGIN } from '../config'

export const API_BASE = `${API_ORIGIN}/api/v1`

type ApiErrorBody = { error?: { message?: string } | string }

function errorMessage(data: ApiErrorBody, fallback: string): string {
  if (typeof data.error === 'string') return data.error
  return data.error?.message || fallback
}

/**
 * A failure the server answered, carrying the status it answered with.
 *
 * Callers that only want the message keep treating this as an Error; the
 * status is there for the ones that have to tell "you aren't signed in"
 * apart from "the server is broken", which look identical without it.
 */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
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
  if (!res.ok) throw new ApiError(errorMessage(data, fallbackError), res.status)
  return data as T
}

/**
 * Call a URL the server handed back in an `_links` map.
 *
 * Every response carries one, and following the link is the difference
 * between the client knowing *that* an order can be cancelled and knowing
 * *where* the cancel route lives. The link is already a full API path
 * (`/api/v1/...`), so unlike apiFetch it is not appended to the base - only
 * the origin is, for the case where the client points somewhere else.
 */
export async function followLink<T>(
  link: string,
  fallbackError: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_ORIGIN}${link}`, { credentials: 'include', ...init })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(errorMessage(data, fallbackError), res.status)
  return data as T
}

/** The absolute URL for a link, for the cases a browser has to navigate to. */
export function linkUrl(link: string): string {
  return `${API_ORIGIN}${link}`
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

/** Build the RequestInit for a JSON PATCH. */
export function patch(body?: unknown): RequestInit {
  return {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  }
}

/** Build the RequestInit for a DELETE. */
export function del(): RequestInit {
  return { method: 'DELETE' }
}
