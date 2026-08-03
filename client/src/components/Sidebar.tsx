import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import './Sidebar.css'

// Three destinations, not five: account settings and logging out moved to
// the account menu in the header, which is where people reach for them.
// That leaves the rail (and the phone's bottom bar) with only the places
// you actually navigate between.
const NAV_ITEMS: { to: string; label: string; icon: ReactNode }[] = [
  {
    to: '/',
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
    to: '/trade',
    label: 'Trade',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5V9m4.5 7.5V4.5M12 16.5v-5m4.5 5V7" />
      </svg>
    ),
  },
  {
    to: '/history',
    label: 'History',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="10" cy="10" r="7.25" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M10 5.5V10l3 2" />
      </svg>
    ),
  },
]

function Sidebar() {
  return (
    <nav className="sidebar" aria-label="Main">
      <ul className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            {/* Links, not buttons: these are places, and a place should be
                openable in a new tab, bookmarkable, and reachable with the
                browser's own back button. */}
            <NavLink
              to={item.to}
              // Only the dashboard matches exactly - /trade should stay lit
              // while looking at an asset underneath it.
              end={item.to === '/'}
              className={({ isActive }) => (isActive ? 'active' : '')}
              title={item.label}
            >
              <span className="sidebar-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="sidebar-label">{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default Sidebar
