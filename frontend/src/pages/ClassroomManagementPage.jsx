import { useEffect, useMemo, useState } from 'react'
import { listCurrentOrganizationMembers } from '../services/organizationApi'
import { MetricStrip } from '../components/ui/WorkspaceKit'
import api from '../services/api'
import {
  addEnrollment, bulkAssignRun, changeLabRunState, createClass, createLab, createLabRun,
  listClasses, listEnrollments, listLabs, listLabRuns, listRunAssignments,
  previewLabRunClose, removeEnrollment, revokeRunAssignment,
} from '../services/classroomApi'

const detail = error => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : JSON.stringify(error?.response?.data?.detail || 'Request failed')
const localDateTimeToIso = value => value ? new Date(value).toISOString() : null
const steps = [
  { id: 'classes', label: '1. Classes & roster' },
  { id: 'labs', label: '2. Lab blueprint' },
  { id: 'runs', label: '3. Run & assignments' },
]

export default function ClassroomPage({ setMessage }) {
  const [classes, setClasses] = useState([]); const [labs, setLabs] = useState([]); const [runs, setRuns] = useState([])
  const [pools, setPools] = useState([]); const [members, setMembers] = useState([])
  const [selectedClass, setSelectedClass] = useState(''); const [selectedRun, setSelectedRun] = useState('')
  const [detailError, setDetailError] = useState('')
  const [detailLoading, setDetailLoading] = useState(false)
  const [enrollments, setEnrollments] = useState([]); const [assignments, setAssignments] = useState([])
  const [classForm, setClassForm] = useState({ name: '', term: '' })
  const [labForm, setLabForm] = useState({ name: '', description: '', default_pool_id: '', student_can_power_off: false, terminal_enabled: false, console_enabled: true, rdp_enabled: false })
  const [runForm, setRunForm] = useState({ name: '', lab_id: '', starts_at: '', ends_at: '', max_vms_per_student: 1 })
  const [memberId, setMemberId] = useState(''); const [activeStep, setActiveStep] = useState('classes')
  const [loading, setLoading] = useState(true); const [loadError, setLoadError] = useState('')

  const reload = async () => {
    setLoading(true); setLoadError('')
    try {
      const [classRows, labRows, runRows, poolResponse, memberRows] = await Promise.all([listClasses(), listLabs(), listLabRuns(), api.get('/pools'), listCurrentOrganizationMembers()])
      setClasses(classRows || []); setLabs(labRows || []); setRuns(runRows || []); setPools(poolResponse.data?.data || []); setMembers(memberRows || [])
    } catch (error) { setLoadError(detail(error)) } finally { setLoading(false) }
  }
  useEffect(() => { reload() }, [])
  useEffect(() => {
    let active = true
    setDetailError(''); setEnrollments([]); setAssignments([])
    if (!selectedClass) { setDetailLoading(false); return }
    setDetailLoading(true)
    Promise.all([listEnrollments(selectedClass), selectedRun ? listRunAssignments(selectedRun) : Promise.resolve([])])
      .then(([roster, assigned]) => { if (active) { setEnrollments(roster); setAssignments(assigned) } })
      .catch(error => { if (active) setDetailError(detail(error)) })
      .finally(() => { if (active) setDetailLoading(false) })
    return () => { active = false }
  }, [selectedClass, selectedRun])

  const classLabs = useMemo(() => labs.filter(lab => String(lab.class_id) === String(selectedClass)), [labs, selectedClass])
  const selectedRunRow = runs.find(run => String(run.id) === String(selectedRun))
  const moveTabFocus = (event, currentIndex) => {
    const keyOffsets = { ArrowLeft: -1, ArrowRight: 1 }
    let nextIndex = keyOffsets[event.key] === undefined ? currentIndex : (currentIndex + keyOffsets[event.key] + steps.length) % steps.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = steps.length - 1
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    setActiveStep(steps[nextIndex].id)
    document.getElementById(`classroom-tab-${steps[nextIndex].id}`)?.focus()
  }
  const save = async (work, message) => { try { await work(); await reload(); setMessage({ type: 'success', text: message }) } catch (error) { setMessage({ type: 'error', text: detail(error) }) } }
  const endRun = async () => {
    try {
      const preview = await previewLabRunClose(selectedRun, 'end')
      if (!window.confirm(`End this run, expire ${preview.assignments_affected} assignment(s), and queue deletion of ${preview.vm_deletions_to_queue} Proxmox VM(s)?`)) return
      await changeLabRunState(selectedRun, 'end', preview.confirmation); await reload(); setMessage({ type: 'success', text: 'Lab run ended; verified VM cleanup was queued.' })
    } catch (error) { setMessage({ type: 'error', text: detail(error) }) }
  }

  return <section className='page-shell' aria-labelledby='classroom-title'>
    <header className='ui-page-header'><div><p className='muted'>Teaching</p><h2 id='classroom-title'>Classroom</h2><p className='ui-page-header__description'>Build the class in order: roster, blueprint, then scheduled run and VM assignments.</p></div><button type='button' onClick={reload} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh data'}</button></header>
    <MetricStrip items={[{ label: 'Classes', value: loading || loadError ? null : classes.length, icon: 'classroom' }, { label: 'Blueprints', value: loading || loadError ? null : labs.length, icon: 'template' }, { label: 'Lab runs', value: loading || loadError ? null : runs.length, icon: 'event' }]}/>
    <div className='workspace-note'><img src='/brand/labgoblin-icon.svg' alt=''/><div><h3>Build. Deploy. Learn. Repeat.</h3><p>{activeStep === 'classes' ? 'Start with a class and enroll its learners.' : activeStep === 'labs' ? 'Define a reusable lab and choose the access students receive.' : 'Schedule the lab, assign learners, and follow their progress.'}</p></div></div>
    {loading ? <p className='muted' role='status'>Loading classroom data…</p> : null}
    {loadError ? <p className='msg error' role='alert'>{loadError}</p> : null}
    {detailLoading ? <p role='status'>Loading roster and assignments…</p> : null}
    {detailError ? <p className='msg error' role='alert'>{detailError}</p> : null}
    <div className='ui-tabs__list' role='tablist' aria-label='Classroom workflow'>{steps.map((step, index) => <button key={step.id} id={`classroom-tab-${step.id}`} className='ui-tabs__tab' role='tab' aria-selected={activeStep === step.id} aria-controls={`classroom-panel-${step.id}`} tabIndex={activeStep === step.id ? 0 : -1} onKeyDown={event => moveTabFocus(event, index)} onClick={() => setActiveStep(step.id)}>{step.label}</button>)}</div>

    {activeStep === 'classes' ? <section id='classroom-panel-classes' className='panel' role='tabpanel' aria-labelledby='classroom-tab-classes'>
      <h3>Classes and roster</h3>
      <div className='ui-form-grid'>
        <label className='ui-field'>Class name<input className='input' value={classForm.name} onChange={event => setClassForm({...classForm, name: event.target.value})} /></label>
        <label className='ui-field'>Term<input className='input' value={classForm.term} onChange={event => setClassForm({...classForm, term: event.target.value})} /></label>
        <div className='ui-cluster ui-form-grid__wide'><button disabled={!classForm.name} onClick={() => save(async () => { await createClass(classForm); setClassForm({name:'', term:''}) }, 'Class created.')}>Create class</button></div>
      </div>
      <label className='ui-field'>Working class<select className='input' value={selectedClass} onChange={event => { setSelectedClass(event.target.value); setSelectedRun('') }}><option value=''>Select a class…</option>{classes.map(row => <option key={row.id} value={row.id}>{row.name}{row.term ? ` — ${row.term}` : ''}</option>)}</select></label>
      {selectedClass ? <>
        <div className='ui-cluster'><label className='ui-field'>Organization member<select className='input' value={memberId} onChange={event => setMemberId(event.target.value)}><option value=''>Select a member…</option>{members.map(row => <option key={row.user_id} value={row.user_id}>{row.username} ({row.role})</option>)}</select></label><button disabled={!memberId} onClick={() => save(async () => { await addEnrollment(selectedClass, {user_id:Number(memberId), role:'student'}); setEnrollments(await listEnrollments(selectedClass)); setMemberId('') }, 'Student enrolled.')}>Enroll student</button></div>
        {!detailLoading && !detailError && enrollments.length === 0 ? <p className='muted'>No students are enrolled in this class.</p> : <div className='ui-table-wrap' role='region' aria-label='Class roster' tabIndex='0'><table className='ui-table'><thead><tr><th scope='col'>Student</th><th scope='col'>Role</th><th scope='col'>Active</th><th scope='col'>Action</th></tr></thead><tbody>{enrollments.map(row => { const name = members.find(member => member.user_id === row.user_id)?.username || row.user_id; return <tr key={row.id}><th scope='row'>{name}</th><td>{row.role || 'student'}</td><td>{row.is_active ? 'Yes' : 'No'}</td><td><button className='btn-danger' aria-label={`Remove ${name} from class`} onClick={() => save(async () => { await removeEnrollment(selectedClass, row.user_id); setEnrollments(await listEnrollments(selectedClass)) }, 'Enrollment removed.')}>Remove</button></td></tr> })}</tbody></table></div>}
      </> : <p className='muted'>Select a class to manage its roster.</p>}
    </section> : null}

    {activeStep === 'labs' ? <section id='classroom-panel-labs' className='panel' role='tabpanel' aria-labelledby='classroom-tab-labs'>
      <h3>Lab blueprint</h3><p className='muted'>Choose the class and define the access students receive.</p>
      <label className='ui-field'>Class<select className='input' value={selectedClass} onChange={event => setSelectedClass(event.target.value)}><option value=''>Select a class…</option>{classes.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <div className='ui-form-grid'>
        <label className='ui-field'>Lab name<input className='input' value={labForm.name} onChange={event => setLabForm({...labForm, name:event.target.value})} /></label>
        <label className='ui-field'>Default pool<select className='input' value={labForm.default_pool_id} onChange={event => setLabForm({...labForm, default_pool_id:event.target.value})}><option value=''>Select a pool…</option>{pools.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <fieldset className='ui-cluster ui-form-grid__wide'><legend>Student access</legend><label><input type='checkbox' checked={labForm.student_can_power_off} onChange={event => setLabForm({...labForm, student_can_power_off:event.target.checked})}/> Power off</label><label><input type='checkbox' checked={labForm.terminal_enabled} onChange={event => setLabForm({...labForm, terminal_enabled:event.target.checked})}/> Browser terminal</label><label><input type='checkbox' checked={labForm.console_enabled} onChange={event => setLabForm({...labForm, console_enabled:event.target.checked})}/> Console</label><label><input type='checkbox' checked={labForm.rdp_enabled} onChange={event => setLabForm({...labForm, rdp_enabled:event.target.checked})}/> RDP</label></fieldset>
        <div className='ui-cluster ui-form-grid__wide'><button disabled={!selectedClass || !labForm.name || !labForm.default_pool_id} onClick={() => save(async () => { await createLab({...labForm, class_id:Number(selectedClass), default_pool_id:Number(labForm.default_pool_id)}); setLabForm({...labForm, name:'', description:''}) }, 'Lab blueprint created.')}>Create blueprint</button></div>
      </div>
      {selectedClass ? <p className='muted' role='status'>Blueprints for this class: {classLabs.map(row => row.name).join(', ') || 'none yet'}</p> : null}
    </section> : null}

    {activeStep === 'runs' ? <section id='classroom-panel-runs' className='panel' role='tabpanel' aria-labelledby='classroom-tab-runs'>
      <h3>Scheduled run and assignments</h3>
      <label className='ui-field'>Class<select className='input' value={selectedClass} onChange={event => { setSelectedClass(event.target.value); setSelectedRun('') }}><option value=''>Select a class…</option>{classes.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <div className='ui-form-grid'>
        <label className='ui-field'>Lab blueprint<select className='input' value={runForm.lab_id} onChange={event => setRunForm({...runForm, lab_id:event.target.value})}><option value=''>Select a lab…</option>{classLabs.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <label className='ui-field'>Run name<input className='input' value={runForm.name} onChange={event => setRunForm({...runForm, name:event.target.value})} /></label>
        <label className='ui-field'>Starts<input className='input' type='datetime-local' value={runForm.starts_at} onChange={event => setRunForm({...runForm, starts_at:event.target.value})}/></label>
        <label className='ui-field'>Ends<input className='input' type='datetime-local' value={runForm.ends_at} onChange={event => setRunForm({...runForm, ends_at:event.target.value})}/></label>
        <label className='ui-field'>VMs per student<input className='input' type='number' min='1' max='10' value={runForm.max_vms_per_student} onChange={event => setRunForm({...runForm, max_vms_per_student:Number(event.target.value)})}/></label>
        <div className='ui-cluster ui-form-grid__wide'><button disabled={!runForm.lab_id || !runForm.name} onClick={() => save(async () => { await createLabRun({...runForm, lab_id:Number(runForm.lab_id), starts_at:localDateTimeToIso(runForm.starts_at), ends_at:localDateTimeToIso(runForm.ends_at)}); setRunForm({...runForm, name:''}) }, 'Lab run created.')}>Create run</button></div>
      </div>
      <label className='ui-field'>Manage run<select className='input' value={selectedRun} onChange={event => setSelectedRun(event.target.value)}><option value=''>Select a run…</option>{runs.filter(run => classLabs.some(lab => lab.id === run.lab_id)).map(row => <option key={row.id} value={row.id}>{row.name} — {row.state}</option>)}</select></label>
      {selectedRunRow ? <>
        <div className='ui-cluster' aria-label='Run actions'><button onClick={() => save(async () => { await bulkAssignRun(selectedRun); setAssignments(await listRunAssignments(selectedRun)) }, 'Assignments created for the active roster.')}>Assign roster</button>{['start','stop','reboot'].map(action => <button key={action} onClick={() => save(() => api.post(`/admin/lab-runs/${selectedRun}/vms/${action}`), `${action} queued for assigned VMs.`)}>{action[0].toUpperCase()+action.slice(1)} all</button>)}{['draft','scheduled'].includes(selectedRunRow.state) && <button onClick={() => save(() => changeLabRunState(selectedRun,'activate'), 'Lab run activated.')}>Activate now</button>}{selectedRunRow.state === 'draft' && selectedRunRow.starts_at && <button onClick={() => save(() => changeLabRunState(selectedRun,'schedule'), 'Lab run scheduled; access will open inside its window.')}>Schedule</button>}{selectedRunRow.state === 'active' && <button className='btn-danger' onClick={endRun}>End run</button>}</div>
        <p className='muted' role='status'>State: {selectedRunRow.state} · Currently open: {selectedRunRow.effective_open ? 'Yes' : 'No'} · Quota: {selectedRunRow.max_vms_per_student} VM(s) per student</p>
        {!detailLoading && !detailError && assignments.length === 0 ? <p className='muted'>No assignments have been created for this run.</p> : <div className='ui-table-wrap' role='region' aria-label='Run assignments' tabIndex='0'><table className='ui-table'><thead><tr><th scope='col'>Student</th><th scope='col'>Slot</th><th scope='col'>Template</th><th scope='col'>Status</th><th scope='col'>VM</th><th scope='col'>Action</th></tr></thead><tbody>{assignments.map(row => { const name = row.username || row.user_id; return <tr key={row.id}><th scope='row'>{name}</th><td>{row.slot_index}</td><td>{row.template_name || row.template_id}</td><td>{row.status}</td><td>{row.student_vm_id || '-'}</td><td><button className='btn-danger' aria-label={`Revoke assignment for ${name}`} onClick={() => save(async () => { await revokeRunAssignment(selectedRun,row.id); setAssignments(await listRunAssignments(selectedRun)) }, 'Assignment revoked.')}>Revoke</button></td></tr> })}</tbody></table></div>}
      </> : <p className='muted'>Select a run to manage assignments and VM actions.</p>}
    </section> : null}
  </section>
}
