import { useState, type ReactNode } from 'react'
import ConfirmDialog from './ConfirmDialog'
import './Sidebar.css'

export type Page = 'dashboard' | 'trade-assets' | 'transaction-history' | 'account'

const NAV_ITEMS: { page: Page; label: string; icon: ReactNode }[] = [
  {
    page: 'dashboard',
    label: 'Dashboard',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1.5" />
        <rect x="11" y="2.5" width="6.5" height="6.5" rx="1.5" />
        <rect x="2.5" y="11" width="6.5" height="6.5" rx="1.5" />
        <rect x="11" y="11" width="6.5" height="6.5" rx="1.5" />
      </svg>
    ),
  },
  {
    page: 'trade-assets',
    label: 'Trade Assets',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5V9m4.5 7.5V4.5M12 16.5v-5m4.5 5V7" />
      </svg>
    ),
  },
  {
    page: 'transaction-history',
    label: 'Transaction History',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="10" cy="10" r="7.25" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M10 5.5V10l3 2" />
      </svg>
    ),
  },
  {
    page: 'account',
    label: 'Account',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2.5" y="4" width="15" height="12" rx="2" />
        <circle cx="7.5" cy="9.5" r="1.75" />
        <path strokeLinecap="round" d="M5.5 13.5c0.5-1.5 1.8-2.25 2-2.25s1.5 0.75 2 2.25" />
        <path strokeLinecap="round" d="M12 8.5h3.5M12 11.5h3.5" />
      </svg>
    ),
  },
]

const LOGOUT_ICON = (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="10" cy="6.5" r="3.25" />
    <path strokeLinecap="round" d="M3.5 17c0-3.59 2.91-6.5 6.5-6.5s6.5 2.91 6.5 6.5" />
  </svg>
)

function Sidebar({
  page,
  onNavigate,
  onLogout,
}: {
  page: Page
  onNavigate: (page: Page) => void
  onLogout: () => void
}) {
  const [confirmingLogout, setConfirmingLogout] = useState(false)

  return (
    <>
      <nav className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-brand-mark">PM</span>
          <span className="sidebar-brand-name">Portfolio Manager</span>
        </div>
        <ul className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <li key={item.page}>
              <button
                type="button"
                className={page === item.page ? 'active' : ''}
                onClick={() => onNavigate(item.page)}
              >
                <span className="sidebar-icon">{item.icon}</span>
                <span className="sidebar-label">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>

        <button type="button" className="sidebar-logout" onClick={() => setConfirmingLogout(true)}>
          <span className="sidebar-icon">{LOGOUT_ICON}</span>
          <span className="sidebar-label">Log Out</span>
        </button>
      </nav>

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

export default Sidebar
