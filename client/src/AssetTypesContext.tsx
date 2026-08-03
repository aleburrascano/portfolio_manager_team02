import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { fetchAssetTypes, type AssetTypeInfo } from './api'
import { AssetTypesContext, DEFAULT_ASSET_TYPES, indexByType } from './asset-types'

export function AssetTypesProvider({ children }: { children: ReactNode }) {
  const [types, setTypes] = useState<AssetTypeInfo[]>(DEFAULT_ASSET_TYPES)

  useEffect(() => {
    let cancelled = false

    fetchAssetTypes()
      .then((result) => {
        if (!cancelled && result.length > 0) setTypes(result)
      })
      .catch(() => {
        if (!cancelled) setTypes(DEFAULT_ASSET_TYPES)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo(() => indexByType(types), [types])

  return <AssetTypesContext.Provider value={value}>{children}</AssetTypesContext.Provider>
}
