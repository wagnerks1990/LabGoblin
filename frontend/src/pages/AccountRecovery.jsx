import { useState } from 'react'
import api from '../services/api'

export default function AccountRecovery({ onBack }) {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [hasCode, setHasCode] = useState(false)
  const [complete, setComplete] = useState(false)
  const submit = async event => {
    event.preventDefault()
    if (busy) return
    setError(''); setMessage('')
    if (hasCode && password !== confirmation) return setError('Passwords do not match.')
    setBusy(true)
    try {
      if (hasCode) {
        await api.post('/auth/email/complete', { email, code: code.trim(), new_password: password })
        setCode(''); setPassword(''); setConfirmation(''); setComplete(true)
        setMessage('Password saved. Previous sessions were revoked. Return to sign in with your email and new password.')
      } else {
        const result = await api.post('/auth/email/request', { email })
        setMessage(result.data.message); setHasCode(true)
      }
    } catch (e) {
      const detail = e?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'The request could not be completed. Check your details and try again.')
    } finally { setBusy(false) }
  }
  return <section className='auth-card ui-stack' aria-labelledby='recovery-title'>
    <h1 id='recovery-title'>Set or recover your password</h1>
    <p>Use the email address on your LabGoblin account. Your lab machine has a separate login.</p>
    {message ? <p className='ui-alert ui-alert--success' role='status'>{message}</p> : null}
    {error ? <p className='ui-alert ui-alert--error' role='alert'>{error}</p> : null}
    {!complete ? <form className='ui-stack' onSubmit={submit} aria-busy={busy}>
      <label className='ui-field'>Account email<input className='ui-input' type='email' autoComplete='email' required autoFocus value={email} onChange={e => setEmail(e.target.value)} /></label>
      {hasCode ? <>
        <label className='ui-field'>Email code<input className='ui-input' type='password' autoComplete='one-time-code' required value={code} onChange={e => setCode(e.target.value)} /></label>
        <label className='ui-field'>New password<input className='ui-input' type='password' autoComplete='new-password' minLength={12} maxLength={72} required aria-describedby='recovery-password-help' value={password} onChange={e => setPassword(e.target.value)} /></label>
        <label className='ui-field'>Confirm new password<input className='ui-input' type='password' autoComplete='new-password' required value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label>
        <p id='recovery-password-help'>Use at least 12 characters with upper- and lower-case letters, a number, and a symbol.</p>
      </> : null}
      <button disabled={busy}>{busy ? 'Working…' : hasCode ? 'Save password' : 'Request an email code'}</button>
      <button type='button' className='ui-button--secondary' disabled={busy} onClick={() => { setHasCode(!hasCode); setError(''); setMessage('') }}>{hasCode ? 'Request another code' : 'I already have an email code'}</button>
    </form> : null}
    <button type='button' className='ui-button--secondary' disabled={busy} onClick={onBack}>Back to sign in</button>
  </section>
}
