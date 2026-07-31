import { useEffect, useRef, useState } from 'react'
import { isWatched, setWatched, type AssetType, type User } from '../api'
import './WatchButton.css'

/**
 * Save-for-later toggle on the asset detail page.
 *
 * Optimistic: the button flips immediately and rolls back if the request
 * fails, because waiting on a round trip to acknowledge a bookmark makes
 * the whole page feel slow for something that isn't a transaction.
 */
function WatchButton({
  user,
  assetType,
  symbol,
  onChange,
}: {
  user: User
  assetType: AssetType
  symbol: string
  /** Lets the dashboard's watchlist refresh without a page reload. */
  onChange?: (watched: boolean) => void
}) {
  // Tagged with the asset it answers, so switching assets shows "loading"
  // again without an effect having to reset the state first.
  const requestKey = `${user.userId}:${assetType}:${symbol}`
  const [state, setState] = useState<{ key: string; watched: boolean }>({
    key: '',
    watched: false,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  // Counts toggles so a slower earlier request can't roll back a newer
  // one. Without it, pressing twice quickly could leave the button showing
  // the opposite of what the server ended up storing.
  const intent = useRef(0)

  const watched = state.key === requestKey ? state.watched : null

  useEffect(() => {
    let cancelled = false

    isWatched(user.userId, assetType, symbol)
      .then((result) => {
        if (!cancelled) setState({ key: requestKey, watched: result })
      })
      .catch(() => {
        // Unknown state reads as "not saved"; pressing it will find out.
        if (!cancelled) setState({ key: requestKey, watched: false })
      })

    return () => {
      cancelled = true
    }
  }, [user.userId, assetType, symbol, requestKey])

  async function toggle() {
    // Only the unknown state blocks a press. An in-flight request must
    // not, or a quick second click would be swallowed with nothing on
    // screen to say so - the button would simply appear stuck.
    if (watched === null) return

    const next = !watched
    const ticket = ++intent.current
    setState({ key: requestKey, watched: next })
    setSaving(true)
    setError('')

    try {
      await setWatched(user.userId, assetType, symbol, next)
      if (ticket === intent.current) onChange?.(next)
    } catch (e) {
      // Superseded by a later press: that request owns the state now, and
      // rolling back to this one's guess would fight it.
      if (ticket !== intent.current) return
      setState({ key: requestKey, watched: !next })
      setError(e instanceof Error ? e.message : 'Could not update your watchlist.')
    } finally {
      if (ticket === intent.current) setSaving(false)
    }
  }

  return (
    <div className="watch-button-wrap">
      <button
        type="button"
        className={`watch-button${watched ? ' watching' : ''}`}
        aria-pressed={watched ?? false}
        aria-busy={saving}
        disabled={watched === null}
        onClick={toggle}
      >
        <svg
          className="icon"
          viewBox="0 0 20 20"
          fill={watched ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M5.5 3.5h9a1 1 0 0 1 1 1v12l-5.5-3.25L4.5 16.5v-12a1 1 0 0 1 1-1z"
          />
        </svg>
        {watched ? 'Saved' : 'Save for later'}
      </button>

      <p className="watch-button-error" role="alert">
        {error}
      </p>
    </div>
  )
}

export default WatchButton
