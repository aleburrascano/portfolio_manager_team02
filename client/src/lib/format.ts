export function formatCurrency(value: number, decimals = 2) {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

export function formatNumber(value: number, decimals = 0) {
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/** Takes a fraction (0.0525) and prints it as "5.25%". */
export function formatPercent(value: number, decimals = 2) {
  return `${(value * 100).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}%`
}
