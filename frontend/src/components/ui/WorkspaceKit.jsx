import NavIcon from '../navigation/NavIcon'

export function WorkspaceHeading({ eyebrow = 'Workspace', title, description, children }) {
  return <header className='workspace-heading'><div><p className='eyebrow'>{eyebrow}</p><h2>{title}</h2><p className='muted'>{description}</p></div><div className='ui-cluster'>{children}</div></header>
}
export function MetricStrip({ items }) {
  return <div className='metric-strip'>{items.map(item => <div className='workspace-metric' key={item.label}><span className='metric-icon'><NavIcon name={item.icon || 'activity'}/></span><div><span className='label'>{item.label}</span><strong>{item.value ?? '—'}</strong>{item.hint ? <small>{item.hint}</small> : null}</div></div>)}</div>
}
export function CollectionToolbar({ query, onQuery, label = 'Search resources', children, count, total, onReset }) {
  return <div className='collection-tools'><div className='collection-controls'><label className='ui-field collection-search'>{label}<input type='search' value={query} onChange={event => onQuery(event.target.value)} placeholder={label}/></label>{children}{onReset ? <button className='ui-button--secondary' type='button' onClick={onReset}>Reset filters</button> : null}</div><p className='collection-count' role='status'>{count} of {total} shown</p></div>
}
export function ViewToggle({ value, onChange }) {
  return <div className='view-toggle' role='group' aria-label='Collection layout'>{['cards', 'list'].map(mode => <button key={mode} type='button' aria-pressed={value === mode} onClick={() => onChange(mode)}>{mode === 'cards' ? 'Cards' : 'List'}</button>)}</div>
}
export function CapacityMeter({ label, value }) {
  const known = value !== null && value !== undefined && Number.isFinite(Number(value))
  return <div className='capacity-meter'><div><span>{label}</span><strong>{known ? `${Number(value).toFixed(1)}%` : 'Not reported'}</strong></div>{known ? <meter aria-label={label} min='0' max='100' value={Math.max(0, Math.min(100, Number(value)))}/> : null}</div>
}
