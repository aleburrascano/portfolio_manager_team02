import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, post } from './client'

function mockFetchOnce(body: unknown, status = 200) {
  const response = {
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  } as Response
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
  return response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('resolves with the parsed JSON body on success', async () => {
    mockFetchOnce({ userId: 1 })
    await expect(apiFetch('/auth/me', 'fallback')).resolves.toEqual({ userId: 1 })
  })

  it('requests the versioned API path with credentials included', async () => {
    mockFetchOnce({})
    await apiFetch('/auth/me', 'fallback')
    expect(fetch).toHaveBeenCalledWith('/api/v1/auth/me', expect.objectContaining({ credentials: 'include' }))
  })

  it('throws the server error string on failure', async () => {
    mockFetchOnce({ error: 'nope' }, 401)
    await expect(apiFetch('/auth/me', 'fallback')).rejects.toThrow('nope')
  })

  it('throws the server error object message on failure', async () => {
    mockFetchOnce({ error: { message: 'bad request' } }, 400)
    await expect(apiFetch('/x', 'fallback')).rejects.toThrow('bad request')
  })

  it('falls back to the given message when the body has no error', async () => {
    mockFetchOnce({}, 500)
    await expect(apiFetch('/x', 'fallback message')).rejects.toThrow('fallback message')
  })

  it('falls back to the given message when the body is not valid JSON', async () => {
    const response = {
      ok: false,
      json: () => Promise.reject(new Error('not json')),
    } as unknown as Response
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    await expect(apiFetch('/x', 'fallback message')).rejects.toThrow('fallback message')
  })
})

describe('post', () => {
  it('builds a JSON POST with the given body', () => {
    const init = post({ amount: 5 })
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({ 'Content-Type': 'application/json' })
    expect(init.body).toBe(JSON.stringify({ amount: 5 }))
  })

  it('defaults to an empty body object', () => {
    expect(post().body).toBe('{}')
  })

  it('adds an Idempotency-Key header when given one', () => {
    const init = post({}, 'abc-123')
    expect(init.headers).toMatchObject({ 'Idempotency-Key': 'abc-123' })
  })

  it('omits the Idempotency-Key header when none is given', () => {
    const init = post({})
    expect(init.headers).not.toHaveProperty('Idempotency-Key')
  })
})
