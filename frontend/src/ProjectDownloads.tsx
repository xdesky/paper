import {useEffect,useState} from 'react';
import {BinarySwitch} from './BinarySwitch';
import type {Project} from './types';
type File={name:string;url:string};
export function ProjectDownloads({project,onClose}:{project:Project;onClose:()=>void}){
 const [files,setFiles]=useState<File[]>([]),[error,setError]=useState(''),[loading,setLoading]=useState(true),[coloring,setColoring]=useState(false);
 useEffect(()=>{const controller=new AbortController();fetch(`/api/projects/${project.id}/artifacts`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('Unable to load files. Please reopen the project and try again.');return r.json();}).then(setFiles).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[project.id,project.revision]);
 const pdf=`printable_${project.paper==='A4'?'a4':'us_letter'}${coloring?'_coloring':''}.pdf`;
 const hasColoring=files.some(f=>f.name.endsWith('_coloring.pdf'));
 const url=(name:string)=>files.find(f=>f.name===name)?.url+'?download=true';
 return <div className="project-downloads" role="region" aria-label={`Downloads for ${project.name}`}>
  <div className="project-download-heading"><strong>Download files</strong><button onClick={onClose} aria-label="Close downloads">×</button></div>
  {loading?<p role="status">Loading files…</p>:error?<p role="alert">{error}</p>:<>
   {hasColoring&&<BinarySwitch label="Print style" off="Full color" on="Coloring pages" checked={coloring} onChange={setColoring}/>}
   <div className="project-card-actions">
    {files.some(f=>f.name===pdf)&&<a className="button primary" href={url(pdf)}>Download PDF</a>}
    {files.some(f=>f.name==='project.zip')&&<a className="button" href={url('project.zip')}>Download all (ZIP)</a>}
    <a className="button" href={`/api/projects/${project.id}/print?style=${coloring?'coloring':'color'}`} target="_blank" rel="noopener noreferrer">Print</a>
   </div>
   <p className="hint">{project.paper} · Print at actual size (100%).</p>
   <details><summary>More files</summary><div className="project-file-list">{files.filter(f=>!f.name.startsWith(coloring?'svg_pages/':'coloring_svg_pages/')&&(!/^printable_.*\.pdf$/.test(f.name)||f.name===pdf)).map(f=><a key={f.name} href={f.url+'?download=true'}>{f.name}</a>)}</div></details>
  </>}
 </div>;
}
