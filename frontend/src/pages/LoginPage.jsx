import { useState } from 'react'
import api from '../services/api'
import Button from '../components/ui/Button'
import FormField from '../components/ui/FormField'

export default function LoginPage({ onLogin, setMessage }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async event => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      await api.post('/auth/login', { username, password })
      setMessage({ type: 'success', text: 'Welcome back. Login successful.' })
      await onLogin()
    } catch (error) {
      setMessage({ type: 'error', text: error?.response?.data?.detail || 'Login failed. Check credentials.' })
    } finally {
      setBusy(false)
    }
  }

  return <main className='auth-shell auth-shell--branded'>
    <section className='auth-story' aria-label='About LabGoblin'><p className='eyebrow'>LabGoblin / Virtual lab management</p><h2>Real Skills.<br/><span>Virtual Machines.</span></h2><p>A place to build, practice, and explore. Your next hands-on lab starts here.</p><div className='auth-story-steps'><span>01 / Build</span><span>02 / Deploy</span><span>03 / Learn</span><span>04 / Repeat</span></div></section>
    <form className='auth-card ui-stack' onSubmit={submit} aria-labelledby='login-title'>
      <div className='login-brand'>
        <img src='/brand/labgoblin-icon.svg' alt='' className='login-brand-mark'/>
        <div><div className='brand-wordmark'>Lab<span>Goblin</span></div><div className='brand-subtitle'>Virtual Lab Provisioning & Management</div></div>
      </div>
      <div><h1 id='login-title'>Sign in</h1><p className='muted' id='login-help'>Access your assigned virtual labs.</p></div>
      <FormField label='Username' id='login-username' required>
        <input className='ui-input' autoComplete='username' aria-describedby='login-help' value={username} onChange={event => setUsername(event.target.value)} autoFocus />
      </FormField>
      <FormField label='Password' id='login-password' required>
        <input className='ui-input' autoComplete='current-password' type='password' value={password} onChange={event => setPassword(event.target.value)} />
      </FormField>
      <Button type='submit' block busy={busy} disabled={!username || !password}>{busy ? 'Signing in…' : 'Sign in'}</Button>
      <div className='login-tagline'>Real Skills. Virtual Machines.</div>
    </form>
  </main>
}
