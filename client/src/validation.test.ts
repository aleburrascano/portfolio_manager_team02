import { describe, expect, it } from 'vitest'
import {
  validateAmountInput,
  validateName,
  validatePassword,
  validateQuantityInput,
  validateUsername,
} from './validation'

describe('validateName', () => {
  it('rejects an empty value', () => {
    expect(validateName('  ', 'First name')).toBe('First name is required.')
  })

  it('rejects a value over 32 characters', () => {
    expect(validateName('a'.repeat(33), 'First name')).toMatch(/32 characters/)
  })

  it('rejects digits and other symbols', () => {
    expect(validateName('Ada9', 'First name')).toMatch(/letters, spaces/)
  })

  it('accepts letters, spaces, hyphens, and apostrophes', () => {
    expect(validateName("Anne-Marie O'Neil", 'First name')).toBeNull()
  })
})

describe('validateUsername', () => {
  it('rejects an empty value', () => {
    expect(validateUsername('')).toBe('Username is required.')
  })

  it('rejects spaces', () => {
    expect(validateUsername('a b')).toMatch(/letters, numbers/)
  })

  it('accepts letters, numbers, underscores, dots, and hyphens', () => {
    expect(validateUsername('ada_lovelace.1-2')).toBeNull()
  })
})

describe('validatePassword', () => {
  it('rejects fewer than 8 characters', () => {
    expect(validatePassword('short')).toBe('Password must be at least 8 characters.')
  })

  it('accepts 8 or more characters', () => {
    expect(validatePassword('password1')).toBeNull()
  })
})

describe('validateAmountInput', () => {
  it.each(['abc', '-5', '1.234', ''])('rejects %s', (raw) => {
    expect(validateAmountInput(raw)).not.toBeNull()
  })

  it('rejects zero', () => {
    expect(validateAmountInput('0')).toBe('Enter a positive amount.')
  })

  it('rejects amounts over the maximum', () => {
    expect(validateAmountInput('1000000001')).toBe('Amount is too large.')
  })

  it('accepts a plain integer', () => {
    expect(validateAmountInput('100')).toBeNull()
  })

  it('accepts up to 2 decimal places', () => {
    expect(validateAmountInput('99.99')).toBeNull()
  })
})

describe('validateQuantityInput', () => {
  it('rejects a non-numeric value', () => {
    expect(validateQuantityInput('abc')).not.toBeNull()
  })

  it('rejects zero', () => {
    expect(validateQuantityInput('0')).toBe('Enter a valid quantity.')
  })

  it('accepts up to 6 decimal places', () => {
    expect(validateQuantityInput('1.123456')).toBeNull()
  })

  it('rejects more than 6 decimal places', () => {
    expect(validateQuantityInput('1.1234567')).not.toBeNull()
  })
})
