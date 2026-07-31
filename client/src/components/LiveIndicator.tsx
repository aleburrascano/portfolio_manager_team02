import './LiveIndicator.css'

/**
 * Proof that the price feed is alive.
 *
 * Without this the app is silent when the market is shut: quotes arrive on
 * schedule, every one carries the same closing price, nothing on screen
 * moves, and a working feed is indistinguishable from a broken one. The
 * timestamp ticks on every received update whether or not the number
 * changed, which is the evidence a still price can't provide.
 */
function LiveIndicator({
  connected,
  lastUpdate,
}: {
  connected: boolean
  lastUpdate: Date | null
}) {
  if (!connected) {
    return (
      <p className="live-indicator offline" role="status">
        <span className="live-dot" aria-hidden="true" />
        Reconnecting — prices may be out of date
      </p>
    )
  }

  return (
    <p className="live-indicator" role="status">
      <span className="live-dot" aria-hidden="true" />
      Live
      {lastUpdate && (
        <span className="live-timestamp figure">
          updated{' '}
          {lastUpdate.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hourCycle: 'h23',
          })}
        </span>
      )}
    </p>
  )
}

export default LiveIndicator
