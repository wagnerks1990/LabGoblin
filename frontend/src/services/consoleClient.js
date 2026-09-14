import Guacamole from '../vendor/guacamole-1.6.0'

export function openBrowserConnection(element, vmId, protocol, onState, onError) {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const tunnel = new Guacamole.WebSocketTunnel(`${scheme}://${window.location.host}/api/vms/${vmId}/console/guacamole/${protocol}/ws`)
  tunnel.receiveTimeout = 90000
  const client = new Guacamole.Client(tunnel)
  const display = client.getDisplay()
  const surface = display.getElement()
  surface.tabIndex = 0
  surface.setAttribute('aria-label', `Remote ${protocol === 'ssh' ? 'terminal' : 'desktop'}`)
  element.appendChild(surface)
  let disposed = false
  let failed = false
  const fail = () => { if (!disposed) { failed = true; onState('failed'); onError('Connection failed. Refresh the connection checks, verify the guest service, or ask your instructor for help.') } }
  client.onerror = fail
  tunnel.onerror = fail
  client.onstatechange = state => {
    if (disposed || failed) return
    if (state === Guacamole.Client.State.CONNECTED) onState('connected')
    else if (state === Guacamole.Client.State.DISCONNECTED) onState('closed')
    else onState('connecting')
  }
  const keyboard = new Guacamole.Keyboard(surface)
  keyboard.onkeydown = keysym => { client.sendKeyEvent(1, keysym); return false }
  keyboard.onkeyup = keysym => client.sendKeyEvent(0, keysym)
  const mouse = new Guacamole.Mouse(surface)
  mouse.onEach(['mousedown', 'mouseup', 'mousemove'], event => client.sendMouseState(event.state, true))
  const touch = new Guacamole.Mouse.Touchscreen(surface)
  touch.onEach(['mousedown', 'mouseup', 'mousemove'], event => client.sendMouseState(event.state, true))
  const blur = () => keyboard.reset()
  const focus = () => surface.focus()
  surface.addEventListener('pointerdown', focus)
  surface.addEventListener('blur', blur)
  const fit = () => {
    if (display.getWidth()) display.scale(Math.min(1, element.clientWidth / display.getWidth()))
    client.sendSize(Math.max(200, Math.min(4096, element.clientWidth)), Math.max(200, Math.min(4096, element.clientHeight)))
  }
  display.onresize = fit
  const observer = new ResizeObserver(fit)
  observer.observe(element)
  const data = new URLSearchParams({ organization_id: localStorage.getItem('organization_id') || '', width: Math.max(200, element.clientWidth), height: Math.max(200, element.clientHeight) })
  client.connect(data.toString())
  return {
    sendCtrlAltDelete: () => { [0xffe3, 0xffe9, 0xffff].forEach(key => client.sendKeyEvent(1, key)); [0xffff, 0xffe9, 0xffe3].forEach(key => client.sendKeyEvent(0, key)) },
    disconnect: () => { disposed = true; keyboard.reset(); client.disconnect(); observer.disconnect(); surface.removeEventListener('pointerdown', focus); surface.removeEventListener('blur', blur); surface.remove() },
  }
}
