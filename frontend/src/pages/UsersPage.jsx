import { useCallback, useEffect, useMemo, useState } from 'react'
import { EmptyState, ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import { createUser, deleteUser, getUserActivity, listUsers, patchUser, patchUserActivate, patchUserPassword, revokeUserSessions } from '../services/adminUsersApi'
import api from '../services/api'

const empty = { username: '', email: '', display_name: '', role_id: 1, password: '', send_invitation: false, is_active: true, force_password_change: true }
const detail = (error, fallback) => {
  const value = error?.response?.data?.detail
  return typeof value === 'string' ? value : value ? JSON.stringify(value) : fallback
}

export default function UsersPage() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(empty)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busy, setBusy] = useState(false)
  const [rowBusy, setRowBusy] = useState(null)
  const [query, setQuery] = useState('')
  const [activity, setActivity] = useState(null)
  const [activityBusy, setActivityBusy] = useState(null)
  const [resetUser, setResetUser] = useState(null)
  const [resetPassword, setResetPassword] = useState('')
  const [resetConfirmation, setResetConfirmation] = useState('')
  const [resetBusy, setResetBusy] = useState(false)
  const [resetError, setResetError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await listUsers()
      setRows(Array.isArray(data) ? data : [])
    } catch (requestError) {
      setLoadError(detail(requestError, 'Users could not be loaded.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const visibleRows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter(user => [user.username, user.email, user.display_name, user.role].some(value => String(value || '').toLowerCase().includes(needle)))
  }, [query, rows])

  const save = async event => {
    event.preventDefault()
    setBusy(true)
    try {
      if (editing) await patchUser(editing, { username: form.username, email: form.email, display_name: form.display_name, role_id: Number(form.role_id), is_active: form.is_active, force_password_change: form.force_password_change })
      else await createUser(form)
      setForm(empty)
      setEditing(null)
      await load()
      setMessage({ type: 'success', text: editing ? 'User changes saved.' : 'User created.' })
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError, 'User could not be saved.') })
    } finally {
      setBusy(false)
    }
  }

  const runRowAction = async (user, action) => {
    setRowBusy(user.id)
    try {
      await action()
      await load()
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError, 'The user action failed.') })
    } finally {
      setRowBusy(null)
    }
  }

  const closeReset = () => { setResetUser(null); setResetPassword(''); setResetConfirmation(''); setResetError('') }
  const submitPasswordReset = async event => {
    event.preventDefault()
    setResetError('')
    if (resetPassword !== resetConfirmation) return setResetError('Passwords do not match.')
    setResetBusy(true)
    try {
      await patchUserPassword(resetUser.id, { password: resetPassword, force_password_change: true })
      setMessage({ type: 'success', text: `Password reset for ${resetUser.email}. Existing sessions were revoked.` })
      closeReset()
    } catch (requestError) {
      setResetError(detail(requestError, 'Password reset failed.'))
    } finally {
      setResetBusy(false)
    }
  }

  const showActivity = async user => {
    setActivityBusy(user.id)
    try {
      setActivity({ user, data: await getUserActivity(user.id) })
    } catch (requestError) {
      setMessage({ type: 'error', text: detail(requestError, 'User activity could not be loaded.') })
    } finally {
      setActivityBusy(null)
    }
  }

  return <section className='page-shell' aria-labelledby='users-title'>
    <header className='ui-page-header'>
      <div className='ui-page-header__copy'><p className='muted'>Platform administration</p><h1 id='users-title' className='ui-page-header__title'>Users</h1><p className='ui-page-header__description'>Manage platform accounts and security. Classroom access is assigned separately.</p></div>
      <div className='ui-page-header__actions'><button type='button' onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh users'}</button></div>
    </header>
    {message ? <p className={`msg ${message.type}`} role={message.type === 'error' ? 'alert' : 'status'} aria-live='polite'>{message.text}</p> : null}

    <details className='panel' open={Boolean(editing) || rows.length === 0}>
      <summary>{editing ? `Edit ${form.username}` : 'Create a user'}</summary>
      <form className='ui-form-grid' onSubmit={save} style={{ marginTop: 16 }}>
        <label className='ui-field'>Email<input className='input' type='email' autoComplete='email' value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} /></label>
        <label className='ui-field'>Display name<input className='input' value={form.display_name} onChange={event => setForm({ ...form, display_name: event.target.value })} /></label>
        {!editing ? <label><input type='checkbox' checked={form.send_invitation} onChange={event => setForm({ ...form, send_invitation: event.target.checked, password: '' })} /> Email a single-use setup code instead of assigning a password</label> : null}
        {!editing && !form.send_invitation ? <label className='ui-field'>Initial password<input className='input' type='password' autoComplete='new-password' value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} /></label> : null}
        <label className='ui-field'>Platform role<select className='input' value={form.role_id} onChange={event => setForm({ ...form, role_id: Number(event.target.value) })}><option value='1'>Student</option><option value='2'>Teacher</option><option value='3'>Administrator</option></select></label>
        <div className='ui-form-grid__wide ui-cluster'><label><input type='checkbox' checked={form.is_active} onChange={event => setForm({ ...form, is_active: event.target.checked })} /> Active account</label><label><input type='checkbox' checked={form.force_password_change} onChange={event => setForm({ ...form, force_password_change: event.target.checked })} /> Require password change</label></div>
        <div className='ui-form-grid__wide ui-cluster'><button disabled={busy || !form.email || (!editing && !form.password && !form.send_invitation)}>{busy ? 'Saving…' : editing ? 'Save changes' : form.send_invitation ? 'Create user and queue invitation' : 'Create user'}</button>{editing ? <button type='button' className='ui-button--secondary' onClick={() => { setEditing(null); setForm(empty) }}>Cancel editing</button> : null}</div>
      </form>
    </details>

    {loading ? <LoadingState label='Loading users…' /> : null}
    {loadError ? <ErrorState message={loadError} onRetry={load} retrying={loading} /> : null}
    {!loading && !loadError ? <section className='panel' aria-labelledby='user-list-title'>
      <div className='panel-head'><div><h2 id='user-list-title'>User accounts</h2><p className='muted'>{rows.length} account(s)</p></div><label className='ui-field'>Search users<input className='input' type='search' value={query} onChange={event => setQuery(event.target.value)} /></label></div>
      {!visibleRows.length ? <EmptyState title={rows.length ? 'No matching users' : 'No users found'} message={rows.length ? 'Clear or change the search.' : 'Create the first user to get started.'} /> : <div className='ui-table-wrap ui-table-wrap--cards' role='region' aria-labelledby='user-list-title' tabIndex='0'><table className='ui-table'><thead><tr><th scope='col'>User</th><th scope='col'>Role</th><th scope='col'>Status</th><th scope='col'>Last sign-in</th><th scope='col'>Actions</th></tr></thead><tbody>
        {visibleRows.map(user => <tr key={user.id}><th scope='row'>{user.display_name || user.email}<div className='muted'>{user.email}</div></th><td>{user.role || user.role_id}</td><td><WorkflowStatus value={user.is_active ? 'active' : 'disabled'} />{user.force_password_change ? <div className='muted'>Password change required</div> : null}</td><td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</td><td><div className='ui-cluster'>
          <button type='button' className='ui-button--secondary' disabled={rowBusy === user.id} onClick={() => { setEditing(user.id); setForm({ ...empty, ...user, password: '', role_id: user.role_id }) }}>Edit {user.email}</button>
          <button type='button' className='ui-button--secondary' disabled={activityBusy === user.id} onClick={() => showActivity(user)}>{activityBusy === user.id ? 'Loading activity…' : `View ${user.email} activity`}</button>
          <details><summary>Security actions</summary><div className='ui-stack' style={{ marginTop: 8 }}>
            <button type='button' className='ui-button--secondary' disabled={rowBusy === user.id || !user.is_active} onClick={() => { if (!window.confirm(`Email a setup code to ${user.email}? Previous email codes will be invalidated.`)) return; runRowAction(user, async () => { await api.post('/admin/email/invitations', { user_id: user.id }); setMessage({ type: 'success', text: 'Setup email queued. Check Email & support for delivery status.' }) }) }}>Email {user.email} a setup code</button>
            <button type='button' className='ui-button--secondary' onClick={() => { setResetUser(user); setResetPassword(''); setResetConfirmation(''); setResetError('') }}>Reset {user.email} password</button>
            <button type='button' className='ui-button--secondary' disabled={rowBusy === user.id} onClick={() => runRowAction(user, async () => { const result = await revokeUserSessions(user.id); setMessage({ type: 'success', text: `${result.sessions_revoked} session(s) revoked for ${user.email}.` }) })}>Revoke {user.email} sessions</button>
            <button type='button' className='ui-button--secondary' disabled={rowBusy === user.id} onClick={() => runRowAction(user, () => patchUserActivate(user.id, !user.is_active))}>{user.is_active ? `Deactivate ${user.email}` : `Activate ${user.email}`}</button>
            <button type='button' className='btn-danger' disabled={rowBusy === user.id} onClick={() => { if (!window.confirm(`Delete or deactivate ${user.email}? Accounts with dependent records are deactivated instead of deleted.`)) return; runRowAction(user, async () => { const result = await deleteUser(user.id); setMessage({ type: 'success', text: result.message || `${user.email} delete/deactivate completed.` }) }) }}>Delete or deactivate {user.email}</button>
          </div></details>
        </div></td></tr>)}
      </tbody></table></div>}
    </section> : null}

    {activity ? <section className='panel' aria-labelledby='user-activity-title'><div className='panel-head'><div><h2 id='user-activity-title'>Activity for {activity.user.email}</h2><p className='muted'>Account-level activity summary.</p></div><button type='button' className='ui-button--secondary' onClick={() => setActivity(null)}>Close activity</button></div><div className='card-grid'><div className='stat-card'><div className='label'>VMS</div><div className='value'>{activity.data.vm_count}</div></div><div className='stat-card'><div className='label'>SESSIONS</div><div className='value'>{activity.data.session_count}</div></div><div className='stat-card'><div className='label'>AUDIT EVENTS</div><div className='value'>{activity.data.audit_log_count}</div></div></div><p className='muted'>Last sign-in: {activity.data.last_login_at ? new Date(activity.data.last_login_at).toLocaleString() : 'Never'}</p></section> : null}

    {resetUser ? <div className='modal-backdrop' role='presentation' onMouseDown={event => { if (event.target === event.currentTarget && !resetBusy) closeReset() }}><form className='panel modal-dialog' role='dialog' aria-modal='true' aria-labelledby='reset-password-title' onSubmit={submitPasswordReset} onKeyDown={event => { if (event.key === 'Escape' && !resetBusy) closeReset() }}>
      <h2 id='reset-password-title'>Reset password for {resetUser.email}</h2><p className='muted' id='reset-password-help'>Existing sessions are revoked and the user must change this password at next sign-in.</p>{resetError ? <p className='msg error' role='alert'>{resetError}</p> : null}
      <label htmlFor='reset-password'>New password</label><input id='reset-password' className='input' type='password' autoComplete='new-password' aria-describedby='reset-password-help' value={resetPassword} onChange={event => setResetPassword(event.target.value)} autoFocus />
      <label htmlFor='reset-password-confirmation'>Confirm new password</label><input id='reset-password-confirmation' className='input' type='password' autoComplete='new-password' value={resetConfirmation} onChange={event => setResetConfirmation(event.target.value)} />
      <div className='ui-cluster'><button disabled={resetBusy || !resetPassword || !resetConfirmation}>{resetBusy ? 'Resetting…' : 'Reset password'}</button><button type='button' className='ui-button--secondary' disabled={resetBusy} onClick={closeReset}>Cancel</button></div>
    </form></div> : null}
  </section>
}
