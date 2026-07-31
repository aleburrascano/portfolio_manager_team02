import { useMemo } from 'react'
import { formatCurrency } from '../format'
import './PortfolioComposition.css'

export type PortfolioCompositionDatum = {
  name: string
  value: number
  fill?: string
}

interface PortfolioCompositionProps {
  data: PortfolioCompositionDatum[]
  title?: string
}

// Ledger-toned, not the chart-default rainbow - each asset class gets a
// fixed hue so the chart reads the same way on every visit.
//
// Spaced on LIGHTNESS, not hue: the classes are drawn in a fixed order and
// the ring is cyclic, so every pair that can touch (Cash-Stocks,
// Stocks-Crypto, Crypto-Bonds, Bonds-Cash) sits at least 1.78:1 apart. That
// is what keeps the chart readable in greyscale and for red-green
// deficiency, which a hue-only palette does not.
const NAME_COLORS: Record<string, string> = {
  Cash: '#99a68c',
  Stocks: '#92702e',
  Crypto: '#3d4c61',
  Bonds: '#a8604e',
}
const FALLBACK_COLORS = Object.values(NAME_COLORS)

const RADIUS = 50
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
/** Paper showing between slices, so touching arcs never read as one. */
const SLICE_GAP = 2.5

function PortfolioComposition({ data, title = 'Portfolio composition' }: PortfolioCompositionProps) {
  const { slices, total } = useMemo(() => {
    const total = data.reduce((sum, entry) => sum + entry.value, 0)
    const withPercent = data
      .filter((entry) => entry.value > 0)
      .map((entry, index) => ({
        ...entry,
        fill: entry.fill ?? NAME_COLORS[entry.name] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length],
        percent: total > 0 ? (entry.value / total) * 100 : 0,
      }))

    // Each slice's start offset is the running total of the percents before
    // it - with at most four asset classes, a fresh reduce per slice reads
    // more plainly than threading a mutable accumulator through the map.
    const slices = withPercent.map((slice, index) => {
      const priorPercent = withPercent.slice(0, index).reduce((sum, s) => sum + s.percent, 0)
      const arc = (slice.percent / 100) * CIRCUMFERENCE
      // A slice thinner than the gap keeps its full length; trimming it
      // would erase it entirely rather than separate it.
      const length = arc > SLICE_GAP * 2 ? arc - SLICE_GAP : arc
      return {
        ...slice,
        dasharray: `${length} ${CIRCUMFERENCE}`,
        dashoffset: -(priorPercent / 100) * CIRCUMFERENCE,
      }
    })

    return { slices, total }
  }, [data])

  return (
    <section className="dashboard-card portfolio-composition-card">
      <h3 className="section-title">{title}</h3>

      {/* Wrapped so that when the dashboard is fitted to the viewport a
          long legend scrolls in the panel rather than pushing the page. */}
      <div className="composition-card-scroll">
      <div className="donut-wrap">
        {/* The legend below carries every value as real text, so the ring
            itself is decoration as far as a screen reader is concerned. */}
        <svg width="112" height="112" viewBox="0 0 120 120" aria-hidden="true" focusable="false">
          <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="var(--surface)" strokeWidth="16" />
          {slices.map((slice) => (
            <circle
              key={slice.name}
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              stroke={slice.fill}
              strokeWidth="16"
              strokeDasharray={slice.dasharray}
              strokeDashoffset={slice.dashoffset}
              transform="rotate(-90 60 60)"
            />
          ))}
        </svg>

        <ul className="composition-legend">
          {slices.map((slice) => (
            <li key={slice.name}>
              <span className="composition-swatch" style={{ background: slice.fill }} />
              <span className="composition-name">{slice.name}</span>
              <span className="figure composition-percent">{slice.percent.toFixed(1)}%</span>
              <span className="figure composition-value">{formatCurrency(slice.value)}</span>
            </li>
          ))}
        </ul>
      </div>
      </div>

      {/* The total sits in the document as text rather than inside the ring,
          where a seven-figure portfolio would print straight over the arcs. */}
      <p className="composition-total">
        <span>Total value</span>
        <span className="figure">{formatCurrency(total)}</span>
      </p>
    </section>
  )
}

export default PortfolioComposition
