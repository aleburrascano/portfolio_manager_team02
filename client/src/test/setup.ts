import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// RTL's auto-cleanup only registers itself when it finds a global afterEach,
// which vitest doesn't provide unless `test.globals` is on - so it's done
// explicitly here instead of turning that on for the whole suite.
afterEach(() => cleanup())

// The app opens one real socket.io connection per session (see realtime.ts).
// Tests never want a live connection, so every module under test gets a
// fake socket whose on/off/emit are no-ops a test can still assert against.
vi.mock('socket.io-client', () => ({
  io: () => ({
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
  }),
}))
