export const setupSteps = ['Lab & class', 'Machines', 'Students', 'Access & schedule', 'Review']
export const emptySetup = () => ({ name: '', description: '', class_id: '', class_name: '', term: '', pool_id: '', template_id: '', student_ids: [], new_students: [], starts_at: '', ends_at: '', slots: 1, console_enabled: true, rdp_enabled: true, terminal_enabled: true, student_can_power_off: false, student_can_reset: false, state: 'draft', reviewed: false })

export function submissionId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128
  const hex = [...bytes].map(v => v.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}

export function setupStepError(form, step, now = Date.now()) {
  if (step === 0 && (!form.name.trim() || (!form.class_id && !form.class_name.trim()))) return 'Enter a lab name and choose or name its class.'
  if (step === 1 && !form.pool_id && !form.template_id) return 'Choose a template or an existing pool.'
  if (step === 2 && form.new_students.some(row => !row.username.trim() || !row.email.includes('@') || !row.password)) return 'Complete the username, email, and password for every new student.'
  if (step === 3) {
    if (!Number.isInteger(Number(form.slots)) || Number(form.slots) < 1 || Number(form.slots) > 10) return 'Choose between 1 and 10 machines per student.'
    if ([form.starts_at, form.ends_at].some(value => value && !Number.isFinite(Date.parse(value)))) return 'Enter valid start and end times.'
    if (form.starts_at && form.ends_at && Date.parse(form.starts_at) >= Date.parse(form.ends_at)) return 'The end must be after the start.'
    if (form.state !== 'draft' && form.ends_at && Date.parse(form.ends_at) <= now) return 'Choose a future end time.'
    if (form.state === 'scheduled' && !form.starts_at) return 'Choose a start time for a scheduled lab.'
    if (form.state === 'active' && form.starts_at && Date.parse(form.starts_at) > now) return 'Choose Scheduled for a future start time.'
    if (form.state !== 'draft' && !form.student_ids.length && !form.new_students.length) return 'Add students before opening the lab, or save a draft.'
  }
  if (step === 4 && !form.reviewed) return 'Confirm that you have reviewed the setup.'
  return ''
}

export function setupPayload(form, requestId) {
  return { ...form, request_id: requestId, class_id: form.class_id ? Number(form.class_id) : null, pool_id: form.pool_id ? Number(form.pool_id) : null, template_id: form.pool_id ? null : Number(form.template_id), student_ids: form.student_ids.map(Number), slots: Number(form.slots), starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null, ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null }
}

export function localInputTime(value) {
  if (!value) return ''
  const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0,16)
}

export function setupFromSaved(row) {
  return { ...emptySetup(), name: row.name, description: row.description, class_id: String(row.class_id), class_name: row.class_name, term: row.term, pool_id: String(row.pool_id), student_ids: row.student_ids, starts_at: localInputTime(row.starts_at), ends_at: localInputTime(row.ends_at), slots: row.slots, console_enabled: row.console_enabled, rdp_enabled: row.rdp_enabled, terminal_enabled: row.terminal_enabled, student_can_power_off: row.student_can_power_off, student_can_reset: row.student_can_reset, state: row.state, expected_etag: row.etag }
}
