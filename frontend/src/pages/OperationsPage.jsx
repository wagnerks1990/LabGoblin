import { useCallback, useEffect, useMemo, useState } from 'react'
import { EmptyState, ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import { listOperations } from '../services/operationsApi'

const activeStates = new Set(['queued', 'running'])
const label = value => String(value || 'operation').replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase())
const formatDate = value => value ? new Date(value).toLocaleString() : 'Not reported'

export default function OperationsPage() {
  const [operations, setOperations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')

  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true)
    try {
      const rows = await listOperations()
      setOperations(Array.isArray(rows) ? rows : [])
      setError('')
    } catch (requestError) {
      const detail = requestError?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Operation history could not be loaded.')
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!operations.some(operation => activeStates.has(String(operation.state).toLowerCase()))) return
    const timer = setInterval(() => load({ quiet: true }), 2000)
    return () => clearInterval(timer)
  }, [operations, load])

  const visible = useMemo(() => filter === 'active'
    ? operations.filter(operation => activeStates.has(String(operation.state).toLowerCase()))
    : filter === 'failed' ? operations.filter(operation => String(operation.state).toLowerCase() === 'failed') : operations, [operations, filter])

  if (loading) return <LoadingState label='Loading operation activity…' />
  if (error && !operations.length) return <ErrorState message={error} onRetry={load} retrying={loading} />

  return <section>
    <div className='panel-head'>
      <div><h1>Operations</h1><p className='muted'>Provisioning and power actions continue safely even if you leave this page.</p></div>
      <button type='button' onClick={() => load()} disabled={loading}>Refresh</button>
    </div>
    {error ? <p className='msg error' role='alert'>{error}</p> : null}
    <div className='group' role='group' aria-label='Filter operations'>
      <button type='button' aria-pressed={filter === 'active'} onClick={() => setFilter('active')}>Active ({operations.filter(operation => activeStates.has(String(operation.state).toLowerCase())).length})</button>
      <button type='button' aria-pressed={filter === 'failed'} onClick={() => setFilter('failed')}>Failed ({operations.filter(operation => String(operation.state).toLowerCase() === 'failed').length})</button>
      <button type='button' aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>History ({operations.length})</button>
    </div>
    {!visible.length ? <EmptyState
      title={filter === 'active' ? 'No operations in progress' : filter === 'failed' ? 'No failed operations' : 'No operation history yet'}
      message={filter === 'active' && operations.length ? 'Completed and failed operations are available under History.' : 'Provisioning and VM actions will appear here.'}
    /> : <div className='card-grid' style={{ marginTop: 16 }}>
      {visible.map(operation => {
        const state = String(operation.state || '').toLowerCase()
        return <article className='panel' key={operation.id} aria-live={activeStates.has(state) ? 'polite' : undefined}>
          <div className='panel-head'><h3>{label(operation.operation_type)}</h3><WorkflowStatus value={operation.state} /></div>
          <p>{label(operation.target_type)} {operation.target_id}</p>
          {(operation.result?.warnings || []).map((warning, index) => <p className='ui-alert ui-alert--warning' key={index}>Completed with warning: {warning.message}</p>)}
          {operation.error ? <p className='msg error' role='alert'>{operation.error}</p> : null}
          {activeStates.has(state) ? <p className='muted'>Attempt {operation.attempts || 0}. This status refreshes automatically.</p> : null}
          <details>
            <summary>Operation details</summary>
            <dl>
              <dt>Operation ID</dt><dd>{operation.id}</dd>
              <dt>Attempts</dt><dd>{operation.attempts ?? 0}</dd>
              <dt>Created</dt><dd>{formatDate(operation.created_at)}</dd>
              <dt>Updated</dt><dd>{formatDate(operation.updated_at)}</dd>
            </dl>
          </details>
        </article>
      })}
    </div>}
  </section>
}
