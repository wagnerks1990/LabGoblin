import { useEffect, useState } from 'react'
import api from '../services/api'

export default function EmailPreferences() {
  const [enabled, setEnabled] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const load = async () => {
    setError('')
    try { const r = await api.get('/email/preferences'); setEnabled(r.data.notifications_enabled) }
    catch { setError('Email preferences could not be loaded.') }
  }
  useEffect(() => { load() }, [])
  const save = async event => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try { await api.put('/email/preferences', { notifications_enabled: enabled }); setMessage('Email preferences saved.') }
    catch { setError('Email preferences could not be saved.') }
    finally { setBusy(false) }
  }
  return <section className='panel' aria-labelledby='email-preferences-title'>
    <h2 id='email-preferences-title'>Email notifications</h2>
    <p>Choose whether to receive lab availability, ending-window, and operation notices. Account security messages are sent when email is enabled.</p>
    {error ? <p role='alert'>{error} <button type='button' onClick={load}>Retry loading</button></p> : null}
    {message ? <p role='status'>{message}</p> : null}
    {enabled === null && !error ? <p role='status'>Loading email preferences…</p> : null}
    {enabled !== null ? <form onSubmit={save}><label><input type='checkbox' checked={enabled} onChange={e => setEnabled(e.target.checked)} /> Receive lab and operation notices</label><button disabled={busy}>{busy ? 'Saving…' : 'Save email preferences'}</button></form> : null}
  </section>
}
