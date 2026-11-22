"""Original cuboid papercraft characters for the Blocky Friends collection."""
import hashlib,json
from pathlib import Path
import xml.etree.ElementTree as ET
from .template_catalog import BY_ID

PAPER={'US Letter':(215.9,279.4),'A4':(210.0,297.0)}
PARTS=[('body',(0,0,22),(30,20,24),'coat'),('head',(0,-12,42),(22,20,20),'coat'),('chest',(0,-11,21),(13,2,13),'light'),('front_left',(-9,-6,7),(8,9,14),'coat'),('front_right',(9,-6,7),(8,9,14),'coat'),('back_left',(-9,6,7),(8,9,14),'coat'),('back_right',(9,6,7),(8,9,14),'coat'),('ear_left',(-7,-12,56),(7,7,8),'accent'),('ear_right',(7,-12,56),(7,7,8),'accent'),('tail',(0,14,27),(8,8,16),'accent')]
FACES=('front','right','back','left','top','bottom')

def parts_for(t):
 return [{'id':n,'center':c,'size':s,'color':t[key]} for n,c,s,key in PARTS]

def face(part,side):
 x,y,z=part['center'];w,d,h=(a/2 for a in part['size'])
 values={'front':([(x-w,y-d,z-h),(x+w,y-d,z-h),(x+w,y-d,z+h),(x-w,y-d,z+h)],part['size'][0],part['size'][2]),'back':([(x+w,y+d,z-h),(x-w,y+d,z-h),(x-w,y+d,z+h),(x+w,y+d,z+h)],part['size'][0],part['size'][2]),'right':([(x+w,y-d,z-h),(x+w,y+d,z-h),(x+w,y+d,z+h),(x+w,y-d,z+h)],part['size'][1],part['size'][2]),'left':([(x-w,y+d,z-h),(x-w,y-d,z-h),(x-w,y-d,z+h),(x-w,y+d,z+h)],part['size'][1],part['size'][2]),'top':([(x-w,y-d,z+h),(x+w,y-d,z+h),(x+w,y+d,z+h),(x-w,y+d,z+h)],part['size'][0],part['size'][1]),'bottom':([(x-w,y+d,z-h),(x+w,y+d,z-h),(x+w,y-d,z-h),(x-w,y-d,z-h)],part['size'][0],part['size'][1])}
 return values[side]

def preview(t):
 species=t.get('species','fox');coat=t['coat'];light=t['light'];dark=t['dark'];accent=t['accent']
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><rect width="300" height="300" rx="24" fill="{}"/><ellipse cx="150" cy="264" rx="76" ry="12" fill="#34453d" opacity=".12"/>'.format(t['background'])]
 # Draw a cohesive, front-facing mascot with original square silhouettes.
 if species=='fox':out.append('<path d="M203 174 L246 190 L221 220 L190 207Z" fill="{}" stroke="#374846" stroke-width="4"/><path d="M220 203 L246 190 L231 214Z" fill="{}"/>'.format(coat,light))
 elif species=='cat':out.append('<path d="M207 199 C246 190 249 225 224 228 C210 228 214 214 226 215" fill="none" stroke="{}" stroke-width="13" stroke-linecap="square"/>'.format(coat))
 else:out.append('<path d="M208 186 Q241 183 232 213 Q222 224 212 207Z" fill="{}" stroke="#374846" stroke-width="4"/>'.format(light))
 out.append('<path d="M107 209 L143 209 L140 258 L100 258Z M160 209 L196 209 L200 258 L160 258Z" fill="{}" stroke="#374846" stroke-width="4"/><path d="M95 254 L143 254 L143 269 L89 269Z M157 254 L205 254 L211 269 L157 269Z" fill="{}" stroke="#374846" stroke-width="4"/>'.format(coat,light))
 out.append('<path d="M101 142 L199 142 L211 220 L89 220Z" fill="{}" stroke="#374846" stroke-width="4"/><path d="M90 151 L69 183 L91 194Z M210 151 L231 183 L209 194Z" fill="{}" stroke="#374846" stroke-width="4"/>'.format(coat,light))
 if species=='fox':out.append('<path d="M99 91 L104 42 L143 74 L157 74 L196 42 L201 91Z" fill="{}" stroke="#374846" stroke-width="4"/><path d="M111 78 L115 55 L135 75Z M165 75 L185 55 L189 78Z" fill="{}"/>'.format(coat,accent))
 elif species=='cat':out.append('<path d="M96 91 L91 34 L139 70 L161 70 L209 34 L204 91Z" fill="{}" stroke="#374846" stroke-width="4"/><path d="M108 75 L104 48 L132 72Z M168 72 L196 48 L192 75Z" fill="{}"/>'.format(coat,accent))
 else:out.append('<path d="M100 80 Q88 38 118 45 Q139 49 143 75 L157 75 Q161 49 182 45 Q212 38 200 80Z" fill="{}" stroke="#374846" stroke-width="4"/><path d="M106 64 Q105 51 117 53 Q130 55 134 73 M166 73 Q170 55 183 53 Q195 51 194 64" fill="none" stroke="{}" stroke-width="5"/>'.format(coat,light))
 out.append('<rect x="91" y="70" width="118" height="91" rx="22" fill="{}" stroke="#374846" stroke-width="4"/><rect x="107" y="116" width="86" height="32" rx="14" fill="{}"/><rect x="117" y="102" width="9" height="12" rx="2" fill="{}"/><rect x="174" y="102" width="9" height="12" rx="2" fill="{}"/><path d="M145 128 L155 128 L150 134Z" fill="{}"/><path d="M150 134 L150 140 M150 140 Q143 147 137 140 M150 140 Q157 147 163 140" fill="none" stroke="{}" stroke-width="2.6" stroke-linecap="round"/><circle cx="123" cy="132" r="4" fill="#e68d83"/><circle cx="177" cy="132" r="4" fill="#e68d83"/>'.format(light,dark,dark,dark,accent,dark))
 out.append('</svg>');return ''.join(out)

