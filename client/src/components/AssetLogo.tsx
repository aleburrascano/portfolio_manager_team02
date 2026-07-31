import type { AssetType } from '../api'
import './AssetLogo.css'

type AssetLogoProps = {
  symbol: string
  assetType: AssetType
}

/**
 * A ticker's mark, set as type rather than fetched as a brand logo.
 *
 * The logos used to come from two third-party CDNs, which meant every list
 * render told someone else's server which tickers this user was looking at,
 * shifted the layout as images arrived, and left the app dependent on an
 * uptime nobody here controls. A statement identifies a holding by its
 * ticker anyway.
 */
function AssetLogo({ symbol, assetType }: AssetLogoProps) {
  // The part before the pair suffix: BTC-USD is Bitcoin, not "BTC-USD".
  const root = symbol.split('-')[0]

  return (
    <span className={`asset-logo asset-logo-${assetType}`} aria-hidden="true">
      {root.slice(0, 2)}
    </span>
  )
}

export default AssetLogo
