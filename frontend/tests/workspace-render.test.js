import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
let server, kit
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  kit = await server.ssrLoadModule('/src/components/ui/WorkspaceKit.jsx')
})
after(async () => { await server?.close() })
test('capacity distinguishes unavailable data from a measured zero', () => {
  const unavailable = renderToStaticMarkup(React.createElement(kit.CapacityMeter, { label: 'CPU', value: null }))
  const zero = renderToStaticMarkup(React.createElement(kit.CapacityMeter, { label: 'CPU', value: 0 }))
  assert.match(unavailable, /Not reported/)
  assert.doesNotMatch(unavailable, /<meter/)
  assert.match(zero, /0.0%/)
  assert.match(zero, /<meter aria-label="CPU" min="0" max="100" value="0"/)
})
test('metric output escapes API text and does not invent zero on failure', () => {
  const html = renderToStaticMarkup(React.createElement(kit.MetricStrip, { items: [{ label: '<script>label</script>', value: null }, { label: 'Running', value: 0 }] }))
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /<strong>—<\/strong>/)
  assert.match(html, /<strong>0<\/strong>/)
})
test('collection controls render named search and mutually exclusive layout selection', () => {
  const html = renderToStaticMarkup(React.createElement(kit.CollectionToolbar, { query: '', onQuery: () => {}, label: 'Search machines', count: 1, total: 4 }))
  assert.match(html, /<label[^>]*>Search machines<input type="search"/)
  assert.match(html, /role="status">1 of 4 shown/)
  const toggle = renderToStaticMarkup(React.createElement(kit.ViewToggle, { value: 'list', onChange: () => {} }))
  assert.match(toggle, /aria-pressed="false">Cards/)
  assert.match(toggle, /aria-pressed="true">List/)
})
