import { useCallback, useEffect, useState } from 'react'
import { ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import { changePassword, listSessions, revokeSession } from '../services/authApi'
import EmailPreferences from '../components/EmailPreferences'

const detail = error => {
  const value = error?.response?.data?.detail
  return typeof value === 'string' ? value : 'The request could not be completed.'
}

const formatDate = value => value ? new Date(value).toLocaleString() : 'Not reported'

export default function AccountSecurityPage({ forceChange = false, onChanged, setMessage }) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [sessions, setSessions] = useState([])
  const [loadingSessions, setLoadingSessions] = useState(!forceChange)
  const [sessionsError, setSessionsError] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordBusy, setPasswordBusy] = useState(false)
  const [revoking, setRevoking] = useState(null)

  const load = useCallback(async () => {
    if (forceChange) return
    setLoadingSessions(true)
    setSessionsError('')
    try {
      const rows = await listSessions()
      setSessions(Array.isArray(rows) ? rows : [])
    } catch (requestError) {
      setSessionsError(detail(requestError))
    } finally {
      setLoadingSessions(false)
    }
  }, [forceChange])

  useEffect(() => { load() }, [load])

  const submit = async event => {
    event.preventDefault()
    setPasswordError('')
    if (newPassword !== confirmPassword) return setPasswordError('New passwords do not match.')
    setPasswordBusy(true)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setMessage?.({ type: 'success', text: 'Password changed. Other signed-in sessions were revoked.' })
      await load()
      await onChanged?.()
    } catch (requestError) {
      setPasswordError(detail(requestError))
    } finally {
      setPasswordBusy(false)
    }
  }

  const revoke = async session => {
    const prompt = session.current
      ? 'Sign out this device now? You will need to sign in again.'
      : `Revoke the session for ${session.user_agent || 'this device'}?`
    if (!window.confirm(prompt)) return
    setRevoking(session.id)
    setSessionsError('')
    try {
      await revokeSession(session.id)
      if (session.current) window.location.reload()
      else await load()
    } catch (requestError) {
      setSessionsError(detail(requestError))
    } finally {
      setRevoking(null)
    }
  }

  return <section>
    <div className='panel-head'><div>
      <h1>{forceChange ? 'Choose a private password' : 'Account security'}</h1>
      <p className='muted'>{forceChange ? 'You must replace the temporary password before continuing.' : 'Update your password and review where your account is signed in.'}</p>
    </div></div>
    <form className='panel' onSubmit={submit} aria-busy={passwordBusy}>
      <h3>Change password</h3>
      {passwordError ? <p className='msg error' role='alert'>{passwordError}</p> : null}
      <label htmlFor='current-password'>Current password</label>
      <input id='current-password' className='input' type='password' autoComplete='current-password' value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} />
      <label htmlFor='new-password'>New password</label>
      <input id='new-password' className='input' type='password' autoComplete='new-password' aria-describedby='password-guidance' value={newPassword} onChange={event => setNewPassword(event.target.value)} />
      <label htmlFor='confirm-password'>Confirm new password</label>
      <input id='confirm-password' className='input' type='password' autoComplete='new-password' value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} />
      <p id='password-guidance' className='muted'>Use at least 12 characters with upper- and lower-case letters, a number, and a symbol.</p>
      <button disabled={passwordBusy || !currentPassword || !newPassword || !confirmPassword}>{passwordBusy ? 'Changing password…' : 'Change password'}</button>
    </form>

    {!forceChange ? <EmailPreferences /> : null}
    {!forceChange ? <section style={{ marginTop: 16 }}>
      <h3>Signed-in devices</h3>
      {loadingSessions ? <LoadingState label='Loading signed-in devices…' /> : null}
      {sessionsError ? <ErrorState message={sessionsError} onRetry={load} retrying={loadingSessions} /> : null}
      {!loadingSessions && !sessionsError && !sessions.length ? <p className='muted'>No active sessions were reported.</p> : null}
      {!loadingSessions && !sessionsError ? <div className='card-grid'>
        {sessions.map(session => <article className='panel' key={session.id}>
          <div className='panel-head'><h4>{session.current ? 'This device' : (session.user_agent || 'Unknown device')}</h4>{session.current ? <span className='badge badge-running'>Current</span> : null}</div>
          <p className='muted'>IP address: {session.client_ip || 'Not reported'}</p>
          <details><summary>Session details</summary><dl><dt>Created</dt><dd>{formatDate(session.created_at)}</dd><dt>Expires</dt><dd>{formatDate(session.expires_at)}</dd></dl></details>
          <button type='button' className='btn-danger' disabled={revoking === session.id} onClick={() => revoke(session)} style={{ marginTop: 12 }}>{revoking === session.id ? 'Revoking…' : session.current ? 'Sign out this device' : 'Revoke session'}</button>
        </article>)}
      </div> : null}
    </section> : null}
  </section>
}
