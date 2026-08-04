import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => cleanup())

/**
 * A working localStorage for the DOM tests.
 *
 * Node 25 defines a `localStorage` global of its own, inert unless the
 * process was started with --localstorage-file, and it is what both
 * `localStorage` and `window.localStorage` resolve to here: a plain object
 * with no getItem on it at all. Anything storing a preference would throw,
 * take its fallback path in every test, and pass without having exercised
 * a thing - which is worse than failing.
 */
function memoryStorage(): Storage {
  const entries = new Map<string, string>()
  return {
    get length() {
      return entries.size
    },
    key: (index: number) => [...entries.keys()][index] ?? null,
    getItem: (key: string) => entries.get(key) ?? null,
    setItem: (key: string, value: string) => void entries.set(key, String(value)),
    removeItem: (key: string) => void entries.delete(key),
    clear: () => entries.clear(),
  } as Storage
}

for (const target of new Set<typeof globalThis | Window>([globalThis, window])) {
  Object.defineProperty(target, 'localStorage', {
    value: memoryStorage(),
    configurable: true,
    writable: true,
  })
}

vi.mock('socket.io-client', () => ({
  io: () => ({
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
  }),
}))
