import { useCallback, useContext, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AccessContext } from '../components/AccessControl'
import { LoadingState, ErrorState } from '../components/workflows/WorkflowState'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import TemplateGuestCredentials from '../components/workflows/TemplateGuestCredentials'
import api from '../services/api'
import { emptySetup, setupSteps, setupStepError, setupPayload, setupFromSaved, submissionId } from '../services/labSetup'
import ClassroomManagementPage from './ClassroomManagementPage'

const detail = error => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : 'Setup could not be saved. Check the fields and try again.'

export default function ClassroomPage({ setMessage }) {
  const access = useContext(AccessContext)
  const [catalog, setCatalog] = useState({ classes: [], pools: [], templates: [], members: [], runs: [] })
  const [loading, setLoading] = useState(true); const [loadError, setLoadError] = useState('')
  const [editing, setEditing] = useState(false); const [runId, setRunId] = useState(null)
  const [form, setForm] = useState(emptySetup); const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('')
  const [advanced, setAdvanced] = useState(false); const [studentSearch, setStudentSearch] = useState('')
  const [machineMode, setMachineMode] = useState('template')
  const requestId = useRef(submissionId()); const title = useRef(null)
  const [dirty, setDirty] = useState(false)
  const load = useCallback(async () => {
    setLoading(true); setLoadError('')
    try {
      setCatalog((await api.get('/admin/lab-setups/catalog')).data)
    } catch (err) { setLoadError(detail(err)) } finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])
  useEffect(() => { if (editing) title.current?.focus() }, [step, editing])
  useEffect(() => {
    const warn = event => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  const update = patch => { setForm(old => ({ ...old, ...patch, reviewed: false })); setDirty(true); setError(''); requestId.current = submissionId() }
  const openNew = () => { setForm(emptySetup()); setRunId(null); setStep(0); setEditing(true); setDirty(false); setError(''); setNotice(''); setMachineMode('template'); requestId.current = submissionId() }
  const openExisting = async id => {
    setBusy(true); setError(''); setNotice('')
    try { const row = (await api.get(`/admin/lab-setups/${id}`)).data; setForm(setupFromSaved(row)); setRunId(id); setStep(0); setMachineMode('pool'); setEditing(true); setDirty(false); requestId.current = submissionId() }
    catch (err) { setError(detail(err)) } finally { setBusy(false) }
  }
  const next = () => { const message = ['ended','cancelled'].includes(form.state) ? '' : setupStepError(form, step); if (message) { setError(message); return } setError(''); setStep(step + 1) }
  const save = async event => {
    event.preventDefault()
    if (busy) return
    for (let i=0; i<setupSteps.length; i++) { const message = setupStepError(form, i); if (message) { setError(message); setStep(i); return } }
    setBusy(true); setError('')
    try {
      const payload = setupPayload(form, requestId.current)
      const result = runId ? await api.put(`/admin/lab-setups/${runId}`, payload) : await api.post('/admin/lab-setups', payload)
      const row = result.data
      setDirty(false); setForm(emptySetup()); setEditing(false); setRunId(null)
      setNotice(`${row.name} saved as ${row.state}. ${row.assignment_count} machine assignment(s) prepared. VM provisioning is tracked separately when students start their labs.`)
      await load()
    } catch (err) { setError(detail(err)) } finally { setBusy(false) }
  }
  const cancel = () => { if (dirty && !window.confirm('Discard unsaved setup changes?')) return; setForm(emptySetup()); setDirty(false); setEditing(false); setError('') }
  if (advanced) return <><div className='ui-cluster'><button type='button' onClick={() => { setAdvanced(false); load() }}>Back to guided setup</button></div><ClassroomManagementPage setMessage={setMessage}/></>
  if (loading) return <LoadingState label='Loading lab setup…'/>
  if (loadError) return <ErrorState message={loadError} onRetry={load}/>
  const students = catalog.members.filter(row => row.role === 'student' && row.is_active !== false)
  const pool = catalog.pools.find(row => String(row.id) === String(form.pool_id))
  const template = catalog.templates.find(row => String(row.id) === String(form.template_id)) || catalog.templates.find(row => row.source_vmid === pool?.template_vmid)
  const classroom = catalog.classes.find(row => String(row.id) === String(form.class_id))
  const readOnly = !['draft', 'scheduled', 'active'].includes(form.state)

  return <section className='page-shell lab-studio' aria-labelledby='setup-title'>
    <header className='workspace-heading'><div><p className='eyebrow'>LabGoblin / Teaching</p><h2 id='setup-title'>Labs, ready for learning</h2><p>One guided setup for the class, machines, student accounts, and access.</p></div>{!editing ? <button type='button' onClick={openNew}>Create a lab</button> : <button type='button' className='ui-button--secondary' onClick={cancel} disabled={busy}>Close setup</button>}</header>
    {notice ? <p className='ui-alert ui-alert--success' role='status'>{notice}</p> : null}
    {error ? <p className='msg error' role='alert'>{error}</p> : null}
    {!editing ? <>
      <div className='workspace-note'><img src='/brand/labgoblin-icon.svg' alt=''/><div><h3>Build. Deploy. Learn. Repeat.</h3><p>Start with a template. LabGoblin creates the connected classroom records together. Save a draft, return to edit, then open the lab when you’re ready.</p></div></div>
      <div className='workspace-section-title'><h3>Your lab setups</h3><button className='ui-button--secondary' onClick={load}>Refresh</button></div>
      {!catalog.runs.length ? <div className='panel workspace-empty'><h3>Your first lab starts here</h3><p>We’ll guide you through five short steps. Existing classes, pools, and accounts can be reused.</p><button onClick={openNew}>Create your first lab</button></div> : <div className='lab-resource-grid'>{catalog.runs.map(row => <article className='panel' key={row.id}><WorkflowStatus value={row.state}/><h3>{row.name}</h3><p>{row.assignment_count} assignment(s) · {row.max_vms_per_student} machine(s) per student</p><button disabled={busy} onClick={() => openExisting(row.id)}>{['ended','cancelled'].includes(row.state) ? 'View setup' : 'Edit setup'}</button></article>)}</div>}
      <details className='panel'><summary>Detailed classroom and infrastructure management</summary><p>Manage shared blueprints, class rosters, run power actions, and reviewed cleanup.</p><div className='ui-cluster'><button onClick={() => setAdvanced(true)}>Open detailed classroom management</button><Link to='/pools'>Manage pools</Link>{access.platformAdmin ? <Link to='/admin/users'>Manage accounts</Link> : null}</div></details>
    </> : <div className='lab-wizard-layout'>
      <nav className='lab-wizard-steps' aria-label='Lab setup steps'><ol>{setupSteps.map((label, index) => <li key={label}><button type='button' aria-current={step === index ? 'step' : undefined} disabled={busy || index > step} onClick={() => { setStep(index); setError('') }}><span aria-hidden='true'>{index + 1}</span>{label}</button></li>)}</ol><p>Changes are saved together after review. Passwords are never saved as a browser draft.</p></nav>
      <form className='panel lab-wizard-panel' onSubmit={save}>
        <p className='eyebrow'>{runId ? 'Edit lab' : 'New lab'} · Step {step + 1} of {setupSteps.length}</p><h3 tabIndex='-1' ref={title}>{setupSteps[step]}</h3>
        {readOnly ? <p role='status'>This lab has ended and is read-only. Create a new setup to run it again.</p> : null}
        <fieldset disabled={busy || readOnly} className='lab-wizard-fields'>
          {step === 0 ? <>
            <label className='ui-field'>Lab name<input value={form.name} maxLength='120' onChange={e => update({name:e.target.value})} placeholder='For example, Linux networking basics'/></label>
            <label className='ui-field'>Student instructions<textarea value={form.description} maxLength='255' rows='4' onChange={e => update({description:e.target.value})} placeholder='What should students do in this lab?'/></label>
            <label className='ui-field'>Class<select disabled={Boolean(runId)} value={form.class_id} onChange={e => update({class_id:e.target.value})}><option value=''>Create a new class</option>{catalog.classes.map(row => <option value={row.id} key={row.id}>{row.name}</option>)}</select></label>
            {!form.class_id ? <div className='ui-form-grid'><label className='ui-field'>New class name<input maxLength='120' value={form.class_name} onChange={e => update({class_name:e.target.value})}/></label><label className='ui-field'>Term (optional)<input maxLength='120' value={form.term} onChange={e => update({term:e.target.value})}/></label></div> : <p>Using {classroom?.name || form.class_name}. Other labs in this class keep their own settings.</p>}
          </> : null}
          {step === 1 ? <>
            <p>Choose the starting machine. A dedicated pool is created automatically when you choose a template.</p>
            <label className='ui-field'>Machine source<select value={machineMode} onChange={e => { setMachineMode(e.target.value); update({pool_id:'',template_id:''}) }}><option value='template'>Start from a template</option><option value='pool'>Reuse an existing pool</option></select></label>
            {machineMode === 'template' ? <label className='ui-field'>Template<select value={form.template_id} onChange={e => update({template_id:e.target.value,pool_id:''})}><option value=''>Choose a template…</option>{catalog.templates.filter(row => row.enabled).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label> : <label className='ui-field'>Existing pool<select value={form.pool_id} onChange={e => update({pool_id:e.target.value,template_id:''})}><option value=''>Choose a pool…</option>{catalog.pools.filter(row => row.enabled && !row.maintenance_mode).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>}
            {template ? <div className='workspace-note'><img src='/brand/labgoblin-icon.svg' alt=''/><div><h4>{template.name}</h4><p>Each assignment uses a separate clone of this template.</p></div></div> : <p>Ask an administrator to import a template if none is available.</p>}
            {pool?.placement_warning ? <p role='status'>{pool.placement_warning}</p> : null}
            <p>Guest logins are managed in template settings. The connection page checks which browser methods are available.</p>
          </> : null}
          {step === 2 ? <>
            <p>Select students for this lab. LabGoblin enrolls them in the class and creates their assignments when you save.</p>
            <label className='ui-field'>Find a student<input type='search' value={studentSearch} onChange={e => setStudentSearch(e.target.value)}/></label>
            <div className='lab-roster-list' role='group' aria-label='Student roster'>{students.filter(row => row.username.toLowerCase().includes(studentSearch.toLowerCase())).map(row => <label key={row.user_id}><input type='checkbox' checked={form.student_ids.includes(row.user_id)} onChange={e => update({student_ids:e.target.checked ? [...form.student_ids,row.user_id] : form.student_ids.filter(id => id !== row.user_id)})}/><span>{row.username}</span></label>)}</div>
            {!students.length ? <p>No active student members are available.</p> : null}<p role='status'>{form.student_ids.length + form.new_students.length} student(s) selected</p>
            {access.platformAdmin ? <details><summary>Create student login accounts here</summary><p>New accounts are added to this organization and class. Students must change their initial password at first sign-in. Use a long initial password with upper- and lowercase letters, a number, and a symbol; share it with the student separately.</p>{form.new_students.map((row,index) => <div className='panel ui-stack' key={index}><h4>New student {index + 1}</h4>{[['username','Username','text'],['email','Email','email'],['password','Initial password','password']].map(([field,label,type]) => <label className='ui-field' key={field}>{label}<input type={type} autoComplete={field === 'password' ? 'new-password' : 'off'} value={row[field]} onChange={e => update({new_students:form.new_students.map((item,i) => i === index ? {...item,[field]:e.target.value} : item)})}/></label>)}<button type='button' className='ui-button--secondary' onClick={() => update({new_students:form.new_students.filter((_,i) => i !== index)})}>Remove new student {index + 1}</button></div>)}<button type='button' disabled={form.new_students.length >= 100} onClick={() => update({new_students:[...form.new_students,{username:'',email:'',password:'',display_name:''}]})}>Add new student account</button></details> : <p>An administrator can create login accounts; instructors can enroll existing student members here.</p>}
          </> : null}
          {step === 3 ? <>
            <label className='ui-field'>Machines per student<input type='number' min='1' max='10' value={form.slots} onChange={e => update({slots:e.target.value})}/></label>
            <fieldset><legend>Browser connection methods</legend><p>Methods appear only after the VM passes its connection checks.</p>{[['console_enabled','VNC desktop'],['rdp_enabled','Windows remote desktop (RDP)'],['terminal_enabled','Linux terminal (SSH)']].map(([key,label]) => <label className='lab-check' key={key}><input type='checkbox' checked={form[key]} onChange={e => update({[key]:e.target.checked})}/>{label}</label>)}</fieldset>
            <details><summary>Student power controls</summary>{[['student_can_power_off','Allow power off'],['student_can_reset','Allow restart / reset']].map(([key,label]) => <label className='lab-check' key={key}><input type='checkbox' checked={form[key]} onChange={e => update({[key]:e.target.checked})}/>{label}</label>)}</details>
            <label className='ui-field'>When should students have access?<select value={form.state} onChange={e => update({state:e.target.value})}>{readOnly ? <option value={form.state}>{form.state}</option> : null}<option value='draft'>Save as draft — open later</option><option value='scheduled'>Open on a schedule</option><option value='active'>Open now</option></select></label>
            <div className='ui-form-grid'><label className='ui-field'>Starts (local time, optional for draft/open now)<input type='datetime-local' value={form.starts_at} onChange={e => update({starts_at:e.target.value})}/></label><label className='ui-field'>Ends (local time, optional)<input type='datetime-local' value={form.ends_at} onChange={e => update({ends_at:e.target.value})}/></label></div><p>After the end time, student access closes. VM cleanup remains a separate reviewed action.</p>
          </> : null}
          {step === 4 ? <>
            <p>Review the connected setup. Saving creates classroom records and assignments; it does not report VM creation as complete.</p>
            <dl className='lab-review'><dt>Lab</dt><dd>{form.name}</dd><dt>Class</dt><dd>{classroom?.name || form.class_name}</dd><dt>Machines</dt><dd>{pool?.name || template?.name || 'Unavailable'} · {form.slots} per student</dd><dt>Students</dt><dd>{form.student_ids.length} existing + {form.new_students.length} new accounts</dd><dt>Access</dt><dd>{[['console_enabled','VNC'],['rdp_enabled','RDP'],['terminal_enabled','Terminal']].filter(([key]) => form[key]).map(([,label]) => label).join(', ') || 'No browser methods enabled'}</dd><dt>Availability</dt><dd>{form.state} · {form.starts_at || 'No start restriction'} → {form.ends_at || 'No end restriction'}</dd></dl>
            <details><summary>Review student names</summary><ul>{form.student_ids.map(id => <li key={id}>{students.find(row => row.user_id === id)?.username || `Student ${id}`}</li>)}{form.new_students.map((row,i) => <li key={`new-${i}`}>{row.username} (new account)</li>)}</ul></details>
            {runId ? <p>Saving replaces this run’s assignment selection. Removing a student or changing the pool is blocked while an affected assignment has a linked VM. Class enrollment and other labs are retained.</p> : null}
            <label className='lab-check'><input type='checkbox' checked={form.reviewed} onChange={e => setForm({...form,reviewed:e.target.checked})}/> I reviewed the students, machine source, access, and schedule.</label>
          </> : null}
        </fieldset>
        <footer className='lab-wizard-footer'><button type='button' className='ui-button--secondary' disabled={step === 0 || busy} onClick={() => {setStep(step-1);setError('')}}>Back</button><span>{dirty ? 'Unsaved changes' : runId ? 'Saved setup' : 'Nothing saved yet'}</span>{step < 4 ? <button type='button' disabled={busy} onClick={next}>Continue</button> : <button type='submit' disabled={busy || readOnly || !form.reviewed}>{busy ? 'Saving setup…' : form.state === 'draft' ? 'Save draft' : runId ? 'Save changes' : form.state === 'scheduled' ? 'Save and schedule lab' : 'Save and open lab'}</button>}</footer>
      </form>
        {step === 1 && template && access.tenantAdmin ? <details className='lab-template-login'><summary>Optional: edit this template’s shared guest login</summary><p>These settings save immediately and affect all VMs inheriting this template login.</p><TemplateGuestCredentials key={template.id} templateId={template.id}/></details> : null}
    </div>}
  </section>
}
