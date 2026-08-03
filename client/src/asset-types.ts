import { createContext, useContext } from 'react'
import type { AssetType, AssetTypeInfo } from './api'

export type AssetTypesContextValue = {
  /** In the server's own registry order, which is the order tabs appear in. */
  types: AssetTypeInfo[]
  byType: Partial<Record<AssetType, AssetTypeInfo>>
}

/**
 * The three types this app shipped with.
 *
 * Not a second source of truth - the server's list replaces it wholesale
 * the moment it arrives. It is the context's default rather than a null,
 * because unlike a balance, "which asset types exist" has a sensible answer
 * without a user or a network: a slow or failed request should leave
 * someone with usable tabs, not an empty trade screen. That is the same
 * best-effort treatment the rest of the app gives market data.
 */
export const DEFAULT_ASSET_TYPES: AssetTypeInfo[] = [
  { assetType: 'stock', label: 'Stocks', streams: true, supportsLimitOrders: true },
  { assetType: 'crypto', label: 'Crypto', streams: true, supportsLimitOrders: true },
  { assetType: 'bond', label: 'Bonds', streams: false, supportsLimitOrders: false },
]

export function indexByType(types: AssetTypeInfo[]): AssetTypesContextValue {
  const byType: Partial<Record<AssetType, AssetTypeInfo>> = {}
  for (const info of types) byType[info.assetType] = info
  return { types, byType }
}

export const AssetTypesContext = createContext<AssetTypesContextValue>(
  indexByType(DEFAULT_ASSET_TYPES),
)

/**
 * What the server says its asset types are.
 *
 * Fetched once for the whole session - the registry is a property of the
 * deployment, not of the user - so a component asking "does this type take
 * limit orders" or "should this show a live indicator" is reading an answer
 * already in memory rather than hardcoding one.
 */
export function useAssetTypes(): AssetTypesContextValue {
  return useContext(AssetTypesContext)
}

/** The display label for a type, falling back to the raw value. */
export function useAssetTypeLabel(assetType: AssetType | string): string {
  const { byType } = useAssetTypes()
  return byType[assetType as AssetType]?.label ?? assetType
}
