import assert from 'node:assert/strict'
import test from 'node:test'
import { matchesQuery, selectMachines, selectOperations } from '../src/state/workspaceCollections.js'

test('resource search handles whitespace, human action labels, mixed case, and missing metadata', () => {
  assert.equal(matchesQuery('  VM   START  ', ['vm.start']), true)
  assert.equal(matchesQuery('node 200001', ['node-a', 200001]), true)
  assert.equal(matchesQuery('undefined', [null, undefined, '']), false)
  assert.equal(matchesQuery('missing', ['running']), false)
})
test('VM filtering composes status and resource search without changing API order', () => {
  const rows = Object.freeze([{ id: 8, vmid: 200002, vm_name: 'Linux', status: 'RUNNING', assigned_ip: '192.0.2.2' }, { id: 3, vmid: 200001, vm_name: 'Windows', status: 'stopped' }])
  assert.deepEqual(selectMachines(rows, { status: 'running', query: '192.0.2' }).map(vm => vm.id), [8])
  assert.deepEqual(selectMachines(rows, { sort: 'vmid' }).map(vm => vm.id), [3, 8])
  assert.deepEqual(rows.map(vm => vm.id), [8, 3])
  assert.deepEqual(selectMachines(rows, { status: 'stopped', query: 'Linux' }), [])
})
test('operations keep warning outcomes distinct from failure and sort newest first', () => {
  const rows = [{ id: 2, operation_type: 'vm.start', state: 'succeeded', result: { warnings: [{ message: 'Deprecated machine' }] } }, { id: 7, operation_type: 'vm.delete', state: 'failed', error: 'Missing configuration' }, { id: 9, operation_type: 'vm.start', state: 'queued' }, { id: 12, operation_type: 'vm.create', state: 'running' }]
  assert.deepEqual(selectOperations(rows, { filter: 'warnings' }).map(op => op.id), [2])
  assert.deepEqual(selectOperations(rows, { filter: 'failed', query: 'missing' }).map(op => op.id), [7])
  assert.deepEqual(selectOperations(rows, { filter: 'active' }).map(op => op.id), [12, 9])
  assert.deepEqual(selectOperations(rows, { action: 'vm.start', query: 'vm start' }).map(op => op.id), [9, 2])
  assert.deepEqual(selectOperations(rows, { filter: 'warnings', action: 'vm.delete' }), [])
  assert.deepEqual(rows.map(op => op.id), [2, 7, 9, 12])
})
