import { useState } from 'react'
import type { AssetType } from '../api'
import './AssetLogo.css'

type AssetLogoProps = {
  symbol: string
  assetType: AssetType
}

function AssetLogo({ symbol, assetType }: AssetLogoProps) {
  const [failed, setFailed] = useState(false)
  const logoSymbol = symbol.split('-')[0]

  if (failed) {
    return <div className="asset-logo asset-logo-fallback">{logoSymbol.slice(0, 2)}</div>
  }

  const src =
    assetType === 'crypto'
      ? `https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/${logoSymbol.toLowerCase()}.png`
      : `https://assets.parqet.com/logos/symbol/${logoSymbol}`

  return <img className="asset-logo" src={src} alt="" onError={() => setFailed(true)} />
}

export default AssetLogo
