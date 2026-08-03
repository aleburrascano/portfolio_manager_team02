import type { AssetType } from '../../api'
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
const MONOGRAM_LENGTH = 2

function AssetLogo({ symbol, assetType }: AssetLogoProps) {
  const withoutPairSuffix = symbol.split('-')[0]

  return (
    <span className={`asset-logo asset-logo-${assetType}`} aria-hidden="true">
      {withoutPairSuffix.slice(0, MONOGRAM_LENGTH)}
    </span>
  )
}

export default AssetLogo
