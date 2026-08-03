import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { io, type Socket } from 'socket.io-client'
import type { AssetType } from './api'
import { API_ORIGIN } from './config'

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
  // No argument means "same origin", which is what both the dev proxy and
  // the deployed rewrites want. API_ORIGIN is the escape hatch for pointing
  // a local client somewhere else; see config.ts.
  if (!socket) socket = io(API_ORIGIN || undefined)
  return socket
}

/**
 * Subscribe to live prices for `symbols` and return the latest quote for
 * each, keyed by symbol.
 *
 * The server pushes updates for subscribed symbols only, so the returned
 * map fills in as quotes arrive rather than being complete up front. Asset
 * types that aren't streamed - bonds are repriced daily - simply never
 * receive anything, so callers don't have to know which is which.
 */
export function useLiveQuotes(assetType: AssetType, symbols: string[]): Record<string, QuoteUpdate> {
  return useLiveFeed(assetType, symbols).quotes
}

export type LiveFeed = {
  quotes: Record<string, QuoteUpdate>
  /** When the last quote arrived, or null if none has yet. */
  lastUpdate: Date | null
}

/**
 * The same subscription as useLiveQuotes, plus when the last update landed.
 *
 * The timestamp exists because a connected feed and a broken one look
 * identical when the market is shut: the price simply never changes. A
 * ticking "updated at" is the only honest evidence that data is arriving.
 */
export function useLiveFeed(assetType: AssetType, symbols: string[]): LiveFeed {
  const [quotes, setQuotes] = useState<Record<string, QuoteUpdate>>({})
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // Depend on the contents, not the array identity - callers build a fresh
  // array every render and it would otherwise resubscribe constantly.
  const subscription = symbols.join(',')

  useEffect(() => {
    if (!subscription) return

    const watched = subscription.split(',')
    const request = { assetType, symbols: watched }
    const connection = getSocket()

    function handleQuote(update: QuoteUpdate) {
      setQuotes((current) => ({ ...current, [update.symbol]: update }))
      setLastUpdate(new Date())
    }

    connection.on('quote', handleQuote)
    connection.emit('subscribe', request)

    return () => {
      connection.emit('unsubscribe', request)
      connection.off('quote', handleQuote)
    }
  }, [assetType, subscription])

  return { quotes, lastUpdate }
}

/**
 * One feed covering several asset types at once, keyed {assetType: symbols}.
 *
 * A subscription names the type its symbols belong to - the server needs it
 * to know which provider to price them through - so a list mixing types, a
 * watchlist, needs one subscription per type. The quotes come back in a
 * single map because a symbol belongs to exactly one type, so nothing
 * collides and callers can look a tile up without knowing what kind it is.
 */
export function useLiveFeeds(symbolsByType: Partial<Record<AssetType, string[]>>): LiveFeed {
  const [quotes, setQuotes] = useState<Record<string, QuoteUpdate>>({})
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // Depend on the contents, not the object identity - callers build a fresh
  // one every render and it would otherwise resubscribe constantly.
  const subscription = Object.entries(symbolsByType)
    .filter(([, symbols]) => symbols && symbols.length > 0)
    .map(([assetType, symbols]) => `${assetType}:${symbols!.join(',')}`)
    .sort()
    .join('|')

  useEffect(() => {
    if (!subscription) return

    const requests = subscription.split('|').map((group) => {
      const [assetType, symbols] = group.split(':')
      return { assetType: assetType as AssetType, symbols: symbols.split(',') }
    })
    const connection = getSocket()

    function handleQuote(update: QuoteUpdate) {
      setQuotes((current) => ({ ...current, [update.symbol]: update }))
      setLastUpdate(new Date())
    }

    connection.on('quote', handleQuote)
    for (const request of requests) connection.emit('subscribe', request)

    return () => {
      for (const request of requests) connection.emit('unsubscribe', request)
      connection.off('quote', handleQuote)
    }
  }, [subscription])

  return { quotes, lastUpdate }
}

/**
 * Whether pushed quotes are currently arriving.
 *
 * A price that has quietly stopped updating looks exactly like a price that
 * hasn't moved, and the difference matters a great deal to someone deciding
 * whether to trade at it. Only call this from a component that is already
 * subscribed - it reuses that connection rather than opening one.
 */
function subscribeToConnection(onChange: () => void) {
  const connection = getSocket()
  connection.on('connect', onChange)
  connection.on('disconnect', onChange)

  return () => {
    connection.off('connect', onChange)
    connection.off('disconnect', onChange)
  }
}

export function useQuoteConnection(): boolean {
  // useSyncExternalStore rather than state-plus-effect: the socket already
  // holds this value, so mirroring it into React state would just be a
  // second copy to keep in step. The server snapshot is false because
  // nothing is connected until the client runs.
  return useSyncExternalStore(
    subscribeToConnection,
    () => socket?.connected ?? false,
    () => false,
  )
}

/**
 * The direction of the most recent price change, for the ~700ms after it
 * lands, or null the rest of the time.
 *
 * A number that changes under the cursor with no acknowledgement is the one
 * place in this app where motion carries information rather than decoration.
 */
export function usePriceDirection(price: number | undefined): 'up' | 'down' | null {
  const previous = useRef(price)
  const [direction, setDirection] = useState<'up' | 'down' | null>(null)

  useEffect(() => {
    if (price == null) return

    const prior = previous.current
    previous.current = price
    if (prior == null || prior === price) return

    setDirection(price > prior ? 'up' : 'down')
    const timer = setTimeout(() => setDirection(null), 700)
    return () => clearTimeout(timer)
  }, [price])

  return direction
}
