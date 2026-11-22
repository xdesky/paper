import {useEffect,useState} from 'react';
import {BinarySwitch} from './BinarySwitch';
import type {HouseTemplate} from './TemplateLibrary';

type Props={templates:HouseTemplate[];initialTemplate?:string;onClose:()=>void;onCreate:(preset:string,personal_name:string,paper:string)=>Promise<void>};
export function PersonalizeHouse({templates,initialTemplate,onClose,onCreate}:Props){
 const [preset,setPreset]=useState(initialTemplate||templates[0]?.id||'gb_classic');
 const [name,setName]=useState(''),[paper,setPaper]=useState('A4'),[preview,setPreview]=useState(''),[error,setError]=useState(''),[previewing,setPreviewing]=useState(false),[creating,setCreating]=useState(false);
 const [previewValid,setPreviewValid]=useState(false);
 const template=templates.find(t=>t.id===preset);
 useEffect(()=>{
  const controller=new AbortController();let objectUrl='';setPreview('');setError('');setPreviewing(true);setPreviewValid(false);
  const timer=setTimeout(async()=>{
   try{
    const response=await fetch(`/api/templates/${preset}/personalize-preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({personal_name:name}),signal:controller.signal});
    if(!response.ok){const result=await response.json();throw Error(typeof result.detail==='string'?result.detail:result.detail?.[0]?.msg||'Unable to preview this name.');}
    const blob=await response.blob();if(controller.signal.aborted)return;
    objectUrl=URL.createObjectURL(blob);setPreview(objectUrl);setPreviewValid(true);
   }catch(e){if(!controller.signal.aborted)setError((e as Error).message);}
   finally{if(!controller.signal.aborted)setPreviewing(false);}
  },300);
  return()=>{clearTimeout(timer);controller.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[preset,name]);
 return <div className="modal-backdrop" onClick={()=>{if(!creating)onClose();}}>
  <form className="personalize-tool" role="dialog" aria-modal="true" aria-label="Create a personalized 3D model" onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Escape'&&!creating)onClose();}} onSubmit={async e=>{e.preventDefault();setCreating(true);setError('');try{await onCreate(preset,name.trim(),paper);}catch(e){setError((e as Error).message);}finally{setCreating(false);}}}>
   <div className="personalize-heading"><div><span>MAKE IT YOURS</span><h2>Create your 3D model</h2></div><button type="button" aria-label="Close model creator" disabled={creating} onClick={onClose}>×</button></div>
   <div className="personalize-body"><div className="personalize-preview" style={{background:template?.background}}>
    {template&&<img src={preview||template.preview_url} alt={name?`Nameplate ${name} on ${template.name}`:template.name}/>}
    <p role="status">{previewing?'Updating nameplate…':'Your nameplate appears on the front of the house'}</p>
   </div><div className="personalize-options">
    <label>Choose a template<select autoFocus value={preset} disabled={creating} onChange={e=>setPreset(e.target.value)}>{templates.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
    <label>Name on your house<input value={name} maxLength={24} disabled={creating} onChange={e=>setName(e.target.value)} placeholder="Example: The Smith Family" aria-describedby="personal-name-help"/></label>
    <p className="hint" id="personal-name-help">{name.length}/24 characters · Accented Latin characters are supported. Text fits the nameplate automatically. Leave blank for no nameplate.</p>
    <BinarySwitch label="Paper format" off="US Letter" on="A4" checked={paper==='A4'} disabled={creating} onChange={checked=>setPaper(checked?'A4':'US Letter')}/>
    <div className="note">Your name appears in the model and on the printed house.<br/><span>Includes the house, overhanging roof, snowy base, tree, gifts, and assembly guide.</span></div>
    {error&&<p role="alert" className="error">{error}</p>}
    <button className="primary" disabled={creating||previewing||!previewValid||!template}>{creating?'Creating your project…':'Create project'}</button>
   </div></div>
  </form>
 </div>;
}
