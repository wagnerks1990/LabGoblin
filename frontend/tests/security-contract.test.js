import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

test('API client uses cookies and never reads a JWT from browser storage', () => {
  const source = readFileSync(new URL('../src/api/client.js', import.meta.url), 'utf8')
  assert.match(source, /withCredentials:\s*true/)
  assert.doesNotMatch(source, /getItem\(['"]token['"]\)/)
})

test('console launch code never puts auth or Proxmox tickets in a URL', () => {
  const eventStream = readFileSync(new URL('../src/hooks/useEventStream.js', import.meta.url), 'utf8')
  const vmPage = readFileSync(new URL('../src/pages/VmsPage.jsx', import.meta.url), 'utf8')
  assert.doesNotMatch(eventStream, /token=/)
  assert.doesNotMatch(vmPage, /ticket=/)
})

test('unsupported SPICE launch controls are not exposed', () => {
  const sources = [
    readFileSync(new URL('../src/pages/VmsPage.jsx', import.meta.url), 'utf8'),
    readFileSync(new URL('../src/pages/PoolsPage.jsx', import.meta.url), 'utf8'),
  ].join('\n')
  assert.doesNotMatch(sources, /console\/spice|>SPICE</)
})

test('VM connections navigate internally without delayed browser popups', () => {
  const source = readFileSync(new URL('../src/pages/VmsPage.jsx', import.meta.url), 'utf8')
  assert.match(source, /to=\{`\/console\/\$\{vm.id\}`\}/)
  assert.doesNotMatch(source, /window.open/)
  assert.doesNotMatch(source, /data\?\.novnc_url/)
})

test('durable VM and asset operations poll all active states', () => {
  const vmPage = readFileSync(new URL('../src/pages/VmsPage.jsx', import.meta.url), 'utf8')
  const assetsPage = readFileSync(new URL('../src/pages/ProxmoxAssetsPage.jsx', import.meta.url), 'utf8')
  assert.match(vmPage, /operations\/\$\{operationId\}/)
  assert.match(assetsPage, /'queued', 'running', 'syncing'/)
})
