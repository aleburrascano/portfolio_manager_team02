import { apiFetch, post } from './client'
import type { AssetType } from './assets'

export type PortfolioBreakdown = { cash: number; stock: number; crypto: number }

export type Transaction = {
  transactionId: number
  type: 'cash' | AssetType
  transactionType: string
  transactionDate: string
  signedAmount: number
  ticker?: string
  qty?: number
  price?: number
}

export type TransactionType = 'deposit' | 'withdraw'

export async function fetchBalance(userId: number): Promise<number> {
  const data = await apiFetch<{ balance: number }>(`/users/${userId}/balance`, 'Failed to fetch balance')
  return data.balance
}

export async function fetchPortfolioBreakdown(userId: number): Promise<PortfolioBreakdown> {
  const data = await apiFetch<Partial<PortfolioBreakdown>>(
    `/users/${userId}/portfolio`,
    'Failed to fetch portfolio breakdown',
  )
  return { cash: data.cash || 0, stock: data.stock || 0, crypto: data.crypto || 0 }
}

export async function fetchTransactions(userId: number): Promise<Transaction[]> {
  const data = await apiFetch<{ transactions: Transaction[] }>(
    `/users/${userId}/transactions`,
    'Failed to fetch transaction history',
  )
  return data.transactions
}

export async function submitCashTransaction(
  userId: number,
  type: TransactionType,
  amount: number,
): Promise<{ message: string }> {
  return apiFetch(`/users/${userId}/${type}`, `Unable to ${type} funds!`, post({ amount }))
}
