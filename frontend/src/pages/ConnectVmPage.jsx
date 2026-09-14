import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { WorkspaceHeading } from '../components/ui/WorkspaceKit'
import { ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import api from '../services/api'
import { openBrowserConnection } from '../services/consoleClient'
import { preferredConnection } from '../services/connectionChoice'

const detail = error => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : 'LabGoblin could not complete the connection check.'

function PrepareGuest({ id, os, onSaved }) {
  const [address, setAddress] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [probe, setProbe] = useState(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [domain, setDomain] = useState('')
  const [mac, setMac] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [observations, setObservations] = useState([])
  const [discoveryHint, setDiscoveryHint] = useState('Reading guest agent information…')
  const [templateAvailable, setTemplateAvailable] = useState(false)
  const [useTemplate, setUseTemplate] = useState(false)
  const port = os === 'windows' ? 3389 : 22
  useEffect(() => {
    let current = true
    api.get(`/vms/${id}/console/profile`).then(response => {
      if (!current) return
      setAddress(response.data.address || '')
      setObservations(response.data.observed_addresses || [])
      setDiscoveryHint(response.data.discovery_hint || '')
      setTemplateAvailable(Boolean(response.data.template_credentials_available))
      setUseTemplate(Boolean(response.data.configured ? response.data.use_template_credentials : response.data.template_credentials_available))
    }).catch(() => { if (current) { setError('Saved guest settings and agent information could not be loaded.'); setDiscoveryHint('Discovery failed.') } })
    return () => { current = false }
  }, [id])
  const check = async event => {
    event.preventDefault(); setBusy(true); setError(''); setProbe(null)
    try {
      const result = (await api.post(`/vms/${id}/console/probe`, { address, port, confirm_reserved_address: confirmed })).data
      setProbe(result); setMac(result.mac_addresses[0] || '')
    } catch (err) { setError(detail(err)) } finally { setBusy(false) }
  }
  const save = async event => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      await api.put(`/vms/${id}/console/profile`, { address, port, mac_address: mac, server_identity: probe.server_identity, username, password, domain, enabled: true, use_template_credentials: useTemplate })
      setPassword(''); setUsername(''); setDomain(''); setProbe(null); await onSaved()
    } catch (err) { setError(detail(err)) } finally { setBusy(false) }
  }
  return <details className='panel connection-prepare'>
    <summary>Administrator: prepare guest access</summary>
    <p>Reserve an address for this VM in DHCP or IPAM, enable {os === 'windows' ? 'Remote Desktop with NLA' : 'SSH'} in the guest, and allow port {port} through its firewall. VNC remains available for setup.</p>
    <form onSubmit={check} className='stack'>
      <p role='status'>{discoveryHint}</p>
      {observations.length ? <label className='ui-field'>Discovered VM address<select value={observations.some(item => item.address === address) ? address : ''} onChange={event => { setAddress(event.target.value); setProbe(null); setConfirmed(false) }}><option value=''>Select an address</option>{observations.map(item => <option key={`${item.address}-${item.mac_address}`} value={item.address}>{item.address} · {item.mac_address}{item.matches_cloud_init ? ' · matches cloud-init' : ''}</option>)}</select></label> : null}
      <label className='ui-field'>Reserved VM IP address<input required value={address} onChange={event => { setAddress(event.target.value); setProbe(null); setConfirmed(false) }} autoComplete='off'/></label>
      <label><input type='checkbox' checked={confirmed} onChange={event => setConfirmed(event.target.checked)} required/> I verified that this address is reserved for this VM, not another VM or a management service.</label>
      <button disabled={busy || !confirmed} type='submit'>{busy ? 'Checking…' : 'Detect guest service'}</button>
    </form>
    {error ? <p role='alert' className='msg error'>{error}</p> : null}
    {probe ? <p role='status'>{probe.hint}</p> : null}
    {probe?.reachable ? <form onSubmit={save} className='stack'>
      <label className='ui-field'>VM network adapter<select required value={mac} onChange={event => setMac(event.target.value)}>{probe.mac_addresses.map(item => <option key={item}>{item}</option>)}</select></label>
      <label className='ui-field'>Detected server identity<textarea readOnly value={probe.server_identity}/></label>
      <p>Verify this identity against the guest before approving it. A changed identity will block future connections.</p>
      {templateAvailable ? <label><input type='checkbox' checked={useTemplate} onChange={event => { setUseTemplate(event.target.checked); setPassword(''); setUsername(''); setDomain('') }}/> Use the guest login saved in template settings</label> : null}
      {!useTemplate ? <><label className='ui-field'>VM-specific guest username<input required autoComplete='off' value={username} onChange={event => setUsername(event.target.value)}/></label>
      <label className='ui-field'>Guest password<input required type='password' autoComplete='new-password' value={password} onChange={event => setPassword(event.target.value)}/></label>
      {os === 'windows' ? <label className='ui-field'>Domain (optional)<input value={domain} onChange={event => setDomain(event.target.value)}/></label> : null}
      </> : null}
      <p>Automatic connections keep credentials on the server. Template settings separately control whether assigned students can reveal the template lab login.</p>
      <button disabled={busy} type='submit'>Approve identity and enable guest access</button>
    </form> : null}
  </details>
}

