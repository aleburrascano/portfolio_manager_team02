import { useState } from 'react'
import './AssetLogo.css'

type AssetLogoProps = {
  symbol: string
}

function AssetLogo({ symbol }: AssetLogoProps) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return <div className="asset-logo asset-logo-fallback">{symbol.slice(0, 2)}</div>
  }

  return (
    <img
      className="asset-logo"
      src={`https://assets.parqet.com/logos/symbol/${symbol}`}
      alt=""
      onError={() => setFailed(true)}
    />
  )
}

export default AssetLogo
