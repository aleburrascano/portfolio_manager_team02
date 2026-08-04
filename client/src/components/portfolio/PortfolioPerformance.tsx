import { useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  fetchPortfolioPerformance,
  type AssetTypeInfo,
  type Benchmark,
  type PortfolioPerformance as Performance,
  type User,
} from '../../api'
import { useAssetTypes } from '../../context/asset-types'
import { formatDayLong, formatDayShort } from '../../lib/dates'
import { formatCurrency, formatNumber } from '../../lib/format'
import BenchmarkPicker from './BenchmarkPicker'
import './PortfolioPerformance.css'

/** The windows a user actually asks for, rather than a free-form date picker. */
const RANGES = [
  { days: 30, label: '1M' },
  { days: 90, label: '3M' },
  { days: 365, label: '1Y' },
  { days: 1825, label: 'All' },
] as const

/** Where the comparison starts, until the user picks something else. */
const DEFAULT_BENCHMARK: Benchmark = { assetType: 'stock', ticker: 'SPY', label: 'S&P 500' }

/** What the user is comparing against, and whether they want to see it. */
type Comparison = { benchmark: Benchmark; comparing: boolean }

const DEFAULT_COMPARISON: Comparison = { benchmark: DEFAULT_BENCHMARK, comparing: true }
const COMPARISON_KEY = 'treetop.performance.comparison'

/**
 * The comparison last chosen, from this browser.
 *
 * Kept here rather than on the account: it is a way of looking at the
 * chart, not a fact about the portfolio, and someone who picked Bitcoin on
 * their laptop hasn't said anything about what their phone should open on.
 *
 * Validated against `known` rather than trusted. The stored value outlives
 * the code that wrote it, so it can name an asset type this deployment no
 * longer has - and the server answers an unknown one with a 422, which
 * would leave the chart showing an error until someone thought to clear
 * their browser storage. Matching it against the live registry means the
 * worst a stale value costs is the default comparison.
 *
 * `window.localStorage`, not the bare global: Node 25 defines a
 * `localStorage` of its own, and under the test runner the bare name finds
 * that one - inert without --localstorage-file - instead of the DOM's.
 */
function savedComparison(known: AssetTypeInfo[]): Comparison {
  try {
    const saved = JSON.parse(window.localStorage.getItem(COMPARISON_KEY) ?? '')
    const { assetType, ticker, label } = saved?.benchmark ?? {}
    if (typeof ticker !== 'string' || !ticker) return DEFAULT_COMPARISON

    const type = known.find((candidate) => candidate.assetType === assetType)
    if (!type) return DEFAULT_COMPARISON

    return {
      benchmark: {
        assetType: type.assetType,
        ticker,
        label: typeof label === 'string' && label ? label : ticker,
      },
      comparing: saved.comparing !== false,
    }
  } catch {
    return DEFAULT_COMPARISON
  }
}

const AXIS_PADDING_FRACTION = 0.08

const formatAxisDate = formatDayShort
const formatFullDate = formatDayLong

function Signed({ value, percent }: { value: number; percent: number }) {
  const tone = value > 0 ? 'positive' : value < 0 ? 'negative' : 'flat'
  const glyph = value > 0 ? '▲' : value < 0 ? '▼' : '—'
  return (
    <span className={`figure performance-delta ${tone}`}>
      {glyph} {formatCurrency(Math.abs(value))} ({formatNumber(Math.abs(percent), 2)}%)
    </span>
  )
}

function PortfolioPerformance({
  user,
  balance,
  balanceSettled = true,
}: {
  user: User
  balance: number | null
  balanceSettled?: boolean
}) {
  const { types, byType } = useAssetTypes()
  const [days, setDays] = useState<number>(365)
  /**
   * `comparing` is client-side only, so turning the line off and back on
   * is instant - the series is fetched with the benchmark either way, and
   * a round trip to hide something the browser already has would make a
   * checkbox feel broken. Changing the asset does refetch.
   */
  const [comparison, setComparison] = useState<Comparison>(() => savedComparison(types))
  const { benchmark, comparing } = comparison
  const [picking, setPicking] = useState(false)

  useEffect(() => {
    try {
      window.localStorage.setItem(COMPARISON_KEY, JSON.stringify(comparison))
    } catch {
      // A browser refusing storage - private mode, a full quota - costs
      // the preference, not the chart.
    }
  }, [comparison])
  const requestKey = `${user.userId}:${days}:${balance}:${benchmark.assetType}:${benchmark.ticker}`
  const [state, setState] = useState<{ key: string; data?: Performance; error?: string }>({
    key: '',
  })

  useEffect(() => {
    if (!balanceSettled) return
    let cancelled = false

    async function loadPerformance() {
      try {
        const result = await fetchPortfolioPerformance(user.userId, days, benchmark)
        if (!cancelled) setState({ key: requestKey, data: result })
      } catch (e) {
        if (!cancelled) {
          setState({
            key: requestKey,
            error: e instanceof Error ? e.message : 'Failed to load performance.',
          })
        }
      }
    }

    void loadPerformance()

    return () => {
      cancelled = true
    }
  }, [user.userId, days, benchmark, requestKey, balanceSettled])

  const loading = state.key !== requestKey
  const data = state.data ?? null
  const error = state.error ?? null

  const domain = useMemo(() => {
    const values = (data?.series ?? []).flatMap((point) => [
      point.portfolioValue,
      point.netDeposits,
      ...(comparing && point.benchmarkValue != null ? [point.benchmarkValue] : []),
    ])
    if (values.length === 0) return undefined
    const low = Math.min(...values)
    const high = Math.max(...values)
    const pad = (high - low || high || 1) * AXIS_PADDING_FRACTION
    return [Math.max(0, low - pad), high + pad] as [number, number]
  }, [data, comparing])

  const summary = data?.summary
  const hasSeries = (data?.series.length ?? 0) > 1
  const priced = (data?.series ?? []).some((point) => point.benchmarkValue != null)
  const hasBenchmark = comparing && priced
  const benchmarkLabel = benchmark.label

  const beatBenchmark = useMemo(() => {
    const last = data?.series.at(-1)
    if (!comparing || !last || last.benchmarkValue == null) return null
    return last.portfolioValue - last.benchmarkValue
  }, [data, comparing])

  return (
    <section className="card performance-card" aria-labelledby="performance-title">
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
              {comparing && !priced && (
                <span className="performance-caption">
                  {benchmarkLabel} couldn't be priced over this window
                </span>
              )}
            </p>
          )}
        </div>

        <div className="performance-controls">
          <div className="performance-benchmark">
            <label className="performance-compare">
              <input
                type="checkbox"
                checked={comparing}
                onChange={(event) =>
                  setComparison((current) => ({ ...current, comparing: event.target.checked }))
                }
              />
              Compare against
            </label>
            <button
              type="button"
              className="benchmark-choice"
              disabled={!comparing}
              onClick={() => setPicking(true)}
            >
              {benchmark.label}
            </button>
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
      </div>

      {picking && (
        <BenchmarkPicker
          current={benchmark}
          onPick={(picked) => {
            setComparison((current) => ({ ...current, benchmark: picked }))
            setPicking(false)
          }}
          onClose={() => setPicking(false)}
        />
      )}

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
