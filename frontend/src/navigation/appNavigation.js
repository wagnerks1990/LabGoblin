const allUsers = () => true

export const navigationGroups = [
  {
    id: 'workspace',
    label: 'Workspace',
    items: [
      { id: 'overview', label: 'Overview', shortLabel: 'Home', to: '/', icon: 'home', visible: allUsers },
      { id: 'vms', label: 'Lab VMs', shortLabel: 'VMs', to: '/vms', icon: 'monitor', visible: allUsers, aliases: ['/console/'] },
      { id: 'create', label: 'Create VM', shortLabel: 'Create', to: '/create', icon: 'plus', visible: access => !access.tenantInstructor },
      { id: 'operations', label: 'Operations', shortLabel: 'Activity', to: '/operations', icon: 'activity', visible: allUsers },
    ],
  },
  {
    id: 'teaching',
    label: 'Teaching',
    visible: access => access.tenantInstructor,
    items: [
      { id: 'classroom', label: 'Classes & labs', shortLabel: 'Classes', to: '/classroom', icon: 'classroom', visible: allUsers },
      { id: 'pools', label: 'Resource pools', shortLabel: 'Pools', to: '/pools', icon: 'layers', visible: allUsers, aliases: ['/pools/'] },
      { id: 'sessions', label: 'Session activity', shortLabel: 'Sessions', to: '/admin/sessions', icon: 'session', visible: allUsers },
      { id: 'events', label: 'Events & tasks', shortLabel: 'Events', to: '/events', icon: 'event', visible: allUsers },
    ],
  },
  {
    id: 'infrastructure',
    label: 'Infrastructure',
    visible: access => access.platformAdmin,
    items: [
      { id: 'proxmox-setup', label: 'Proxmox setup', shortLabel: 'Setup', to: '/admin/proxmox-setup', icon: 'server', visible: allUsers },
      { id: 'proxmox-inventory', label: 'Inventory', shortLabel: 'Inventory', to: '/admin/proxmox-inventory', icon: 'inventory', visible: allUsers },
      { id: 'templates', label: 'Templates', shortLabel: 'Templates', to: '/admin/templates', icon: 'template', visible: allUsers },
      { id: 'proxmox-assets', label: 'Assets & sync', shortLabel: 'Assets', to: '/admin/proxmox-assets', icon: 'sync', visible: allUsers },
    ],
  },
  {
    id: 'access',
    label: 'People & access',
    visible: access => access.tenantAdmin,
    items: [
      { id: 'organizations', label: 'Organizations', shortLabel: 'Orgs', to: '/admin/organizations', icon: 'organization', visible: access => access.platformAdmin },
      { id: 'users', label: 'Users', shortLabel: 'Users', to: '/admin/users', icon: 'people', visible: access => access.platformAdmin },
      { id: 'groups', label: 'Groups', shortLabel: 'Groups', to: '/admin/groups', icon: 'group', visible: allUsers },
    ],
  },
  {
    id: 'system',
    label: 'System',
    visible: access => access.platformAdmin,
    items: [
      { id: 'telemetry', label: 'Telemetry', shortLabel: 'System', to: '/telemetry', icon: 'pulse', visible: allUsers },
      { id: 'troubleshooting', label: 'Troubleshooting', shortLabel: 'Issues', to: '/troubleshooting', icon: 'wrench', visible: allUsers },
      { id: 'updates', label: 'System updates', shortLabel: 'Updates', to: '/admin/system-update', icon: 'update', visible: allUsers },
    ],
  },
]

export function visibleNavigation(access) {
  return navigationGroups
    .filter(group => !group.visible || group.visible(access))
    .map(group => ({ ...group, items: group.items.filter(item => item.visible(access)).map(item => !access.tenantInstructor && !access.platformAdmin ? { ...item, label: ({ overview: 'My labs', vms: 'My machines', create: 'Start a lab', operations: 'Lab activity' })[item.id] || item.label } : item) }))
    .filter(group => group.items.length > 0)
}

export function isNavigationItemActive(item, pathname) {
  if (item.to === '/') return pathname === '/'
  return pathname === item.to
    || pathname.startsWith(`${item.to}/`)
    || (item.aliases || []).some(alias => pathname.startsWith(alias))
}

export function pageTitleForPath(pathname) {
  for (const group of navigationGroups) {
    const item = group.items.find(candidate => isNavigationItemActive(candidate, pathname))
    if (item) return item.label
  }
  if (pathname.startsWith('/account/security')) return 'Account security'
  return 'LabGoblin'
}

export function mobileNavigation(access) {
  if (access.platformAdmin) {
    return [
      navigationGroups[0].items[0],
      navigationGroups[2].items[0],
      navigationGroups[4].items[0],
    ]
  }
  if (access.tenantInstructor) {
    return [
      navigationGroups[0].items[0],
      navigationGroups[1].items[0],
      navigationGroups[0].items[1],
    ]
  }
  return [navigationGroups[0].items[0], navigationGroups[0].items[1], navigationGroups[0].items[3]]
}
