const successful = new Set(['running', 'succeeded', 'completed', 'verified', 'active', 'ready'])
const neutral = new Set(['stopped', 'closed', 'cancelled', 'ended', 'disabled', 'draft'])
const pending = new Set(['pending', 'queued', 'running', 'provisioning', 'creating', 'syncing', 'warning', 'maintenance', 'scheduled'])

export default function WorkflowStatus({ value }) {
  const status = String(value || 'unknown').toLowerCase()
  const tone = status === 'running'
    ? 'badge-running'
    : successful.has(status)
      ? 'badge-running'
      : neutral.has(status)
        ? 'badge-stopped'
        : pending.has(status)
          ? 'badge-provisioning'
          : 'badge-error'
  return <span className={`badge ${tone}`}>{status.replaceAll('_', ' ')}</span>
}