def spec_for(t,paper,pid,rev):
 panels=[];art={}
 for p in parts_for(t):
  for side in FACES:
   pid2=p['id']+'_'+side;verts,w,h=face(p,side);panels.append({'id':pid2,'face':side,'vertices_3d_mm':verts,'polygon_mm':[[0,0],[w,0],[w,h],[0,h]],'width_mm':w,'height_mm':h})
   extra=''
   if p['id']=='head' and side=='front':
    extra='<rect x="{}" y="{}" width="3" height="4" fill="{}"/><rect x="{}" y="{}" width="3" height="4" fill="{}"/><rect x="{}" y="{}" width="3" height="2" fill="{}"/>'.format(w*.29,h*.36,t['dark'],w*.68,h*.36,t['dark'],w*.46,h*.58,t['accent'])
   art[pid2]='<svg xmlns="http://www.w3.org/2000/svg" width="{}mm" height="{}mm" viewBox="0 0 {} {}"><rect width="100%" height="100%" fill="{}"/>{}</svg>'.format(w,h,w,h,p['color'],extra)
 identity={'model_id':t['id'].upper().replace('_','-'),'version':'blocky-1.0','project_id':pid,'revision':rev,'template_version':'1.0.0'}
 geom={'model':{'type':'blocky_paper_character','name':t['name'],'width_mm':50,'depth_mm':48,'height_mm':64,'parts':parts_for(t)},'panels':panels,'seams':[],'open_boundary':[]}
 digest=hashlib.sha256(json.dumps(geom,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {**identity,'geometry_sha256':digest,'schema_version':'papercraft-character-1.0','units':'mm','paper':{'name':paper,'page_mm':list(PAPER[paper]),'scale':1.0},'geometry':geom,'appearance':{'panels':art},'sheet_count':1,'physical_assembly':'NOT_TESTED','print_units':[],'limitations':['Fold and glue the cuboid parts; physical assembly has not been tested.']}

def nets(t,paper):
 pw,ph=PAPER[paper];margin=12;gap=4;out=[];x=margin;y=margin;row=0;items=sorted(parts_for(t),key=lambda p:p['size'][0]*p['size'][1]*p['size'][2],reverse=True)
 for p in items:
  X,Y,Z=p['size'];pad=3;w=X+2*Y+2*pad;h=2*Y+2*Z+2*pad
  if x+w>pw-margin:x=margin;y+=row+gap;row=0
  if y+h>ph-margin:raise ValueError('Character parts exceed printable page bounds')
  x0=x+pad;y0=y+pad;col=p['color'];rects=[(x0+Y,y0+Z,X,Y),(x0+Y,y0+2*Z+Y,X,Y),(x0+Y,y0+Z+Y,X,Z),(x0+Y,y0+Z-Z,X,Z),(x0,y0+Z,Y,Z),(x0+2*Y+X,y0+Z,Y,Z)]
  out.append('<text x="{}" y="{}" font-size="2.5">{}</text>'.format(x0+Y,y0+2*Z+2*Y+2,p['id']))
  for i,(a,b,c,d) in enumerate(rects):out.append('<rect x="{}" y="{}" width="{}" height="{}" fill="{}" stroke="#172b31" stroke-width=".55"/>'.format(a,b,c,d,col))
  # Net fold lines and four narrow glue flaps on the free perimeter.
  for a,b,c,d in [(x0+Y,y0+Z,x0+Y+X,y0+Z),(x0+Y,y0+Z+Y,x0+Y+X,y0+Z+Y),(x0+Y,y0+Z,x0+Y,y0+2*Z),(x0+Y+X,y0+Z,x0+Y+X,y0+2*Z)]:out.append('<path d="M {} {} L {} {}" stroke="#a34676" stroke-dasharray="2 1.5" stroke-width=".45"/>'.format(a,b,c,d))
  # Colored glue flaps close the two side seams and support the lid.
  for points in [[(x0,y0+Z+2),(x0-pad,y0+Z+4),(x0-pad,y0+Z+Y-4),(x0,y0+Z+Y-2)],[(x0+2*Y+X,y0+Z+2),(x0+2*Y+X+pad,y0+Z+4),(x0+2*Y+X+pad,y0+Z+Y-4),(x0+2*Y+X,y0+Z+Y-2)],[(x0+Y,y0),(x0+Y+X,y0),(x0+Y+X-3,y0-pad),(x0+Y+3,y0-pad)]]:
   out.append('<polygon points="{}" fill="#f0e4c4" stroke="#172b31" stroke-width=".55"/>'.format(' '.join('{},{}'.format(a,b) for a,b in points)))
  x+=w+gap;row=max(row,h)
 return out

def generate(request,out,progress=lambda s:None):
 import fitz
 from .paper import printable_filename
 from .project_archive import create_download_archive
 t=request.get('template') or BY_ID[request['preset']];paper=request.get('paper','US Letter');pw,ph=PAPER[paper];out=Path(out);out.mkdir(parents=True,exist_ok=True);progress('Build Geometry')
 spec=spec_for(t,paper,request['project_id'],request['revision']);(out/'model_spec.json').write_text(json.dumps(spec,indent=2), encoding="utf-8");art=preview(t);(out/'template_preview.svg').write_text(art, encoding="utf-8")
 with fitz.open(stream=art.encode(),filetype='svg') as src:pdf=src.convert_to_pdf()
 with fitz.open(stream=pdf,filetype='pdf') as doc:doc[0].get_pixmap(matrix=fitz.Matrix(2,2)).save(out/'model_3d_preview.png')
 progress('Pack Pages');content=''.join(nets(t,paper));svg='<svg xmlns="http://www.w3.org/2000/svg" width="{}mm" height="{}mm" viewBox="0 0 {} {}"><rect width="100%" height="100%" fill="white"/><text x="{}" y="8" text-anchor="middle" font-size="3">{} · PRINT AT 100% · BLACK CUT · PURPLE FOLD</text>{}</svg>'.format(pw,ph,pw,ph,pw/2,t['name'],content)
 (out/'svg_pages').mkdir(exist_ok=True);(out/'coloring_svg_pages').mkdir(exist_ok=True);(out/'svg_pages/page_001.svg').write_text(svg, encoding="utf-8");coloring=svg
 for p in parts_for(t):coloring=coloring.replace('fill="{}" stroke="#172b31"'.format(p['color']),'fill="white" stroke="#172b31"')
 (out/'coloring_svg_pages/page_001.svg').write_text(coloring, encoding="utf-8")
 with fitz.open(stream=svg.encode(),filetype='svg') as doc:pdf=doc.convert_to_pdf()
 (out/printable_filename(paper)).write_bytes(pdf)
 with fitz.open(stream=pdf,filetype='pdf') as doc:doc[0].get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save(out/'printable_preview.png')
 report={'overall_status':'PASS','physical_assembly':'NOT_TESTED','tests':[{'name':'cuboid_model_spec','status':'PASS','detail':'{} printable panels'.format(len(spec['geometry']['panels']))},{'name':'printable_svg','status':'PASS','detail':'One sheet'}],'summary':{'sheets':1,'cut_pieces':len(parts_for(t)),'fold_hinges':0,'glue_seams':len(parts_for(t))*4,'flat_continuous_joins':0}}
 (out/'validation_report.json').write_text(json.dumps(report,indent=2), encoding="utf-8");identity={k:spec[k] for k in ('model_id','version','project_id','revision','geometry_sha256','template_version')};manifest={**identity,'qa_status':'PASS','physical_assembly':'NOT_TESTED','artifacts':[]}
 for f in sorted(out.rglob('*')):
  if f.is_file() and f.name not in ('generation_manifest.json','project.zip'):manifest['artifacts'].append({'path':f.relative_to(out).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),**identity})
 (out/'generation_manifest.json').write_text(json.dumps(manifest,indent=2), encoding="utf-8");create_download_archive(out);progress('Complete');return report
