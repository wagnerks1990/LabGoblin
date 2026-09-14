import test from 'node:test'
import assert from 'node:assert/strict'
import { emptySetup, setupStepError, setupPayload, setupFromSaved, submissionId } from '../src/services/labSetup.js'

test('wizard prevents incomplete setup and invalid schedules before submission', () => {
  const form = emptySetup()
  assert.ok(setupStepError(form,0))
  assert.ok(setupStepError(form,1))
  form.name = 'Linux'; form.class_name = 'Class'; form.template_id = '2'
  assert.equal(setupStepError(form,0),'')
  assert.equal(setupStepError(form,1),'')
  form.state = 'scheduled'; form.starts_at = ''
  assert.ok(setupStepError(form,3))
  form.state = 'draft'; form.starts_at = 'invalid'
  assert.ok(setupStepError(form,3))
  form.starts_at = '2027-01-01T12:00'; form.ends_at = '2027-01-01T11:00'
  assert.ok(setupStepError(form,3))
  form.ends_at = '2027-01-01T14:00'; form.slots = 1.5
  assert.ok(setupStepError(form,3))
  assert.ok(setupStepError(form,4))
})

test('existing setup retains its record bindings and concurrency token on edit', () => {
  const form = setupFromSaved({name:'Lab',description:'Practice',class_id:1,class_name:'Class',term:'Fall',pool_id:2,student_ids:[3],slots:2,state:'draft',starts_at:null,ends_at:null,etag:'server-version',console_enabled:true,rdp_enabled:true,terminal_enabled:true,student_can_power_off:false,student_can_reset:false})
  const result = setupPayload({...form,reviewed:true},'request-id')
  assert.equal(result.class_id,1); assert.equal(result.pool_id,2)
  assert.equal(result.template_id,null); assert.equal(result.expected_etag,'server-version')
  assert.deepEqual(result.student_ids,[3]); assert.deepEqual(result.new_students,[])
  assert.equal(result.request_id,'request-id')
})

test('submission IDs work without secure-context randomUUID on LAN HTTP', () => {
  const id = submissionId()
  assert.match(id,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  assert.notEqual(id,submissionId())
})
