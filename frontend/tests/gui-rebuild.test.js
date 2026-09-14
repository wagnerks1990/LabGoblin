import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  isNavigationItemActive,
  mobileNavigation,
  pageTitleForPath,
  visibleNavigation,
} from '../src/navigation/appNavigation.js'

const source = relativePath => readFileSync(new URL(`../${relativePath}`, import.meta.url), 'utf8')
const itemIds = access => visibleNavigation(access).flatMap(group => group.items.map(item => item.id))

const student = { platformAdmin: false, tenantInstructor: false, tenantAdmin: false }
const instructor = { platformAdmin: false, tenantInstructor: true, tenantAdmin: false }
const tenantAdmin = { platformAdmin: false, tenantInstructor: true, tenantAdmin: true }
const platformAdmin = { platformAdmin: true, tenantInstructor: true, tenantAdmin: true }

test('navigation model exposes only role-appropriate workflow destinations', () => {
  assert.deepEqual(itemIds(student), ['overview', 'vms', 'create', 'operations'])
  assert.deepEqual(itemIds(instructor), ['overview', 'vms', 'operations', 'classroom', 'pools', 'sessions', 'events'])
  assert.deepEqual(itemIds(tenantAdmin), ['overview', 'vms', 'operations', 'classroom', 'pools', 'sessions', 'events', 'groups'])
  assert.deepEqual(itemIds(platformAdmin), [
    'overview', 'vms', 'operations',
    'classroom', 'pools', 'sessions', 'events',
    'proxmox-setup', 'proxmox-inventory', 'templates', 'proxmox-assets',
    'organizations', 'users', 'groups',
    'telemetry', 'troubleshooting', 'updates',
  ])
})

test('route activity and page titles include nested workflow routes', () => {
  const pool = visibleNavigation(instructor).flatMap(group => group.items).find(item => item.id === 'pools')
  const vms = visibleNavigation(student).flatMap(group => group.items).find(item => item.id === 'vms')
  assert.equal(isNavigationItemActive(pool, '/pools/42'), true)
  assert.equal(isNavigationItemActive(vms, '/console/17'), true)
  assert.equal(isNavigationItemActive(vms, '/create'), false)
  assert.equal(pageTitleForPath('/admin/proxmox-assets'), 'Assets & sync')
  assert.equal(pageTitleForPath('/account/security'), 'Account security')
})

test('compact navigation keeps three role-aware priorities plus More', () => {
  assert.deepEqual(mobileNavigation(student).map(item => item.id), ['overview', 'vms', 'operations'])
  assert.deepEqual(mobileNavigation(instructor).map(item => item.id), ['overview', 'classroom', 'vms'])
  assert.deepEqual(mobileNavigation(platformAdmin).map(item => item.id), ['overview', 'proxmox-setup', 'telemetry'])
  const bottom = source('src/components/navigation/MobileBottomNav.jsx')
  assert.match(bottom, /aria-label='Quick navigation'/)
  assert.match(bottom, /aria-label='Open more navigation'/)
  assert.match(bottom, /aria-current=\{active \? 'page' : undefined\}/)
})

