import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { fetchBalance } from './api'
import { BalanceContext } from './balance-context'
import { useBondRedemptions, useOrderFills } from './realtime'

export function BalanceProvider({ userId, children }: { userId: number; children: ReactNode }) {
  const [balance, setBalance] = useState<number | null>(null)

  const refreshBalance = useCallback(
    () => fetchBalance(userId).then(setBalance, () => setBalance(null)),
    [userId],
  )

  useEffect(() => {
    refreshBalance()
  }, [refreshBalance])

  useOrderFills(refreshBalance)
  useBondRedemptions(refreshBalance)

  return <BalanceContext.Provider value={{ balance, refreshBalance }}>{children}</BalanceContext.Provider>
}
