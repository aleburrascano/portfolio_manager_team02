/**
 * The API speaks UTC, and the browser mangles it two different ways.
 *
 * Chart points arrive as bare calendar days - '2026-08-03'. `new Date` reads
 * those as UTC midnight and then `toLocaleDateString` prints them in the
 * viewer's own zone, so anyone west of Greenwich sees the day before: a
 * position bought on the 3rd charts under the 2nd.
 *
 * Timestamps arrive from the server's `isoformat()` with no offset -
 * '2026-08-03T17:37:17' - which is UTC, but `new Date` reads an offset-less
 * datetime as *local*, shifting the instant by the viewer's offset and
 * tipping it across midnight near the ends of the day.
 *
 * Both come from the same root: the value means UTC and nothing in the string
 * says so. `parseUtc` supplies the missing intent, and every formatter here
 * renders in UTC, so a day is the same day for every viewer.
 */
export function parseUtc(value: string): Date {
  const isBareIsoDateTime = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)
  const carriesZone = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(value)
  return new Date(isBareIsoDateTime && !carriesZone ? `${value}Z` : value)
}

const UTC = 'UTC'

/** "Aug 3" - axis ticks and compact labels. */
export function formatDayShort(value: string): string {
  return parseUtc(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: UTC,
  })
}

/** "Aug 3, 2026" - a date with its year. */
export function formatDayLong(value: string): string {
  return parseUtc(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: UTC,
  })
}

/** Where the market trades, and the frame the day-change logic already uses. */
const MARKET_TZ = 'America/New_York'

/**
 * "8/3/2026, 13:37 EDT" - a timestamp in US market time.
 *
 * The instant is parsed as UTC (where the server keeps it) and rendered in
 * the market's own zone, so a trade reads at the hour the exchange saw it
 * rather than the viewer's. `timeZoneName` prints the live abbreviation, so
 * it says EST or EDT correctly across the daylight-saving boundary instead
 * of a hardcoded guess.
 */
export function formatMarketDateTime(value: string): string {
  return parseUtc(value).toLocaleString('en-US', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: MARKET_TZ,
    timeZoneName: 'short',
  })
}
