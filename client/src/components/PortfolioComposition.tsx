import { useMemo } from 'react'
import { PieChart, Pie, Tooltip, Legend, ResponsiveContainer } from 'recharts'
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

const DEFAULT_COLORS = ['#3f66af', '#67c4e0', '#697ada', '#80d8a0']

function formatTooltipValue(value: number | string | undefined) {
  if (value == null) {
    return ''
  }

  if (typeof value === 'number') {
    return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  return String(value)
}

function PortfolioComposition({ data, title = 'Portfolio Composition' }: PortfolioCompositionProps) {
  const chartData = useMemo(
    () =>
      data.map((entry, index) => ({
        ...entry,
        fill: entry.fill ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length],
      })),
    [data],
  )

  const total = chartData.reduce((sum, entry) => sum + entry.value, 0)

  return (
    <section className="dashboard-card portfolio-composition-card">
      <div className="dashboard-card-header">
        <h3>{title}</h3>
      </div>
      <div className="portfolio-chart-wrapper">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={100}
            />
            <Tooltip formatter={formatTooltipValue} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

export default PortfolioComposition
