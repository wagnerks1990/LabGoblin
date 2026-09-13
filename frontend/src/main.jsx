import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import useAuth from './hooks/useAuth'
import MessageBanner from './components/MessageBanner'
import ErrorBoundary from './components/ErrorBoundary'
import UnavailablePage from './components/UnavailablePage'
import { RequireCapability } from './components/AccessControl'
import AppLayout from './layouts/AppLayout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import VmsPage from './pages/VmsPage'
import CreateVmPage from './pages/CreateVmPage'
import SessionActivityPage from './pages/SessionActivityPage'
import TelemetryPage from './pages/TelemetryPage'
import PoolsPage from './pages/PoolsPage'
import PoolDetailPage from './pages/PoolDetailPage'
import OperationsPage from './pages/OperationsPage'
import TroubleshootingPage from './pages/TroubleshootingPage'
import ProxmoxSetupPage from './pages/ProxmoxSetupPage'
import ProxmoxInventoryPage from './pages/ProxmoxInventoryPage'
import ProxmoxAssetsPage from './pages/ProxmoxAssetsPage'
import UsersPage from './pages/UsersPage'
import GroupsPage from './pages/GroupsPage'
import EventsPage from './pages/EventsPage'
import SystemUpdatePage from './pages/SystemUpdatePage'
import OrganizationsPage from './pages/OrganizationsPage'
import AccountSecurityPage from './pages/AccountSecurityPage'
import ClassroomPage from './pages/ClassroomPage'
import BootstrapPage from './pages/BootstrapPage'
import TemplatesPage from './pages/TemplatesPage'
import './styles.css'
import './workspace.css'
import api from './services/api'

const ConsolePage = React.lazy(() => import('./pages/ConsolePage'))

function App() {
  const { user, setUser, loading, error: authError, refresh } = useAuth()
  const [message, setMessage] = React.useState(null)
  const [bootstrapRequired, setBootstrapRequired] = React.useState(null)
  const [bootstrapError, setBootstrapError] = React.useState(null)
  const [retrying, setRetrying] = React.useState(false)
  const loadBootstrapStatus = React.useCallback(async () => {
    setBootstrapError(null)
    try {
      const response = await api.get('/bootstrap/status')
      setBootstrapRequired(response.data.bootstrap_required)
    } catch {
      setBootstrapRequired(null)
      setBootstrapError('LabGoblin cannot check first-run status. Check the server connection and try again.')
    }
  }, [])
  React.useEffect(() => { loadBootstrapStatus() }, [loadBootstrapStatus])
  const retryStartup = async () => {
    setRetrying(true)
    await Promise.all([refresh(), loadBootstrapStatus()])
    setRetrying(false)
  }
  const completeBootstrap = async () => Promise.all([refresh(), loadBootstrapStatus()])

  if (authError || bootstrapError) return <UnavailablePage message={authError || bootstrapError} onRetry={retryStartup} busy={retrying || loading} />
  if (loading || bootstrapRequired === null) return <div className='login-wrap'>Loading...</div>
  if (bootstrapRequired) return <><MessageBanner message={message} /><BootstrapPage onComplete={completeBootstrap} setMessage={setMessage} /></>
  if (user === false) return <><MessageBanner message={message} /><LoginPage onLogin={refresh} setMessage={setMessage} /></>
  if (user.force_password_change) return <><MessageBanner message={message} /><div className='login-wrap'><div className='login-card login-card--wide'><AccountSecurityPage forceChange onChanged={refresh} setMessage={setMessage} /></div></div></>
  return <BrowserRouter><AppLayout setUser={setUser} user={user}><MessageBanner message={message} /><Routes>
    <Route path='/' element={<DashboardPage user={user} />} />
    <Route path='/account/security' element={<AccountSecurityPage onChanged={refresh} setMessage={setMessage} />} />
    <Route path='/vms' element={<VmsPage setMessage={setMessage} />} />
    <Route path='/console/:id' element={<React.Suspense fallback={<div className='panel'>Loading console…</div>}><ConsolePage /></React.Suspense>} />
    <Route path='/terminal/:id' element={<Navigate to='/vms' replace />} />
    <Route path='/create' element={<CreateVmPage setMessage={setMessage} />} />
    <Route path='/operations' element={<OperationsPage />} />
    <Route path='/classroom' element={<RequireCapability capability='tenantInstructor'><ClassroomPage setMessage={setMessage} /></RequireCapability>} />
    <Route path='/admin/sessions' element={<RequireCapability capability='tenantInstructor'><SessionActivityPage setMessage={setMessage} /></RequireCapability>} />
    <Route path='/events' element={<RequireCapability capability='tenantInstructor'><EventsPage /></RequireCapability>} />
    <Route path='/pools' element={<RequireCapability capability='tenantInstructor'><PoolsPage /></RequireCapability>} />
    <Route path='/pools/:id' element={<RequireCapability capability='tenantInstructor'><PoolDetailPage /></RequireCapability>} />
    <Route path='/admin/groups' element={<RequireCapability capability='tenantAdmin'><GroupsPage /></RequireCapability>} />
    <Route path='/telemetry' element={<RequireCapability capability='platformAdmin'><TelemetryPage /></RequireCapability>} />
    <Route path='/troubleshooting' element={<RequireCapability capability='platformAdmin'><TroubleshootingPage /></RequireCapability>} />
    <Route path='/admin/proxmox-setup' element={<RequireCapability capability='platformAdmin'><ProxmoxSetupPage /></RequireCapability>} />
    <Route path='/admin/proxmox-inventory' element={<RequireCapability capability='platformAdmin'><ProxmoxInventoryPage /></RequireCapability>} />
    <Route path='/admin/proxmox-assets' element={<RequireCapability capability='platformAdmin'><ProxmoxAssetsPage /></RequireCapability>} />
    <Route path='/admin/templates' element={<RequireCapability capability='platformAdmin'><TemplatesPage setMessage={setMessage} /></RequireCapability>} />
    <Route path='/admin/users' element={<RequireCapability capability='platformAdmin'><UsersPage /></RequireCapability>} />
    <Route path='/admin/organizations' element={<RequireCapability capability='platformAdmin'><OrganizationsPage /></RequireCapability>} />
    <Route path='/admin/system-update' element={<RequireCapability capability='platformAdmin'><SystemUpdatePage setMessage={setMessage} /></RequireCapability>} />
    <Route path='*' element={<Navigate to='/' />} />
  </Routes></AppLayout></BrowserRouter>
}

ReactDOM.createRoot(document.getElementById('root')).render(<ErrorBoundary><App /></ErrorBoundary>)
