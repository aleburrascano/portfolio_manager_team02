import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { fetchBalance } from './api'
import { BalanceContext } from './balance-context'

export function BalanceProvider({ userId, children }: { userId: number; children: ReactNode }) {
  const [balance, setBalance] = useState<number | null>(null)

  const refreshBalance = useCallback(async () => {
    try {
      setBalance(await fetchBalance(userId))
    } catch {
      setBalance(null)
    }
  }, [userId])

  useEffect(() => {
    refreshBalance()
  }, [refreshBalance])

  return <BalanceContext.Provider value={{ balance, refreshBalance }}>{children}</BalanceContext.Provider>
}
