import { describe, expect, it } from 'vitest'
import { formatDayLong, formatDayShort, formatMarketDateTime, parseUtc } from './dates'

describe('parseUtc', () => {
  it('reads a bare calendar day as UTC midnight, not local', () => {
    expect(parseUtc('2026-08-03').toISOString()).toBe('2026-08-03T00:00:00.000Z')
  })

  it('treats an offset-less timestamp as UTC rather than local', () => {
    expect(parseUtc('2026-08-03T17:37:17').toISOString()).toBe('2026-08-03T17:37:17.000Z')
  })

  it('leaves a timestamp that already carries a zone alone', () => {
    expect(parseUtc('2026-08-03T00:00:00Z').toISOString()).toBe('2026-08-03T00:00:00.000Z')
    expect(parseUtc('2026-08-03T00:00:00+00:00').toISOString()).toBe('2026-08-03T00:00:00.000Z')
  })
})

describe('formatting is stable regardless of the viewer timezone', () => {
  it('shows the calendar day the server meant, not the day before', () => {
    // The bug: a position bought on the 3rd charting under the 2nd.
    expect(formatDayShort('2026-08-03')).toBe('Aug 3')
    expect(formatDayLong('2026-08-03')).toBe('Aug 3, 2026')
  })

  it('does not tip a late-in-the-day UTC timestamp back a day', () => {
    // 23:30 UTC would fall on the previous day for any negative offset if it
    // were read as local; in UTC it stays on the 3rd.
    expect(formatDayLong('2026-08-03T23:30:00')).toBe('Aug 3, 2026')
  })

  it('renders a timestamp in US market time, labelled EDT in summer', () => {
    // 17:37 UTC is 13:37 in New York during daylight saving.
    const formatted = formatMarketDateTime('2026-08-03T17:37:00')
    expect(formatted).toContain('8/3/2026')
    expect(formatted).toContain('13:37')
    expect(formatted).toContain('EDT')
  })

  it('labels a winter timestamp EST, not a hardcoded abbreviation', () => {
    // 12:00 UTC is 07:00 in New York during standard time.
    const formatted = formatMarketDateTime('2026-01-05T12:00:00')
    expect(formatted).toContain('07:00')
    expect(formatted).toContain('EST')
  })
})
