import { StrictMode, useEffect, useMemo, useState } from 'react';
import {createRoot} from 'react-dom/client';
import {DesignControls,DesignPreview,ThumbnailPicker,defaultDesign,type Design,type DesignOptions} from './DesignControls';
import {BinarySwitch} from './BinarySwitch';
import {Account,type AccountState} from './Account';
import {ProjectLibrary} from './ProjectLibrary';
import {ModelViewer} from './ModelViewer';
import {PersonalizeHouse} from './PersonalizeHouse';
import {PrintPreview} from './PrintPreview';
import {TemplateLibrary, type HouseTemplate} from './TemplateLibrary';
import type {Project,Spec,QA,Job} from './types';
import './style.css';
import {LandingPage} from './LandingPage';
const basePresets:Record<string,string>={cube_100:'Cube 100 mm',cube_200:'Cube 200 mm',cube_300:'Cube 300 mm',house_frame:'House frame 120 × 90 × 180 mm'};
const statuses:Record<string,string>={DRAFT:'Draft',STALE:'Update needed',GENERATING:'Building',READY:'Ready to print',FAILED:'Build failed'};
const stages:Record<string,string>={'Queued':'Queued','Validate Input':'Checking settings','Build Geometry':'Building geometry','Choose Hinges / Unfold / Add Tabs':'Preparing folds and glue tabs','Pack Pages':'Arranging pages','Export':'Exporting artwork','QA':'Checking print quality','Verify exported files':'Verifying exported files','Complete':'Complete','Failed':'Failed','Interrupted':'Interrupted'};
async function api<T>(url:string,method='GET',body?:unknown):Promise<T>{const r=await fetch('/api'+url,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw Error(typeof e.detail==='string'?e.detail:Array.isArray(e.detail)?e.detail.map((d:{msg:string})=>d.msg).join(' · '):JSON.stringify(e.detail));}return r.status===204?undefined as T:r.json();}
function App(){
 const [account,setAccount]=useState<AccountState>({user:null,project_limit:3,project_count:0}),[accountLoaded,setAccountLoaded]=useState(false);
 async function refreshAccount(){const result=await api<AccountState>('/account');setAccount(result);setAccountLoaded(true);}
 const [autoTarget,setAutoTarget]=useState('');
 const [printStyle,setPrintStyle]=useState<'color'|'coloring'>('color');
 const [designOptions,setDesignOptions]=useState<DesignOptions|null>(null);
 const [templates,setTemplates]=useState<HouseTemplate[]>([]);
 const presets:Record<string,string>={...basePresets,...Object.fromEntries(templates.map(t=>[t.id,t.name]))};
 const [projects,setProjects]=useState<Project[]>([]),[selected,setSelected]=useState(''),[error,setError]=useState('');
 const [spec,setSpec]=useState<Spec|null>(null),[qa,setQA]=useState<QA|null>(null),[pages,setPages]=useState<{number:number;url:string}[]>([]),[files,setFiles]=useState<{name:string;url:string}[]>([]);
 const [job,setJob]=useState<Job|null>(null),[seam,setSeam]=useState(''),[zoom,setZoom]=useState(100),[wire,setWire]=useState(false),[tab,setTabState]=useState(readTab);
 function readTab(){if(location.pathname!=='/'&&location.pathname!=='/studio')return 'templates';const route=location.hash.slice(1).split('/')[0];return ['account','templates','workspace','projects'].includes(route)?route:'projects';}
 function setTab(value:string){setTabState(value);history.pushState(null,'','/studio#'+value);window.dispatchEvent(new PopStateEvent('popstate'));}
 useEffect(()=>{const changed=()=>setTabState(readTab());window.addEventListener('hashchange',changed);window.addEventListener('popstate',changed);return()=>{window.removeEventListener('hashchange',changed);window.removeEventListener('popstate',changed);};},[]);
 const [draft,setDraft]=useState<{id:string;name:string;preset:string;paper:string;personal_name:string;design:Design}|null>(null),[busy,setBusy]=useState(false),[newOpen,setNewOpen]=useState(false);
 const [layers,setLayers]=useState<Record<string,boolean>>({CUT:true,FOLD:true,TABS:true,CODES:true});
 const current=projects.find(p=>p.id===selected);
 const [personalize,setPersonalize]=useState<string|null>(null);
 const name=draft?.id===selected?draft.name:current?.name||'';
 const preset=draft?.id===selected?draft.preset:current?.preset||'cube_100';
 const paper=draft?.id===selected?draft.paper:current?.paper||'US Letter';
 const personalName=draft?.id===selected?draft.personal_name:current?.personal_name||'';
 const design=draft?.id===selected?draft.design:current?.design||defaultDesign;
 const setDesign=(value:Design)=>{setAutoTarget(selected);setDraft({id:selected,name,preset,paper,personal_name:personalName,design:value});};
 const setPersonalName=(value:string)=>{setAutoTarget(selected);setDraft({id:selected,name,preset,paper,personal_name:value,design});};
 const setPaper=(value:string)=>{setAutoTarget(selected);setDraft({id:selected,name,preset,paper:value,personal_name:personalName,design});};
 const setName=(value:string)=>setDraft({id:selected,name:value,preset,paper,personal_name:personalName,design});
 const setPreset=(value:string)=>{setAutoTarget(selected);setDraft({id:selected,name,preset:value,paper,personal_name:personalName,design});};
 async function refresh(preferred?:string){if(!account.user){setProjects([]);setSelected('');return;}const all=await api<Project[]>('/projects');setProjects(all);setAccount(a=>({...a,project_count:all.length}));setSelected(s=>all.some(p=>p.id===(preferred||s))?(preferred||s):all[0]?.id||'');}
 useEffect(()=>{api<DesignOptions>('/design-options').then(setDesignOptions).catch(e=>setError(e.message));refreshAccount().catch(e=>{setError(e.message);setAccountLoaded(true);});api<HouseTemplate[]>('/templates').then(setTemplates).catch(e=>setError(e.message));},[]);
 useEffect(()=>{if(accountLoaded)refresh().catch(e=>setError(e.message));},[account.user?.id,accountLoaded]);
 useEffect(()=>{if(!projects.some(p=>p.status==='GENERATING'))return;const timer=setInterval(()=>refresh().catch(e=>setError(e.message)),1000);return()=>clearInterval(timer);},[projects]);
 useEffect(()=>{setPrintStyle('color');setSpec(null);setQA(null);setPages([]);setFiles([]);setSeam('');setJob(null);setDraft(null); if(!current)return;
 let cancelled=false;
 if(current.status==='READY')Promise.all([api<Spec>(`/projects/${selected}/geometry`),api<QA>(`/projects/${selected}/validation`),api<typeof pages>(`/projects/${selected}/pages`),api<typeof files>(`/projects/${selected}/artifacts`)]).then(([s,q,p,f])=>{if(!cancelled){setSpec(s);setQA(q);setPages(p);setFiles(f);}}).catch(e=>!cancelled&&setError(e.message));
 const poll=()=>api<{latest_job:Job|null}>(`/projects/${selected}`).then(async p=>{if(p.latest_job){const j=await api<Job>(`/jobs/${p.latest_job.id}`);if(!cancelled)setJob(j);}}).catch(e=>!cancelled&&setError(e.message));poll();const timer=current.status==='GENERATING'?setInterval(poll,600):undefined;
 return()=>{cancelled=true;clearInterval(timer);};
 },[selected,current?.status,current?.revision]);
 async function action(fn:()=>Promise<unknown>){setAutoTarget('');setBusy(true);setError('');try{await fn();setDraft(null);await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const generating=current?.status==='GENERATING';
 const houseTemplate=templates.find(t=>t.id===preset);
 const blockyTemplate=houseTemplate?.category==='blocky-characters';
 const dirty=!!current&&(name!==current.name||preset!==current.preset||paper!==current.paper||personalName!==(current.personal_name||'')||JSON.stringify(design)!==JSON.stringify(current.design||defaultDesign));
 useEffect(()=>{
  if(!autoTarget||autoTarget!==selected||draft?.id!==selected||busy||generating||!name.trim())return;
  const timer=setTimeout(()=>{void action(async()=>{
   await api(`/projects/${selected}`,'PATCH',{name,preset,paper,personal_name:personalName,design});
   await api(`/projects/${selected}/generate`,'POST');
  });},650);
  return()=>clearTimeout(timer);
 },[draft,autoTarget,selected,busy,generating]);
 const hasColoring=files.some(f=>f.name.endsWith('_coloring.pdf'));
 const visiblePages=useMemo(()=>printStyle==='coloring'?pages.map(p=>({...p,url:p.url.replace('/svg_pages/','/coloring_svg_pages/')})):pages,[pages,printStyle]);
 const stylePicker=<BinarySwitch label="Print style" off="Full color" on="Coloring pages" checked={printStyle==='coloring'} disabled={!hasColoring} onChange={checked=>setPrintStyle(checked?'coloring':'color')}/>;
 const download=(name:string)=>`/api/projects/${selected}/artifacts/${name}?download=true`;

 return <div className="app-shell">
  <aside className="sidebar"><a className="brand" href="/#workspace" onClick={e=>{e.preventDefault();setTab('workspace');}}><span className="brand-icon">◇</span><span>Print Play Magic<small>PAPERCRAFT STUDIO</small></span></a><div className="side-caption">CREATE & MAKE</div>
   <button className={tab==='templates'?'nav active':'nav'} onClick={()=>setTab('templates')}>⌂ <span>Template library</span></button><button className={tab==='workspace'?'nav active':'nav'} onClick={()=>setTab('workspace')}>▧ <span>Workspace</span></button><button className={tab==='projects'?'nav active':'nav'} onClick={()=>setTab('projects')}>▤ <span>My projects</span></button><button className={tab==='account'?'nav active':'nav'} onClick={()=>setTab('account')}>○ <span>Account</span></button>
   <div className="side-caption projects-title">PROJECTS <button aria-label="Add project" onClick={()=>account.user?setNewOpen(true):setTab('account')}>＋</button></div>{projects.length>0&&<div className="project-list">{projects.map(p=><button key={p.id} className={selected===p.id?'project selected':'project'} onClick={()=>{setSelected(p.id);setTab('workspace');}}><span>◇</span><span>{p.name}<small>{statuses[p.status]}</small></span></button>)}</div>}
   <button className="new-project" onClick={()=>account.user?setNewOpen(true):setTab('account')}>＋ New project</button><div className="side-bottom"><span className="dot"/> Print-ready designs<small>Made to print. Built to fit.</small></div>
  </aside>
  <main><header><div><div className="breadcrumb">Studio / {tab==='templates'?'Template library':tab==='workspace'?'Workspace':tab==='account'?'Account':'My projects'}</div><h1>{tab==='templates'?'Template library':tab==='account'?'Account & membership':tab==='projects'?'My projects':current?.name||'Start with a sheet of paper.'}</h1><p className="subtitle">Turn your ideas into paper models.</p></div><div className="header-actions" hidden={tab==='templates'||tab==='account'||tab==='projects'||!account.user}>{current&&<span className={'badge '+(current.status==='READY'?'success':'')}>{statuses[current.status]}</span>}<button className="primary" disabled={!current||busy||generating||!name.trim()} onClick={()=>action(async()=>{if(dirty)await api(`/projects/${selected}`,'PATCH',{name,preset,paper,personal_name:personalName,design});await api(`/projects/${selected}/generate`,'POST');})}>{generating?'Building…':'Rebuild'}</button>{spec&&!dirty&&<>{houseTemplate&&stylePicker}<a className="button" href={`/api/projects/${selected}/print?style=${printStyle}`} target="_blank" rel="noopener noreferrer" title={`Print on ${paper} at 100% scale`}>⎙ Print</a><a className="button" href={download('project.zip')}>Download all</a></>}</div></header>
  {error&&<div role="alert" className="error">{error}<button aria-label="Dismiss error" onClick={()=>setError('')}>×</button></div>}
  {autoTarget===selected&&draft&&<div className="progress" role="status">Applying your design to both previews…</div>}
  {generating&&<div className="progress" role="status"><span className="spinner"/>{stages[job?.stage||'Queued']||job?.stage}<span>Building print files · version {current?.revision}</span></div>}
  {job?.status==='FAILED'&&<div role="alert" className="error"><strong>Unable to create print files.</strong><pre>{job.error}</pre><span>Review the error and select Rebuild to try again.</span></div>}
  {tab==='projects'&&<section className="panel home-create"><div><span className="season-kicker">MAKE SOMETHING MAGICAL</span><h2>Your next 3D model starts here.</h2><p>Choose a template, make it your own, and bring it to life in 3D.</p></div><div className="home-create-actions"><button className="primary" disabled={!templates.length} onClick={()=>account.user?setPersonalize(templates[0]?.id||'gb_classic'):setTab('account')}>Let’s create</button><button onClick={()=>setTab('templates')}>Browse templates</button></div></section>}
  {tab==='account'&&<Account state={account} onRefresh={refreshAccount} onSignOut={()=>{setProjects([]);setSelected('');setSpec(null);setPages([]);setFiles([]);setQA(null);setPersonalize(null);setNewOpen(false);}}/>}
  {['workspace','projects'].includes(tab)&&accountLoaded&&!account.user&&<section className="panel empty-workspace"><h2>Your projects, saved in one place</h2><p>Sign in to create, save, and return to your 3D models.</p><button className="primary" onClick={()=>setTab('account')}>Sign in or create an account</button></section>}
  {tab==='projects'&&account.user&&<ProjectLibrary projects={projects} templates={templates} busy={busy} onOpen={id=>{setSelected(id);setTab('workspace');}} onCreate={()=>setTab('templates')} onDuplicate={id=>void action(async()=>{const p=await api<Project>(`/projects/${id}/duplicate`,'POST');await refresh(p.id);})} onDelete={id=>{if(confirm('Delete this project from your library?'))void action(()=>api(`/projects/${id}`,'DELETE'));}}/>}
  {tab==='templates'&&<TemplateLibrary onPersonalize={t=>account.user?setPersonalize(t.id):setTab('account')} templates={templates} busy={busy} onUse={t=>{if(!account.user){setTab('account');return;}void action(async()=>{const p=await api<Project>('/projects','POST',{name:t.name,preset:t.id});await api(`/projects/${p.id}/generate`,'POST');await refresh(p.id);setTab('workspace');});}}/>}
  {tab==='workspace'&&account.user&&!current&&<section className="panel empty-workspace"><h2>No projects yet</h2><p>Choose a template to start your first 3D model.</p><button className="primary" onClick={()=>setTab('templates')}>Browse templates →</button></section>}
  {tab==='workspace'&&account.user&&current&&<><div className="workspace"><section className="panel settings"><div className="panel-heading"><h2>Design settings</h2><span>01</span></div><div className="settings-body"><label>Project name<input value={name} onChange={e=>setName(e.target.value)} disabled={!current||generating}/></label><ThumbnailPicker label="Model style" value={preset} disabled={generating||busy} scroll onChange={setPreset} choices={templates.map(t=>({id:t.id,label:t.name,image:t.preview_url}))}/><div className="dimension-card"><span>{houseTemplate&&!blockyTemplate?'HOUSE DIMENSIONS':'MODEL DIMENSIONS'}</span><strong>{houseTemplate?houseTemplate.dimensions_mm.join(' × '):preset==='house_frame'?'120 × 90 × 180':Array(3).fill(preset.split('_')[1]).join(' × ')} <small>mm</small></strong><p>{blockyTemplate?'Original character built from separate cuboid parts.':houseTemplate?`${houseTemplate.face_count} faces · roof, base, tree, and two gifts${houseTemplate.chimney?' + 3D chimney':''}`:preset==='house_frame'?'Four walls · open top and bottom':'Six square faces · closed cube'}</p></div>{houseTemplate&&!blockyTemplate&&<div className="name-settings"><label>Name on your house<input value={personalName} maxLength={24} disabled={generating||busy} onChange={e=>setPersonalName(e.target.value)} placeholder="The Smith Family"/></label><p className="hint">{personalName.length}/24 characters · Front nameplate. Previews update automatically.</p></div>}{houseTemplate&&!blockyTemplate&&<><DesignControls design={design} options={designOptions} onChange={setDesign} disabled={generating||busy}/><DesignPreview preset={preset} name={personalName} design={design}/></>}<button className="save" disabled={!current||busy||generating||!dirty||!name.trim()} onClick={()=>action(()=>api(`/projects/${selected}`,'PATCH',{name,preset,paper,personal_name:personalName,design}))}>Save changes</button><p className="hint">Your selections save automatically and update both previews.</p><hr/><h3>Paper & printing</h3><dl><div><dt>Paper size</dt><dd><BinarySwitch label="Paper format" off="US Letter" on="A4" checked={paper==='A4'} disabled={!current||generating||busy} onChange={checked=>setPaper(checked?'A4':'US Letter')}/></dd></div><div><dt>Dimensions</dt><dd>{paper==='A4'?'210 × 297':'215.9 × 279.4'} mm</dd></div><div><dt>Print scale</dt><dd>100% · 1:1</dd></div><div><dt>Glue tabs</dt><dd>{blockyTemplate?'4 mm':houseTemplate?'5 mm':'7 mm'}</dd></div></dl><div className="note">↳ Fold-first<br/><span>Connected pieces make assembly easier. Print at actual size.</span></div><p className="hint">A4 or US Letter · Print at 100%.<br/>Use the included assembly guide.</p><div className="project-tools"><button disabled={!current||busy} onClick={()=>action(async()=>{const p=await api<Project>(`/projects/${selected}/duplicate`,'POST');await refresh(p.id);})}>Duplicate</button><button disabled={!current||busy||generating} onClick={()=>{if(confirm('Delete this project from your list?'))action(()=>api(`/projects/${selected}`,'DELETE'));}}>Delete project</button></div></div></section>
   <section className="panel preview"><div className="panel-heading"><h2>3D preview</h2><label className="inline"><input type="checkbox" checked={wire} onChange={e=>setWire(e.target.checked)}/> Wireframe</label></div>{spec?<><ModelViewer spec={spec} seam={seam} wire={wire}/><div className="viewer-help">Drag to rotate · Scroll to zoom · Right-drag to pan</div><div className="model-footer"><span>◇ {spec.geometry.panels.length} panels</span><span>True-to-size geometry · mm</span></div></>:<div className="empty"><div className="paper-cube">◇</div><h3>{generating?'Updating your 3D preview…':'Your design, brought to life'}</h3><p>{generating?'Print pages update with your model.':'Choose a thumbnail to build your model and print pages.'}</p></div>}</section>
   <PrintPreview key={`${selected}:${current?.revision}`} pages={visiblePages} spec={spec} seam={seam} onSelectSeam={setSeam} zoom={zoom} setZoom={setZoom} layers={layers} setLayers={setLayers}/>

  </div>{qa&&<div className="metrics">{[[qa.summary.sheets,'PRINT PAGES'],[qa.summary.cut_pieces,'CUT PIECES'],[qa.summary.fold_hinges+(qa.summary.accessory_fold_hinges||0),'FOLDS'],[qa.summary.glue_seams+(qa.summary.accessory_glue_seams||0),'GLUE JOINTS'],[qa.summary.flat_continuous_joins,'FLAT JOINS']].map(([value,label])=><div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>}</>}

  <footer>{spec&&<code title={spec.geometry_sha256}>SHA-256 {spec.geometry_sha256.slice(0,12)}…</code>}</footer>
 </main>
 {personalize!==null&&<PersonalizeHouse templates={templates} initialTemplate={personalize} onClose={()=>setPersonalize(null)} onCreate={async(preset,personal_name,paper)=>{
  const template=templates.find(t=>t.id===preset);
  const p=await api<Project>('/projects','POST',{name:personal_name?`Model for ${personal_name}`:template?.name||'3D paper model',preset,paper,personal_name});
  await api(`/projects/${p.id}/generate`,'POST');await refresh(p.id);setTab('workspace');setPersonalize(null);
 }}/>}
 {newOpen&&<div className="modal-backdrop"><form className="modal" onSubmit={e=>{e.preventDefault();const form=new FormData(e.currentTarget);action(async()=>{const p=await api<Project>('/projects','POST',{name:form.get('name'),preset:form.get('preset')});await refresh(p.id);setTab('workspace');setNewOpen(false);});}}><h2>Create a project</h2><label>Project name<input name="name" required maxLength={100} autoFocus placeholder="My 3D model"/></label><label>Template<select name="preset" defaultValue="gb_classic">{Object.entries(presets).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><div className="modal-actions"><button type="button" onClick={()=>setNewOpen(false)}>Cancel</button><button className="primary" disabled={busy}>Create project</button></div></form></div>}
 </div>;
}
createRoot(document.getElementById('root')!).render(<StrictMode>{location.pathname==='/'?<LandingPage/>:<App/>}</StrictMode>);
