import { useEffect, useRef, useState } from 'react'
import api from '../../services/api'

export default function GuestCredentialReveal({ vmId }) {
  const [credentials, setCredentials] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const generation = useRef(0)
  useEffect(() => {
    const hide = () => { generation.current += 1; setCredentials(null); setBusy(false) }
    const visibility = () => { if (document.hidden) hide() }
    document.addEventListener('visibilitychange', visibility)
    return () => { generation.current += 1; document.removeEventListener('visibilitychange', visibility) }
  }, [vmId])
  useEffect(() => {
    if (!credentials) return undefined
    const timeout = setTimeout(() => setCredentials(null), 30000)
    return () => clearTimeout(timeout)
  }, [credentials])
  const reveal = async () => {
    const request = ++generation.current
    setBusy(true); setError('')
    try {
      const result = await api.post(`/vms/${vmId}/guest-credentials/reveal`)
      if (generation.current === request && !document.hidden) setCredentials(result.data)
    } catch (err) { if (generation.current === request) setError(typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : 'Lab credentials could not be loaded.') }
    finally { if (generation.current === request) setBusy(false) }
  }
  return <div className='guest-credential-reveal'>
    <button type='button' className='ui-button--secondary' disabled={busy} aria-expanded={Boolean(credentials)} onClick={credentials ? () => setCredentials(null) : reveal}>{busy ? 'Checking access…' : credentials ? 'Hide lab login' : 'Show lab login'}</button>
    {error ? <p className='msg error' role='alert'>{error}</p> : null}
    {credentials ? <div className='stack'><p>Template lab account. This view hides after 30 seconds.</p><dl><dt>Username</dt><dd><code>{credentials.username}</code></dd><dt>Password</dt><dd><code>{credentials.password}</code></dd>{credentials.domain ? <><dt>Domain</dt><dd><code>{credentials.domain}</code></dd></> : null}</dl></div> : null}
  </div>
}
