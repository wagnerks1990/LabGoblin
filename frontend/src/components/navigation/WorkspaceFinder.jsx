import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { visibleNavigation } from '../../navigation/appNavigation'
import NavIcon from './NavIcon'

export default function WorkspaceFinder({ access }) {
  const dialog = useRef(null)
  const trigger = useRef(null)
  const [query, setQuery] = useState('')
  const location = useLocation()
  const close = () => dialog.current?.close()
  const open = () => { setQuery(''); dialog.current?.showModal() }
  useEffect(() => { dialog.current?.close() }, [location.pathname])
  useEffect(() => {
    const shortcut = event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        if (dialog.current?.open) dialog.current.close()
        else { setQuery(''); dialog.current?.showModal() }
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])
  const groups = visibleNavigation(access).map(group => ({ ...group,
    items: group.items.filter(item => `${group.label} ${item.label}`.toLowerCase().includes(query.trim().toLowerCase())),
  })).filter(group => group.items.length)
  return <>
    <button ref={trigger} type='button' className='workspace-find-trigger' onClick={open} aria-label='Find a page' aria-keyshortcuts='Control+k Meta+k'><NavIcon name='search'/><span>Find a page</span><kbd>⌘ / Ctrl K</kbd></button>
    <dialog ref={dialog} className='workspace-finder' aria-labelledby='finder-title' onClose={() => trigger.current?.focus()} onClick={event => { if (event.target === dialog.current) close() }}>
      <div className='panel-head'><div><p className='eyebrow'>LabGoblin workspace</p><h2 id='finder-title'>Where do you want to go?</h2></div><button type='button' className='icon-button' aria-label='Close page finder' onClick={close}><NavIcon name='close'/></button></div>
      <label className='ui-field'>Search pages<input autoFocus type='search' value={query} onChange={event => setQuery(event.target.value)} placeholder='Try templates, classes or updates…'/></label>
      <div className='finder-results'>
        {!groups.length ? <p role='status'>No matching pages. Try a different name.</p> : groups.map(group => <section key={group.id}><h3 className='eyebrow'>{group.label}</h3>{group.items.map(item => <Link to={item.to} key={item.id} onClick={close}><NavIcon name={item.icon}/><span>{item.label}</span><NavIcon name='expand'/></Link>)}</section>)}
      </div>
      <p className='ui-field__hint'>Tab to a page, Enter to open. Escape to close.</p>
    </dialog>
  </>
}
