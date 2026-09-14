export function preferredConnection(options, requested) {
  if (!options?.running) return null
  const available = { vnc: options.vnc, rdp: options.operating_system === 'windows' && options.rdp, ssh: options.operating_system === 'linux' && options.terminal }
  if (Object.hasOwn(available, requested) && available[requested]) return requested
  return ['rdp', 'ssh', 'vnc'].find(method => available[method]) || null
}
