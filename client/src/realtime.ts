import { useEffect, useState } from 'react'
import { io, type Socket } from 'socket.io-client'

/**
 * A pushed price update. Only the fields that changed hands are present,
 * so an update is merged over an existing quote rather than replacing it.
 */
export type QuoteUpdate = {
  symbol: string
  currentPrice?: number
  change?: number
  changePercent?: number
  dayLow?: number
  dayHigh?: number
  volume?: number
}

// One connection for the whole app, opened lazily so a session that never
// looks at a price never opens a socket.
let socket: Socket | null = null

function getSocket(): Socket {
  if (!socket) socket = io()
  return socket
}

/**
 * Subscribe to live prices for `symbols` and return the latest quote for
 * each, keyed by symbol.
 *
 * The server pushes updates for subscribed symbols only, so the returned
 * map fills in as quotes arrive rather than being complete up front.
 */
export function useLiveQuotes(symbols: string[]): Record<string, QuoteUpdate> {
  const [quotes, setQuotes] = useState<Record<string, QuoteUpdate>>({})

  // Depend on the contents, not the array identity - callers build a fresh
  // array every render and it would otherwise resubscribe constantly.
  const subscription = symbols.join(',')

  useEffect(() => {
    if (!subscription) return

    const watched = subscription.split(',')
    const connection = getSocket()

    function handleQuote(update: QuoteUpdate) {
      setQuotes((current) => ({ ...current, [update.symbol]: update }))
    }

    connection.on('quote', handleQuote)
    connection.emit('subscribe', { symbols: watched })

    return () => {
      connection.emit('unsubscribe', { symbols: watched })
      connection.off('quote', handleQuote)
    }
  }, [subscription])

  return quotes
}
