import { useState } from 'react'
import api from '../../services/api'

export default function TemplateGuestCredentials({ templateId }) {
  const [open, setOpen] = useState(false)
  const [policy, setPolicy] = useState(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [domain, setDomain] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const path = `/admin/templates/${templateId}/guest-credentials`
  const run = async action => {
    setBusy(true); setError(''); setMessage('')
    try { await action() } catch (err) { setError(typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : 'Guest credential settings could not be updated.') }
    finally { setBusy(false) }
  }
  const close = () => { setOpen(false); setPassword(''); setUsername(''); setDomain(''); setPolicy(null); setError('') }
  const load = () => { setOpen(true); run(async () => setPolicy((await api.get(path)).data)) }
  const save = event => {
    event.preventDefault()
    run(async () => {
      setPolicy((await api.put(path, { username, password, domain, auto_connect: policy.auto_connect, student_visible: policy.student_visible })).data)
      setPassword(''); setUsername(''); setDomain(''); setMessage('Guest credentials saved. Existing guest passwords were not changed.')
    })
  }
  return <div className='template-guest-settings'>
    <button type='button' className='ui-button--secondary' disabled={busy} aria-expanded={open} onClick={open ? close : load}>{open ? 'Close guest settings' : 'Guest credentials'}</button>
    {open ? <div className='stack'>
      <p>Save the guest account already configured in this template or by cloud-init. This does not create or reset accounts inside VMs. Clones inheriting this login share the same credentials.</p>
      {busy ? <p role='status'>Updating guest settings…</p> : null}
      {error ? <p className='msg error' role='alert'>{error}</p> : null}
      {message ? <p role='status'>{message}</p> : null}
      {policy ? <form onSubmit={save} className='stack'>
        <p>{policy.configured ? 'Credentials are stored securely. Enter a new login below to replace them.' : 'No guest credentials saved.'}</p>
        <label><input type='checkbox' checked={policy.auto_connect} onChange={event => setPolicy({ ...policy, auto_connect: event.target.checked })}/> Use for automatic browser connections</label>
        <label><input type='checkbox' checked={policy.student_visible} onChange={event => setPolicy({ ...policy, student_visible: event.target.checked })}/> Allow assigned students to reveal the template lab login</label>
        {policy.configured ? <button type='button' disabled={busy} onClick={() => run(async () => { setPolicy((await api.patch(path, { auto_connect: policy.auto_connect, student_visible: policy.student_visible })).data); setMessage('Sharing and connection policy saved.') })}>Save sharing policy</button> : null}
        <label className='ui-field'>Guest username<input required value={username} autoComplete='off' onChange={event => setUsername(event.target.value)}/></label>
        <label className='ui-field'>Guest password<input required type='password' value={password} autoComplete='new-password' onChange={event => setPassword(event.target.value)}/></label>
        <label className='ui-field'>Domain (optional)<input value={domain} autoComplete='off' onChange={event => setDomain(event.target.value)}/></label>
        <button disabled={busy} type='submit'>{policy.configured ? 'Replace saved login' : 'Save guest login'}</button>
        {policy.configured ? <button type='button' className='ui-button--secondary' disabled={busy} onClick={() => run(async () => { setPolicy((await api.delete(path)).data); setPassword(''); setUsername(''); setDomain(''); setMessage('Saved credentials removed. Guest accounts were not changed.') })}>Remove saved credentials</button> : null}
      </form> : null}
    </div> : null}
  </div>
}
