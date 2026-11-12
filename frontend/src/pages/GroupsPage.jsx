import { useEffect, useState } from 'react'
import { listGroups, createGroup, patchGroup, deleteGroup, listGroupMembers, addGroupMember, removeGroupMember } from '../services/adminGroupsApi'
import { listCurrentOrganizationMembers } from '../services/organizationApi'

const empty = { name:'', description:'', enabled:true }

export default function GroupsPage(){
  const [rows,setRows]=useState([]); const [users,setUsers]=useState([]); const [form,setForm]=useState(empty); const [editing,setEditing]=useState(null); const [members,setMembers]=useState({})
  const [message,setMessage]=useState(null); const [loading,setLoading]=useState(true); const [loadError,setLoadError]=useState('')
  const load = async()=>{setLoading(true);setLoadError('');try{setRows(await listGroups())}catch{setRows([]);setLoadError('Unable to load groups.')}finally{setLoading(false)}}
  useEffect(()=>{load();listCurrentOrganizationMembers().then(items=>setUsers(items.map(item=>({id:item.user_id,...item})))).catch(()=>setUsers([]))},[])
  const reportError=(error,fallback)=>setMessage({type:'error',text:JSON.stringify(error?.response?.data?.detail||fallback)})
  const save=async event=>{event.preventDefault();try{if(editing)await patchGroup(editing,form);else await createGroup(form);setForm(empty);setEditing(null);await load();setMessage({type:'success',text:'Group saved.'})}catch(error){reportError(error,'Save failed')}}
  const loadMembers=async group=>{try{const groupMembers=await listGroupMembers(group.id);setMembers(previous=>({...previous,[group.id]:groupMembers}))}catch(error){reportError(error,'Failed to load group members')}}
  const removeMember=async(group,user)=>{try{await removeGroupMember(group.id,user.user_id);await loadMembers(group)}catch(error){reportError(error,'Failed to remove group member')}}
  const addMember=async(group,userId)=>{if(!userId)return;try{await addGroupMember(group.id,{user_id:userId});await loadMembers(group);setMessage({type:'success',text:`Member added to ${group.name}.`})}catch(error){reportError(error,'Failed to add group member')}}

  return <section className='page-shell' aria-labelledby='groups-title'>
    <header className='ui-page-header'><div><p className='muted'>Organization</p><h2 id='groups-title'>Groups</h2><p className='ui-page-header__description'>Organize tenant members. Classroom VM access remains controlled by lab assignments.</p></div><button onClick={load} disabled={loading}>{loading?'Refreshing…':'Refresh'}</button></header>
    {message?<p className={`msg ${message.type}`} role={message.type==='error'?'alert':'status'} aria-live='polite'>{message.text}</p>:null}
    {loadError?<p className='msg error' role='alert'>{loadError}</p>:null}
    <section className='panel' aria-labelledby='group-form-title'><h3 id='group-form-title'>{editing?'Edit group':'Create group'}</h3><form className='ui-form-grid' onSubmit={save}>
      <label className='ui-field'>Name<input className='input' value={form.name} onChange={event=>setForm({...form,name:event.target.value})}/></label>
      <label className='ui-field'>Description<input className='input' value={form.description} onChange={event=>setForm({...form,description:event.target.value})}/></label>
      <label className='ui-field'><input type='checkbox' checked={form.enabled} onChange={event=>setForm({...form,enabled:event.target.checked})}/> Enabled</label>
      <div className='ui-cluster ui-form-grid__wide'><button type='submit' disabled={!form.name}>Save group</button>{editing?<button type='button' className='ui-button--secondary' onClick={()=>{setEditing(null);setForm(empty)}}>Cancel</button>:null}</div>
    </form></section>
    <section className='panel' aria-labelledby='group-list-title'><h3 id='group-list-title'>Configured groups</h3>
      {!loading&&!loadError&&rows.length===0?<p className='muted'>No groups are configured yet.</p>:null}
      {rows.length?<div className='ui-table-wrap' role='region' aria-labelledby='group-list-title' tabIndex='0'><table className='ui-table'><thead><tr><th scope='col'>Name</th><th scope='col'>Status</th><th scope='col'>Members</th><th scope='col'>Actions</th></tr></thead><tbody>
        {rows.map(group=><tr key={group.id}><th scope='row'>{group.name}<div className='muted'>{group.description||'No description'}</div></th><td>{group.enabled?'Enabled':'Disabled'}</td><td>{group.member_count}</td><td><div className='ui-cluster'><button aria-label={`Edit group ${group.name}`} onClick={()=>{setEditing(group.id);setForm({name:group.name,description:group.description||'',enabled:group.enabled})}}>Edit</button><button aria-expanded={Array.isArray(members[group.id])} aria-controls={`group-members-${group.id}`} onClick={()=>loadMembers(group)}>Members</button><button className='btn-danger' aria-label={`Delete group ${group.name}`} onClick={async()=>{if(!confirm(`Delete group ${group.name}? This removes memberships and permissions, but not users or VMs.`))return;try{await deleteGroup(group.id);await load();setMessage({type:'success',text:`${group.name} deleted.`})}catch(error){reportError(error,'Delete failed')}}}>Delete</button></div>
          {Array.isArray(members[group.id])?<section id={`group-members-${group.id}`} className='ui-card ui-card--muted' aria-label={`Members of ${group.name}`}><h4>Members</h4>{members[group.id].length===0?<p className='muted'>No members in this group.</p>:<ul className='member-list'>{members[group.id].map(member=><li key={member.user_id}><span>{member.email||member.username||member.user_id}</span><button className='ui-button--secondary' aria-label={`Remove ${member.email||member.username||member.user_id} from ${group.name}`} onClick={()=>removeMember(group,member)}>Remove</button></li>)}</ul>}<label className='ui-field'>Add organization member<select className='input' value='' onChange={event=>addMember(group,Number(event.target.value))}><option value=''>Select a user…</option>{users.map(user=><option key={user.id} value={user.id}>{user.email || user.username}</option>)}</select></label></section>:null}
        </td></tr>)}
      </tbody></table></div>:null}
    </section>
  </section>
}
