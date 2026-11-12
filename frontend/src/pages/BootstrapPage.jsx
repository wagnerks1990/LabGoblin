import { useState } from 'react'
import api from '../services/api'
import Button from '../components/ui/Button'
import FormField from '../components/ui/FormField'

export default function BootstrapPage({ onComplete, setMessage }) {
  const [form, setForm] = useState({ token: '', email: '', password: '' })
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async event => {
    event.preventDefault()
    if (form.password !== confirm) {
      setMessage({ type: 'error', text: 'Passwords do not match.' })
      return
    }
    setBusy(true)
    try {
      await api.post('/bootstrap/admin', form)
      setMessage({ type: 'success', text: 'Administrator created. Welcome to LabGoblin.' })
      await onComplete()
    } catch (error) {
      setMessage({ type: 'error', text: error?.response?.data?.detail || 'Administrator setup failed.' })
    } finally {
      setBusy(false)
    }
  }

  const mismatch = confirm && form.password !== confirm ? 'Passwords do not match.' : ''
  return <main className='auth-shell'>
    <form className='auth-card ui-stack' onSubmit={submit} aria-labelledby='bootstrap-title'>
      <div className='login-brand'>
        <img src='/brand/labgoblin-icon.svg' alt='' className='login-brand-mark'/>
        <div><div className='brand-wordmark'>Lab<span>Goblin</span></div><div className='brand-subtitle'>Virtual Lab Provisioning & Management</div></div>
      </div>
      <div><h1 id='bootstrap-title'>First-run setup</h1><p className='muted'>Create the first LabGoblin administrator.</p></div>
      <FormField label='Bootstrap token' id='bootstrap-token' hint='Enter the one-time token printed by the installer. It is not your administrator password.' required>
        <input className='ui-input' type='password' autoComplete='off' value={form.token} onChange={event => setForm({...form, token: event.target.value})} autoFocus />
      </FormField>
      <FormField label='Administrator email' id='bootstrap-email' hint='Use this email to sign in and recover your password.' required>
        <input className='ui-input' type='email' autoComplete='username' value={form.email} onChange={event => setForm({...form, email: event.target.value})} />
      </FormField>
      <FormField label='Password' id='bootstrap-password' hint='Use at least 12 characters with upper- and lower-case letters, a number, and a symbol.' required>
        <input className='ui-input' type='password' autoComplete='new-password' value={form.password} onChange={event => setForm({...form, password: event.target.value})} />
      </FormField>
      <FormField label='Confirm password' id='bootstrap-confirm-password' error={mismatch} required>
        <input className='ui-input' type='password' autoComplete='new-password' value={confirm} onChange={event => setConfirm(event.target.value)} />
      </FormField>
      <Button type='submit' block busy={busy} disabled={!form.token || !form.email || !form.password || !confirm || Boolean(mismatch)}>{busy ? 'Creating administrator…' : 'Create administrator'}</Button>
      <div className='login-tagline'>Build. Deploy. Learn. Repeat.</div>
    </form>
  </main>
}
