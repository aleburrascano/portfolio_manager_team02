import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { fetchBalance } from '../api'
import { BalanceContext } from './balance-context'
import { useBondRedemptions, useOrderFills } from '../hooks/realtime'

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
    async function loadBalance() {
      await refreshBalance()
    }

    void loadBalance()
  }, [refreshBalance])

  useOrderFills(refreshBalance)
  useBondRedemptions(refreshBalance)

  return <BalanceContext.Provider value={{ balance, refreshBalance }}>{children}</BalanceContext.Provider>
}
