// Client-side validation for form inputs, checked before hitting the API.
// Operates on the raw string from the input (not the parsed Number) so
// decimal-place checks aren't thrown off by floating-point rounding.

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

// Mirrors MIN_PASSWORD_LENGTH in the server's auth routes.
export function validatePassword(value: string): string | null {
  if (value.length < 8) return 'Password must be at least 8 characters.'
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
