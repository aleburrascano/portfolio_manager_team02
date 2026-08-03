import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { User } from '../../api'
import ConfirmDialog from '../ui/ConfirmDialog'
import './AccountMenu.css'

function initials(user: User) {
  return `${user.firstName[0] ?? ''}${user.lastName[0] ?? ''}`.toUpperCase()
}

/**
 * The account control in the top-right corner.
 *
 * Positioned `fixed` from the trigger's measured rect rather than absolutely
 * inside the header: the app shell is `overflow: hidden` so it never scrolls
 * as a whole, which would clip an absolutely-positioned panel.
 */
function AccountMenu({
  user,
  onOpenAccount,
  onLogout,
}: {
  user: User
  onOpenAccount: () => void
  onLogout: () => void
}) {
  const [open, setOpen] = useState(false)
  const [confirmingLogout, setConfirmingLogout] = useState(false)
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!open) return
    const rect = triggerRef.current?.getBoundingClientRect()
    if (rect) {
      setPosition({ top: rect.bottom + 8, right: window.innerWidth - rect.right })
    }
  }, [open])

  useEffect(() => {
    if (!open) return

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node
      if (!menuRef.current?.contains(target) && !triggerRef.current?.contains(target)) {
        setOpen(false)
      }
    }

    function handleReflow() {
      setOpen(false)
    }

    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('resize', handleReflow)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('resize', handleReflow)
    }
  }, [open])

  useEffect(() => {
    if (open) menuRef.current?.querySelector('button')?.focus()
  }, [open])

  function choose(action: () => void) {
    setOpen(false)
    action()
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="account-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="avatar" aria-hidden="true">
          {initials(user)}
        </span>
        <span className="account-menu-name">
          {user.firstName} {user.lastName}
        </span>
        <span className="account-menu-chevron" aria-hidden="true">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="m6 8 4 4 4-4" />
          </svg>
        </span>
        <span className="visually-hidden">Account menu</span>
      </button>

      {open && (
        <div
          ref={menuRef}
          className="account-menu"
          role="menu"
          style={position ? { top: position.top, right: position.right } : { visibility: 'hidden' }}
        >
          <p className="account-menu-header">
            Signed in as <span className="account-menu-username">{user.username}</span>
          </p>
          <button type="button" role="menuitem" onClick={() => choose(onOpenAccount)}>
            Account settings
          </button>
          <button
            type="button"
            role="menuitem"
            className="account-menu-danger"
            onClick={() => choose(() => setConfirmingLogout(true))}
          >
            Log Out
          </button>
        </div>
      )}

      {confirmingLogout && (
        <ConfirmDialog
          title="Log out?"
          message="You'll need to sign in again to get back to your portfolio."
          confirmLabel="Log Out"
          destructive
          onConfirm={onLogout}
          onCancel={() => setConfirmingLogout(false)}
        />
      )}
    </>
  )
}

export default AccountMenu
