import type { Asset, AssetType } from '../api'
import AssetLogo from './AssetLogo'
import './AssetList.css'

type AssetListProps = {
  title: string
  assets: Asset[]
  assetType: AssetType
  loading?: boolean
  onSelect?: (symbol: string) => void
}

function AssetList({ title, assets, assetType, loading, onSelect }: AssetListProps) {
  return (
    <div className="asset-list">
      <h2>{title}</h2>
      {loading ? (
        <p className="asset-list-status">Loading…</p>
      ) : assets.length === 0 ? (
        <p className="asset-list-status">No results</p>
      ) : (
        <ul>
          {assets.map((asset) => {
            const isPositive = (asset.change ?? 0) >= 0
            return (
              <li
                key={asset.symbol}
                className="asset-row"
                onClick={() => onSelect?.(asset.symbol)}
                role={onSelect ? 'button' : undefined}
                tabIndex={onSelect ? 0 : undefined}
              >
                <AssetLogo symbol={asset.symbol} assetType={assetType} />
                <div className="asset-info">
                  <span className="asset-name">{asset.name}</span>
                  <span className="asset-symbol">{asset.symbol}</span>
                </div>
                <div className="asset-stats">
                  {asset.currentPrice != null && (
                    <span className="asset-price">
                      ${asset.currentPrice.toFixed(2)}
                    </span>
                  )}
                  {asset.changePercent != null && (
                    <span
                      className={`asset-change ${isPositive ? 'positive' : 'negative'}`}
                    >
                      {isPositive ? '▲' : '▼'} {Math.abs(asset.changePercent).toFixed(2)}%
                    </span>
                  )}
                  {asset.dayLow != null && asset.dayHigh != null && (
                    <span className="asset-range">
                      ${asset.dayLow.toFixed(2)} - ${asset.dayHigh.toFixed(2)}
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

export default AssetList
