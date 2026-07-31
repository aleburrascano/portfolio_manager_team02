import { useEffect, useState } from 'react'
import { fetchPopularAssets, type Asset, type AssetType } from '../api'
import { useLiveQuotes } from '../realtime'
import { formatCurrency, formatNumber } from '../format'
import './TickerRail.css'

type TickerAsset = Asset & { assetType: AssetType }

function TickerRail() {
  const [stocks, setStocks] = useState<Asset[]>([])
  const [cryptos, setCryptos] = useState<Asset[]>([])

  useEffect(() => {
    let cancelled = false
    fetchPopularAssets('stock')
      .then((assets) => !cancelled && setStocks(assets.slice(0, 5)))
      .catch(() => {
        // The rail is ambient decoration - a watchlist that fails to load
        // just stays empty rather than surfacing an error anywhere.
      })
    fetchPopularAssets('crypto')
      .then((assets) => !cancelled && setCryptos(assets.slice(0, 4)))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const liveStock = useLiveQuotes('stock', stocks.map((a) => a.symbol))
  const liveCrypto = useLiveQuotes('crypto', cryptos.map((a) => a.symbol))

  const items: TickerAsset[] = [
    ...stocks.map((asset) => ({ ...asset, ...liveStock[asset.symbol], assetType: 'stock' as const })),
    ...cryptos.map((asset) => ({ ...asset, ...liveCrypto[asset.symbol], assetType: 'crypto' as const })),
  ]

  if (items.length === 0) return <div className="ticker-rail" aria-hidden="true" />

  // Duplicated so the CSS animation can loop the track by exactly -50% with
  // no seam - reduced motion falls back to a plain scrollable strip instead.
  const track = [...items, ...items]

  return (
    <div className="ticker-rail" role="marquee" aria-label="Live market prices">
      <div className="ticker-track">
        {track.map((asset, index) => {
          const isPositive = (asset.changePercent ?? 0) >= 0
          return (
            <span className="ticker-item" key={`${asset.symbol}-${index}`}>
              <span className="ticker-symbol">{asset.symbol}</span>
              <span className="figure ticker-price">
                {asset.currentPrice != null ? formatCurrency(asset.currentPrice) : '—'}
              </span>
              {asset.changePercent != null && (
                <span className={`figure ticker-change ${isPositive ? 'positive' : 'negative'}`}>
                  {isPositive ? '▲' : '▼'} {formatNumber(Math.abs(asset.changePercent), 2)}%
                </span>
              )}
            </span>
          )
        })}
      </div>
    </div>
  )
}

export default TickerRail
