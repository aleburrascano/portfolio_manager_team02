import type { ReactNode } from 'react'
import './Sidebar.css'

export type Page = 'dashboard' | 'trade-assets' | 'transaction-history' | 'account'

// Three destinations, not five: account settings and logging out moved to
// the account menu in the header, which is where people reach for them.
// That leaves the rail (and the phone's bottom bar) with only the places
// you actually navigate between.
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
    label: 'Trade',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5V9m4.5 7.5V4.5M12 16.5v-5m4.5 5V7" />
      </svg>
    ),
  },
  {
    page: 'transaction-history',
    label: 'History',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="10" cy="10" r="7.25" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M10 5.5V10l3 2" />
      </svg>
    ),
  },
]

function Sidebar({ page, onNavigate }: { page: Page; onNavigate: (page: Page) => void }) {
  return (
    <nav className="sidebar" aria-label="Main">
      <ul className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <li key={item.page}>
            <button
              type="button"
              className={page === item.page ? 'active' : ''}
              aria-current={page === item.page ? 'page' : undefined}
              title={item.label}
              onClick={() => onNavigate(item.page)}
            >
              <span className="sidebar-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="sidebar-label">{item.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default Sidebar
