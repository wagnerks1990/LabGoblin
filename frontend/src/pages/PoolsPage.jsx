import { useContext, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AccessContext } from '../components/AccessControl'
import { CollectionToolbar, MetricStrip, WorkspaceHeading } from '../components/ui/WorkspaceKit'
import api from '../services/api'
import { listPools, createPool, updatePool, deletePool, togglePoolEnabled, togglePoolMaintenance, readinessPool, planPool } from '../services/poolsApi'

const emptyForm = { name:'', description:'', pool_type:'persistent', template_vmid:'', template_node:'', default_protocol:'NOVNC', desired_size:0, enabled:true, maintenance_mode:false }
const statusClass = status => status === 'PASS' ? 'ui-status-badge--success' : status === 'WARN' ? 'ui-status-badge--warning' : status === 'FAIL' ? 'ui-status-badge--danger' : 'ui-status-badge--neutral'

export default function PoolsPage(){
  const access = useContext(AccessContext)
  const editor = useRef(null)
  const [query, setQuery] = useState('')
  const [saving, setSaving] = useState(false)
  const [templateError, setTemplateError] = useState('')
  const [rows,setRows]=useState([]); const [templates,setTemplates]=useState([]); const [form,setForm]=useState(emptyForm)
  const [editing,setEditing]=useState(null); const [message,setMessage]=useState(null); const [readiness,setReadiness]=useState({}); const [plan,setPlan]=useState({}); const [loading,setLoading]=useState(true); const [loadError,setLoadError]=useState('')
  const load = async () => { setLoading(true); setLoadError(''); try { setRows(await listPools()) } catch { setRows([]); setLoadError('Unable to load desktop pools.') } finally { setLoading(false) } }
  useEffect(()=>{ load(); api.get('/templates').then(response=>setTemplates(Array.isArray(response.data)?response.data:[])).catch(()=>setTemplateError('Templates could not be loaded. Refresh the page to retry.')) },[])

  const save = async event => {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    try {
      const payload = { ...form, template_vmid: form.template_vmid ? Number(form.template_vmid) : null, desired_size: Number(form.desired_size||0) }
      if (editing) await updatePool(editing, payload); else await createPool(payload)
      setForm(emptyForm); setEditing(null); if (editor.current) editor.current.open = false; setMessage({type:'success', text:'Pool saved. No automatic VM provisioning was triggered.'}); await load()
    } catch(error){ setMessage({type:'error', text:JSON.stringify(error?.response?.data?.detail||'Save failed')}) } finally { setSaving(false) }
  }
  const run = async work => { try { await work() } catch (error) { setMessage({type:'error', text:JSON.stringify(error?.response?.data?.detail || 'Request failed')}) } }
  const selectedTemplate = templates.find(template=>String(template.source_vmid)===String(form.template_vmid))

  return <section className='page-shell' aria-label='Resource pools'>
    <WorkspaceHeading eyebrow='Teaching / Resources' title='Resource pools' description='Organize templates, placement, and capacity for your classroom.'><button type='button' className='ui-button--secondary' onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button><button type='button' onClick={() => { setEditing(null); setForm(emptyForm); editor.current.open = true; editor.current.querySelector('input')?.focus() }}>Create pool</button></WorkspaceHeading>
    <MetricStrip items={[{ label: 'Pools', value: loading || loadError ? null : rows.length, icon: 'layers' }, { label: 'Enabled', value: loading || loadError ? null : rows.filter(pool => pool.enabled).length, icon: 'event' }, { label: 'In maintenance', value: loading || loadError ? null : rows.filter(pool => pool.maintenance_mode).length, icon: 'wrench' }]}/>
    {message ? <p className={`msg ${message.type}`} role={message.type==='error'?'alert':'status'} aria-live='polite'>{message.text}</p> : null}
    {loading ? <p role='status'>Loading resource pools…</p> : null}
    {loadError ? <p className='msg error' role='alert'>{loadError}</p> : null}

    <details ref={editor} className='panel pool-editor'>
      <summary>{editing ? 'Edit pool configuration' : 'New pool configuration'}</summary>
      <form className='ui-form-grid' onSubmit={save}>
        <label className='ui-field'>Name<input className='input' value={form.name} onChange={event=>setForm({...form,name:event.target.value})}/></label>
        <label className='ui-field'>Description<input className='input' value={form.description} onChange={event=>setForm({...form,description:event.target.value})}/></label>
        <label className='ui-field'>Pool type<select className='input' value={form.pool_type} onChange={event=>setForm({...form,pool_type:event.target.value})}><option value='persistent'>Persistent</option><option value='non_persistent'>Non-persistent</option></select></label>
        <label className='ui-field'>Default protocol<select className='input' value={form.default_protocol} onChange={event=>setForm({...form,default_protocol:event.target.value})}><option>NOVNC</option><option value='SSH_WS' disabled>SSH (unavailable)</option><option>RDP</option></select></label>
        <label className='ui-field'>Desired VM count<input className='input' type='number' min='0' inputMode='numeric' value={form.desired_size} onChange={event=>setForm({...form,desired_size:event.target.value})}/></label>
        <label className='ui-field'>Imported template<select className='input' value={form.template_vmid} onChange={event=>{const value=event.target.value; const template=templates.find(item=>String(item.source_vmid)===value); setForm({...form,template_vmid:value,template_node:template?.proxmox_node||''})}}><option value=''>Select a template</option>{templates.map(template=><option key={template.id} value={template.source_vmid}>{template.name} (VMID {template.source_vmid}, {template.proxmox_node})</option>)}</select></label>
        <fieldset className='ui-cluster ui-form-grid__wide'><legend>Availability</legend><label><input type='checkbox' checked={form.enabled} onChange={event=>setForm({...form,enabled:event.target.checked})}/> Enabled</label><label><input type='checkbox' checked={form.maintenance_mode} onChange={event=>setForm({...form,maintenance_mode:event.target.checked})}/> Maintenance mode</label></fieldset>
        <div className='ui-cluster ui-form-grid__wide'><button type='submit' disabled={saving || !form.name.trim()}>{saving ? 'Saving…' : 'Save pool'}</button><button type='button' className='ui-button--secondary' onClick={()=>{setEditing(null);setForm(emptyForm);editor.current.open = false;editor.current.querySelector('summary')?.focus()}}>Cancel</button></div>
      </form>
      {selectedTemplate ? <p className='muted'>Selected: {selectedTemplate.name} · VMID {selectedTemplate.source_vmid} · {selectedTemplate.proxmox_node}</p> : null}
      {templateError ? <p role='alert' className='msg error'>{templateError}</p> : null}
      {!templateError && templates.length===0 ? <p className='muted'>No templates are available. {access.platformAdmin ? <Link to='/admin/templates'>Open template library</Link> : 'Ask a platform administrator to enable templates.'}</p> : null}
    </details>

    <CollectionToolbar query={query} onQuery={setQuery} label='Search pools' count={rows.filter(pool => `${pool.name} ${pool.description || ''}`.toLowerCase().includes(query.trim().toLowerCase())).length} total={rows.length}/>
    <section className='panel' aria-labelledby='pool-list-title'>
      <div className='panel-head'><div><h3 id='pool-list-title'>Configured pools</h3><p className='muted'>{rows.length} total</p></div></div>
      {!loading && !loadError && rows.length===0 ? <p className='muted'>No desktop pools are configured yet.</p> : null}
      {!loading && !loadError && rows.length > 0 && !rows.some(pool => `${pool.name} ${pool.description || ''}`.toLowerCase().includes(query.trim().toLowerCase())) ? <p role='status'>No pools match this search.</p> : null}
      {rows.length ? <div className='ui-table-wrap' role='region' aria-labelledby='pool-list-title' tabIndex='0'><table className='ui-table'><thead><tr><th scope='col'>Name</th><th scope='col'>Configuration</th><th scope='col'>Capacity</th><th scope='col'>Readiness</th><th scope='col'>Actions</th></tr></thead><tbody>
        {rows.filter(pool => `${pool.name} ${pool.description || ''}`.toLowerCase().includes(query.trim().toLowerCase())).map(pool=>{ const ready=readiness[pool.id]?.status||pool.readiness_status||'Not checked'; return <tr key={pool.id}><th scope='row'><Link to={`/pools/${pool.id}`}>{pool.name}</Link><div className='muted'>{pool.pool_type}</div></th><td>{pool.enabled?'Enabled':'Disabled'} · {pool.maintenance_mode?'Maintenance':'Available'}<div className='muted'>{pool.default_protocol} · {pool.template_vmid?`${pool.template_vmid}@${pool.template_node||'-'}`:'No template'}</div></td><td>{pool.desired_size} desired<div className='muted'>{pool.linked_vm_count ?? 0} VMs · {pool.linked_template_count ?? 0} templates · {pool.linked_group_count ?? 0} groups</div></td><td><span className={`status-badge ${statusClass(ready)}`}>{ready}</span>{pool.placement_warning?<div className='muted'>{pool.placement_warning}</div>:null}{(pool.constrained_nodes||[]).length?<div className='muted'>Constrained: {pool.constrained_nodes.join(', ')}</div>:null}</td><td><div className='ui-cluster'>
          <button aria-label={`Edit pool ${pool.name}`} onClick={()=>{editor.current.open = true;setEditing(pool.id);setForm({...emptyForm,...pool,template_vmid:pool.template_vmid||''});editor.current.querySelector('input')?.focus()}}>Edit</button>
          <button aria-label={`${pool.enabled?'Disable':'Enable'} pool ${pool.name}`} onClick={()=>run(async()=>{await togglePoolEnabled(pool.id,!pool.enabled);await load()})}>{pool.enabled?'Disable':'Enable'}</button>
          <button aria-label={`${pool.maintenance_mode?'End':'Start'} maintenance for ${pool.name}`} onClick={()=>run(async()=>{await togglePoolMaintenance(pool.id,!pool.maintenance_mode);await load()})}>{pool.maintenance_mode?'End maintenance':'Maintenance'}</button>
          <button aria-label={`Check readiness for ${pool.name}`} onClick={()=>run(async()=>{const result=await readinessPool(pool.id);setReadiness(previous=>({...previous,[pool.id]:result}));setMessage({type:result.status==='FAIL'?'error':'success',text:(result.failures||[]).concat(result.warnings||[]).join(' | ')||`Readiness ${result.status}`})})}>Readiness</button>
          <button aria-label={`Plan pool ${pool.name}`} onClick={()=>run(async()=>{const result=await planPool(pool.id);setPlan(previous=>({...previous,[pool.id]:result}));setMessage({type:'success',text:`Plan: desired=${result.desired_size}, preview=${(result.vmid_preview||[]).join(',')}`})})}>Plan</button>
          <button className='btn-danger' aria-label={`Delete pool ${pool.name}`} onClick={()=>run(async()=>{if(!confirm(`Delete pool ${pool.name}? No Proxmox VMs are deleted automatically.`))return;await deletePool(pool.id);await load()})}>Delete</button>
        </div><p className='ui-field__hint'>Prewarm is unavailable until provisioning is implemented safely.</p>{plan[pool.id]?.warnings?.length?<div className='muted'>Warnings: {plan[pool.id].warnings.join('; ')}</div>:null}</td></tr>})}
      </tbody></table></div> : null}
    </section>
  </section>
}
