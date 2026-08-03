import { createContext, useContext } from 'react'

export type BalanceContextValue = {
  balance: number | null
  /**
   * Whether the balance request has finished, however it went. Distinct
   * from `balance !== null`, which can't tell "hasn't arrived yet" from
   * "couldn't be fetched" - panels keyed on the balance would otherwise
   * either fetch everything twice or hang on a failure.
   */
  settled: boolean
  refreshBalance: () => Promise<void>
}

export const BalanceContext = createContext<BalanceContextValue | null>(null)

export function useBalance() {
  const context = useContext(BalanceContext)
  if (!context) throw new Error('useBalance must be used within a BalanceProvider')
  return context
}
