import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Sidebar from './Sidebar'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>,
  )
}

describe('Sidebar', () => {
  it('marks the current page as active', () => {
    renderAt('/trade/stock')
    expect(screen.getByRole('link', { name: /Trade/ })).toHaveClass('active')
    expect(screen.getByRole('link', { name: /Dashboard/ })).not.toHaveClass('active')
  })

  it('tells assistive tech which page is current', () => {
    renderAt('/trade/stock')
    expect(screen.getByRole('link', { name: /Trade/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: /Dashboard/ })).not.toHaveAttribute('aria-current')
  })

  it('keeps Trade active while looking at one asset', () => {
    renderAt('/trade/stock/NVDA')
    expect(screen.getByRole('link', { name: /Trade/ })).toHaveClass('active')
  })

  it('does not light the dashboard on every path', () => {
    renderAt('/history')
    expect(screen.getByRole('link', { name: /Dashboard/ })).not.toHaveClass('active')
    expect(screen.getByRole('link', { name: /History/ })).toHaveClass('active')
  })

  it('navigates by address', () => {
    renderAt('/')
    expect(screen.getByRole('link', { name: /History/ })).toHaveAttribute('href', '/history')
    expect(screen.getByRole('link', { name: /Trade/ })).toHaveAttribute('href', '/trade')
  })

  it('carries only the navigation destinations', () => {
    renderAt('/')

    expect(screen.getAllByRole('link')).toHaveLength(3)
    expect(screen.queryByRole('link', { name: /Log Out/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Account/ })).not.toBeInTheDocument()
  })
})
