import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { fetchBalance } from '../api'
import { BalanceContext } from './balance-context'
import { useBondRedemptions, useOrderFills } from '../hooks/realtime'

export function BalanceProvider({ userId, children }: { userId: number; children: ReactNode }) {
  const [loaded, setLoaded] = useState<{ userId: number; balance: number | null } | null>(null)

  const refreshBalance = useCallback(async () => {
    try {
      setLoaded({ userId, balance: await fetchBalance(userId) })
    } catch {
      setLoaded({ userId, balance: null })
    }
  }, [userId])

  useEffect(() => {
    async function loadBalance() {
      await refreshBalance()
    }

    void loadBalance()
  }, [refreshBalance])

  useOrderFills(refreshBalance)
  useBondRedemptions(refreshBalance)

  const settled = loaded !== null && loaded.userId === userId
  const balance = settled ? loaded.balance : null

  const value = useMemo(
    () => ({ balance, settled, refreshBalance }),
    [balance, settled, refreshBalance],
  )

  return <BalanceContext.Provider value={value}>{children}</BalanceContext.Provider>
}
