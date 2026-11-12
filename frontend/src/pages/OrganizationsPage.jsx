import { useCallback, useEffect, useState } from 'react'
import { EmptyState, ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import { createOrganization, deactivateOrganizationMember, listAdminOrganizations, listOrganizationMembers, patchOrganization, putOrganizationMember } from '../services/adminOrganizationsApi'
import { listUsers } from '../services/adminUsersApi'

const emptyOrganization = { name: '', slug: '', enabled: true }
const detail = (error, fallback) => {
  const value = error?.response?.data?.detail
  return typeof value === 'string' ? value : value ? JSON.stringify(value) : fallback
}

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState([])
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(emptyOrganization)
  const [selectedId, setSelectedId] = useState(null)
  const [members, setMembers] = useState([])
  const [memberRoles, setMemberRoles] = useState({})
  const [memberForm, setMemberForm] = useState({ user_id: '', role: 'student' })
  const [message, setMessage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [membersLoading, setMembersLoading] = useState(false)
  const [membersError, setMembersError] = useState('')
  const [busy, setBusy] = useState(false)
  const [rowBusy, setRowBusy] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [organizationRows, userRows] = await Promise.all([listAdminOrganizations(), listUsers()])
      setOrganizations(Array.isArray(organizationRows) ? organizationRows : [])
      setUsers(Array.isArray(userRows) ? userRows : [])
    } catch (requestError) {
      setLoadError(detail(requestError, 'Organization administration could not be loaded.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const loadMembers = async id => {
    setSelectedId(id)
    setMembersLoading(true)
    setMembersError('')
    try {
      const rows = await listOrganizationMembers(id)
      setMembers(Array.isArray(rows) ? rows : [])
      setMemberRoles(Object.fromEntries((rows || []).map(member => [member.user_id, member.role])))
    } catch (requestError) {
      setMembersError(detail(requestError, 'Organization members could not be loaded.'))
    } finally {
      setMembersLoading(false)
    }
  }

  const create = async event => {
    event.preventDefault()
    setBusy(true)
    try {
      await createOrganization(form)
      setForm(emptyOrganization)
      await load()
      setMessage({ type: 'success', text: 'Organization created. You were added as its first owner.' })
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError, 'Organization creation failed.') })
    } finally {
      setBusy(false)
    }
  }

  const saveMember = async event => {
    event.preventDefault()
    if (!selectedId || !memberForm.user_id) return
    setBusy(true)
    try {
      await putOrganizationMember(selectedId, Number(memberForm.user_id), { role: memberForm.role, is_active: true })
      setMemberForm({ user_id: '', role: 'student' })
      await Promise.all([loadMembers(selectedId), load()])
      setMessage({ type: 'success', text: 'Organization membership saved.' })
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError, 'Membership update failed.') })
    } finally {
      setBusy(false)
    }
  }

  const updateMemberRole = async member => {
    const role = memberRoles[member.user_id] || member.role
    if (member.role === 'owner' && role !== 'owner' && !window.confirm(`Change ${member.email || member.username || member.user_id} from owner to ${role}? The organization must retain another active owner.`)) return
    setRowBusy(member.user_id)
    try {
      await putOrganizationMember(selectedId, member.user_id, { role, is_active: member.is_active })
      await loadMembers(selectedId)
      setMessage({ type: 'success', text: `Role updated for ${member.email || member.username || member.user_id}.` })
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError, 'Role update failed.') })
    } finally {
      setRowBusy(null)
    }
  }

  const toggleMember = async member => {
    const name = member.email || member.username || member.user_id
    if (member.is_active && !window.confirm(`Deactivate ${name} in this organization? Their organization access will end immediately.`)) return
    setRowBusy(member.user_id)
    try {
      if (member.is_active) await deactivateOrganizationMember(selectedId, member.user_id)
      else await putOrganizationMember(selectedId, member.user_id, { role: member.role, is_active: true })
      await Promise.all([loadMembers(selectedId), load()])
      setMessage({ type: 'success', text: `${name} ${member.is_active ? 'deactivated' : 'reactivated'}.` })
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError, 'Membership status update failed.') })
    } finally {
      setRowBusy(null)
    }
  }

  return <section className='page-shell' aria-labelledby='organizations-title'>
    <header className='ui-page-header'>
      <div className='ui-page-header__copy'><p className='muted'>Platform administration</p><h1 id='organizations-title' className='ui-page-header__title'>Organizations</h1><p className='ui-page-header__description'>Manage tenant boundaries and membership roles. Every organization must retain an active owner.</p></div>
      <div className='ui-page-header__actions'><button type='button' onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh organizations'}</button></div>
    </header>
    {message ? <p className={`msg ${message.type}`} role={message.type === 'error' ? 'alert' : 'status'} aria-live='polite'>{message.text}</p> : null}

    <details className='panel' open={!organizations.length}>
      <summary>Create an organization</summary>
      <form className='ui-form-grid' onSubmit={create} style={{ marginTop: 16 }}>
        <label className='ui-field'>Organization name<input className='input' value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /></label>
        <label className='ui-field'>URL-safe slug<input className='input' pattern='[a-z0-9]+(?:-[a-z0-9]+)*' aria-describedby='organization-slug-help' value={form.slug} onChange={event => setForm({ ...form, slug: event.target.value.toLowerCase() })} /></label>
        <p id='organization-slug-help' className='muted ui-form-grid__wide'>Use lowercase letters, numbers, and single hyphens.</p>
        <label className='ui-form-grid__wide'><input type='checkbox' checked={form.enabled} onChange={event => setForm({ ...form, enabled: event.target.checked })} /> Enable immediately</label>
        <div className='ui-form-grid__wide'><button disabled={busy || !form.name || !form.slug}>{busy ? 'Creating…' : 'Create organization'}</button></div>
      </form>
    </details>

    {loading ? <LoadingState label='Loading organizations…' /> : null}
    {loadError ? <ErrorState message={loadError} onRetry={load} retrying={loading} /> : null}
    {!loading && !loadError ? <section className='panel' aria-labelledby='organization-list-title'>
      <h2 id='organization-list-title'>Configured organizations</h2>
      {!organizations.length ? <EmptyState title='No organizations yet' message='Create an organization to establish the first tenant boundary.' /> : <div className='ui-table-wrap ui-table-wrap--cards' role='region' aria-labelledby='organization-list-title' tabIndex='0'><table className='ui-table'><thead><tr><th scope='col'>Organization</th><th scope='col'>Status</th><th scope='col'>Members</th><th scope='col'>Actions</th></tr></thead><tbody>
        {organizations.map(organization => <tr key={organization.id}><th scope='row'>{organization.name}<div className='muted'>{organization.slug}</div></th><td><WorkflowStatus value={organization.enabled ? 'active' : 'disabled'} /></td><td>{organization.member_count}</td><td><div className='ui-cluster'><button type='button' onClick={() => loadMembers(organization.id)}>Manage {organization.name} members</button><button type='button' className='ui-button--secondary' onClick={async () => { if (organization.enabled && !window.confirm(`Disable ${organization.name}? Members will lose access until it is enabled again.`)) return; try { await patchOrganization(organization.id, { enabled: !organization.enabled }); await load(); setMessage({ type: 'success', text: `${organization.name} ${organization.enabled ? 'disabled' : 'enabled'}.` }) } catch (requestError) { setMessage({ type: 'error', text: detail(requestError, 'Organization status update failed.') }) } }}>{organization.enabled ? `Disable ${organization.name}` : `Enable ${organization.name}`}</button></div></td></tr>)}
      </tbody></table></div>}
    </section> : null}

    {selectedId ? <section className='panel' aria-labelledby='organization-members-title'>
      <div className='panel-head'><div><h2 id='organization-members-title'>Members of {organizations.find(row => row.id === selectedId)?.name || selectedId}</h2><p className='muted'>Role changes affect access in this organization only.</p></div><button type='button' className='ui-button--secondary' onClick={() => setSelectedId(null)}>Close members</button></div>
      {membersLoading ? <LoadingState label='Loading organization members…' /> : null}
      {membersError ? <ErrorState message={membersError} onRetry={() => loadMembers(selectedId)} retrying={membersLoading} /> : null}
      {!membersLoading && !membersError && !members.length ? <EmptyState title='No members' message='Add an existing platform user below.' /> : null}
      {!membersLoading && !membersError && members.length ? <div className='ui-table-wrap ui-table-wrap--cards' role='region' aria-labelledby='organization-members-title' tabIndex='0'><table className='ui-table'><thead><tr><th scope='col'>User</th><th scope='col'>Status</th><th scope='col'>Organization role</th><th scope='col'>Actions</th></tr></thead><tbody>{members.map(member => <tr key={member.user_id}><th scope='row'>{member.email || member.username || member.user_id}</th><td><WorkflowStatus value={member.is_active ? 'active' : 'disabled'} /></td><td><label className='ui-field'>Role for {member.email || member.username || member.user_id}<select className='input' value={memberRoles[member.user_id] || member.role} onChange={event => setMemberRoles(current => ({ ...current, [member.user_id]: event.target.value }))}><option value='student'>Student</option><option value='instructor'>Instructor</option><option value='admin'>Administrator</option><option value='owner'>Owner</option></select></label></td><td><div className='ui-cluster'><button type='button' disabled={rowBusy === member.user_id || (memberRoles[member.user_id] || member.role) === member.role} onClick={() => updateMemberRole(member)}>Save {member.email || member.username || member.user_id} role</button><button type='button' className={member.is_active ? 'btn-danger' : 'ui-button--secondary'} disabled={rowBusy === member.user_id} onClick={() => toggleMember(member)}>{member.is_active ? `Deactivate ${member.email || member.username || member.user_id}` : `Reactivate ${member.email || member.username || member.user_id}`}</button></div></td></tr>)}</tbody></table></div> : null}
      <details style={{ marginTop: 16 }}><summary>Add an existing user</summary><form className='ui-form-grid' onSubmit={saveMember} style={{ marginTop: 16 }}><label className='ui-field'>Platform user<select className='input' value={memberForm.user_id} onChange={event => setMemberForm({ ...memberForm, user_id: event.target.value })}><option value=''>Select a user…</option>{users.map(user => <option key={user.id} value={user.id}>{user.username} ({user.email})</option>)}</select></label><label className='ui-field'>Organization role<select className='input' value={memberForm.role} onChange={event => setMemberForm({ ...memberForm, role: event.target.value })}><option value='student'>Student</option><option value='instructor'>Instructor</option><option value='admin'>Administrator</option><option value='owner'>Owner</option></select></label><div className='ui-form-grid__wide'><button disabled={busy || !memberForm.user_id}>{busy ? 'Saving…' : 'Add organization member'}</button></div></form></details>
    </section> : null}
  </section>
}
