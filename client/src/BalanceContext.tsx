import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { fetchBalance } from './api'
import { BalanceContext } from './balance-context'
import { useOrderFills } from './realtime'

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

  // A fill moves cash without this session having asked for anything, and
  // the balance is keyed off by the dashboard and the trade panel - so
  // refreshing it here is what makes the rest of the screen follow.
  useOrderFills(refreshBalance)

  return <BalanceContext.Provider value={{ balance, refreshBalance }}>{children}</BalanceContext.Provider>
}
