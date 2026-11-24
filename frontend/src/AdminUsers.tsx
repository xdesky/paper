import {useEffect,useMemo,useState} from 'react';

type AdminUser={id:string;email:string;display_name:string;plan:'starter'|'lifetime';created_at:number;is_admin:boolean;is_active:boolean;project_count:number};
async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{const response=await fetch('/api'+path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});if(!response.ok){const data=await response.json().catch(()=>({}));throw Error(data.detail||'Could not complete this request.');}return response.json();}

export function AdminUsers(){
 const [users,setUsers]=useState<AdminUser[]>([]),[query,setQuery]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState('');
 async function load(){setError('');try{setUsers(await request<AdminUser[]>('/admin/users'));}catch(e){setError((e as Error).message);}}
 useEffect(()=>{void load();},[]);
 const filtered=useMemo(()=>users.filter(user=>`${user.display_name} ${user.email}`.toLowerCase().includes(query.toLowerCase())),[users,query]);
 async function update(user:AdminUser,changes:Partial<Pick<AdminUser,'is_active'|'plan'>>){
  const next={...user,...changes},key=user.id+'-'+Object.keys(changes).join('-');setBusy(key);setError('');
  try{const updated=await request<AdminUser>(`/admin/users/${user.id}`,'PATCH',{active:next.is_active,lifetime:next.plan==='lifetime'});setUsers(old=>old.map(item=>item.id===updated.id?updated:item));}
  catch(e){setError((e as Error).message);}finally{setBusy('');}
 }
 return <section className="panel admin-users">
  <div className="admin-users-heading"><div><span className="season-kicker">ADMINISTRATION</span><h2>User management</h2><p>Review accounts, saved projects, access, and Lifetime status.</p></div><span className="badge">{users.length} {users.length===1?'user':'users'}</span></div>
  {error&&<p className="error" role="alert">{error}</p>}
  <label className="admin-search">Search users<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Name or email address"/></label>
  <div className="admin-user-list">{filtered.map(user=><article className="admin-user-row" key={user.id}>
   <div className="admin-user-identity"><strong>{user.display_name}</strong><span>{user.email}</span><small>Joined {new Date(user.created_at*1000).toLocaleDateString('en-US')}</small></div>
   <div className="admin-user-meta"><span className="badge">{user.project_count} {user.project_count===1?'project':'projects'}</span><span className={'badge '+(user.is_active?'success':'suspended')}>{user.is_active?'Active':'Suspended'}</span>{user.is_admin&&<span className="badge admin-badge">Admin</span>}</div>
   <label className="admin-toggle"><input type="checkbox" checked={user.plan==='lifetime'} disabled={!!busy||user.is_admin} onChange={e=>void update(user,{plan:e.target.checked?'lifetime':'starter'})}/><span>Lifetime</span></label>
   <label className="admin-toggle"><input type="checkbox" checked={user.is_active} disabled={!!busy||user.is_admin} onChange={e=>void update(user,{is_active:e.target.checked})}/><span>{user.is_admin?'Protected admin':user.is_active?'Enabled':'Suspended'}</span></label>
  </article>)}{filtered.length===0&&<div className="admin-empty">{users.length?'No users match your search.':'No accounts found.'}</div>}</div>
 </section>;
}
