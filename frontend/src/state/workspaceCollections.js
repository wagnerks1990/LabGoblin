const normalize = value => String(value ?? '').toLowerCase().replace(/[._]/g, ' ').replace(/\s+/g, ' ').trim()

// Match every search term, including human-readable action names such as VM start.
export function matchesQuery(query, values) {
  const haystack = values.map(normalize).join(' ')
  return normalize(query).split(' ').every(term => haystack.includes(term))
}
export function selectMachines(rows, { query = '', status = '', sort = 'name' } = {}) {
  return rows.filter(vm => (!status || normalize(vm.status) === normalize(status)) &&
    matchesQuery(query, [vm.vm_name, vm.vmid, vm.proxmox_node, vm.assigned_ip, vm.hostname, ...(vm.observed_addresses || []).map(item => item.address)]))
    .sort((a, b) => sort === 'vmid' ? Number(a.vmid) - Number(b.vmid) : String(a.vm_name || '').localeCompare(String(b.vm_name || '')))
}
export function selectOperations(rows, { query = '', filter = 'all', action = '' } = {}) {
  return rows.filter(operation => {
    const state = normalize(operation.state)
    const matchState = filter === 'all' || (filter === 'active' ? ['queued', 'running'].includes(state) : filter === 'warnings' ? operation.result?.warnings?.length > 0 : state === filter)
    return matchState && (!action || operation.operation_type === action) &&
      matchesQuery(query, [operation.id, operation.operation_type, operation.target_type, operation.target_id, operation.error])
  }).sort((a, b) => Number(b.id) - Number(a.id))
}
