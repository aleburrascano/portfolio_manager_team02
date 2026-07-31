import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ConfirmDialog from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('renders the title and message', () => {
    render(<ConfirmDialog title="Log out?" message="Are you sure?" onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Log out?' })).toBeInTheDocument()
    expect(screen.getByText('Are you sure?')).toBeInTheDocument()
  })

  it('calls onConfirm when the confirm button is clicked', async () => {
    const onConfirm = vi.fn()
    const typer = userEvent.setup()
    render(<ConfirmDialog title="Log out?" confirmLabel="Log Out" onConfirm={onConfirm} onCancel={vi.fn()} />)

    await typer.click(screen.getByRole('button', { name: 'Log Out' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('calls onCancel when the cancel button is clicked', async () => {
    const onCancel = vi.fn()
    const typer = userEvent.setup()
    render(<ConfirmDialog title="Log out?" onConfirm={vi.fn()} onCancel={onCancel} />)

    await typer.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('calls onCancel when the backdrop is clicked but not when the card is', async () => {
    const onCancel = vi.fn()
    const typer = userEvent.setup()
    render(<ConfirmDialog title="Log out?" onConfirm={vi.fn()} onCancel={onCancel} />)

    await typer.click(screen.getByRole('heading', { name: 'Log out?' }))
    expect(onCancel).not.toHaveBeenCalled()

    await typer.click(screen.getByRole('alertdialog').parentElement!)
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('calls onCancel on Escape', async () => {
    const onCancel = vi.fn()
    const typer = userEvent.setup()
    render(<ConfirmDialog title="Log out?" onConfirm={vi.fn()} onCancel={onCancel} />)

    await typer.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalledOnce()
  })
})
