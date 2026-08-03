import { useState } from 'react'
import type { AssetType } from '../../api'
import './AssetLogo.css'

type AssetLogoProps = {
  symbol: string
  assetType: AssetType
}

const MONOGRAM_LENGTH = 2

/** Where this ticker's brand mark lives, or null for a type that has none. */
function logoUrl(root: string, assetType: AssetType): string | null {
  if (assetType === 'crypto') {
    return `https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/${root.toLowerCase()}.png`
  }
  if (assetType === 'stock') {
    return `https://assets.parqet.com/logos/symbol/${root}`
  }
  return null
}

/**
 * A ticker's mark: its brand logo where one is available, its monogram
 * otherwise.
 *
 * The monogram is not a fallback that replaces the logo - it is always
 * rendered, and the logo fades in on top of it once it has loaded. The tile
 * is therefore its final size from the first paint, so a list of them can't
 * shift as images arrive, and a CDN that is slow, blocked, down, or simply
 * doesn't know this ticker costs a logo rather than an empty square.
 *
 * The logos are third-party requests, so the CDN can see which tickers are
 * being viewed. `no-referrer` keeps it from also learning which page they
 * were viewed from.
 */
function AssetLogo({ symbol, assetType }: AssetLogoProps) {
  const withoutPairSuffix = symbol.split('-')[0]
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)

  const src = failed ? null : logoUrl(withoutPairSuffix, assetType)

  return (
    <span className={`asset-logo asset-logo-${assetType}`} aria-hidden="true">
      {withoutPairSuffix.slice(0, MONOGRAM_LENGTH)}
      {src && (
        <img
          className={`asset-logo-mark${loaded ? ' is-loaded' : ''}`}
          src={src}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      )}
    </span>
  )
}

export default AssetLogo
