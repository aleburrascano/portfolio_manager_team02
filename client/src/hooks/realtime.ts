import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { io, type Socket } from 'socket.io-client'
import type { AssetType } from '../api'
import { API_ORIGIN } from '../lib/config'

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

const SAME_ORIGIN = undefined

let socket: Socket | null = null

function getSocket(): Socket {
  if (!socket) socket = io(API_ORIGIN || SAME_ORIGIN)
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

  const subscriptionKey = symbols.join(',')

  useEffect(() => {
    if (!subscriptionKey) return

    const watched = subscriptionKey.split(',')
    const request = { assetType, symbols: watched }
    const connection = getSocket()

    function handleQuote(update: QuoteUpdate) {
      setQuotes((current) => ({ ...current, [update.symbol]: { ...current[update.symbol], ...update } }))
      setLastUpdate(new Date())
    }

    connection.on('quote', handleQuote)
    connection.emit('subscribe', request)

    return () => {
      connection.emit('unsubscribe', request)
      connection.off('quote', handleQuote)
    }
  }, [assetType, subscriptionKey])

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

  const subscriptionKey = Object.entries(symbolsByType)
    .filter(([, symbols]) => symbols && symbols.length > 0)
    .map(([assetType, symbols]) => `${assetType}:${symbols!.join(',')}`)
    .sort()
    .join('|')

  useEffect(() => {
    if (!subscriptionKey) return

    const requests = subscriptionKey.split('|').map((group) => {
      const [assetType, symbols] = group.split(':')
      return { assetType: assetType as AssetType, symbols: symbols.split(',') }
    })
    const connection = getSocket()

    function handleQuote(update: QuoteUpdate) {
      setQuotes((current) => ({ ...current, [update.symbol]: { ...current[update.symbol], ...update } }))
      setLastUpdate(new Date())
    }

    connection.on('quote', handleQuote)
    for (const request of requests) connection.emit('subscribe', request)

    return () => {
      for (const request of requests) connection.emit('unsubscribe', request)
      connection.off('quote', handleQuote)
    }
  }, [subscriptionKey])

  return { quotes, lastUpdate }
}

/** A conditional order that has just filled, pushed to its owner alone. */
export type OrderFill = {
  limitOrderId: number
  ticker: string
  side: 'buy' | 'sell'
  orderType: 'limit' | 'stop'
  quantity: number
  /** What it actually executed at, which is not the trigger price. */
  price: number
  assetTransactionId: number
}

/** A conditional order dropped because its position no longer exists. */
export type OrderCancellation = {
  limitOrderId: number
  ticker: string
  side: 'buy' | 'sell'
  orderType: 'limit' | 'stop'
  quantity: number
  reason: 'position_closed'
}

/** A bond of this user's that has matured and been paid out at par. */
export type BondRedemption = {
  ticker: string
  quantity: number
  /** Face value, which is what a bond pays at maturity. */
  price: number
  proceeds: number
}

/**
 * Run `onRedeem` whenever a bond of this user's matures and pays out.
 *
 * Same shape of subscription as a fill, and for the same reason: it happens
 * on a date rather than in response to anything they did, so nothing on
 * this side would otherwise know their cash had moved.
 */
export function useBondRedemptions(onRedeem: (payout: BondRedemption) => void): void {
  useUserEvent('bondRedeemed', onRedeem)
}

/**
 * Run `onFill` whenever one of this user's conditional orders fills.
 *
 * A fill happens in the server's poller, minutes or days after the request
 * that placed the order, so nothing on this side would otherwise know: an
 * open orders list would sit there showing a row that has already resolved,
 * and the balance beside it would be wrong.
 *
 */
export function useOrderFills(onFill: (fill: OrderFill) => void): void {
  useUserEvent('orderFilled', onFill)
}

/**
 * Run `onCancel` whenever the server drops one of this user's orders
 * because the position behind it is gone.
 *
 * The one server-side resolution the user did not ask for, which is exactly
 * why it is announced: an open orders list that quietly loses a row, or a
 * row that silently changes tab, reads as a bug rather than as the tidying
 * up it is.
 */
export function useOrderCancellations(onCancel: (cancellation: OrderCancellation) => void): void {
  useUserEvent('orderCancelled', onCancel)
}

/**
 * Subscribe to an event the server addresses to this user alone.
 *
 * The handler is kept in a ref, updated in its own effect, so a caller can
 * pass a fresh closure every render - which it will, since the useful ones
 * capture state - without the socket listener being torn down and put back
 * on each one. Writing the ref during render would be the shorter way to
 * say that and is not safe: a render React discards would still have
 * changed it.
 */
function useUserEvent<T>(event: string, onEvent: (payload: T) => void): void {
  const handler = useRef(onEvent)

  useEffect(() => {
    handler.current = onEvent
  }, [onEvent])

  useEffect(() => {
    const connection = getSocket()
    const listener = (payload: T) => handler.current(payload)

    connection.on(event, listener)
    return () => {
      connection.off(event, listener)
    }
  }, [event])
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
  const isConnected = () => socket?.connected ?? false
  const isConnectedOnServer = () => false

  return useSyncExternalStore(subscribeToConnection, isConnected, isConnectedOnServer)
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
