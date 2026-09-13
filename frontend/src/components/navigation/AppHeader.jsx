import { Link } from 'react-router-dom'
import BrandLockup from './BrandLockup'
import NavIcon from './NavIcon'
import WorkspaceFinder from './WorkspaceFinder'
import OrganizationSwitcher from './OrganizationSwitcher'

function userLabel(user) {
  return user?.display_name || user?.username || user?.email || 'Account'
}

export default function AppHeader({ access, title, user, organizations, organizationId, onOrganizationChange, onMenuOpen, menuOpen, menuButtonRef, onLogout, logoutBusy, logoutError }) {
  return <header className='app-header'>
    <div className='app-header-leading'>
      <button ref={menuButtonRef} className='mobile-menu-button icon-button' type='button' onClick={onMenuOpen} aria-label='Open navigation' aria-expanded={menuOpen} aria-controls='mobile-navigation-drawer'>
        <NavIcon name='menu'/>
      </button>
      <div className='mobile-brand'><BrandLockup compact/></div>
      <div className='page-heading'>
        <span className='page-heading-context'>LabGoblin</span>
        <h1>{title}</h1>
      </div>
    </div>
    <div className='app-header-actions'>
      <WorkspaceFinder access={access}/>
      <OrganizationSwitcher organizations={organizations} organizationId={organizationId} onChange={onOrganizationChange} compact/>
      <details className='account-menu'>
        <summary aria-label={`Account menu for ${userLabel(user)}`}>
          <span className='account-avatar' aria-hidden='true'><NavIcon name='user'/></span>
          <span className='account-summary-copy'><strong>{userLabel(user)}</strong><span>{user?.role || 'User'}</span></span>
        </summary>
        <div className='account-menu-popover'>
          <div className='account-menu-identity'><strong>{userLabel(user)}</strong><span>{user?.email || user?.role || ''}</span></div>
          <Link to='/account/security'>Account security</Link>
          <button type='button' onClick={onLogout} disabled={logoutBusy}>{logoutBusy ? 'Signing out…' : 'Sign out'}</button>
          {logoutError ? <div className='msg error account-menu-error' role='alert'>{logoutError}</div> : null}
        </div>
      </details>
    </div>
  </header>
}
