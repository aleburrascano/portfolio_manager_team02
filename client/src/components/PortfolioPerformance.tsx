import { useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  fetchPortfolioPerformance,
  type PortfolioPerformance as Performance,
  type User,
} from '../api'
import { useAssetTypes } from '../asset-types'
import { formatCurrency, formatNumber } from '../format'
import './PortfolioPerformance.css'

/** The windows a user actually asks for, rather than a free-form date picker. */
const RANGES = [
  { days: 30, label: '1M' },
  { days: 90, label: '3M' },
  { days: 365, label: '1Y' },
  { days: 1825, label: 'All' },
] as const

const AXIS_PADDING_FRACTION = 0.08

function formatAxisDate(value: string) {
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatFullDate(value: string) {
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function Signed({ value, percent }: { value: number; percent: number }) {
  const tone = value > 0 ? 'positive' : value < 0 ? 'negative' : 'flat'
  const glyph = value > 0 ? '▲' : value < 0 ? '▼' : '—'
  return (
    <span className={`figure performance-delta ${tone}`}>
      {glyph} {formatCurrency(Math.abs(value))} ({formatNumber(Math.abs(percent), 2)}%)
    </span>
  )
}

function PortfolioPerformance({ user, balance }: { user: User; balance: number | null }) {
  const { byType } = useAssetTypes()
  const [days, setDays] = useState<number>(365)
  const requestKey = `${user.userId}:${days}:${balance}`
  const [state, setState] = useState<{ key: string; data?: Performance; error?: string }>({
    key: '',
  })

  useEffect(() => {
    let cancelled = false

    fetchPortfolioPerformance(user.userId, days)
      .then((result) => {
        if (!cancelled) setState({ key: requestKey, data: result })
      })
      .catch((e) => {
        if (!cancelled) {
          setState({
            key: requestKey,
            error: e instanceof Error ? e.message : 'Failed to load performance.',
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [user.userId, days, requestKey])

  const loading = state.key !== requestKey
  const data = state.data ?? null
  const error = state.error ?? null

  const domain = useMemo(() => {
    const values = (data?.series ?? []).flatMap((point) => [
      point.portfolioValue,
      point.netDeposits,
      ...(point.benchmarkValue != null ? [point.benchmarkValue] : []),
    ])
    if (values.length === 0) return undefined
    const low = Math.min(...values)
    const high = Math.max(...values)
    const pad = (high - low || high || 1) * AXIS_PADDING_FRACTION
    return [Math.max(0, low - pad), high + pad] as [number, number]
  }, [data])

  const summary = data?.summary
  const hasSeries = (data?.series.length ?? 0) > 1
  const hasBenchmark = (data?.series ?? []).some((point) => point.benchmarkValue != null)
  const benchmarkLabel = data?.benchmark?.label ?? 'Benchmark'

  const beatBenchmark = useMemo(() => {
    const last = data?.series.at(-1)
    if (!last || last.benchmarkValue == null) return null
    return last.portfolioValue - last.benchmarkValue
  }, [data])

  return (
    <section className="dashboard-card performance-card" aria-labelledby="performance-title">
      <div className="performance-header">
        <div>
          <h3 id="performance-title" className="section-title">
            Portfolio performance
          </h3>
          {summary && hasSeries && (
            <p className="performance-headline">
              <Signed value={summary.gainLoss} percent={summary.gainLossPercent} />
              <span className="performance-caption">
                against {formatCurrency(summary.netDeposits)} paid in
              </span>
              {beatBenchmark !== null && (
                <span className="performance-caption">
                  {beatBenchmark >= 0 ? 'ahead of' : 'behind'} {benchmarkLabel} by{' '}
                  {formatCurrency(Math.abs(beatBenchmark))}
                </span>
              )}
            </p>
          )}
        </div>

        <div className="performance-ranges" role="group" aria-label="Chart range">
          {RANGES.map((range) => (
            <button
              key={range.days}
              type="button"
              className={days === range.days ? 'active' : ''}
              aria-pressed={days === range.days}
              onClick={() => setDays(range.days)}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="performance-body" aria-busy="true">
          <span className="visually-hidden">Loading portfolio performance</span>
          <span className="skeleton skeleton-performance" />
        </div>
      ) : error ? (
        <p className="performance-empty">{error} Refresh the page to try again.</p>
      ) : !hasSeries ? (
        <p className="performance-empty">
          There isn't enough history to chart yet. Once you've held a position for a day or
          two, your portfolio's value over time will appear here.
        </p>
      ) : (
        <>
          <div className="performance-body">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data!.series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="performanceFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.28} />
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatAxisDate}
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  axisLine={{ stroke: 'var(--border)' }}
                  tickLine={false}
                  minTickGap={44}
                />
                <YAxis
                  domain={domain}
                  tickFormatter={(value) => formatCurrency(Number(value), 0)}
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={68}
                />
                <Tooltip
                  labelFormatter={(label) => formatFullDate(String(label))}
                  formatter={(value, name) => [formatCurrency(Number(value)), String(name)]}
                  contentStyle={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border-strong)',
                    borderRadius: 4,
                    fontSize: 13,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="portfolioValue"
                  name="Portfolio"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  fill="url(#performanceFill)"
                />
                <Line
                  type="stepAfter"
                  dataKey="netDeposits"
                  name="Paid in"
                  stroke="var(--text-muted)"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                />
                {hasBenchmark && (
                  <Line
                    type="monotone"
                    dataKey="benchmarkValue"
                    name={benchmarkLabel}
                    stroke="var(--accent-ink)"
                    strokeWidth={1.5}
                    dot={false}
                  />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {data!.byAssetType.length > 0 && (
            <dl className="performance-classes">
              {data!.byAssetType.map((row) => (
                <div key={row.assetType}>
                  <dt>{byType[row.assetType]?.label ?? row.assetType}</dt>
                  <dd>
                    <Signed value={row.gainLoss} percent={row.gainLossPercent} />
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </>
      )}
    </section>
  )
}

export default PortfolioPerformance