export default function ConnectVmPage() {
  const { id } = useParams()
  const [search] = useSearchParams()
  const [options, setOptions] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [protocol, setProtocol] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState('closed')
  const [fullscreen, setFullscreen] = useState(false)
  const screen = useRef(null)
  const connection = useRef(null)
  const autoOpened = useRef(false)
  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try { setOptions((await api.get(`/vms/${id}/console/options`)).data) }
    catch (err) { setProtocol(null); setOptions(null); setError(detail(err)) }
    finally { setLoading(false) }
  }, [id])
  useEffect(() => { autoOpened.current = false; setProtocol(null); refresh() }, [refresh])
  useEffect(() => {
    if (!options || options.vm_id !== Number(id) || autoOpened.current) return
    const preferred = preferredConnection(options, search.get('method'))
    if (preferred) { autoOpened.current = true; setProtocol(preferred) }
  }, [options, search, id])
  useEffect(() => {
    if (!protocol || !screen.current) return undefined
    setState('connecting'); setError('')
    try { connection.current = openBrowserConnection(screen.current, id, protocol, setState, setError) }
    catch { setState('failed'); setError('The browser could not initialize this connection.') }
    return () => { connection.current?.disconnect(); connection.current = null }
  }, [protocol, attempt, id])
  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === screen.current)
    document.addEventListener('fullscreenchange', update)
    return () => document.removeEventListener('fullscreenchange', update)
  }, [])
  const toggleFullscreen = async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await screen.current?.requestFullscreen() }
    catch { setError('The browser could not enter full screen.') }
  }
  const methods = options ? [
    { protocol: 'vnc', label: 'VNC console', ready: options.vnc, description: 'The VM’s physical screen, including boot and recovery.' },
    ...(options.operating_system === 'windows' ? [{ protocol: 'rdp', label: 'Windows desktop · RDP', ready: options.rdp, description: 'A remote Windows desktop inside your browser.' }] : []),
    ...(options.operating_system === 'linux' ? [{ protocol: 'ssh', label: 'Linux terminal', ready: options.terminal, description: 'An interactive shell inside your browser.' }] : []),
  ] : []
  return <section className='page-shell'>
    <WorkspaceHeading title={options?.vm_name || 'Connect to your VM'} description='Your lab, right here in the browser.'><Link className='btn ui-button--secondary' to='/vms'>Back to VMs</Link><button onClick={refresh} disabled={loading}>Check connections</button></WorkspaceHeading>
    {loading && !protocol ? <LoadingState label='Checking VM, operating system and available connections…'/> : null}
    {error ? <ErrorState message={error} onRetry={refresh} retrying={loading}/> : null}
    {options ? <>
      <p className='muted'>{options.operating_system === 'unknown' ? 'Guest OS not identified' : options.operating_system === 'windows' ? 'Windows' : 'Linux'} · {options.running ? 'VM running' : 'VM stopped'}</p>
      <div className='connection-choices'>{methods.map(method => <button key={method.protocol} className={`connection-choice ${protocol === method.protocol ? 'connection-choice--active' : ''}`} disabled={!method.ready || loading} aria-pressed={protocol === method.protocol} onClick={() => { setProtocol(method.protocol); setAttempt(value => value + 1) }}><strong>{method.label}</strong><span>{method.description}</span><span>{method.ready ? 'Connect in browser' : 'Not available'}</span></button>)}</div>
      <p className='ui-field__hint' role='status'>{options.hint}</p>
    </> : null}
    {protocol ? <div className='panel'>
      <div className='console-toolbar group'><span role='status'>Connection: <WorkflowStatus value={state}/></span><button onClick={() => setAttempt(value => value + 1)}>Reconnect</button><button onClick={() => { setProtocol(null); setState('closed') }}>Disconnect</button><button disabled={state !== 'connected'} onClick={toggleFullscreen} aria-pressed={fullscreen}>{fullscreen ? 'Exit full screen' : 'Full screen'}</button>{protocol !== 'ssh' ? <button disabled={state !== 'connected'} onClick={() => connection.current?.sendCtrlAltDelete()}>Ctrl+Alt+Delete</button> : null}</div>
      <p className='ui-field__hint'>Click the session to send keyboard input. Closing this page disconnects your session; it does not shut down the VM.</p>
      <div ref={screen} className='console-surface guacamole-surface' role='application' aria-label='LabGoblin remote session'/>
    </div> : null}
    {options?.vm_id === Number(id) && options.can_configure && options.operating_system !== 'unknown' ? <PrepareGuest key={id} id={id} os={options.operating_system} onSaved={refresh}/> : null}
  </section>
}
