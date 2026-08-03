export function validateName(value: string, field: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return `${field} is required.`
  if (trimmed.length > 32) return `${field} must be 32 characters or fewer.`
  if (!/^[A-Za-z' -]+$/.test(trimmed)) {
    return `${field} can only contain letters, spaces, hyphens, and apostrophes.`
  }
  return null
}

export function validateUsername(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return 'Username is required.'
  if (trimmed.length > 32) return 'Username must be 32 characters or fewer.'
  if (!/^[A-Za-z0-9_.-]+$/.test(trimmed)) {
    return 'Username can only contain letters, numbers, underscores, dots, and hyphens.'
  }
  return null
}

const MIN_PASSWORD_LENGTH = 8

export function validatePassword(value: string): string | null {
  if (value.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
  }
  return null
}

export function validateAmountInput(raw: string): string | null {
  const trimmed = raw.trim()
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) {
    return 'Enter an amount with at most 2 decimal places.'
  }
  const value = Number(trimmed)
  if (value <= 0) return 'Enter a positive amount.'
  if (value > 1_000_000_000) return 'Amount is too large.'
  return null
}

export function validateQuantityInput(raw: string): string | null {
  const trimmed = raw.trim()
  if (!/^\d+(\.\d{1,6})?$/.test(trimmed)) {
    return 'Enter a quantity with at most 6 decimal places.'
  }
  if (Number(trimmed) <= 0) return 'Enter a valid quantity.'
  return null
}
