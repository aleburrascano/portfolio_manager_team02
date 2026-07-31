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
// fixed hue so the bar reads the same way on every visit.
const NAME_COLORS: Record<string, string> = {
  Cash: '#6b7a5e',
  Stocks: '#92702e',
  Crypto: '#5b6f8c',
  Bonds: '#7a5a3a',
}
const FALLBACK_COLORS = Object.values(NAME_COLORS)

function PortfolioComposition({ data, title = 'Portfolio Composition' }: PortfolioCompositionProps) {
  const slices = useMemo(() => {
    const total = data.reduce((sum, entry) => sum + entry.value, 0)
    return data
      .filter((entry) => entry.value > 0)
      .map((entry, index) => ({
        ...entry,
        fill: entry.fill ?? NAME_COLORS[entry.name] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length],
        percent: total > 0 ? (entry.value / total) * 100 : 0,
      }))
  }, [data])

  return (
    <section className="dashboard-card portfolio-composition-card">
      <div className="dashboard-card-header">
        <h3>{title}</h3>
      </div>

      <div className="composition-bar" role="img" aria-label={`Portfolio composition: ${slices.map((s) => `${s.name} ${s.percent.toFixed(0)}%`).join(', ')}`}>
        {slices.map((slice) => (
          <div
            key={slice.name}
            className="composition-bar-segment"
            style={{ width: `${slice.percent}%`, background: slice.fill }}
          />
        ))}
      </div>

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
    </section>
  )
}

export default PortfolioComposition
