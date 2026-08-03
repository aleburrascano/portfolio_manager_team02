import type { User } from '../../api'
import AccountMenu from './AccountMenu'
import treetopIcon from '../../assets/treetop-icon.svg'
import './Header.css'

function Header({
  user,
  onOpenAccount,
  onLogout,
}: {
  user: User
  onOpenAccount: () => void
  onLogout: () => void
}) {
  return (
    <header className="app-header">
      <div className="wordmark">
        <img className="wordmark-mark" src={treetopIcon} alt="" width="28" height="28" />
        <span className="wordmark-text">TreeTop Trading</span>
      </div>
      <AccountMenu user={user} onOpenAccount={onOpenAccount} onLogout={onLogout} />
    </header>
  )
}

export default Header
