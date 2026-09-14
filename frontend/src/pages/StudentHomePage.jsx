import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { listMyAssignments } from '../services/classroomApi'
import { LoadingState, ErrorState } from '../components/workflows/WorkflowState'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import VmResources from '../components/workflows/VmResources'
import GuestCredentialReveal from '../components/workflows/GuestCredentialReveal'

const detail = error => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : 'Your lab resources could not be loaded. Please try again.'
const dateLabel = value => value ? new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toLocaleString() : null

export default function StudentHomePage({ user }) {
  const [rows, setRows] = useState([]); const [vms, setVms] = useState([])
  const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  const [query, setQuery] = useState(''); const [busy, setBusy] = useState({})
  const [messages, setMessages] = useState({}); const [jobs, setJobs] = useState({})
  const mounted = useRef(true)
  const refreshing = useRef(false)
  const load = useCallback(async (quiet = false) => {
    if (refreshing.current) return
    refreshing.current = true
    if (!quiet) setLoading(true)
    try {
      const [assigned, machines] = await Promise.all([listMyAssignments(), api.get('/vms')])
      if (mounted.current) { setRows(assigned); setVms(machines.data || []); setError('') }
    } catch (err) { if (mounted.current) setError(detail(err)) }
    finally { refreshing.current = false; if (mounted.current) setLoading(false) }
  }, [])
  useEffect(() => { mounted.current = true; load(); return () => { mounted.current = false } }, [load])
  useEffect(() => {
    const timer = setInterval(() => { if (!document.hidden) load(true) }, 10000)
    return () => clearInterval(timer)
  }, [load])
  useEffect(() => {
    let active = true
    const pending = Object.entries(jobs).filter(([,job]) => job.id && !['succeeded','warning','failed','cancelled'].includes(job.state))
    if (!pending.length) return undefined
    const timer = setTimeout(async () => {
      for (const [key,job] of pending) {
        try { const row = (await api.get(`/operations/${job.id}`)).data; if (active) { setJobs(old => ({...old,[key]:{id:job.id,state:row.state,error:row.error,warnings:row.result?.warnings || []}})); if (row.state === 'succeeded') setMessages(old => ({...old,[key]:'Preparation completed.'})); if (row.state === 'failed') setMessages(old => ({...old,[key]:'Preparation failed. Review the operation details or contact your instructor.'})) } }
        catch (err) { if (active) { setMessages(old => ({...old,[key]:detail(err)})); setJobs(old => ({...old})) } }
      }
      if (active) load(true)
    }, 2500)
    return () => { active = false; clearTimeout(timer) }
  }, [jobs, load])
  const start = async (assignment, vm) => {
    if (busy[assignment.id]) return
    setBusy(old => ({...old,[assignment.id]:true}))
    try {
      const response = vm ? await api.post(`/vms/${vm.id}/start`) : await api.post('/vms', {template_id:assignment.template_id,assignment_id:assignment.id,lab_name:assignment.lab_name || 'classroom-lab',auto_start:true})
      if (mounted.current) {
        setMessages(old => ({...old,[assignment.id]:vm ? 'Start requested. Waiting for the worker.' : 'Your lab machine is being prepared. You can leave this page.'}))
        setJobs(old => ({...old,[assignment.id]:{id:response.data.operation_id,state:'queued'}}))
        await load(true)
      }
    } catch (err) { if (mounted.current) setMessages(old => ({...old,[assignment.id]:detail(err)})) }
    finally { if (mounted.current) setBusy(old => ({...old,[assignment.id]:false})) }
  }
  if (loading) return <LoadingState label='Finding your labs…'/>
  if (error) return <ErrorState message={error} onRetry={() => load()}/>
  const matching = rows.filter(row => `${row.lab_name} ${row.run_name} ${row.template_name}`.toLowerCase().includes(query.toLowerCase().trim()))
  const groups = Map.groupBy ? Map.groupBy(matching,row => row.lab_run_id) : matching.reduce((map,row) => map.set(row.lab_run_id,[...(map.get(row.lab_run_id)||[]),row]),new Map())
  return <section className='page-shell student-home' aria-labelledby='student-title'>
    <header className='student-welcome'><div><p className='eyebrow'>LabGoblin / Your learning space</p><h2 id='student-title'>Ready to explore, {user?.display_name || user?.username}?</h2><p>Choose a lab below. Your machine opens right here in the browser.</p></div><img src='/brand/labgoblin-icon.svg' alt=''/></header>
    <div className='workspace-section-title'><h3>My labs</h3><button type='button' className='ui-button--secondary' onClick={() => load()}>Refresh labs</button></div>
    {rows.length ? <label className='ui-field'>Find a lab<input type='search' placeholder='Search labs or machines' value={query} onChange={event => setQuery(event.target.value)}/></label> : null}
    {!rows.length ? <section className='panel workspace-empty'><img src='/brand/labgoblin-icon.svg' alt=''/><h3>Your labs will appear here</h3><p>Your instructor will assign your first lab. If you expected one already, check the selected organization or ask your instructor.</p><button onClick={() => load()}>Check again</button></section> : !matching.length ? <p role='status'>No labs match your search. Try another name.</p> : null}
    {[...groups].map(([id,assigned]) => <section className='student-lab panel' key={id} aria-labelledby={`lab-${id}`}>
      <header><p className='eyebrow'>{assigned[0].run_name}</p><h3 id={`lab-${id}`}>{assigned[0].lab_name}</h3>{assigned[0].instructions ? <p className='student-instructions'>{assigned[0].instructions}</p> : null}<p className='muted'>{assigned[0].starts_at ? `Starts ${dateLabel(assigned[0].starts_at)} · ` : ''}{assigned[0].ends_at ? `Ends ${dateLabel(assigned[0].ends_at)}` : 'No scheduled end'}</p></header>
      <div className='lab-resource-grid'>{assigned.map(row => {
        const vm = vms.find(item => item.id === row.student_vm_id)
        const job = jobs[row.id]
        const working = busy[row.id] || (job?.id && !['succeeded','warning','failed','cancelled'].includes(job.state))
        return <article className='student-machine' key={row.id}>
          <h4>{row.template_name || 'Lab machine'}{assigned.length > 1 ? ` · Machine ${row.slot_index}` : ''}</h4>
          <WorkflowStatus value={(job && job.state !== 'succeeded' ? job.state : null) || vm?.status || (row.can_provision ? 'ready' : row.run_state || 'unavailable')}/>
          {row.access_open && vm?.status === 'running' && !working ? <Link className='btn btn-connection' to={`/console/${vm.id}`}>Connect in browser</Link> : row.access_open && vm?.status === 'stopped' ? <button disabled={working} onClick={() => start(row,vm)}>{working ? 'Starting…' : 'Start machine'}</button> : row.can_provision ? <button disabled={working} onClick={() => start(row,null)}>{working ? 'Preparing…' : 'Start lab'}</button> : <p>{!row.access_open ? 'Your instructor will open access during the lab window.' : vm ? 'Your machine is not ready to connect yet.' : 'Machine information is not available yet.'}</p>}
          {messages[row.id] ? <p role='status'>{messages[row.id]}</p> : null}
          {job?.error ? <p className='msg error' role='alert'>{job.error}</p> : null}
          {(job?.warnings || []).map((warning,index) => <p className='ui-alert ui-alert--warning' key={index}>Completed with warning: {warning.message}</p>)}
          {job ? <Link to='/operations'>View preparation progress</Link> : null}
          {row.access_open && vm ? <GuestCredentialReveal key={vm.id} vmId={vm.id}/> : null}
          {vm ? <details><summary>Machine details</summary><p>{vm.vm_name}</p><VmResources vm={vm}/><Link to='/vms'>More machine actions</Link></details> : null}
        </article>
      })}</div>
    </section>)}
    <section className='workspace-note'><img src='/brand/labgoblin-icon.svg' alt=''/><div><h3>A little help getting started</h3><p><strong>Start lab</strong> prepares your machine. <strong>Connect in browser</strong> chooses an available desktop or terminal. <strong>Show lab login</strong> displays a guest account when your instructor has enabled sharing.</p><p>Need your LabGoblin password changed? <Link to='/account/security'>Open account settings</Link>. For missing labs or access problems, contact your instructor.</p></div></section>
  </section>
}
