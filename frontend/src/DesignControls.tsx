import {useEffect,useState} from 'react';
export type Design={roof:string;wall:string;tree:string;gift:string};
export const defaultDesign:Design={roof:'classic',wall:'classic',tree:'classic',gift:'classic'};
export type DesignOptions=Record<keyof Design,{id:string;label:string}[]>;
const labels:Record<keyof Design,string>={roof:'Roof pattern',wall:'Wall pattern',tree:'Tree style',gift:'Gift box style'};
type Choice={id:string;label:string;image:string};
export function ThumbnailPicker({label,value,choices,onChange,disabled,scroll=false}:{label:string;value:string;choices:Choice[];onChange:(value:string)=>void;disabled?:boolean;scroll?:boolean}){
 return <fieldset className="thumbnail-picker"><legend>{label}</legend><div className={'thumbnail-grid'+(scroll?' thumbnail-scroll':'')} role="group" aria-label={label}>{choices.map(o=><button type="button" key={o.id} className={'thumbnail-choice'+(value===o.id?' selected':'')} aria-pressed={value===o.id} aria-label={'Choose '+o.label} title={o.label} disabled={disabled} onClick={()=>{if(o.id!==value)onChange(o.id);}}><img src={o.image} alt="" loading="lazy"/><span>{o.label}</span>{value===o.id&&<b aria-hidden="true">✓</b>}</button>)}</div></fieldset>;
}
export function DesignControls({design,options,onChange,disabled}:{design:Design;options:DesignOptions|null;onChange:(value:Design)=>void;disabled?:boolean}){
 return <div className="design-controls">{options&&(Object.keys(labels) as (keyof Design)[]).map(key=><ThumbnailPicker key={key} label={labels[key]} value={design[key]} disabled={disabled} onChange={value=>onChange({...design,[key]:value})} choices={options[key].map(o=>({...o,image:`/api/design-options/${key}/${o.id}/thumbnail.jpg`}))}/>)}</div>;
}
export function DesignPreview({preset,name,design}:{preset:string;name:string;design:Design}){
 const [src,setSrc]=useState(''),[error,setError]=useState('');
 const value=JSON.stringify(design);
 useEffect(()=>{
  const controller=new AbortController();let url='';setSrc('');setError('');
  const timer=setTimeout(async()=>{try{
   const r=await fetch(`/api/templates/${preset}/personalize-preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({personal_name:name,design:JSON.parse(value)}),signal:controller.signal});
   if(!r.ok)throw Error('Unable to preview this design. Check the name you entered.');
   const blob=await r.blob();if(controller.signal.aborted)return;
   url=URL.createObjectURL(blob);setSrc(url);
  }catch(e){if(!controller.signal.aborted)setError((e as Error).message);}},350);
  return()=>{clearTimeout(timer);controller.abort();if(url)URL.revokeObjectURL(url);};
 },[preset,name,value]);
 return <div className="design-preview"><strong>Design preview</strong>{src?<img src={src} alt="Selected house, patterns, and accessories"/>:<p role="status">{error||'Updating design…'}</p>}<p>Changes update the 3D preview and print files automatically.</p></div>;
}
