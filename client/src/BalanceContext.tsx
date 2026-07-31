import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { fetchBalance } from './api'
import { BalanceContext } from './balance-context'

export function BalanceProvider({ userId, children }: { userId: number; children: ReactNode }) {
  const [balance, setBalance] = useState<number | null>(null)

  // Settles in a promise callback rather than after an await, so the
  // mount-time load below never sets state synchronously in the effect.
  const refreshBalance = useCallback(
    () => fetchBalance(userId).then(setBalance, () => setBalance(null)),
    [userId],
  )

  useEffect(() => {
    refreshBalance()
  }, [refreshBalance])

  return <BalanceContext.Provider value={{ balance, refreshBalance }}>{children}</BalanceContext.Provider>
}
