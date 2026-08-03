import type { Asset, AssetType } from '../../api'
import { formatCurrency, formatNumber } from '../../lib/format'
import AssetLogo from '../ui/AssetLogo'
import './AssetList.css'

type AssetListProps = {
  title: string
  assets: Asset[]
  assetType: AssetType
  loading?: boolean
  /** Text shown when there are no assets, e.g. why a search came back empty. */
  emptyMessage?: string
  onSelect?: (symbol: string) => void
}

const SKELETON_ROWS = 6

function AssetList({
  title,
  assets,
  assetType,
  loading,
  emptyMessage = 'No assets to show.',
  onSelect,
}: AssetListProps) {
  return (
    <div className="asset-list">
      <h2 className="section-title">{title}</h2>
      {loading ? (
        <ul aria-hidden="true">
          {Array.from({ length: SKELETON_ROWS }, (_, index) => (
            <li key={index} className="asset-row asset-row-skeleton">
              <span className="skeleton skeleton-logo" />
              <span className="skeleton skeleton-name" />
              <span className="skeleton skeleton-price" />
            </li>
          ))}
        </ul>
      ) : assets.length === 0 ? (
        <p className="asset-list-status">{emptyMessage}</p>
      ) : (
        <ul>
          {assets.map((asset) => {
            const isPositive = (asset.change ?? 0) >= 0
            const content = (
              <>
                <AssetLogo symbol={asset.symbol} assetType={assetType} />
                <span className="asset-info">
                  <span className="asset-name" title={asset.name}>
                    {asset.name}
                  </span>
                  <span className="asset-symbol">{asset.symbol}</span>
                </span>
                <span className="asset-stats">
                  {asset.currentPrice != null && (
                    <span className="figure asset-price">
                      {formatCurrency(asset.currentPrice)}
                    </span>
                  )}
                  {asset.changePercent != null && (
                    <span
                      className={`figure asset-change ${isPositive ? 'positive' : 'negative'}`}
                    >
                      {isPositive ? '▲' : '▼'} {formatNumber(Math.abs(asset.changePercent), 2)}%
                    </span>
                  )}
                  {asset.dayLow != null && asset.dayHigh != null && (
                    <span className="figure asset-range">
                      {formatCurrency(asset.dayLow)} - {formatCurrency(asset.dayHigh)}
                    </span>
                  )}
                </span>
              </>
            )

            return (
              <li key={asset.symbol}>
                {onSelect ? (
                  <button type="button" className="asset-row" onClick={() => onSelect(asset.symbol)}>
                    {content}
                  </button>
                ) : (
                  <div className="asset-row">{content}</div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export default AssetList
