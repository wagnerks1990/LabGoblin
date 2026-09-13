import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CollectionToolbar, MetricStrip, ViewToggle, WorkspaceHeading } from '../components/ui/WorkspaceKit'
import NavIcon from '../components/navigation/NavIcon'
import api from '../services/api'

const errorDetail = error => {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : JSON.stringify(detail || 'Request failed.')
}

export default function TemplatesPage({ setMessage }) {
  const [view, setView] = useState('cards')
  const [availability, setAvailability] = useState('all')
  const [rows, setRows] = useState([])
  const [nodeFilter, setNodeFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      await api.post('/admin/proxmox/templates/sync')
      const response = await api.get('/admin/templates')
      setRows(Array.isArray(response.data) ? response.data : [])
    } catch (requestError) {
      setRows([])
      setError(errorDetail(requestError))
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const toggleEnabled = async template => {
    setBusyId(template.id)
    try {
      await api.patch(`/admin/templates/${template.id}`, { enabled: !template.enabled })
      setMessage({ type: 'success', text: `${template.name} ${template.enabled ? 'disabled' : 'enabled'}.` })
      await load()
    } catch (requestError) {
      setMessage({ type: 'error', text: errorDetail(requestError) })
    } finally {
      setBusyId(null)
    }
  }

  const visibleRows = useMemo(() => rows.filter(template =>
    (availability === 'all' || Boolean(template.enabled) === (availability === 'enabled')) && (!nodeFilter || `${template.name} ${template.proxmox_node} ${template.source_vmid}`.toLowerCase().includes(nodeFilter.trim().toLowerCase()))
  ), [nodeFilter, rows, availability])

  return <section className='page-shell' aria-label='Template library'>
    <WorkspaceHeading eyebrow='Infrastructure / Library' title='Template library' description='Reusable starting points for every lab. Discovered from your active Proxmox cluster.'><Link to='/admin/proxmox-inventory' className='btn ui-button--secondary'>Explore inventory</Link><button type='button' onClick={load} disabled={loading}>{loading ? 'Discovering…' : 'Discover templates'}</button></WorkspaceHeading>
    <MetricStrip items={[{ label: 'Templates', value: loading || error ? null : rows.length, icon: 'template' }, { label: 'Enabled', value: loading || error ? null : rows.filter(row => row.enabled).length, icon: 'layers' }, { label: 'Source nodes', value: loading || error ? null : new Set(rows.map(row => row.proxmox_node).filter(Boolean)).size, icon: 'server' }]}/>
    <section aria-labelledby='template-list-title'>
      <h3 id='template-list-title' className='sr-only'>Template catalog</h3>
      <CollectionToolbar query={nodeFilter} onQuery={setNodeFilter} label='Search name, node or VMID' count={visibleRows.length} total={rows.length} onReset={() => { setNodeFilter(''); setAvailability('all') }}>
        <label className='ui-field'>Availability<select value={availability} onChange={event => setAvailability(event.target.value)}><option value='all'>All templates</option><option value='enabled'>Enabled</option><option value='disabled'>Disabled</option></select></label><ViewToggle value={view} onChange={setView}/>
      </CollectionToolbar>
      <p className='muted'>Enable a template for catalog use, then assign it through Classes &amp; labs to make it available to students.</p>
      {error ? <p className='msg error' role='alert'>{error}</p> : null}
      {loading ? <p className='muted' role='status'>Loading templates…</p> : null}
      {!loading && !error && visibleRows.length === 0 ? <p className='muted'>{rows.length ? 'No templates match the current filter.' : 'No templates were discovered. Check the active cluster and try discovery again.'}</p> : null}
      {view === 'cards' && !loading && !error ? <div className='resource-collection resource-collection--cards'>{visibleRows.map(template => <article className='panel resource-card' key={template.id}><div className='panel-head'><span className='resource-emblem'><NavIcon name='template'/></span><span className={`ui-status-badge ui-status-badge--${template.enabled ? 'success' : 'neutral'}`}>{template.enabled ? 'Enabled' : 'Disabled'}</span></div><h3>{template.name}</h3><div className='resource-facts'><span>Source VMID <strong>{template.source_vmid}</strong></span><span>Node <strong>{template.proxmox_node || 'Not reported'}</strong></span></div><div className='resource-card-footer'><Link to='/classroom'>Configure lab access</Link><button type='button' className='ui-button--secondary' disabled={busyId === template.id} aria-label={`${template.enabled ? 'Disable' : 'Enable'} ${template.name}`} onClick={() => toggleEnabled(template)}>{busyId === template.id ? 'Saving…' : template.enabled ? 'Disable' : 'Enable'}</button></div></article>)}</div> : null}
      {view === 'list' && visibleRows.length > 0 ? <div className='ui-table-wrap' role='region' aria-labelledby='template-list-title' tabIndex='0'>
        <table className='ui-table'><thead><tr><th scope='col'>Name</th><th scope='col'>Node</th><th scope='col'>VMID</th><th scope='col'>Availability</th><th scope='col'>Action</th></tr></thead><tbody>{visibleRows.map(template => <tr key={template.id}><th scope='row'>{template.name}</th><td>{template.proxmox_node}</td><td>{template.source_vmid}</td><td><span className={`ui-status-badge ui-status-badge--${template.enabled ? 'success' : 'neutral'}`}>{template.enabled ? 'Enabled' : 'Disabled'}</span></td><td><button type='button' className='ui-button--secondary' disabled={busyId === template.id} aria-label={`${template.enabled ? 'Disable' : 'Enable'} ${template.name}`} onClick={() => toggleEnabled(template)}>{busyId === template.id ? 'Saving…' : template.enabled ? 'Disable' : 'Enable'}</button></td></tr>)}</tbody></table>
      </div> : null}
    </section>
  </section>
}
