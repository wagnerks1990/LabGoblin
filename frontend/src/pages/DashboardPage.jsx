import { useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import { AccessContext } from '../components/AccessControl'
import NavIcon from '../components/navigation/NavIcon'
import { CapacityMeter } from '../components/ui/WorkspaceKit'
import api from '../services/api'

function formatBytes(value) {
  if (value == null) return '—'
  const bytes = Number(value)
  if (!Number.isFinite(bytes)) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let amount = bytes / 1024
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit += 1 }
  return `${amount.toFixed(1)} ${units[unit]}`
}

function formatPercent(value) {
  return value != null && Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'
}

function formatUptime(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) return '—'
  const value = Number(seconds)
  return `${Math.floor(value / 86400)}d ${Math.floor((value % 86400) / 3600)}h`
}

function errorDetail(error, fallback) {
  const value = error?.response?.data?.detail
  return typeof value === 'string' ? value : value ? JSON.stringify(value) : fallback
}

export default function DashboardPage({ user }) {
  const access = useContext(AccessContext)
  const isPlatformAdmin = String(user?.role || '').toLowerCase() === 'admin'
  const [vms, setVms] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [resourceStats, setResourceStats] = useState(null)
  const [resourceLoading, setResourceLoading] = useState(false)
  const [resourceError, setResourceError] = useState('')
  const [nodeStorage, setNodeStorage] = useState({})
  const [resourceNotices, setResourceNotices] = useState([])
  const [assetReadiness, setAssetReadiness] = useState(null)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [vmResponse, templateResponse] = await Promise.all([api.get('/vms'), api.get('/templates')])
      setVms(Array.isArray(vmResponse.data) ? vmResponse.data : [])
      setTemplates(Array.isArray(templateResponse.data) ? templateResponse.data : [])
    } catch (requestError) {
      setError(errorDetail(requestError, 'Dashboard information could not be loaded.'))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadInfrastructure = useCallback(async () => {
    if (!isPlatformAdmin) return
    setResourceLoading(true)
    setResourceError('')
    setResourceNotices([])
    try {
      const response = await api.get('/admin/proxmox/resource-stats')
      setResourceStats(response.data)
      const [clustersResult, readinessResult] = await Promise.allSettled([
        api.get('/admin/proxmox/clusters'), api.get('/admin/proxmox/assets/readiness'),
      ])
      setResourceNotices([...(readinessResult.status === 'rejected' ? ['Asset readiness could not be checked.'] : []), ...(clustersResult.status === 'rejected' ? ['Storage discovery could not load cluster configuration.'] : [])])
      setAssetReadiness(readinessResult.status === 'fulfilled' ? readinessResult.value.data : null)
      if (clustersResult.status === 'fulfilled') {
        const active = (Array.isArray(clustersResult.value.data) ? clustersResult.value.data : []).find(item => item.is_active)
        if (active?.id) {
          const storageResponse = await api.get(`/admin/proxmox/clusters/${active.id}/storage`)
          const grouped = {}
          for (const item of (Array.isArray(storageResponse.data) ? storageResponse.data : [])) {
            const node = item?.node || 'unknown'
            grouped[node] = [...(grouped[node] || []), item]
          }
          setNodeStorage(grouped)
        } else setNodeStorage({})
      } else setNodeStorage({})
    } catch (requestError) {
      setResourceStats(null)
      setResourceError(errorDetail(requestError, 'Infrastructure status could not be loaded.'))
    } finally {
      setResourceLoading(false)
    }
  }, [isPlatformAdmin])

  useEffect(() => { loadSummary() }, [loadSummary])
  useEffect(() => { if (isPlatformAdmin) loadInfrastructure() }, [isPlatformAdmin, loadInfrastructure])

  const summary = useMemo(() => ({
    total: vms.length,
    running: vms.filter(vm => vm.status === 'running').length,
    stopped: vms.filter(vm => vm.status === 'stopped').length,
    provisioning: vms.filter(vm => ['pending', 'provisioning', 'creating'].includes(String(vm.status).toLowerCase())).length,
  }), [vms])

  if (loading) return <LoadingState label='Loading your lab overview…' />
  if (error) return <ErrorState message={error} onRetry={loadSummary} retrying={loading} />

  return <section>
    <div className='workspace-hero'>
      <div className='hero-copy'><p className='eyebrow'>Welcome back, {user?.display_name || user?.username || 'learner'}</p><h2>Real Skills.<br/><span>Virtual Machines.</span></h2><p>Your LabGoblin workspace brings machines, learning, and lab activity together.</p><div className='ui-cluster'><Link className='btn' to='/vms'>Open lab machines</Link><Link className='btn ui-button--secondary' to={access.tenantInstructor ? '/classroom' : '/create'}>{access.tenantInstructor ? 'Manage classes & labs' : 'Explore assignments'}</Link></div></div>
      <div className='hero-brand' aria-hidden='true'><img src='/brand/labgoblin-icon.svg' alt=''/><span>BUILD. DEPLOY.<br/>LEARN. REPEAT.</span></div>
    </div>
    <div className='workspace-section-title'><h3>Your workspace at a glance</h3><button type='button' className='ui-button--secondary' onClick={loadSummary}>Refresh overview</button></div>
    <div className='card-grid' aria-label='Virtual machine summary'>
      <div className='stat-card'><div className='label'>TOTAL VMS</div><div className='value'>{summary.total}</div></div>
      <div className='stat-card'><div className='label'>RUNNING</div><div className='value'>{summary.running}</div></div>
      <div className='stat-card'><div className='label'>STOPPED</div><div className='value'>{summary.stopped}</div></div>
      <div className='stat-card'><div className='label'>IN PROGRESS</div><div className='value'>{summary.provisioning}</div></div>
    </div>
    <div className='workspace-launchers'>
      {[{ to: '/vms', icon: 'monitor', title: 'Connect & learn', text: 'Open a machine and manage its power.' },
        access.tenantInstructor ? { to: '/classroom', icon: 'classroom', title: 'Organize learning', text: 'Classes, blueprints, assignments, and runs.' } : { to: '/create', icon: 'plus', title: 'Start your next lab', text: 'Provision an available classroom assignment.' },
        { to: '/operations', icon: 'activity', title: 'Follow the progress', text: 'Review active jobs, outcomes, and warnings.' },
        ...(isPlatformAdmin ? [{ to: '/admin/templates', icon: 'template', title: 'Build from a template', text: 'Discover and manage the template library.' }] : [])].map(item => <Link className='workspace-launcher' key={item.to} to={item.to}><NavIcon name={item.icon}/><h3>{item.title}</h3><p>{item.text}</p><span>Open <span aria-hidden='true'>→</span></span></Link>)}
    </div>
    {!vms.length ? <div className='workspace-note'><img src='/brand/labgoblin-icon.svg' alt=''/><div><h3>Your next lab starts here</h3><p>No machines are provisioned yet. {access.tenantInstructor ? 'Prepare a class and assignment to get learners started.' : 'Choose an available assignment to create your first lab machine.'}</p></div></div> : null}

    {isPlatformAdmin ? <section className='panel' style={{ marginTop: 16 }}>
      <div className='panel-head'>
        <div><h3>Infrastructure health</h3><p className='muted'>A concise view of the active virtualization cluster.</p></div>
        <button type='button' onClick={loadInfrastructure} disabled={resourceLoading}>{resourceLoading ? 'Refreshing…' : 'Refresh'}</button>
      </div>
      {resourceNotices.map(notice => <p className='ui-alert ui-alert--warning' role='status' key={notice}>{notice}</p>)}
      {resourceError ? <div role='alert'><p className='muted'>{resourceError}</p><button type='button' onClick={loadInfrastructure}>Try again</button></div> : null}
      {!resourceError && resourceLoading && !resourceStats ? <p className='muted' role='status'>Loading infrastructure health…</p> : null}
      {resourceStats ? <>
        {resourceStats.config_source === 'not_configured' ? <p className='msg error'>No cluster is configured. <Link to='/admin/proxmox-setup'>Connect infrastructure</Link>.</p> : null}
        {resourceStats.config_source === 'env_fallback' ? <p className='msg'>The cluster uses environment fallback settings. <Link to='/admin/proxmox-setup'>Review the connection</Link>.</p> : null}
        {(resourceStats.summary?.templates ?? 0) > 0 && templates.length === 0 ? <p className='msg'>Templates were discovered but none are available in this organization. <Link to='/admin/proxmox-inventory'>Review templates</Link>.</p> : null}
        {assetReadiness && assetReadiness.status !== 'PASS' ? <p className='msg'>Asset readiness: {assetReadiness.status}. <Link to='/admin/proxmox-assets'>Review assets</Link>.</p> : null}
        <div className='card-grid'>
          <div className='stat-card'><div className='label'>NODES ONLINE</div><div className='value'>{resourceStats.summary?.online_nodes ?? '—'} / {resourceStats.summary?.total_nodes ?? '—'}</div></div>
          <div className='stat-card'><div className='label'>CPU</div><div className='value'>{formatPercent(resourceStats.summary?.cpu_usage_percent)}</div></div>
          <div className='stat-card'><div className='label'>MEMORY</div><div className='value'>{formatPercent(resourceStats.summary?.memory_usage_percent)}</div></div>
          <div className='stat-card'><div className='label'>STORAGE</div><div className='value'>{formatPercent(resourceStats.summary?.disk_usage_percent)}</div></div>
        </div>
        <details style={{ marginTop: 16 }}>
          <summary>Node details and capacity</summary>
          {(resourceStats.warnings || []).map((warning, index) => <p key={index} className='muted'>{warning}</p>)}
          {!resourceStats.nodes?.length ? <p className='muted'>No node details are available.</p> : <div className='card-grid' style={{ marginTop: 12 }}>
            {resourceStats.nodes.map(node => <article className='panel' key={node.name}>
              <h4>{node.name}</h4><p>{node.status} · {node.running_vm_count ?? 0} running VM(s)</p>
              <CapacityMeter label='CPU utilization' value={node.cpu_usage_percent}/><CapacityMeter label='Memory utilization' value={node.memory_usage_percent}/><p className='muted'>Memory {formatBytes(node.memory_used_bytes)} / {formatBytes(node.memory_total_bytes)}</p>
              <p className='muted'>Disk {formatBytes(node.disk_used_bytes)} / {formatBytes(node.disk_total_bytes)} · Uptime {formatUptime(node.uptime_seconds)}</p>
              <p className='muted'>Storage: {(nodeStorage[node.name] || []).map(item => item.storage).filter(Boolean).join(', ') || 'not reported'}</p>
            </article>)}
          </div>}
        </details>
      </> : null}
    </section> : null}
  </section>
}
