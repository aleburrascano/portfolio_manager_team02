import { useState } from 'react'
import './StockLogo.css'

type StockLogoProps = {
  symbol: string
}

function StockLogo({ symbol }: StockLogoProps) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return <div className="stock-logo stock-logo-fallback">{symbol.slice(0, 2)}</div>
  }

  return (
    <img
      className="stock-logo"
      src={`https://assets.parqet.com/logos/symbol/${symbol}`}
      alt=""
      onError={() => setFailed(true)}
    />
  )
}

export default StockLogo
