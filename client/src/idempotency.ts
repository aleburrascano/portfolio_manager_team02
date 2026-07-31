import { useRef } from 'react'

/**
 * Hands out an Idempotency-Key per user intent.
 *
 * Resubmitting the same thing — the same amount, the same trade — reuses
 * the key, so if the first attempt actually reached the server the retry
 * replays it instead of doing it twice. Changing the inputs, or completing
 * the action and starting another, is a new intent and gets a new key:
 * depositing $100 twice on purpose has to go through both times.
 */
export function useIdempotencyKey() {
  const intent = useRef('')
  const key = useRef('')

  return {
    /** The key for this intent, minted on first sight of it. */
    keyFor(next: string): string {
      if (intent.current !== next) {
        intent.current = next
        key.current = crypto.randomUUID()
      }
      return key.current
    },
    /** Call after the action succeeds, so an identical one can follow it. */
    reset(): void {
      intent.current = ''
    },
  }
}
