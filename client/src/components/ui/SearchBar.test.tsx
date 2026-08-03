import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import SearchBar from './SearchBar'

describe('SearchBar', () => {
  it('renders the given value', () => {
    render(<SearchBar value="AAPL" onChange={vi.fn()} />)
    expect(screen.getByRole('searchbox')).toHaveValue('AAPL')
  })

  it('calls onChange as the user types', async () => {
    const onChange = vi.fn()
    const typer = userEvent.setup()
    render(<SearchBar value="" onChange={onChange} />)

    await typer.type(screen.getByRole('searchbox'), 'A')
    expect(onChange).toHaveBeenCalledWith('A')
  })
})
