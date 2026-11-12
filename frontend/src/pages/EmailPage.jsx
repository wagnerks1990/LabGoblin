import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../services/api'

const errorText = error => error?.response?.status === 403 ? 'You do not have permission to manage email.' : typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : 'The email service could not complete this request.'

export default function EmailPage() {
  const [config, setConfig] = useState(null)
  const [form, setForm] = useState(null)
  const [rows, setRows] = useState([])
  const [direction, setDirection] = useState('inbound')
  const [next, setNext] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState(null)
  const [reply, setReply] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  const [apiKey, setApiKey] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const selectedHeading = useRef(null)
  useEffect(() => { selectedHeading.current?.focus() }, [selected?.id])
  const load = useCallback(async () => {
    setLoading(true); setError(''); setSelected(null); setRows([]); setConfig(null)
    try {
      const [settings, messages] = await Promise.all([api.get('/admin/email/settings'), api.get('/admin/email/messages', { params: { direction } })])
      setConfig(settings.data); setForm(settings.data); setRows(messages.data.items); setNext(messages.data.next_before)
    } catch (e) { setError(errorText(e)) }
    finally { setLoading(false) }
  }, [direction])
  useEffect(() => { load() }, [load])
  const perform = async action => {
    if (busy) return
    setBusy(true); setError(''); setNotice('')
    try { await action() }
    catch (e) { setError(errorText(e)) }
    finally { setBusy(false) }
  }
  const save = event => {
    event.preventDefault()
    perform(async () => {
      const payload = Object.fromEntries(['enabled', 'receiving_enabled', 'notifications_enabled', 'public_origin', 'sender', 'support_address'].map(key => [key, form[key]]))
      if (apiKey) payload.api_key = apiKey
      if (webhookSecret) payload.webhook_secret = webhookSecret
      const r = await api.put('/admin/email/settings', payload)
      setConfig(r.data); setForm(r.data); setApiKey(''); setWebhookSecret(''); setNotice('Email settings saved.')
    })
  }
  const read = row => perform(async () => {
    const r = await api.get(`/admin/email/messages/${row.id}`)
    setSelected(r.data); setReply(''); setRequestId(crypto.randomUUID())
  })
  const sendReply = event => {
    event.preventDefault()
    perform(async () => {
      await api.post(`/admin/email/messages/${selected.id}/reply`, { text: reply, request_id: requestId })
      setReply(''); setRequestId(crypto.randomUUID()); setNotice('Reply queued. Check Outgoing mail for delivery status.')
    })
  }
  return <section className='page-shell' aria-labelledby='email-title'>
    <header className='ui-page-header'><div><h1 id='email-title'>Email & support</h1><p className='ui-page-header__description'>Account messages, lab notifications, delivery status, and support mail.</p></div><button disabled={loading || busy} onClick={load}>Refresh email</button></header>
    {error ? <p className='ui-alert ui-alert--error' role='alert'>{error} <button onClick={load} disabled={loading || busy}>Try again</button></p> : null}
    {notice ? <p className='ui-alert ui-alert--success' role='status'>{notice}</p> : null}
    {loading ? <p role='status'>Loading email…</p> : null}
    {!loading && config && form ? <>
      <section className='panel' aria-labelledby='email-connection-title'>
        <h2 id='email-connection-title'>Connection</h2>
        <p><span className={`ui-status-badge ${config.enabled ? 'ui-status-badge--success' : 'ui-status-badge--warning'}`}>{config.enabled ? 'Sending enabled' : 'Sending disabled'}</span> · {config.receiving_enabled ? 'Support receiving enabled' : 'Support receiving disabled'}</p>
        <p>API key: {config.api_key_configured ? 'Configured' : 'Not configured'}. Webhook verification: {config.webhook_secret_configured ? 'Configured' : 'Not configured'}.</p>
        {config.failed_webhooks ? <p className='ui-alert ui-alert--error' role='alert'>{config.failed_webhooks} webhook event(s) could not be processed. Check the provider connection, then <button disabled={busy} onClick={() => perform(async () => { await api.post('/admin/email/retry-webhooks'); await load(); setNotice('Failed webhook events queued for another attempt.') })}>Retry failed events</button>.</p> : null}
        <button disabled={busy || !config.enabled} onClick={() => perform(async () => { await api.post('/admin/email/test'); setNotice('Test queued to your account email. Check Outgoing mail for delivery status.') })}>Queue test to my email</button>
        <details><summary>Edit email settings</summary><form className='ui-form-grid' onSubmit={save}>
          <label className='ui-field'>Application HTTPS origin<input className='ui-input' type='url' required value={form.public_origin} onChange={e => setForm({ ...form, public_origin: e.target.value })} /></label>
          <label className='ui-field'>Notification sender<input className='ui-input' type='email' required value={form.sender} onChange={e => setForm({ ...form, sender: e.target.value })} /></label>
          <label className='ui-field'>Support and reply address<input className='ui-input' type='email' required value={form.support_address} onChange={e => setForm({ ...form, support_address: e.target.value })} /></label>
          <label className='ui-field'>Replace Resend API key<input className='ui-input' type='password' autoComplete='new-password' value={apiKey} onChange={e => setApiKey(e.target.value)} /></label>
          <label className='ui-field'>Replace webhook signing secret<input className='ui-input' type='password' autoComplete='new-password' value={webhookSecret} onChange={e => setWebhookSecret(e.target.value)} /></label>
          <p className='ui-form-grid__wide'>Leave credential fields blank to keep the saved values. Mail contents are retained for 30 days.</p>
          <label><input type='checkbox' checked={form.enabled} onChange={e => setForm({ ...form, enabled: e.target.checked })} /> Enable sending</label>
          <label><input type='checkbox' checked={form.receiving_enabled} onChange={e => setForm({ ...form, receiving_enabled: e.target.checked })} /> Receive support mail</label>
          <label><input type='checkbox' checked={form.notifications_enabled} onChange={e => setForm({ ...form, notifications_enabled: e.target.checked })} /> Send lab and operation notices</label>
          <div className='ui-form-grid__wide'><button disabled={busy}>Save email settings</button></div>
        </form></details>
      </section>
      <section className='panel' aria-labelledby='email-messages-title'>
        <h2 id='email-messages-title'>{direction === 'inbound' ? 'Support inbox' : 'Outgoing mail'}</h2>
        <div className='ui-cluster'><button aria-pressed={direction === 'inbound'} disabled={busy} onClick={() => setDirection('inbound')}>Support inbox</button><button aria-pressed={direction === 'outbound'} disabled={busy} onClick={() => setDirection('outbound')}>Outgoing mail</button></div>
        {!rows.length && !error ? <p>No {direction === 'inbound' ? 'support messages' : 'outgoing messages'} yet.</p> : null}
        <ul className='email-message-list'>{rows.map(row => <li key={row.id}><article className='ui-stack'><h3>{row.subject}</h3><p>{row.address}</p><p>{row.state} · {new Date(row.created_at + (row.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString()}</p>{row.error ? <p role='status'>{row.error}</p> : null}{direction === 'inbound' ? <button disabled={busy} onClick={() => read(row)}>Read message {row.id}</button> : null}</article></li>)}</ul>
        {next ? <button disabled={busy} onClick={() => perform(async () => { const r = await api.get('/admin/email/messages', { params: { direction, before: next } }); setRows(current => [...current, ...r.data.items]); setNext(r.data.next_before) })}>Load older messages</button> : null}
      </section>
      {selected && direction === 'inbound' ? <section className='panel' aria-labelledby='email-selected-title'>
        <h2 id='email-selected-title' tabIndex={-1} ref={selectedHeading}>{selected.subject}</h2><p>From: {selected.address}</p>
        <p>Incoming messages are untrusted. Attachments ({selected.attachment_count}) are not opened automatically.</p><pre className='email-message-body'>{selected.text}</pre>
        <form className='ui-stack' onSubmit={sendReply}><label className='ui-field'>Reply to {selected.address}<textarea className='ui-input' required maxLength={10000} rows={6} value={reply} onChange={e => setReply(e.target.value)} /></label><button disabled={busy || !config.enabled || !reply.trim()}>Queue reply</button></form>
        <div className='ui-cluster'><button disabled={busy} onClick={() => perform(async () => { await api.patch(`/admin/email/messages/${selected.id}`, { state: selected.state === 'archived' ? 'received' : 'archived' }); await load(); setNotice('Support message updated.') })}>{selected.state === 'archived' ? 'Reopen message' : 'Archive message'}</button><button disabled={busy} onClick={() => setSelected(null)}>Close message</button></div>
      </section> : null}
    </> : null}
  </section>
}
