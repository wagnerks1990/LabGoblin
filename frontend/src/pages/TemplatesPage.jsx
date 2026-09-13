import { useEffect, useMemo, useState } from 'react'
import api from '../services/api'

const errorDetail = error => {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : JSON.stringify(detail || 'Request failed.')
}

export default function TemplatesPage({ setMessage }) {
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
    !nodeFilter || `${template.name} ${template.proxmox_node} ${template.source_vmid}`.toLowerCase().includes(nodeFilter.toLowerCase())
  ), [nodeFilter, rows])

  return <section className='page-shell' aria-labelledby='templates-title'>
    <header className='ui-page-header'>
      <div><p className='muted'>Infrastructure</p><h2 id='templates-title'>Templates</h2><p className='ui-page-header__description'>Templates are discovered automatically from your active Proxmox cluster for this organization.</p></div>
    </header>

    <section className='panel' aria-labelledby='template-list-title'>
      <div className='panel-head'><div><h3 id='template-list-title'>Template catalog</h3><p className='muted'>{visibleRows.length} shown</p></div><button type='button' className='ui-button--secondary' onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button></div>
      <label className='ui-field'>Search name, node or VMID<input type='search' value={nodeFilter} onChange={event => setNodeFilter(event.target.value)} /></label>
      {error ? <p className='msg error' role='alert'>{error}</p> : null}
      {loading ? <p className='muted' role='status'>Loading templates…</p> : null}
      {!loading && !error && visibleRows.length === 0 ? <p className='muted'>No templates match the current filter.</p> : null}
      {visibleRows.length > 0 ? <div className='ui-table-wrap' role='region' aria-labelledby='template-list-title' tabIndex='0'>
        <table className='ui-table'><thead><tr><th scope='col'>Name</th><th scope='col'>Node</th><th scope='col'>VMID</th><th scope='col'>Availability</th><th scope='col'>Action</th></tr></thead><tbody>{visibleRows.map(template => <tr key={template.id}><th scope='row'>{template.name}</th><td>{template.proxmox_node}</td><td>{template.source_vmid}</td><td><span className={`ui-status-badge ui-status-badge--${template.enabled ? 'success' : 'neutral'}`}>{template.enabled ? 'Enabled' : 'Disabled'}</span></td><td><button type='button' className='ui-button--secondary' disabled={busyId === template.id} aria-label={`${template.enabled ? 'Disable' : 'Enable'} ${template.name}`} onClick={() => toggleEnabled(template)}>{busyId === template.id ? 'Saving…' : template.enabled ? 'Disable' : 'Enable'}</button></td></tr>)}</tbody></table>
      </div> : null}
    </section>
  </section>
}
