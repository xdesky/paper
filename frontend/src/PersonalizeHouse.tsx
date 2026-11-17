import {useEffect,useState} from 'react';
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
    if(!response.ok){const result=await response.json();throw Error(typeof result.detail==='string'?result.detail:result.detail?.[0]?.msg||'Không thể xem thử tên này.');}
    const blob=await response.blob();if(controller.signal.aborted)return;
    objectUrl=URL.createObjectURL(blob);setPreview(objectUrl);setPreviewValid(true);
   }catch(e){if(!controller.signal.aborted)setError((e as Error).message);}
   finally{if(!controller.signal.aborted)setPreviewing(false);}
  },300);
  return()=>{clearTimeout(timer);controller.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[preset,name]);
 return <div className="modal-backdrop" onClick={()=>{if(!creating)onClose();}}>
  <form className="personalize-tool" role="dialog" aria-modal="true" aria-label="Tạo nhà bánh gừng cá nhân hoá" onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Escape'&&!creating)onClose();}} onSubmit={async e=>{e.preventDefault();setCreating(true);setError('');try{await onCreate(preset,name.trim(),paper);}catch(e){setError((e as Error).message);}finally{setCreating(false);}}}>
   <div className="personalize-heading"><div><span>NGÔI NHÀ CỦA RIÊNG BẠN</span><h2>Tạo nhà bánh gừng</h2></div><button type="button" aria-label="Đóng công cụ cá nhân hoá" disabled={creating} onClick={onClose}>×</button></div>
   <div className="personalize-body"><div className="personalize-preview" style={{background:template?.background}}>
    {template&&<img src={preview||template.preview_url} alt={name?`Bảng tên ${name} trên ${template.name}`:template.name}/>}
    <p role="status">{previewing?'Đang cập nhật bảng tên…':'Bảng tên nằm trên mặt trước ngôi nhà'}</p>
   </div><div className="personalize-options">
    <label>Chọn mẫu nhà<select autoFocus value={preset} disabled={creating} onChange={e=>setPreset(e.target.value)}>{templates.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
    <label>Tên trên ngôi nhà<input value={name} maxLength={24} disabled={creating} onChange={e=>setName(e.target.value)} placeholder="Ví dụ: Gia đình An" aria-describedby="personal-name-help"/></label>
    <p className="hint" id="personal-name-help">{name.length}/24 ký tự · Hỗ trợ tiếng Việt có dấu. Chữ tự xuống dòng và vừa bảng tên. Để trống nếu không cần tên.</p>
    <label>Khổ giấy bản in<select value={paper} disabled={creating} onChange={e=>setPaper(e.target.value)}><option>A4</option><option>US Letter</option></select></label>
    <div className="note">Tên được in trên nhà và hiển thị trong 3D.<br/><span>Bộ file gồm nhà, mái đua, đế tuyết, cây thông, hộp quà và hướng dẫn lắp.</span></div>
    {error&&<p role="alert" className="error">{error}</p>}
    <button className="primary" disabled={creating||previewing||!previewValid||!template}>{creating?'Đang tạo dự án…':'Tạo nhà & bản in'}</button>
   </div></div>
  </form>
 </div>;
}
