import { useCallback, useEffect, useMemo, useState } from 'react'
import { EmptyState, ErrorState, LoadingState } from '../components/workflows/WorkflowState'
import { CollectionToolbar, MetricStrip, WorkspaceHeading } from '../components/ui/WorkspaceKit'
import WorkflowStatus from '../components/workflows/WorkflowStatus'
import { selectOperations } from '../state/workspaceCollections'
import { listOperations } from '../services/operationsApi'

const activeStates = new Set(['queued', 'running'])
const label = value => String(value || 'operation').replaceAll('_', ' ').replaceAll('.', ' ').replace(/\b\w/g, character => character.toUpperCase())
const formatDate = value => value ? new Date(value).toLocaleString() : 'Not reported'

export default function OperationsPage() {
  const [query, setQuery] = useState('')
  const [actionFilter, setActionFilter] = useState('')
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

  const visible = useMemo(() => selectOperations(operations, { query, filter, action: actionFilter }), [operations, filter, actionFilter, query])

  if (loading) return <LoadingState label='Loading operation activity…' />
  if (error && !operations.length) return <ErrorState message={error} onRetry={load} retrying={loading} />

  return <section>
    <WorkspaceHeading title='Activity center' description='Track provisioning and power actions. Work continues safely when you leave this page.'><button type='button' onClick={() => load()} disabled={loading}>Refresh</button></WorkspaceHeading>
    <MetricStrip items={[{ label: 'In progress', value: operations.filter(op => activeStates.has(op.state)).length, icon: 'activity' }, { label: 'Succeeded', value: operations.filter(op => op.state === 'succeeded').length, icon: 'event' }, { label: 'Failed', value: operations.filter(op => op.state === 'failed').length, icon: 'wrench' }, { label: 'With warnings', value: operations.filter(op => op.result?.warnings?.length).length, icon: 'pulse' }]}/>
    <CollectionToolbar query={query} onQuery={setQuery} label='Search operation, resource or error' count={visible.length} total={operations.length} onReset={() => { setQuery(''); setActionFilter(''); setFilter('all') }}><label className='ui-field'>Action<select value={actionFilter} onChange={event => setActionFilter(event.target.value)}><option value=''>All actions</option>{[...new Set(operations.map(op => op.operation_type))].sort().map(type => <option key={type} value={type}>{label(type)}</option>)}</select></label></CollectionToolbar>
    {error ? <p className='msg error' role='alert'>{error}</p> : null}
    <div className='collection-tabs' role='group' aria-label='Filter operations'>
      <button type='button' aria-pressed={filter === 'active'} onClick={() => setFilter('active')}>Active ({operations.filter(operation => activeStates.has(String(operation.state).toLowerCase())).length})</button>
      <button type='button' aria-pressed={filter === 'failed'} onClick={() => setFilter('failed')}>Failed ({operations.filter(operation => String(operation.state).toLowerCase() === 'failed').length})</button>
      <button type='button' aria-pressed={filter === 'succeeded'} onClick={() => setFilter('succeeded')}>Succeeded</button>
      <button type='button' aria-pressed={filter === 'warnings'} onClick={() => setFilter('warnings')}>Warnings</button>
      <button type='button' aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>History ({operations.length})</button>
    </div>
    {!visible.length ? <EmptyState
      title={query || actionFilter ? 'No matching operations' : filter === 'active' ? 'No operations in progress' : filter === 'failed' ? 'No failed operations' : filter === 'warnings' ? 'No operations with warnings' : filter === 'succeeded' ? 'No successful operations yet' : 'No operation history yet'}
      message={filter === 'active' && operations.length ? 'Completed and failed operations are available under History.' : 'Provisioning and VM actions will appear here.'}
    /> : <div className='operation-timeline'>
      {visible.map(operation => {
        const state = String(operation.state || '').toLowerCase()
        return <article className='panel operation-entry' key={operation.id} aria-live={activeStates.has(state) ? 'polite' : undefined}>
          <div className='panel-head'><h3>{label(operation.operation_type)}</h3><WorkflowStatus value={operation.state} /></div>
          <p className='muted'>{label(operation.target_type)} {operation.target_id} · #{operation.id} · {formatDate(operation.created_at)}</p>
          {(operation.result?.warnings || []).map((warning, index) => <p className='ui-alert ui-alert--warning' key={index}>Completed with warning: {warning.message}</p>)}
          {operation.error ? <details className='operation-error'><summary>Failure details</summary><p className='msg error'>{operation.error}</p></details> : null}
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
