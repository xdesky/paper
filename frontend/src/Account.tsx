import {useEffect,useState} from 'react';
export type User={id:string;email:string;display_name:string;plan:'starter'|'lifetime';is_admin:boolean;is_active:boolean};
export type AccountState={user:User|null;project_limit:number|null;project_count:number};
type Plan={name:string;configured:boolean;mode:string;one_time:boolean;free_project_limit:number;amount?:number;currency?:string};
async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{
 const r=await fetch('/api'+path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
 if(!r.ok){const e=await r.json();throw Error(typeof e.detail==='string'?e.detail:e.detail?.map((x:{msg:string})=>x.msg).join(' · ')||'Please try again.');}
 return r.status===204?undefined as T:r.json();
}
export function Account({state,onRefresh,onSignOut}:{state:AccountState;onRefresh:()=>Promise<void>;onSignOut:()=>void}){
 const [mode,setMode]=useState<'login'|'register'>('login'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 const [plan,setPlan]=useState<Plan|null>(null),[planError,setPlanError]=useState(''),[purchases,setPurchases]=useState<{id:string;status:string;amount:number;currency:string;created_at:number}[]>([]);
 useEffect(()=>{let active=true;request<Plan>('/billing/plan').then(p=>active&&setPlan(p)).catch(e=>active&&setPlanError(e.message));return()=>{active=false;};},[]);
 useEffect(()=>{let active=true;if(state.user)request<typeof purchases>('/billing/purchases').then(p=>active&&setPurchases(p)).catch(e=>active&&setError(e.message));return()=>{active=false;};},[state.user?.id,state.user?.plan]);
 // The return URL never activates access. Only the signed payment webhook does.
 useEffect(()=>{
  if(!state.user||state.user.plan==='lifetime'||new URLSearchParams(location.search).get('checkout')!=='success')return;
  let attempts=0;const timer=setInterval(()=>{void onRefresh();if(++attempts>=12)clearInterval(timer);},2500);
  return()=>clearInterval(timer);
 },[state.user?.id,state.user?.plan]);
 async function run(fn:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const money=(amount:number,currency:string)=>new Intl.NumberFormat('en-US',{style:'currency',currency}).format(amount/(new Set(['jpy','krw','vnd','clp','pyg','rwf','ugx','vuv','xaf','xof','xpf','bif','djf','gnf','kmf','mga']).has(currency.toLowerCase())?1:100));
 return <div className="account-layout">
  <section className="panel account-card"><span className="season-kicker">YOUR CREATIVE SPACE</span><h2>{state.user?'Your account':mode==='register'?'Create your account':'Welcome back'}</h2><p>{state.user?'Your designs are saved to your personal project library.':'Sign in to save your models and pick up where you left off.'}</p>
   {error&&<p className="error" role="alert">{error}</p>}{message&&<p className="account-success" role="status">{message}</p>}
   {!state.user?<>
    <div className="auth-tabs" role="group" aria-label="Account access"><button aria-pressed={mode==='login'} onClick={()=>{setMode('login');setError('');}}>Sign in</button><button aria-pressed={mode==='register'} onClick={()=>{setMode('register');setError('');}}>Create account</button></div>
    <form key={mode} onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{await request('/auth/'+(mode==='login'?'login':'register'),'POST',{email:f.get('email'),password:f.get('password'),...(mode==='register'?{display_name:f.get('display_name')}:{})});await onRefresh();});}}>
     {mode==='register'&&<label>Your name<input name="display_name" autoComplete="name" maxLength={80} required disabled={busy}/></label>}
     <label>{mode==='login'?'Email or username':'Email address'}<input name="email" type={mode==='login'?'text':'email'} autoComplete={mode==='login'?'username':'email'} maxLength={254} required disabled={busy}/></label>
     <label>Password<input name="password" type="password" autoComplete={mode==='register'?'new-password':'current-password'} minLength={10} maxLength={128} required disabled={busy}/></label>
     <p className="hint">Use at least 10 characters. Your password is never stored as plain text.</p>
     <button className="primary" disabled={busy}>{busy?'Please wait…':mode==='register'?'Create account':'Sign in'}</button>
    </form>
   </>:<>
    <div className="account-identity"><strong>{state.user.display_name}</strong><span>{state.user.email}</span><span className="badge success">{state.user.plan==='lifetime'?'Lifetime access':'Starter account'}</span></div>
    <form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{await request('/account','PATCH',{display_name:f.get('display_name')});await onRefresh();setMessage('Profile updated.');});}}><label>Display name<input name="display_name" defaultValue={state.user.display_name} maxLength={80} required/></label><button disabled={busy}>Save profile</button></form>
    <details className="password-settings"><summary>Change password</summary><form onSubmit={e=>{e.preventDefault();const form=e.currentTarget;const f=new FormData(form);void run(async()=>{await request('/account/password','POST',{current_password:f.get('current_password'),new_password:f.get('new_password')});form.reset();setMessage('Password updated. Other sessions have been signed out.');});}}><label>Current password<input name="current_password" type="password" autoComplete="current-password" required maxLength={128}/></label><label>New password<input name="new_password" type="password" autoComplete="new-password" required minLength={10} maxLength={128}/></label><button disabled={busy}>Update password</button></form></details>
    <p>{state.project_count} saved {state.project_count===1?'project':'projects'}{state.project_limit!==null?` · ${state.project_limit} included with Starter`:''}</p>
    <button disabled={busy} onClick={()=>void run(async()=>{await request('/auth/logout','POST');onSignOut();await onRefresh();})}>Sign out</button>
   </>}
  </section>
  <section className="panel account-card lifetime-card"><span className="season-kicker">ONE PAYMENT. YOUR CREATIVE LIBRARY.</span><h2>Lifetime access</h2><p>Buy once. No recurring subscription.</p><ul><li>Save your 3D model projects</li><li>Customize your models with available design options</li><li>Download full-color and coloring-page files</li><li>Return to your saved designs from your account</li></ul>
   {plan?.configured&&plan.amount!==undefined&&plan.currency&&<div className="plan-price">{money(plan.amount,plan.currency)}<small>one-time payment</small></div>}
   {state.user?.plan==='lifetime'?<p className="account-success">Your Lifetime access is active. No further payment is required.</p>:<>
    {planError&&<p role="alert">{planError}</p>}
    {!plan?.configured?<p className="note">Purchases are not available yet. Pricing and payment setup are pending.</p>:<>{plan.mode==='test'&&<p className="note">Test checkout — no live payment.</p>}<button className="primary" disabled={busy||!state.user} onClick={()=>void run(async()=>{const result=await request<{url:string}>('/billing/checkout','POST');window.location.assign(result.url);})}>{busy?'Opening checkout…':'Buy Lifetime access'}</button>{!state.user&&<p className="hint">Sign in or create an account before checkout.</p>}</>}
    {new URLSearchParams(location.search).get('checkout')==='success'&&state.user&&<p role="status">Waiting for payment confirmation. Your access activates after the payment provider confirms payment.</p>}
    {new URLSearchParams(location.search).get('checkout')==='canceled'&&<p>Checkout was canceled. Your plan has not changed.</p>}
   </>}
   {purchases.length>0&&<div className="purchase-history"><h3>Purchase history</h3>{purchases.map(p=><div key={p.id}><span>{new Date(p.created_at*1000).toLocaleDateString('en-US')}</span><span>{money(p.amount,p.currency)}</span><strong>{p.status==='paid'?'Paid':p.status==='expired'?'Expired':'Pending'}</strong></div>)}</div>}
  </section>
 </div>;
}
