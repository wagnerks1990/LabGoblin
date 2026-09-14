import test from 'node:test'
import assert from 'node:assert/strict'
import { formatBytes, formatUptime, vmAddress } from '../src/services/vmResources.js'
import { selectMachines } from '../src/state/workspaceCollections.js'

test('resource display distinguishes zero from unavailable and uses binary units', () => {
  assert.equal(formatBytes(0), '0 B')
  assert.equal(formatBytes(null), 'Not reported')
  assert.equal(formatBytes(60 * 1024 ** 3), '60 GiB')
  assert.equal(formatBytes(Infinity), 'Not reported')
  assert.equal(formatUptime(90061), '1d 1h 1m')
  assert.equal(formatUptime(null), 'Not reported')
})
test('VM address display and search include observed guest addresses', () => {
  const vm = {vmid: 100, vm_name: 'lab', assigned_ip: '10.0.0.1', observed_addresses: [{address:'10.0.0.2'}, {address:'2001:db8::2'}]}
  assert.equal(vmAddress(vm), '10.0.0.2, 2001:db8::2')
  assert.equal(selectMachines([vm], {query:'2001:db8::2'}).length, 1)
  assert.equal(vmAddress({}), 'Not reported')
})
