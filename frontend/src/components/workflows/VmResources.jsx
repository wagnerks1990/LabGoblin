import { formatBytes, formatUptime, vmAddress } from '../../services/vmResources'

export default function VmResources({ vm }) {
  const data = vm.resources || {}
  return <div className='vm-resources'>
    <div className='resource-facts'>
      <span>vCPUs<strong>{data.cpu_count ?? 'Not reported'}</strong></span>
      <span>Memory allocated<strong>{formatBytes(data.memory_bytes)}</strong></span>
      <span>Disk capacity<strong>{formatBytes(data.disk_capacity_bytes)}</strong></span>
      <span>{vm.observed_addresses?.length ? 'Guest IP · agent' : 'Saved address'}<strong>{vmAddress(vm)}</strong></span>
    </div>
    {vm.resource_warning ? <p className='msg error' role='status'>{vm.resource_warning}</p> : null}
    <details><summary>Resource and network details</summary>
      <dl className='vm-resource-details'>
        <dt>Operating system</dt><dd>{vm.operating_system || 'Not reported'}</dd>
        <dt>CPU use</dt><dd>{data.cpu_usage_percent == null ? 'Not reported' : `${data.cpu_usage_percent}%`}</dd>
        <dt>Memory use · Proxmox</dt><dd>{formatBytes(data.memory_used_bytes)}</dd>
        <dt>Uptime</dt><dd>{formatUptime(data.uptime_seconds)}</dd>
        {data.disks?.map(disk => <div key={disk.device}><dt>Disk {disk.device}</dt><dd>{formatBytes(disk.capacity_bytes)}</dd></div>)}
        <dt>Network received / sent</dt><dd>{formatBytes(data.network_received_bytes)} / {formatBytes(data.network_sent_bytes)}</dd>
        <dt>Disk read / written</dt><dd>{formatBytes(data.disk_read_bytes)} / {formatBytes(data.disk_written_bytes)}</dd>
        {vm.observed_addresses?.map(item => <div key={`${item.address}-${item.mac_address}`}><dt>Guest IP / MAC</dt><dd>{item.address} / {item.mac_address}{item.matches_cloud_init ? ' · matches cloud-init' : ''}</dd></div>)}
        <dt>Last observed</dt><dd>{vm.observed_at ? new Date(vm.observed_at).toLocaleString() : 'Not refreshed'}</dd>
      </dl>
      <p className='ui-field__hint'>{vm.discovery_hint}</p>
      <p className='ui-field__hint'>Disk capacity is allocated virtual storage, not filesystem free space. I/O values are cumulative bytes. Agent IPs are observations; connection approval is separate.</p>
    </details>
  </div>
}
