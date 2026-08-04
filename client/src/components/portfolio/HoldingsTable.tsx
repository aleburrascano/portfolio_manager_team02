import { useMemo, useState } from 'react'
import type { AssetType, Holding, HoldingsResult } from '../../api'
import { formatDayLong } from '../../lib/dates'
import { formatCurrency, formatNumber } from '../../lib/format'
import AssetLogo from '../ui/AssetLogo'
import './HoldingsTable.css'

/** Sortable columns. `numeric` also decides which way the first click goes. */
type Column = {
  key: keyof Holding
  label: string
  numeric?: boolean
}

const COLUMNS: Column[] = [
  { key: 'ticker', label: 'Asset' },
  { key: 'quantity', label: 'Quantity', numeric: true },
  { key: 'averageCost', label: 'Avg cost', numeric: true },
  { key: 'value', label: 'Value', numeric: true },
  { key: 'gainLoss', label: 'Gain / loss', numeric: true },
  { key: 'acquiredAt', label: 'Acquired', numeric: true },
]

type SortOrder = 'asc' | 'desc'

const ASSET_LABELS: Record<string, string> = {
  stock: 'Stock',
  crypto: 'Crypto',
  bond: 'Bond',
}

function formatAcquired(value: string | null) {
  if (!value) return '—'
  return formatDayLong(value)
}

/**
 * Nulls last in both directions, so an unknown acquisition date never
 * leads the table. Direction is a parameter rather than a swap of the
 * arguments, because swapping would flip the null handling too.
 */
function compare(a: Holding, b: Holding, key: keyof Holding, order: SortOrder): number {
  const left = a[key]
  const right = b[key]
  if (left == null && right == null) return 0
  if (left == null) return 1
  if (right == null) return -1

  const ascending =
    typeof left === 'number' && typeof right === 'number'
      ? left - right
      : String(left).localeCompare(String(right))
  return order === 'asc' ? ascending : -ascending
}

function GainLoss({ value, percent }: { value: number; percent: number }) {
  const tone = value > 0 ? 'positive' : value < 0 ? 'negative' : 'flat'
  const glyph = value > 0 ? '▲' : value < 0 ? '▼' : '—'
  return (
    <span className={`holdings-delta ${tone}`}>
      {glyph} {formatCurrency(Math.abs(value))}
      <span className="holdings-delta-percent">{formatNumber(Math.abs(percent), 2)}%</span>
    </span>
  )
}

/**
 * The book is passed in rather than fetched here: the statement head above
 * shows the same totals, and two fetches would price it at two instants
 * and disagree on screen.
 */
function HoldingsTable({
  data,
  loading,
  error,
  onSelectAsset,
}: {
  data: HoldingsResult | null
  loading: boolean
  error: string | null
  onSelectAsset?: (assetType: AssetType, symbol: string) => void
}) {
  const [sort, setSort] = useState<keyof Holding>('value')
  const [order, setOrder] = useState<SortOrder>('desc')

  const holdings = useMemo(() => {
    const rows = [...(data?.holdings ?? [])]
    rows.sort((a, b) => compare(a, b, sort, order))
    return rows
  }, [data, sort, order])

  function toggleSort(column: Column) {
    if (column.key === sort) {
      setOrder((current) => (current === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSort(column.key)
    setOrder(column.numeric ? 'desc' : 'asc')
  }

  const totals = data?.totals

  return (
    <section className="card holdings-card" aria-labelledby="holdings-title">
      <div className="holdings-header">
        <h3 id="holdings-title" className="section-title">
          Your holdings
        </h3>
        {totals && totals.positions > 0 && (
          <p className="holdings-count">
            {totals.positions} {totals.positions === 1 ? 'position' : 'positions'}
          </p>
        )}
      </div>

      {loading ? (
        <div className="holdings-loading" aria-busy="true">
          <span className="visually-hidden">Loading your holdings</span>
          {Array.from({ length: 4 }, (_, index) => (
            <span key={index} className="skeleton skeleton-holding" />
          ))}
        </div>
      ) : error ? (
        <p className="holdings-empty">{error} Refresh the page to try again.</p>
      ) : holdings.length === 0 ? (
        <p className="holdings-empty">
          You don't hold any positions yet. Anything you buy will be listed here with what you
          paid and what it's worth now.
        </p>
      ) : (
        <div className="holdings-scroll">
          <table className="holdings-table">
            <caption className="visually-hidden">
              Your holdings, sorted by {sort}, {order === 'asc' ? 'ascending' : 'descending'}
            </caption>
            <thead>
              <tr>
                {COLUMNS.map((column) => {
                  const active = column.key === sort
                  return (
                    <th
                      key={column.key}
                      scope="col"
                      className={column.numeric ? 'numeric' : undefined}
                      aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      <button type="button" onClick={() => toggleSort(column)}>
                        {column.label}
                        <span className="holdings-sort-glyph" aria-hidden="true">
                          {active ? (order === 'asc' ? '▲' : '▼') : '↕'}
                        </span>
                      </button>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {holdings.map((holding) => (
                <tr key={holding.ticker}>
                  <td data-label="Asset">
                    {onSelectAsset ? (
                      <button
                        type="button"
                        className="holdings-asset holdings-asset-link"
                        onClick={() => onSelectAsset(holding.assetType, holding.ticker)}
                      >
                        <AssetLogo symbol={holding.ticker} assetType={holding.assetType} />
                        <span className="holdings-asset-text">
                          <span className="figure holdings-ticker">{holding.ticker}</span>
                          <span className="holdings-type">
                            {ASSET_LABELS[holding.assetType] ?? holding.assetType}
                          </span>
                        </span>
                      </button>
                    ) : (
                      <span className="holdings-asset">
                        <AssetLogo symbol={holding.ticker} assetType={holding.assetType} />
                        <span className="holdings-asset-text">
                          <span className="figure holdings-ticker">{holding.ticker}</span>
                          <span className="holdings-type">
                            {ASSET_LABELS[holding.assetType] ?? holding.assetType}
                          </span>
                        </span>
                      </span>
                    )}
                  </td>
                  <td data-label="Quantity" className="numeric figure">
                    {formatNumber(holding.quantity, 2)}
                  </td>
                  <td data-label="Avg cost" className="numeric figure">
                    {formatCurrency(holding.averageCost)}
                  </td>
                  <td data-label="Value" className="numeric figure">
                    {formatCurrency(holding.value)}
                  </td>
                  <td data-label="Gain / loss" className="numeric figure">
                    <GainLoss value={holding.gainLoss} percent={holding.gainLossPercent} />
                  </td>
                  <td data-label="Acquired" className="numeric figure holdings-acquired">
                    {formatAcquired(holding.acquiredAt)}
                  </td>
                </tr>
              ))}
            </tbody>
            {totals && (
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td className="numeric" />
                  <td className="numeric figure" data-label="Cost basis">
                    {formatCurrency(totals.costBasis)}
                  </td>
                  <td className="numeric figure" data-label="Value">
                    {formatCurrency(totals.value)}
                  </td>
                  <td className="numeric figure" data-label="Gain / loss">
                    <GainLoss value={totals.gainLoss} percent={totals.gainLossPercent} />
                  </td>
                  <td className="numeric" />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </section>
  )
}

export default HoldingsTable
