import { createContext, useContext } from 'react'

export type BalanceContextValue = {
  balance: number | null
  refreshBalance: () => Promise<void>
}

export const BalanceContext = createContext<BalanceContextValue | null>(null)

export function useBalance() {
  const context = useContext(BalanceContext)
  if (!context) throw new Error('useBalance must be used within a BalanceProvider')
  return context
}
