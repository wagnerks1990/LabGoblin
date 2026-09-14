export function formatBytes(value) {
  if (value == null || !Number.isFinite(Number(value)) || Number(value) < 0) return 'Not reported'
  let amount = Number(value)
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit += 1 }
  return `${Number(amount.toFixed(1))} ${units[unit]}`
}
export function formatUptime(value) {
  if (value == null || !Number.isFinite(Number(value)) || Number(value) < 0) return 'Not reported'
  const minutes = Math.floor(Number(value) / 60)
  return `${Math.floor(minutes / 1440)}d ${Math.floor(minutes / 60) % 24}h ${minutes % 60}m`
}
export function vmAddress(vm) {
  return vm.observed_addresses?.map(item => item.address).join(', ') || vm.assigned_ip || vm.hostname || 'Not reported'
}
