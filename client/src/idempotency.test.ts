import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useIdempotencyKey } from './idempotency'

describe('useIdempotencyKey', () => {
  it('mints the same key for the same intent', () => {
    const { result } = renderHook(() => useIdempotencyKey())
    const first = result.current.keyFor('deposit:100')
    const second = result.current.keyFor('deposit:100')
    expect(first).toBe(second)
  })

  it('mints a new key when the intent changes', () => {
    const { result } = renderHook(() => useIdempotencyKey())
    const first = result.current.keyFor('deposit:100')
    const second = result.current.keyFor('deposit:200')
    expect(first).not.toBe(second)
  })

  it('mints a new key for the same intent after a reset', () => {
    const { result } = renderHook(() => useIdempotencyKey())
    const first = result.current.keyFor('deposit:100')
    result.current.reset()
    const second = result.current.keyFor('deposit:100')
    expect(first).not.toBe(second)
  })
})
