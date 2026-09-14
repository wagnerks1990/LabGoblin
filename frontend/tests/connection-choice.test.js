import test from 'node:test'
import assert from 'node:assert/strict'
import { preferredConnection } from '../src/services/connectionChoice.js'

test('automatically selects a verified OS-appropriate service with VNC fallback', () => {
  const windows = { running: true, operating_system: 'windows', rdp: true, terminal: true, vnc: true }
  assert.equal(preferredConnection(windows), 'rdp')
  assert.equal(preferredConnection({ ...windows, rdp: false }), 'vnc')
  assert.equal(preferredConnection({ ...windows, operating_system: 'linux' }), 'ssh')
  assert.equal(preferredConnection({ ...windows, operating_system: 'unknown' }), 'vnc')
  assert.equal(preferredConnection({ ...windows, running: false }), null)
  assert.equal(preferredConnection({ ...windows, rdp: false, vnc: false }), null)
})

test('only honors available, recognized connection choices', () => {
  const linux = { running: true, operating_system: 'linux', terminal: true, vnc: true }
  assert.equal(preferredConnection(linux, 'vnc'), 'vnc')
  assert.equal(preferredConnection(linux, 'rdp'), 'ssh')
  assert.equal(preferredConnection(linux, '__proto__'), 'ssh')
  assert.equal(preferredConnection(null, 'vnc'), null)
})
