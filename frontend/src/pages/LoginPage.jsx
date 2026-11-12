import { useState } from 'react'
import api from '../services/api'
import Button from '../components/ui/Button'
import FormField from '../components/ui/FormField'
import AccountRecovery from './AccountRecovery'

export default function LoginPage({ onLogin, setMessage }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [recovering, setRecovering] = useState(false)

  const submit = async event => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      await api.post('/auth/login', { email: email.trim(), password })
      setMessage({ type: 'success', text: 'Welcome back. Login successful.' })
      await onLogin()
    } catch (error) {
      setMessage({ type: 'error', text: error?.response?.data?.detail || 'Login failed. Check credentials.' })
    } finally {
      setBusy(false)
    }
  }

  if (recovering) return <main className='auth-shell auth-shell--branded'><AccountRecovery onBack={() => setRecovering(false)} /></main>
  return <main className='auth-shell auth-shell--branded'>
    <section className='auth-story' aria-label='About LabGoblin'><p className='eyebrow'>LabGoblin / Your learning space</p><h2>Real Skills.<br/><span>Virtual Machines.</span></h2><p>A place to build, practice, and explore. Your next hands-on lab starts here.</p><ol className='auth-learning-steps'><li><strong>Sign in</strong><span>Use the account provided by your instructor.</span></li><li><strong>Choose your lab</strong><span>Your assigned resources are waiting in My labs.</span></li><li><strong>Connect and explore</strong><span>Open your desktop or terminal in the browser.</span></li></ol></section>
    <form className='auth-card ui-stack' onSubmit={submit} aria-labelledby='login-title'>
      <div className='login-brand'>
        <img src='/brand/labgoblin-icon.svg' alt='' className='login-brand-mark'/>
        <div><div className='brand-wordmark'>Lab<span>Goblin</span></div><div className='brand-subtitle'>Virtual Lab Provisioning & Management</div></div>
      </div>
      <div><h1 id='login-title'>Welcome to your lab</h1><p className='muted' id='login-help'>Access your assigned virtual labs.</p></div>
      <FormField label='Email address' id='login-email' required>
        <input className='ui-input' type='email' autoComplete='username' inputMode='email' autoCapitalize='none' spellCheck={false} aria-describedby='login-help' value={email} onChange={event => setEmail(event.target.value)} autoFocus />
      </FormField>
      <FormField label='Password' id='login-password' required>
        <input className='ui-input' autoComplete='current-password' type={showPassword ? 'text' : 'password'} value={password} onChange={event => setPassword(event.target.value)} />
      </FormField>
      <label className='lab-check'><input type='checkbox' checked={showPassword} onChange={event => setShowPassword(event.target.checked)}/> Show password</label>
      <Button type='submit' block busy={busy} disabled={!email || !password}>{busy ? 'Signing in…' : 'Sign in'}</Button>
      <button type='button' className='ui-button--secondary' onClick={() => setRecovering(true)}>Forgot password?</button>
      <details><summary>Need help signing in?</summary><p>Sign in with the email address on your LabGoblin account. Your lab machine has a separate login. Request an email code to set or reset your password.</p><button type='button' className='ui-button--secondary' onClick={() => setRecovering(true)}>Use an email code</button></details>
      <div className='login-tagline'>Real Skills. Virtual Machines.</div>
    </form>
  </main>
}
