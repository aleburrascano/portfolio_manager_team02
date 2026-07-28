import type { Stock } from '../api'
import StockLogo from './StockLogo'
import './StockList.css'

type StockListProps = {
  title: string
  stocks: Stock[]
  loading?: boolean
  onSelect?: (symbol: string) => void
}

function StockList({ title, stocks, loading, onSelect }: StockListProps) {
  return (
    <div className="stock-list">
      <h2>{title}</h2>
      {loading ? (
        <p className="stock-list-status">Loading…</p>
      ) : stocks.length === 0 ? (
        <p className="stock-list-status">No results</p>
      ) : (
        <ul>
          {stocks.map((stock) => {
            const isPositive = (stock.change ?? 0) >= 0
            return (
              <li
                key={stock.symbol}
                className="stock-row"
                onClick={() => onSelect?.(stock.symbol)}
                role={onSelect ? 'button' : undefined}
                tabIndex={onSelect ? 0 : undefined}
              >
                <StockLogo symbol={stock.symbol} />
                <div className="stock-info">
                  <span className="stock-name">{stock.name}</span>
                  <span className="stock-symbol">{stock.symbol}</span>
                </div>
                <div className="stock-stats">
                  {stock.currentPrice !== undefined && (
                    <span className="stock-price">
                      ${stock.currentPrice.toFixed(2)}
                    </span>
                  )}
                  {stock.changePercent !== undefined && (
                    <span
                      className={`stock-change ${isPositive ? 'positive' : 'negative'}`}
                    >
                      {isPositive ? '▲' : '▼'} {Math.abs(stock.changePercent).toFixed(2)}%
                    </span>
                  )}
                  {stock.dayLow !== undefined && stock.dayHigh !== undefined && (
                    <span className="stock-range">
                      ${stock.dayLow.toFixed(2)} - ${stock.dayHigh.toFixed(2)}
                    </span>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export default StockList
