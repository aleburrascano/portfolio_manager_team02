import { renderHook, act } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useLiveFeed, type QuoteUpdate } from './realtime'

/**
 * A socket that hands back whatever the code under test registered, so a
 * test can push a quote through the same path the server's would take.
 * The global mock in test/setup.ts is deliberately inert, which is right
 * for components that merely happen to subscribe and wrong here.
 */
const handlers = new Set<(update: QuoteUpdate) => void>()

vi.mock('socket.io-client', () => ({
  io: () => ({
    on: (event: string, handler: (update: QuoteUpdate) => void) => {
      if (event === 'quote') handlers.add(handler)
    },
    off: (event: string, handler: (update: QuoteUpdate) => void) => {
      if (event === 'quote') handlers.delete(handler)
    },
    emit: vi.fn(),
  }),
}))

function push(update: QuoteUpdate) {
  act(() => {
    for (const handler of handlers) handler(update)
  })
}

beforeEach(() => handlers.clear())

describe('useLiveFeed', () => {
  it('merges a sparse update over the quote it already holds', () => {
    const { result } = renderHook(() => useLiveFeed('stock', ['AAPL']))

    push({ symbol: 'AAPL', currentPrice: 315.58, dayLow: 313.49, dayHigh: 316.29, volume: 6144001 })
    // Yahoo streams only what moved, so a price tick arrives on its own.
    push({ symbol: 'AAPL', currentPrice: 315.9 })

    expect(result.current.quotes.AAPL).toEqual({
      symbol: 'AAPL',
      currentPrice: 315.9,
      dayLow: 313.49,
      dayHigh: 316.29,
      volume: 6144001,
    })
  })

  it('keeps each symbol separate', () => {
    const { result } = renderHook(() => useLiveFeed('stock', ['AAPL', 'MSFT']))

    push({ symbol: 'AAPL', currentPrice: 315.58, dayHigh: 316.29 })
    push({ symbol: 'MSFT', currentPrice: 495.77 })

    expect(result.current.quotes.AAPL.dayHigh).toBe(316.29)
    expect(result.current.quotes.MSFT.dayHigh).toBeUndefined()
  })
})
