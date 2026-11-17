import {useEffect,useState} from 'react';
export type Design={roof:string;wall:string;tree:string;gift:string};
export const defaultDesign:Design={roof:'classic',wall:'classic',tree:'classic',gift:'classic'};
export type DesignOptions=Record<keyof Design,{id:string;label:string}[]>;
const labels:Record<keyof Design,string>={roof:'Hoạ tiết mái',wall:'Hoạ tiết thân nhà',tree:'Mẫu cây thông',gift:'Mẫu hộp quà'};
export function DesignControls({design,options,onChange,disabled}:{design:Design;options:DesignOptions|null;onChange:(value:Design)=>void;disabled?:boolean}){
 return <div className="design-controls">{options&&(Object.keys(labels) as (keyof Design)[]).map(key=><label key={key}>{labels[key]}<select value={design[key]} disabled={disabled} onChange={e=>onChange({...design,[key]:e.target.value})}>{options[key].map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></label>)}</div>;
}
export function DesignPreview({preset,name,design}:{preset:string;name:string;design:Design}){
 const [src,setSrc]=useState(''),[error,setError]=useState('');
 const value=JSON.stringify(design);
 useEffect(()=>{
  const controller=new AbortController();let url='';setSrc('');setError('');
  const timer=setTimeout(async()=>{try{
   const r=await fetch(`/api/templates/${preset}/personalize-preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({personal_name:name,design:JSON.parse(value)}),signal:controller.signal});
   if(!r.ok)throw Error('Không thể xem thử phối mẫu. Kiểm tra tên đã nhập.');
   const blob=await r.blob();if(controller.signal.aborted)return;
   url=URL.createObjectURL(blob);setSrc(url);
  }catch(e){if(!controller.signal.aborted)setError((e as Error).message);}},350);
  return()=>{clearTimeout(timer);controller.abort();if(url)URL.revokeObjectURL(url);};
 },[preset,name,value]);
 return <div className="design-preview"><strong>Xem thử phối mẫu</strong>{src?<img src={src} alt="Thân nhà, hoạ tiết và phụ kiện đang chọn"/>:<p role="status">{error||'Đang phối mẫu…'}</p>}<p>Generate để cập nhật mô hình 3D và bản in.</p></div>;
}
