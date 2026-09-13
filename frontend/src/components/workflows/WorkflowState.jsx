export function LoadingState({ label = 'Loading…' }) {
  return <div className='panel' role='status' aria-live='polite'><div className='branded-state'><img src='/brand/labgoblin-icon.svg' alt=''/><div><span className='eyebrow'>LabGoblin</span><p>{label}</p></div></div></div>
}

export function ErrorState({ message, onRetry, retrying = false }) {
  return <div className='panel' role='alert'>
    <h3>Something went wrong</h3>
    <p className='muted'>{message}</p>
    {onRetry ? <button type='button' onClick={onRetry} disabled={retrying}>{retrying ? 'Trying again…' : 'Try again'}</button> : null}
  </div>
}

export function EmptyState({ title, message, action = null }) {
  return <div className='panel workspace-empty'>
    <img src='/brand/labgoblin-icon.svg' alt=''/>
    <h3>{title}</h3>
    <p className='muted'>{message}</p>
    {action}
  </div>
}