test('application shell preserves skip navigation and refresh-free tenant switching', () => {
  const layout = source('src/layouts/AppLayout.jsx')
  assert.match(layout, /className='skip-link' href='#main-content'/)
  assert.match(layout, /id='main-content' tabIndex=\{-1\}/)
  assert.match(layout, /<AppSidebar/)
  assert.match(layout, /<AppHeader/)
  assert.match(layout, /<MobileNavigation/)
  assert.match(layout, /<MobileBottomNav/)
  assert.match(layout, /new CustomEvent\('organization:changed'/)
  assert.match(layout, /key=\{organizationId \|\| 'no-organization'\}/)
  assert.doesNotMatch(layout, /window\.location\.reload\(\)/)
  assert.match(layout, /organizationBootstrapRoute/)
  assert.match(layout, /canRenderWithoutOrganization/)
})

test('template registration exposes only fields backed by the API contract', () => {
  const templates = source('src/pages/TemplatesPage.jsx')
  assert.match(templates, /source_vmid/)
  assert.match(templates, /proxmox_node/)
  assert.match(templates, /enabled/)
  assert.doesNotMatch(templates, /operating_system/)
  assert.doesNotMatch(templates, /default_protocols/)
  assert.doesNotMatch(templates, /Filter by cluster/)
})

test('mobile drawer exposes state, traps keyboard focus, and restores the trigger', () => {
  const header = source('src/components/navigation/AppHeader.jsx')
  const drawer = source('src/components/navigation/MobileNavigation.jsx')
  assert.match(header, /aria-expanded=\{menuOpen\}/)
  assert.match(header, /aria-controls='mobile-navigation-drawer'/)
  assert.match(drawer, /event\.key === 'Escape'/)
  assert.match(drawer, /event\.key !== 'Tab'/)
  assert.match(drawer, /document\.body\.style\.overflow = 'hidden'/)
  assert.match(drawer, /returnFocusRef\.current\?\.focus\(\)/)
  assert.match(drawer, /aria-modal='true' role='dialog'/)
})

test('responsive design contract includes compact layouts, focus, and reduced motion', () => {
  const styles = source('src/styles.css')
  assert.match(styles, /html\s*\{[^}]*min-width:\s*20rem/s)
  assert.match(styles, /:focus-visible\s*\{/)
  assert.match(styles, /@media \(max-width:\s*63\.9375rem\)/)
  assert.match(styles, /@media \(max-width:\s*47\.9375rem\)/)
  assert.match(styles, /@media \(max-width:\s*39\.9375rem\)/)
  assert.match(styles, /@media \(prefers-reduced-motion:\s*reduce\)/)
  assert.match(styles, /\.mobile-drawer/)
  assert.match(styles, /\.mobile-bottom-nav/)
})

test('shared UI primitives preserve labels, status meaning, and dialog safety', () => {
  const formField = source('src/components/ui/FormField.jsx')
  const statusBadge = source('src/components/ui/StatusBadge.jsx')
  const alert = source('src/components/ui/Alert.jsx')
  const dialog = source('src/components/ui/ConfirmDialog.jsx')
  assert.match(formField, /<label[^>]*htmlFor=\{id\}/)
  assert.match(formField, /'aria-describedby': describedBy/)
  assert.match(formField, /'aria-invalid'/)
  assert.match(statusBadge, /ui-status-badge--\$\{resolvedTone\}/)
  assert.match(alert, /tone === 'error' \? 'alert' : 'status'/)
  assert.match(alert, /aria-live=/)
  assert.match(dialog, /role='alertdialog' aria-modal='true'/)
  assert.match(dialog, /event\.key === 'Escape'/)
  assert.match(dialog, /previousFocus\?\.focus\?\.\(\)/)
})

test('core workflows distinguish loading, failure, empty, and durable activity', () => {
  const workflowState = source('src/components/workflows/WorkflowState.jsx')
  const vms = source('src/pages/VmsPage.jsx')
  const createVm = source('src/pages/CreateVmPage.jsx')
  const operations = source('src/pages/OperationsPage.jsx')
  assert.match(workflowState, /role='status' aria-live='polite'/)
  assert.match(workflowState, /role='alert'/)
  for (const page of [vms, createVm, operations]) {
    assert.match(page, /<LoadingState/)
    assert.match(page, /<ErrorState/)
    assert.match(page, /<EmptyState/)
  }
  assert.match(vms, /delete-preview/)
  assert.match(vms, /operations\/\$\{operationId\}/)
  assert.match(operations, /aria-pressed=\{filter === 'active'\}/)
  assert.match(operations, /setInterval\(\(\) => load\(\{ quiet: true \}\), 2000\)/)
})

test('instructor workflow pages expose semantic regions, labels, and table structure', () => {
  const classroom = source('src/pages/ClassroomManagementPage.jsx')
  const pools = source('src/pages/PoolsPage.jsx')
  const sessions = source('src/pages/SessionActivityPage.jsx')
  const events = source('src/pages/EventsPage.jsx')
  assert.match(classroom, /role='tablist' aria-label='Classroom workflow'/)
  assert.match(classroom, /role='tab'/)
  assert.match(classroom, /aria-selected=/)
  assert.match(classroom, /role='tabpanel'/)
  for (const page of [classroom, pools, sessions, events]) {
    assert.match(page, /role='region'/)
    assert.match(page, /aria-labelledby=/)
    assert.match(page, /scope='col'/)
  }
})

test('GUI documentation records role, viewport, accessibility, and sanitized evidence contracts', () => {
  const architecture = source('../docs/frontend-architecture.md')
  const validation = source('../docs/gui-section-validation.md')
  const testing = source('../docs/development/frontend-testing.md')
  for (const document of [architecture, validation, testing]) {
    assert.match(document, /320/)
    assert.match(document, /student/i)
    assert.match(document, /keyboard/i)
  }
  assert.match(validation, /platform admin/i)
  assert.match(validation, /sanitized/i)
  assert.match(testing, /Loading.*Empty.*Populated/s)
})
