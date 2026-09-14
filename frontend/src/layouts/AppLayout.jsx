import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { listOrganizations } from '../services/organizationApi'
import { logoutSession } from '../services/authApi'
import { AccessContext } from '../components/AccessControl'
import { deriveCapabilities } from '../auth/access'
import AppHeader from '../components/navigation/AppHeader'
import AppSidebar from '../components/navigation/AppSidebar'
import MobileBottomNav from '../components/navigation/MobileBottomNav'
import MobileNavigation from '../components/navigation/MobileNavigation'
import { pageTitleForPath } from '../navigation/appNavigation'

export default function AppLayout({ children, setUser, user }) {
  const nav = useNavigate()
  const loc = useLocation()
  const [organizations, setOrganizations] = useState([])
  const [organizationReady, setOrganizationReady] = useState(false)
  const [organizationError, setOrganizationError] = useState('')
  const [organizationId, setOrganizationId] = useState(localStorage.getItem('organization_id') || '')
  const [logoutError, setLogoutError] = useState('')
  const [logoutBusy, setLogoutBusy] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(localStorage.getItem('labgoblin_sidebar_collapsed') === 'true')
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const mobileMenuButtonRef = useRef(null)
  const logout = async () => {
    setLogoutBusy(true)
    setLogoutError('')
    try {
      await logoutSession()
      localStorage.removeItem('organization_id')
      setUser(false)
      nav('/')
    } catch (error) {
      const detail = error?.response?.data?.detail
      setLogoutError(typeof detail === 'string' ? detail : 'Sign out failed. Your server session is still active; try again.')
    } finally {
      setLogoutBusy(false)
    }
  }
  useEffect(() => {
    let active = true
    listOrganizations().then((rows) => {
      if (!active) return
      const available = Array.isArray(rows) ? rows : []
      setOrganizations(available)
      const stored = localStorage.getItem('organization_id')
      const platformAdmin = String(user?.role || '').toLowerCase() === 'admin'
      const selected = available.find((item) => String(item.id) === stored) || (!platformAdmin ? available[0] : null)
      if (selected) {
        localStorage.setItem('organization_id', String(selected.id))
        setOrganizationId(String(selected.id))
      } else {
        localStorage.removeItem('organization_id')
        if (available.length === 0) setOrganizationError('No active organization membership is available for this account.')
      }
      setOrganizationReady(true)
    }).catch((error) => {
      if (!active) return
      setOrganizationError(error?.response?.data?.detail || 'Unable to load organization access.')
      setOrganizationReady(true)
    })
    return () => { active = false }
  }, [user?.role])
  const changeOrganization = (event) => {
    const nextOrganizationId = event.target.value
    localStorage.setItem('organization_id', nextOrganizationId)
    setOrganizationId(nextOrganizationId)
    window.dispatchEvent(new CustomEvent('organization:changed', { detail: { organizationId: nextOrganizationId } }))
  }
  const closeMobileNavigation = useCallback(() => setMobileNavigationOpen(false), [])
  const openMobileNavigation = () => setMobileNavigationOpen(true)
  const toggleSidebar = () => setSidebarCollapsed(previous => {
    const next = !previous
    localStorage.setItem('labgoblin_sidebar_collapsed', String(next))
    return next
  })
  const activeOrganization = organizations.find(organization => String(organization.id) === organizationId)
  const tenantRole = activeOrganization?.role
  const access = deriveCapabilities(user, tenantRole)
  const accountRoute = loc.pathname.startsWith('/account/security')
  const organizationBootstrapRoute = access.platformAdmin && loc.pathname.startsWith('/admin/organizations')
  const canRenderWithoutOrganization = accountRoute || organizationBootstrapRoute
  const content = !organizationReady && !accountRoute
    ? <section className='panel' role='status'>Selecting organization…</section>
    : organizationError && !canRenderWithoutOrganization
      ? <section className='panel error' role='alert'>{organizationError}</section>
      : !organizationId && !canRenderWithoutOrganization
        ? <section className='panel'>Select an organization to continue.</section>
        : <div className='route-content' key={organizationId || 'no-organization'}>{children}</div>

  return <AccessContext.Provider value={access}>
    <a className='skip-link' href='#main-content'>Skip to main content</a>
    <div className={`app-shell${sidebarCollapsed ? ' app-shell-sidebar-collapsed' : ''}`}>
      <AppSidebar access={access} collapsed={sidebarCollapsed} onToggle={toggleSidebar}/>
      <div className='app-workspace'>
        <AppHeader
          access={access}
          title={loc.pathname === '/' && !access.tenantInstructor && !access.platformAdmin ? 'My labs' : pageTitleForPath(loc.pathname)}
          user={user}
          organizations={organizations}
          organizationId={organizationId}
          onOrganizationChange={changeOrganization}
          onMenuOpen={openMobileNavigation}
          menuOpen={mobileNavigationOpen}
          menuButtonRef={mobileMenuButtonRef}
          onLogout={logout}
          logoutBusy={logoutBusy}
          logoutError={logoutError}
        />
        <main className='content' id='main-content' tabIndex={-1}>{content}</main>
      </div>
      <MobileNavigation access={access} open={mobileNavigationOpen} onClose={closeMobileNavigation} returnFocusRef={mobileMenuButtonRef}/>
      <MobileBottomNav access={access} onMore={openMobileNavigation}/>
    </div>
  </AccessContext.Provider>
}
