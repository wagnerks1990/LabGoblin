import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import { CollectionToolbar, MetricStrip, ViewToggle, WorkspaceHeading } from '../components/ui/WorkspaceKit'
import NavIcon from '../components/navigation/NavIcon'
import { selectMachines } from '../state/workspaceCollections'
import api from '../services/api'
import GuestCredentialReveal from '../components/workflows/GuestCredentialReveal'

const terminalStates = new Set(['succeeded', 'failed', 'cancelled'])
const errorDetail = error => {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : JSON.stringify(detail || error?.message || 'Action failed')
}

export default function VmsPage({ setMessage }) {
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [view, setView] = useState('cards')
  const [sort, setSort] = useState('name')
  const [vms, setVms] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState({})

  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true)
    setError('')
    try {
      const response = await api.get('/vms')
      setVms(Array.isArray(response.data) ? response.data : [])
    } catch (requestError) {
      setError(errorDetail(requestError))
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const waitForOperation = async operationId => {
    if (!operationId) return
    for (let attempt = 0; attempt < 60; attempt += 1) {
      const operation = (await api.get(`/operations/${operationId}`)).data
      const state = String(operation.state).toLowerCase()
      if (terminalStates.has(state)) {
        if (state !== 'succeeded') throw new Error(operation.error || 'Operation failed')
        return
      }
      await new Promise(resolve => setTimeout(resolve, 2000))
    }
    throw new Error('This operation is still running. Check Operations for progress.')
  }

  const act = async (vm, action) => {
    setBusy(previous => ({ ...previous, [vm.id]: action }))
    try {
      let response
      if (action === 'delete') {
        const preview = (await api.get(`/vms/${vm.id}/delete-preview`)).data
        if (!window.confirm(`Delete ${preview.vm_name} (VMID ${preview.vmid}) from Proxmox? Its history will be retained after deletion is verified.`)) return
        response = await api.delete(`/vms/${vm.id}`, { params: { confirmation: preview.confirmation } })
      } else if (action === 'status') response = await api.get(`/vms/${vm.id}/status`)
      else response = await api.post(`/vms/${vm.id}/${action}`)
      await waitForOperation(response?.data?.operation_id)
      await load({ quiet: true })
      setMessage({ type: 'success', text: action === 'status' ? `${vm.vm_name} status refreshed.` : `${vm.vm_name}: ${action} completed.` })
    } catch (requestError) {
      setMessage({ type: 'error', text: errorDetail(requestError) })
    } finally {
      setBusy(previous => ({ ...previous, [vm.id]: null }))
    }
  }

  const visible = selectMachines(vms, { query, status: statusFilter, sort })

  if (loading) return <LoadingState label='Loading your virtual machines…' />
  if (error && !vms.length) return <ErrorState message={error} onRetry={load} retrying={loading} />

  return <section>
    <WorkspaceHeading title='Your lab machines' description='Find your machine, connect, and get back to learning.'><Link className='ui-button--secondary btn' to='/operations'>View activity</Link><button type='button' className='ui-button--secondary' onClick={() => load()}>Refresh all</button><Link className='btn' to='/create'>Provision a VM</Link></WorkspaceHeading>
    <MetricStrip items={[{ label: 'Lab machines', value: vms.length, icon: 'monitor' }, { label: 'Running', value: vms.filter(vm => vm.status === 'running').length, icon: 'pulse' }, { label: 'Stopped', value: vms.filter(vm => vm.status === 'stopped').length, icon: 'server' }, { label: 'Needs attention', value: vms.filter(vm => ['error', 'missing'].includes(vm.status)).length, icon: 'wrench' }]}/>
    <CollectionToolbar query={query} onQuery={setQuery} label='Search name, VMID, node or IP' count={visible.length} total={vms.length} onReset={() => { setQuery(''); setStatusFilter(''); setSort('name') }}>
      <label className='ui-field'>Status<select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value=''>All statuses</option>{[...new Set(vms.map(vm => String(vm.status).toLowerCase()))].sort().map(status => <option key={status}>{status}</option>)}</select></label>
      <label className='ui-field'>Sort by<select value={sort} onChange={event => setSort(event.target.value)}><option value='name'>Name</option><option value='vmid'>VMID</option></select></label><ViewToggle value={view} onChange={setView}/>
    </CollectionToolbar>
    {error ? <p className='msg error' role='alert'>{error}</p> : null}
    {!vms.length ? <EmptyState title='No virtual machines yet' message='When a classroom assignment is available, provision it here.' action={<Link to='/create'>View available assignments</Link>} /> : null}
    {vms.length > 0 && !visible.length ? <EmptyState title='No matching machines' message='Try a different search or reset the filters.'/> : null}
    <div className={`resource-collection resource-collection--${view}`}>
      {visible.map(vm => {
        const state = String(vm.status || '').toLowerCase()
        const missing = ['missing', 'error'].includes(state)
        const running = state === 'running'
        const stopped = state === 'stopped'
        const working = Boolean(busy[vm.id])
        return <article className='panel resource-card' key={vm.id} aria-busy={working}>
          <div className='panel-head'>
            <div><span className='resource-emblem'><NavIcon name='monitor'/></span><h3>{vm.vm_name}</h3><WorkflowStatus value={vm.status} /></div>
            <button type='button' onClick={() => act(vm, 'status')} disabled={working} aria-label={`Refresh ${vm.vm_name} status`}>Refresh</button>
          </div>
          <div className='resource-facts'><span>VMID <strong>{vm.vmid}</strong></span><span>Node <strong>{vm.proxmox_node || 'Not assigned'}</strong></span><span>Address <strong>{vm.assigned_ip || vm.hostname || 'Not reported'}</strong></span></div>
          {working ? <p className='muted' role='status'>{busy[vm.id] === 'status' ? 'Refreshing status…' : `${busy[vm.id]} in progress…`}</p> : null}
          {missing ? <p className='msg error'>This VM is unavailable. Refresh its status or ask an instructor for help.</p> : null}
          {running ? <Link className='btn btn-connection' to={`/console/${vm.id}`}>Connect in browser</Link>
            : stopped ? <button type='button' disabled={working} onClick={() => act(vm, 'start')}>Start VM</button>
              : <p className='muted'>A connection will be available when this VM is running.</p>}
          <GuestCredentialReveal key={vm.id} vmId={vm.id}/><details style={{ marginTop: 14 }}>
            <summary>More actions and details</summary>
            <dl>
              <dt>VMID</dt><dd>{vm.vmid}</dd>
              <dt>Node</dt><dd>{vm.proxmox_node || 'Not assigned'}</dd>
              <dt>Address</dt><dd>{vm.assigned_ip || vm.hostname || 'Not reported'}</dd>
              {vm.assignment_expires_at ? <><dt>Assignment ends</dt><dd>{new Date(vm.assignment_expires_at).toLocaleString()}</dd></> : null}
            </dl>
            <div className='group'>
              {!running && !missing && !stopped ? <button type='button' disabled={working} onClick={() => act(vm, 'start')}>Start</button> : null}
              {running && vm.allowed_stop !== false ? <button type='button' disabled={working} onClick={() => act(vm, 'stop')}>Stop</button> : null}
              {running ? <button type='button' disabled={working} onClick={() => act(vm, 'reboot')}>Reboot</button> : null}
            </div>
            {vm.allowed_delete !== false ? <details style={{ marginTop: 12 }}>
              <summary>Delete this VM</summary>
              <p className='muted'>Deletion removes the Proxmox VM after a server-verified preview. History is retained.</p>
              <button type='button' className='btn-danger' disabled={working} onClick={() => act(vm, 'delete')}>Delete VM</button>
            </details> : null}
          </details>
        </article>
      })}
    </div>
  </section>
}
