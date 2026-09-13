import { useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AccessContext } from '../components/AccessControl'
import { EmptyState, ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import api from '../services/api'
import { listOperations } from '../services/operationsApi'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import { listMyAssignments } from '../services/classroomApi'

const detail = error => {
  const value = error?.response?.data?.detail
  return typeof value === 'string' ? value : JSON.stringify(value || error?.message || 'Request failed')
}

export default function CreateVmPage({ setMessage }) {
  const access = useContext(AccessContext)
  const [templates, setTemplates] = useState([])
  const [assignments, setAssignments] = useState([])
  const [availability, setAvailability] = useState([])
  const [assignmentId, setAssignmentId] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [labName, setLabName] = useState('classroom-lab')
  const [mode, setMode] = useState('assignment')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [createdVmId, setCreatedVmId] = useState(null)
  const [operation, setOperation] = useState(null)
  const [operationError, setOperationError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    setWarning('')
    if (access.platformAdmin) {
      try { await api.post('/admin/proxmox/templates/sync') }
      catch (requestError) { setWarning(`Template refresh failed: ${detail(requestError)}`) }
    }
    const requests = [api.get('/templates'), listMyAssignments()]
    if (access.platformAdmin) requests.push(api.get('/admin/proxmox/templates/availability'))
    const [templatesResult, assignmentsResult, availabilityResult] = await Promise.allSettled(requests)
    const templateRows = templatesResult.status === 'fulfilled' && Array.isArray(templatesResult.value.data) ? templatesResult.value.data.filter(row => row.enabled) : []
    const assignmentRows = assignmentsResult.status === 'fulfilled' && Array.isArray(assignmentsResult.value) ? assignmentsResult.value : []
    setTemplates(templateRows)
    setAssignments(assignmentRows)
    setAvailability(availabilityResult?.status === 'fulfilled' && Array.isArray(availabilityResult.value.data) ? availabilityResult.value.data : [])
    const firstAssignment = assignmentRows.find(row => row.can_provision)
    if (firstAssignment) {
      setMode('assignment')
      setAssignmentId(String(firstAssignment.id))
      setTemplateId(String(firstAssignment.template_id))
      setLabName(firstAssignment.lab_name || 'classroom-lab')
    } else if (access.tenantInstructor && templateRows.length) {
      setMode('direct')
      setTemplateId(String(templateRows[0].id))
    }
    if (templatesResult.status === 'rejected' && assignmentsResult.status === 'rejected') {
      setError(detail(assignmentsResult.reason || templatesResult.reason))
    } else if (assignmentsResult.status === 'rejected') {
      setWarning('Classroom assignments could not be loaded. Direct provisioning remains available to instructors.')
    } else if (templatesResult.status === 'rejected' && access.tenantInstructor) {
      setWarning('Organization templates could not be loaded.')
    }
    setLoading(false)
  }, [access.platformAdmin, access.tenantInstructor])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!createdVmId) return
    let cancelled = false
    let timer
    const poll = async () => {
      let finished = false
      try {
        const rows = await listOperations()
        if (cancelled) return
        const found = rows.find(row => row.operation_type === 'vm.create' && String(row.target_id) === String(createdVmId))
        setOperation(found || null)
        setOperationError('')
        finished = found && !['queued', 'running'].includes(found.state)
      } catch (requestError) {
        if (!cancelled) setOperationError(detail(requestError))
      }
      if (!cancelled && !finished) timer = setTimeout(poll, 2000)
    }
    poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [createdVmId])

  const usableAssignments = useMemo(() => assignments.filter(row => row.can_provision), [assignments])
  const selectedAssignment = assignments.find(row => String(row.id) === assignmentId)
  const selectedAvailability = availability.find(row => String(row.template_id) === String(templateId))

  const chooseAssignment = id => {
    const assignment = assignments.find(row => String(row.id) === String(id))
    setAssignmentId(String(id))
    if (assignment) {
      setTemplateId(String(assignment.template_id))
      setLabName(assignment.lab_name || 'classroom-lab')
    }
  }

  const create = async event => {
    event.preventDefault()
    setBusy(true)
    try {
      const response = await api.post('/vms', {
        template_id: Number(templateId),
        assignment_id: mode === 'assignment' ? Number(assignmentId) : null,
        lab_name: labName,
        auto_start: true,
      })
      setOperationError('')
      setCreatedVmId(response.data.id)
      setOperation(null)
      setMessage({ type: 'success', text: response.data.message || 'VM provisioning was queued.' })
      if (mode === 'assignment') {
        setAssignments(rows => rows.map(row => String(row.id) === assignmentId ? { ...row, can_provision: false, student_vm_id: response.data.id } : row))
        setAssignmentId('')
      }
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError) })
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingState label='Finding available lab assignments…' />
  if (error) return <ErrorState message={error} onRetry={load} retrying={loading} />

  const canSubmit = Boolean(templateId && labName.trim() && (mode === 'direct' || assignmentId))
  return <section>
    <div className='panel-head'>
      <div><h1>Provision a virtual machine</h1><p className='muted'>Choose an assignment and LabGoblin will create and start the correct VM.</p></div>
      <Link to='/vms'>Back to my VMs</Link>
    </div>
    {createdVmId ? <section className='panel' aria-label='Provisioning progress' aria-live='polite'>
      <div className='panel-head'><h2>VM creation</h2><WorkflowStatus value={operation?.state || 'queued'} /></div>
      <p>{operation ? `VM ${createdVmId} · ${operation.state}` : 'Waiting for the worker to report progress…'}</p>
      {operation?.error ? <p className='msg error' role='alert'>{operation.error}</p> : null}
      {operationError ? <p className='msg error' role='alert'>Progress could not be refreshed: {operationError}</p> : null}
      <Link to='/operations'>View operation details</Link>
    </section> : null}
    {warning ? <p className='msg error' role='alert'>{warning}</p> : null}

    {!usableAssignments.length && !access.tenantInstructor ? <EmptyState
      title='No assignment is ready'
      message={assignments.length ? 'Your assignments are already provisioned or outside their active schedule.' : 'Your instructor has not assigned an active lab yet.'}
      action={<Link to='/vms'>Return to my VMs</Link>}
    /> : <form className='panel' onSubmit={create}>
      {usableAssignments.length ? <fieldset>
        <legend>Available assignments</legend>
        <div className='card-grid'>
          {usableAssignments.map(assignment => <label className='panel' key={assignment.id}>
            <input type='radio' name='assignment' value={assignment.id} checked={String(assignment.id) === assignmentId} onChange={() => { setMode('assignment'); chooseAssignment(assignment.id) }} />
            <strong>{assignment.lab_name || assignment.run_name}</strong>
            <span className='muted' style={{ display: 'block' }}>{assignment.run_name} · {assignment.template_name}</span>
            {assignment.expires_at ? <span className='muted' style={{ display: 'block' }}>Available until {new Date(assignment.expires_at).toLocaleString()}</span> : null}
          </label>)}
        </div>
      </fieldset> : null}

      {access.tenantInstructor ? <details open={!usableAssignments.length} style={{ marginTop: 16 }}>
        <summary>Instructor provisioning</summary>
        <p className='muted'>Create a VM directly from an organization template without using a student assignment.</p>
        <label>
          <input type='radio' name='assignment' checked={mode === 'direct'} onChange={() => setMode('direct')} /> Provision directly
        </label>
        {mode === 'direct' ? <div style={{ marginTop: 12 }}>
          <label htmlFor='provision-template'>Template</label>
          <select id='provision-template' className='input' value={templateId} onChange={event => setTemplateId(event.target.value)}>
            <option value=''>Select a template…</option>
            {templates.map(template => <option key={template.id} value={template.id}>{template.name} (VMID {template.source_vmid}, {template.proxmox_node})</option>)}
          </select>
          <label htmlFor='provision-lab-name'>VM name prefix</label>
          <input id='provision-lab-name' className='input' value={labName} onChange={event => setLabName(event.target.value)} />
          {selectedAvailability && !selectedAvailability.can_balance_across_all_nodes ? <p className='msg'>Placement is limited to {(selectedAvailability.available_nodes || []).join(', ') || 'the source node'}. {selectedAvailability.recommended_action || ''}</p> : null}
          {!templates.length ? <p className='muted'>No organization templates are available. Ask an administrator to refresh the template catalog and enable a discovered template.</p> : null}
        </div> : null}
      </details> : null}

      {mode === 'assignment' && selectedAssignment ? <div className='panel' style={{ marginTop: 16 }}>
        <h3>Ready to provision</h3>
        <p>{selectedAssignment.lab_name} using {selectedAssignment.template_name}</p>
        <p className='muted'>The VM will start automatically. Progress is available on the Operations page.</p>
      </div> : null}
      <button type='submit' disabled={busy || !canSubmit} style={{ marginTop: 16 }}>{busy ? 'Queuing provisioning…' : 'Provision and start VM'}</button>
    </form>}
  </section>
}
