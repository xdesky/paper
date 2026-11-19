import {useEffect,useRef,useState} from 'react';
import type {Spec} from './types';

type PrintPage={number:number;url:string};
type Props={pages:PrintPage[];spec:Spec|null;seam:string;onSelectSeam:(id:string)=>void;zoom:number;setZoom:(value:number)=>void;layers:Record<string,boolean>;setLayers:(value:Record<string,boolean>)=>void};

function Sheet({page,spec,seam,onSelectSeam,layers}:{page:PrintPage}&Pick<Props,'spec'|'seam'|'onSelectSeam'|'layers'>){
 const host=useRef<HTMLDivElement>(null);
 const [svg,setSvg]=useState(''),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();setSvg('');setError('');
  fetch(page.url,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error(`Unable to load page ${page.number}.`);return r.text();}).then(value=>{if(!controller.signal.aborted)setSvg(value);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);});
  return()=>controller.abort();
 },[page.url,page.number,attempt]);
 useEffect(()=>{
  if(!host.current)return;
  const codes=new Set(spec?.geometry.seams.map(s=>s.id));
  host.current.querySelectorAll('polygon,line,text').forEach(node=>{
   const stroke=node.getAttribute('data-original-stroke')||node.getAttribute('stroke'),fill=node.getAttribute('data-original-fill')||node.getAttribute('fill');let visible=true;
   if(stroke==='#16252e')visible=layers.CUT;
   if(stroke==='#9a3971'||stroke==='#216c94'||stroke==='#b27d19')visible=layers.FOLD;
   if(fill==='#fff1d3')visible=layers.TABS;
   const isCode=codes.has(node.textContent||'');
   if(spec?.scene_accessories&&/^[ABRC][1-7]$/.test(node.textContent||''))visible=layers.CODES;
   if(isCode){visible=layers.CODES;node.classList.add('seam-code');node.setAttribute('tabindex',visible?'0':'-1');node.setAttribute('role','button');node.setAttribute('aria-label','Joint '+node.textContent);node.classList.toggle('chosen',node.textContent===seam);}
   (node as SVGElement).style.opacity=visible?'1':'0';(node as SVGElement).style.pointerEvents=visible?'auto':'none';
  });
 },[svg,layers,seam,spec]);
 const pick=(target:EventTarget|null)=>{const code=(target as Element)?.textContent||'';if(layers.CODES&&spec?.geometry.seams.some(s=>s.id===code))onSelectSeam(code);};
 const dimensions=spec?.paper?.page_mm||[215.9,279.4];
 return <div className="svg-sheet" style={{aspectRatio:`${dimensions[0]} / ${dimensions[1]}`}}>
  {svg?<div ref={host} onClick={e=>pick(e.target)} onKeyDown={e=>{if((e.key==='Enter'||e.key===' ')&&(e.target as Element).classList.contains('seam-code')){e.preventDefault();pick(e.target);}}} dangerouslySetInnerHTML={{__html:svg}}/>:<div className="sheet-placeholder" role="status">{error?<><p>{error}</p><button onClick={()=>setAttempt(a=>a+1)}>Retry page {page.number}</button></>:<p>Loading page {page.number}…</p>}</div>}
 </div>;
}

export function PrintPreview({pages,spec,seam,onSelectSeam,zoom,setZoom,layers,setLayers}:Props){
 const surface=useRef<HTMLDivElement>(null),cards=useRef<(HTMLElement|null)[]>([]);
 const [active,setActive]=useState(0);
 const updatePosition=()=>{
  const element=surface.current;if(!element||!pages.length)return;
  const bottom=element.scrollHeight-element.scrollTop-element.clientHeight<2;
  let next=0;
  if(bottom&&element.scrollTop>0)next=pages.length-1;
  else cards.current.forEach((card,i)=>{if(card&&card.offsetTop<=element.scrollTop+25)next=i;});
  setActive(next);
 };
 const scrollToPage=(index:number,behavior:ScrollBehavior='smooth')=>{
  const element=surface.current,card=cards.current[index];if(!element||!card)return;
  element.scrollTo({top:Math.max(0,card.offsetTop-18),behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':behavior});
 };
 useEffect(()=>{setActive(0);surface.current?.scrollTo({top:0,left:0});cards.current.length=pages.length;},[pages]);
 useEffect(()=>{scrollToPage(active,'auto');},[zoom]);
 return <section className="panel printable">
  <div className="panel-heading"><h2>Print preview</h2><span className="mini-badge">VECTOR SVG</span></div>
  <div className="page-tools">
   <div className="page-navigation" role="group" aria-label="Print page navigation">
    <button aria-label="Previous page" title="Scroll to the previous page" disabled={!pages.length||active===0} onClick={()=>scrollToPage(active-1)}>‹</button>
    <span className="page-position" aria-label="Current page" aria-live="polite">{pages.length?`${active+1} / ${pages.length}`:'0 / 0'}</span>
    <button aria-label="Next page" title="Scroll to the next page" disabled={!pages.length||active===pages.length-1} onClick={()=>scrollToPage(active+1)}>›</button>
   </div>
   <label>Zoom <select aria-label="Page zoom" value={zoom} onChange={e=>setZoom(Number(e.target.value))}>{[75,100,125,150,200].map(v=><option key={v}>{v}</option>)}</select>%</label>
  </div>
  <div className="page-surface" ref={surface} role="region" aria-label="Print pages" tabIndex={0} onScroll={updatePosition}>
   {pages.length?<div className="page-stack" style={{width:`${zoom}%`}}>{pages.map((p,i)=><article className="preview-page" aria-label={`Print page ${p.number}`} key={p.url} ref={node=>{cards.current[i]=node;}}>
    <div className="sheet-caption">Page {p.number} / {pages.length}</div>
    <Sheet page={p} spec={spec} seam={seam} onSelectSeam={onSelectSeam} layers={layers}/>
   </article>)}</div>:<div className="empty"><span className="sheet-icon">▤</span><p>Your print pages will appear here.</p></div>}
  </div>
  <div className="layers">{Object.entries({CUT:'Cut lines',FOLD:'Fold lines',TABS:'Glue tabs',CODES:'Joint labels'}).map(([key,label])=><label key={key}><input type="checkbox" checked={layers[key]} onChange={e=>setLayers({...layers,[key]:e.target.checked})}/>{label}</label>)}</div>
  <div className="page-footer">Scroll to view every page. Select a joint label to highlight it in 3D.{seam&&<strong> Selected: {seam}</strong>}</div>
 </section>;
}
