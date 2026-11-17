"""Gabled house extension: exact 3D seam pairing + rigid connected nets.

Reuses v1.2 tab generation, rigid transforms, PaperUnit and shelf packing.
Does not modify or replace the original cube/frame algorithms.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
from shapely.geometry import Polygon

from .template_catalog import BY_ID, CATALOG_VERSION
from .paper import printable_filename
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mpl-cache'))
sys.path.insert(0, str(ROOT / 'papercraft-v1.2'))
import generate_connected_nets_v1_2 as base

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
CUT, FOLD, TAB = '#16252e', '#9a3971', '#fff1d3'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass
class Panel:
    id: str
    points: list
    vertices: list
    edges: dict = field(default_factory=dict)
    tabs: dict = field(default_factory=dict)

    @property
    def square(self):
        return Polygon(self.points)

    def seg(self, e):
        i = int(e)
        return self.points[i], self.points[(i+1) % len(self.points)]


def model(t):
    w, d, h, r = (t[k] for k in ('width', 'depth', 'wall_height', 'roof_rise'))
    slope = math.hypot(w/2, r)
    gable = [(0,0), (w,0), (w,h), (w/2,h+r), (0,h)]
    wall = [(0,0), (d,0), (d,h), (0,h)]
    roof = [(0,0), (d,0), (d,slope), (0,slope)]
    mappings = {
        'FRONT': (gable, lambda u,v: (u-w/2, -d/2, v)),
        'RIGHT': (wall, lambda u,v: (w/2, u-d/2, v)),
        'BACK': (gable, lambda u,v: (w/2-u, d/2, v)),
        'LEFT': (wall, lambda u,v: (-w/2, d/2-u, v)),
        'ROOF_RIGHT': (roof, lambda u,v: (w/2-v*w/(2*slope), u-d/2, h+v*r/slope)),
        'ROOF_LEFT': (roof, lambda u,v: (-w/2+v*w/(2*slope), d/2-u, h+v*r/slope)),
    }
    panels = {pid: Panel(pid, pts, [fn(*p) for p in pts]) for pid,(pts,fn) in mappings.items()}
    if t.get('profile'):
        ridge=[(x*w,h+z*r) for x,z in t['profile']]
        front=[(0,0),(w,0)]+list(reversed(ridge))
        # Keep local polygons counter-clockwise, with outward 3D winding.
        panels={
            'FRONT':Panel('FRONT',front,[(x-w/2,-d/2,z) for x,z in front]),
            'BACK':Panel('BACK',[(w-x,z) for x,z in reversed(front)],[(x-w/2,d/2,z) for x,z in reversed(front)]),
        }
        for pid,height,fn in [('RIGHT',ridge[-1][1],lambda u,v:(w/2,u-d/2,v)),('LEFT',ridge[0][1],lambda u,v:(-w/2,d/2-u,v))]:
            pts=[(0,0),(d,0),(d,height),(0,height)]
            panels[pid]=Panel(pid,pts,[fn(*q) for q in pts])
        for i,(a,b) in enumerate(zip(ridge,ridge[1:])):
            length=math.dist(a,b);pts=[(0,0),(d,0),(d,length),(0,length)]
            pid=f'ROOF_{i+1}'
            panels[pid]=Panel(pid,pts,[(b[0]-w/2+v*(a[0]-b[0])/length,u-d/2,b[1]+v*(a[1]-b[1])/length) for u,v in pts])
    occurrences = defaultdict(list)
    for p in panels.values():
        for i,a in enumerate(p.vertices):
            b=p.vertices[(i+1)%len(p.vertices)]
            key=tuple(sorted(tuple(round(float(v),6) for v in point) for point in (a,b)))
            occurrences[key].append({'panel':p.id, 'edge':str(i)})
    seams=[]; boundary=[]
    for key, mates in sorted(occurrences.items()):
        if len(mates)==1:
            boundary.append({'endpoints':key, 'mate':mates[0]})
            continue
        if len(mates)!=2:
            raise ValueError('Non-manifold house seam')
        a,b = (panels[m['panel']] for m in mates)
        def normal(p):
            n=np.cross(np.subtract(p.vertices[1],p.vertices[0]), np.subtract(p.vertices[2],p.vertices[1]))
            return n/np.linalg.norm(n)
        angle=math.degrees(math.acos(float(np.clip(np.dot(normal(a),normal(b)),-1,1))))
        sid=f'G{len(seams)+1:02d}'
        seam={'id':sid,'kind':'house_edge','occurrences':mates,'length_mm':math.dist(*key), 'fold_degrees':angle,'hinge':False}
        if all(p.id.startswith('ROOF') for p in (a,b)) and all(key[0][2] < np.mean([v[2] for v in p.vertices])-1e-6 for p in (a,b)):
            seam['fold_direction']='VALLEY_FROM_PRINTED_OUTSIDE'
        seams.append(seam)
        for m in mates: panels[m['panel']].edges[m['edge']]=sid
    # Three real connected units: two wall pairs and one roof ridge pair.
    pair_sets=[{'FRONT','RIGHT'},{'BACK','LEFT'},{'ROOF_RIGHT','ROOF_LEFT'}]
    if t.get('profile'):
        roofs=[pid for pid in panels if pid.startswith('ROOF')]
        pair_sets=[{'FRONT','RIGHT'},{'BACK','LEFT'}]+[set(roofs[i:i+2]) for i in range(0,len(roofs)-1,2)]
    for seam in seams:
        seam['hinge']={m['panel'] for m in seam['occurrences']} in pair_sets
        if not seam['hinge']:
            owner=seam['occurrences'][0]
            p=panels[owner['panel']]
            p.tabs[owner['edge']]=base.base.flap_for_edge(*p.seg(owner['edge']),depth=5)
    lookup={s['id']:s for s in seams}
    units=[base.construct_unit(tuple(m['panel'] for m in s['occurrences']),s['id'],panels,lookup) for s in seams if s['hinge']]
    placed={pid for u in units for pid in u.ids}
    units += [base.construct_unit((pid,),None,panels,lookup) for pid in panels if pid not in placed]
    if not all(base.fits(u) for u in units):
        raise ValueError('Catalog model exceeds printable bounds; scaling is forbidden')
    pages=base.pack_units(units)
    return panels,seams,units,pages,boundary


def base_decorations(t,p):
    """Shared vector drawing primitives, used by printable and 3D textures."""
    x0,y0,w,h=p.square.bounds
    w-=x0;h-=y0
    cream=t['trim']; accent=t['accent']; shapes=[]
    def line(points,color=cream,width=1.3): shapes.append({'type':'line','points':points,'stroke':color,'width':width})
    def poly(points,fill,stroke=None,width=0): shapes.append({'type':'polygon','points':points,'fill':fill,'stroke':stroke,'width':width})
    def circle(x,y,r,fill,stroke=None,width=0): shapes.append({'type':'circle','center':[x,y],'radius':r,'fill':fill,'stroke':stroke,'width':width})
    def rect(x,y,rw,rh,fill,stroke=None,width=0):poly([(x,y),(x+rw,y),(x+rw,y+rh),(x,y+rh)],fill,stroke,width)
    roof=p.id.startswith('ROOF')
    poly(p.points,t['roof'] if roof else t['wall'])
    if t.get('premium'):
        return premium_decorations(t,p)
    # Icing follows an inset perimeter, safely inside the panel.
    inset=p.square.buffer(-3,join_style=2)
    if not inset.is_empty:line(list(inset.exterior.coords),cream,1.7)
    if roof:
        for y in np.arange(10,h-5,10):
            points=[(float(x),float(y+2.2*math.sin(x*math.pi/10))) for x in np.linspace(5,w-5,40)]
            line(points,cream,1.2)
        for x in np.arange(10,w-5,15):
            for y in np.arange(10,h-5,20):
                circle(float(x),float(y),1.6,accent if t['motif']!='snow' else '#ffffff')
        return shapes
    wall_h=t['wall_height']; front=p.id=='FRONT'
    if t['motif']=='chalet':
        for y in np.arange(9,wall_h-4,8):line([(5,float(y)),(w-5,float(y))],'#805539',.6)
    def window(cx,cy,size):
        rect(cx-size/2,cy-size/2,size,size,'#f8d788',cream,1.8)
        line([(cx-size/2,cy),(cx+size/2,cy)],cream,1)
        line([(cx,cy-size/2),(cx,cy+size/2)],cream,1)
        rect(cx-size/2-2,cy-size/2-3,size+4,2,cream)
    if front:
        dw=min(20,w*.24);dh=min(32,wall_h*.42)
        rect(w/2-dw/2,5,dw,dh,accent,cream,2)
        circle(w/2+dw*.26,5+dh*.42,1.1,'#f8d788')
        for x in [w*.22,w*.78]:window(x,wall_h*.58,min(15,w*.19))
        # Wreath above the door; printed artwork only.
        circle(w/2,wall_h*.78,5,'#39785a',cream,.8)
        circle(w/2,wall_h*.78,2.8,t['wall'])
        circle(w/2-2,wall_h*.78-3.5,1.7,'#d14c47');circle(w/2+2,wall_h*.78-3.5,1.7,'#d14c47')
    else:
        for x in [w*.3,w*.7]:window(x,wall_h*.55,min(17,w*.24))
    if len(p.points)==5:
        circle(w/2,wall_h+t['roof_rise']*.35,4.5,'#f8d788',cream,1.6)
        line([(w/2-3,wall_h+t['roof_rise']*.35),(w/2+3,wall_h+t['roof_rise']*.35)],cream,.8)
    # Seasonal motifs sit below the windows and do not change the cut geometry.
    if t['motif']=='forest':
        for x in [w*.17,w*.83]:
            poly([(x-4,7),(x,22),(x+4,7)],accent,cream,.6)
    elif t['motif']=='snow':
        for x in [w*.18,w*.82]:
            for angle in (0,math.pi/3,2*math.pi/3):
                dx,dy=4*math.cos(angle),4*math.sin(angle)
                line([(x-dx,15-dy),(x+dx,15+dy)],cream,.8)
    else:
        for x in [w*.14,w*.86]:
            line([(x,7),(x,22),(x+3,24),(x+5,22)],cream,3)
            for y in (10,15,20):line([(x-1,y),(x+1,y+1.5)],accent,1.2)
    return shapes


def decorations(t,p):
    from .confectionery import house_art
    from .personalization import nameplate
    return house_art(t,p)+nameplate(t,p)


def premium_decorations(t,p):
    """Architectural vector finishes shared by preview, texture, PDF and SVG."""
    w=p.square.bounds[2];h=p.square.bounds[3];shapes=[]
    trim=t['trim'];accent=t['accent'];roof=p.id.startswith('ROOF')
    def line(points,color=trim,width=.45):shapes.append(dict(type='line',points=points,stroke=color,width=width))
    def rect(x,y,a,b,color):shapes.append(dict(type='polygon',points=[(x,y),(x+a,y),(x+a,y+b),(x,y+b)],fill=color))
    def circle(x,y,r,color):shapes.append(dict(type='circle',center=[x,y],radius=r,fill=color))
    shapes.append(dict(type='polygon',points=p.points,fill=t['roof'] if roof else t['wall']))
    if roof:
        return shapes
    wh=min(t['wall_height'],h);material=t['material']
    if material=='board':
        for x in np.arange(4,w-2,6):line([(float(x),2),(float(x),wh-2)],trim,.35)
    else:
        for row,y in enumerate(np.arange(4,wh-2,4)):
            line([(2,float(y)),(w-2,float(y))],trim,.25)
            if material in ('brick','shingle'):
                for x in np.arange(3+(row%2)*4,w-3,8):line([(float(x),float(y)),(float(x),float(min(y+4,wh-2)))],trim,.22)
    rect(2,2,w-4,3,trim)
    for x in (2,w-4):rect(x,3,2,wh-5,trim)
    front=p.id=='FRONT';back=p.id=='BACK'
    def window(x,y,ww=13,hh=17):
        rect(x-ww/2-1,y-1,ww+2,hh+2,trim)
        rect(x-ww/2,y,ww,hh,'#f3cf83')
        rect(x-ww/2+1,y+hh*.55,ww-2,hh*.4,'#f9e9b7')
        for dx in (-ww/2-3,ww/2+1):
            rect(x+dx,y,2,hh,accent)
            for yy in np.arange(y+2,y+hh,3):line([(x+dx,yy),(x+dx+2,yy)],trim,.2)
        line([(x,y),(x,y+hh)],trim,.7)
        for yy in (y+hh/3,y+2*hh/3):line([(x-ww/2,yy),(x+ww/2,yy)],trim,.6)
        rect(x-ww/2-2,y-2,ww+4,1.4,trim)
        line([(x-ww/2-1,y+hh+3),(x,y+hh+5),(x+ww/2+1,y+hh+3)],trim,.8)
    floors=3 if wh>125 else 2 if wh>90 else 1
    for level in range(floors):
        y=wh*(.40 if floors==1 else .16+level*.29)
        for x in (w*.24,w*.76):window(x,y,min(13,w*.18),min(17,wh*.30))
    if front:
        dw=min(17,w*.23);dh=min(29,wh*.72)
        rect(w/2-dw/2-1,3,dw+2,dh+2,trim);rect(w/2-dw/2,3,dw,dh,accent)
        for yy in (6,dh*.55):
            for xx in (w/2-dw*.36,w/2+dw*.05):
                rect(xx,yy,dw*.30,dh*.30,t['wall'])
        circle(w/2+dw*.33,dh*.5, .7,'#e8bc68')
        rect(w/2-dw/2-3,2,dw+6,1.5,trim)
        cy=min(wh-8,dh+11)
        circle(w/2,cy,4.3,'#294b3b');circle(w/2,cy,2.4,t['wall'])
        for a in range(0,360,45):circle(w/2+3.3*math.cos(math.radians(a)),cy+3.3*math.sin(math.radians(a)),.55,'#d2a45c')
        line([(w/2-2,cy-4),(w/2,cy-3),(w/2+2,cy-4)],accent,1.5)
    # Garland and tiny bulbs are kept in the rectangular wall area.
    for x in np.linspace(5,w-5,24):
        y=wh-4-1.8*math.sin((x-5)/(w-10)*math.pi*3)**2
        circle(float(x),float(y),.9,'#365743')
    for x in np.linspace(7,w-7,10):circle(float(x),wh-7,.55,'#e4af53')
    if (front or back) and t['roof_rise']>=28:
        from shapely.geometry import box
        ay=wh+t['roof_rise']*.24
        if p.square.buffer(-2).covers(box(w/2-11,ay-3,w/2+11,ay+20)):
            window(w/2,ay,12,14)
    if (front or back) and len(p.points)>4:
        inset=p.square.buffer(-2,join_style=2)
        if not inset.is_empty:line(list(inset.exterior.coords),trim,1)
    return shapes


def svg_art(shapes, width, height):
    root=ET.Element('{'+NS+'}svg',{'width':f'{width}mm','height':f'{height}mm','viewBox':f'0 0 {width} {height}'})
    def transform(p):return p[0],height-p[1]
    draw_shapes(None,root,shapes,transform,1)
    return ET.tostring(root,encoding='unicode')


def draw_shapes(c, root, shapes, transform, scale=base.PT):
    """Emit the same vector geometry to PDF (mm->pt) and SVG (mm)."""
    from reportlab.lib.colors import HexColor
    if root is not None:root=ET.SubElement(root,'{'+NS+'}g',{'data-artwork':'true'})
    for shape in shapes:
        tag=shape['type']; fill=shape.get('fill'); stroke=shape.get('stroke'); width=shape.get('width',0)
        attrs={'fill':fill or 'none','stroke':stroke or 'none','stroke-width':str(width),'stroke-linejoin':'round','stroke-linecap':'round'}
        if c:
            c.saveState()
            if fill:c.setFillColor(HexColor(fill))
            if stroke:c.setStrokeColor(HexColor(stroke));c.setLineWidth(width*scale)
        if tag=='path':
            if c:path=c.beginPath()
            commands=[]
            for ring in shape['rings']:
                points=[transform(q) for q in ring]
                if not points:continue
                if c:
                    path.moveTo(points[0][0]*scale,points[0][1]*scale)
                    for x,y in points[1:]:path.lineTo(x*scale,y*scale)
                    path.close()
                commands.append('M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in points)+' Z')
            if c:c.drawPath(path,fill=1,stroke=0,fillMode=1)
            if root is not None:ET.SubElement(root,'{'+NS+'}path',d=' '.join(commands),**attrs,**{'fill-rule':'nonzero','data-personal-name':shape.get('label','')})
        elif tag=='circle':
            x,y=transform(shape['center']);r=shape['radius']
            if c:c.circle(x*scale,y*scale,r*scale,fill=bool(fill),stroke=bool(stroke))
            if root is not None:ET.SubElement(root,'{'+NS+'}circle',cx=str(x),cy=str(y),r=str(r),**attrs)
        else:
            points=[transform(q) for q in shape['points']]
            if c:
                path=c.beginPath();path.moveTo(points[0][0]*scale,points[0][1]*scale)
                for x,y in points[1:]:path.lineTo(x*scale,y*scale)
                if tag=='polygon':path.close()
                c.drawPath(path,fill=bool(fill),stroke=bool(stroke))
            if root is not None:ET.SubElement(root,'{'+NS+'}'+('polygon' if tag=='polygon' else 'polyline'),points=' '.join(f'{x:.6f},{y:.6f}' for x,y in points),**attrs)
        if c:c.restoreState()


def preview_svg(t):
    """Orthographic catalog image from the exact panel vertices and artwork."""
    panels,_,_,_,_=model(t)
    w,d,h,r=(t[k] for k in ('width','depth','wall_height','roof_rise'))
    def project(v):
        x,y,z=v
        return (x*.82+y*.55, x*.25-y*.38-z)
    from .accessories import scene
    accessory_scene=scene(t)
    accessory_panels={p['id']:Panel(p['id'],p['polygon_mm'],p['vertices_3d_mm']) for p in accessory_scene['panels']}
    all_pts=[project(v) for p in [*panels.values(),*accessory_panels.values()] for v in p.vertices]
    lo=np.min(all_pts,axis=0);hi=np.max(all_pts,axis=0)
    scale=min(285/(hi[0]-lo[0]),235/(hi[1]-lo[1]))
    shift=(180-(hi[0]+lo[0])*scale/2,145-(hi[1]+lo[1])*scale/2)
    root=ET.Element('{'+NS+'}svg',viewBox='0 0 360 300',role='img')
    ET.SubElement(root,'{'+NS+'}title').text=t['name']
    ET.SubElement(root,'{'+NS+'}rect',width='360',height='300',fill=t['background'])
    ET.SubElement(root,'{'+NS+'}ellipse',cx='180',cy='265',rx='110',ry='14',fill='#253d30',opacity='.08')
    # Camera looks at front (+ negative y), right (+ x) and top.
    visible=['FRONT','RIGHT']
    for pid,p in panels.items():
        if pid.startswith('ROOF'):
            n=np.cross(np.subtract(p.vertices[1],p.vertices[0]),np.subtract(p.vertices[2],p.vertices[0]))
            if np.dot(n,[.55,-.82,.4491])>0:visible.append(pid)
    visible_caps=[];hidden_caps=[]
    for pid,p in accessory_panels.items():
        if pid.startswith('CAP_'):
            normal=np.cross(np.subtract(p.vertices[1],p.vertices[0]),np.subtract(p.vertices[2],p.vertices[0]))
            if np.dot(normal,[.55,-.82,.4491])>0:visible_caps.append(pid)
            else:hidden_caps.append(pid)
    visible=['DISPLAY_BASE']+hidden_caps+visible+visible_caps+['TREE_1','TREE_2']+[pid for pid in accessory_panels if pid.startswith('GIFT') and pid.endswith(('FRONT','RIGHT','TOP'))]
    for pid in visible:
        p=panels.get(pid) or accessory_panels[pid]
        local=np.array(p.points); xyz=np.array(p.vertices)
        basis=np.linalg.lstsq(np.column_stack([local,np.ones(len(local))]),xyz,rcond=None)[0]
        def trans(q):
            projected=project(np.array([q[0],q[1],1])@basis)
            return projected[0]*scale+shift[0],projected[1]*scale+shift[1]
        group=ET.SubElement(root,'{'+NS+'}g')
        # Apply an affine group so circles remain correctly projected ellipses.
        o=trans((0,0));u=trans((1,0));v=trans((0,1))
        group.set('transform',f'matrix({u[0]-o[0]} {u[1]-o[1]} {v[0]-o[0]} {v[1]-o[1]} {o[0]} {o[1]})')
        shapes=decorations(t,p) if pid in panels else accessory_scene['artwork'][pid]
        if pid in hidden_caps:shapes=[dict(type='polygon',points=p.points,fill='#e8d9c1',stroke='#b99b76',width=.2)]
        draw_shapes(None,group,shapes,lambda q:q,1)
    return ET.tostring(root,encoding='unicode')


def generate(request,out,progress=lambda stage:None):
    import fitz
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from PIL import Image,PngImagePlugin
    from .paper import configure_engine, printable_filename
    paper_name=request.get('paper','US Letter')
    configure_engine(base,paper_name)
    t=request.get('template') or BY_ID[request['preset']]
    if request.get('personal_name'):t={**t,'personal_name':request['personal_name']}
    out.mkdir(parents=True,exist_ok=True)
    fontdir=Path(matplotlib.get_data_path())/'fonts/ttf'
    for name,file in [(base.base.FONT,'DejaVuSans.ttf'),(base.base.FONT_BOLD,'DejaVuSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(fontdir/file)))
    progress('Build Geometry')
    panels,seams,units,pages,boundary=model(t)
    progress('Choose Hinges / Unfold / Add Tabs')
    geometry={'model':{'type':t.get('model_family','gable_house_open_bottom'),'name':t['name'],'width_mm':t['width'],'depth_mm':t['depth'],'wall_height_mm':t['wall_height'],'roof_rise_mm':t['roof_rise'],'height_mm':t['wall_height']+t['roof_rise'],'open_bottom':True},
              'panels':[{'id':p.id,'face':p.id,'width_mm':p.square.bounds[2],'height_mm':p.square.bounds[3], 'polygon_mm':p.points,'vertices_3d_mm':p.vertices,'edge_codes':p.edges} for p in panels.values()],
              'seams':[{'id':s['id'],'kind':s['kind'],'length_mm':s['length_mm'],'fold_degrees':s['fold_degrees'],'mates':s['occurrences'],'hinged_uncut':s['hinge'],'fold_direction':s.get('fold_direction','MOUNTAIN_FROM_PRINTED_OUTSIDE')} for s in seams], 'open_boundary':boundary}
    identity={'model_id':t['id'].upper().replace('_','-'),'version':'gingerbread-4.0.0','project_id':request['project_id'],'revision':request['revision'],'geometry_sha256':digest(geometry),'source_spec_hash':digest(request),'design_sha256':digest(t),'template_version':CATALOG_VERSION}
    spec={**identity,'schema_version':'gingerbread-1.0.0','locked':True,'units':'mm','paper':{'name':paper_name,'page_mm':[base.PAGE_W,base.PAGE_H],'scale':1.0,'printable_body_mm':base.BODY,'tab_depth_mm':5},'geometry':geometry,'sheet_count':len(pages),'physical_assembly':'NOT_TESTED',
          'print_units':[{'panel_ids':list(u.ids),'sheet_number':u.sheet+1,'fold_code':u.hinge_id,'bounds_mm':list(u.cut_bounds()),'orientation_degrees':u.orientation} for u in units],
          'personalization':{'name':t.get('personal_name',''),'placement':'FRONT_NAMEPLATE'},
          'appearance':{'template_id':t['id'],'motif':t['motif'],'panels':{p.id:svg_art(decorations(t,p),p.square.bounds[2],p.square.bounds[3]) for p in panels.values()}},
          'limitations':['Open bottom; no floor or chimney. Doors and windows are printed decorations, not cut-outs.','Fixed preset dimensions. Physical assembly NOT_TESTED.']}
    progress('Pack Pages')
    progress('Export')
    pdf=out/printable_filename(base.PAPER_NAME); c=canvas.Canvas(str(pdf),pagesize=(base.PAGE_W*base.PT,base.PAGE_H*base.PT),invariant=1)
    c.setTitle(t['name']);c.setSubject(canonical(identity))
    (out/'svg_pages').mkdir(exist_ok=True)
    def label(root,x,y,text,size=2.1,color='#263d35'):
        base.pdf_text(c,x,y,text,size*base.PT,clr=color,center=True)
        base.svg_label(root,x,y,text,size,color)
    for index,page in enumerate(pages):
        root=ET.Element('{'+NS+'}svg',width=f'{base.PAGE_W}mm',height=f'{base.PAGE_H}mm',viewBox=f'0 0 {base.PAGE_W} {base.PAGE_H}')
        ET.SubElement(root,'{'+NS+'}metadata').text=canonical(identity)
        label(root,base.PAGE_W/2,base.PAGE_H-12.4,t['name']+' | '+identity['model_id'],3.2)
        label(root,base.PAGE_W/2,base.PAGE_H-19.4,f'Page {index+1}/{len(pages)} | CUT black | FOLD purple | Print Actual Size 100%',2.1)
        for unit in page['units']:
            def emit(shapes,transform):
                draw_shapes(c,None,shapes,transform)
                draw_shapes(None,root,shapes,lambda q:(transform(q)[0],base.PAGE_H-transform(q)[1]),1)
            for pid in unit.ids:
                p=panels[pid];transform=lambda q,pid=pid:unit.transform(pid,q)
                emit(decorations(t,p),transform)
                for tab in p.tabs.values():emit([{'type':'polygon','points':list(tab.exterior.coords),'fill':TAB}],transform)
                for edge in p.tabs:
                    a,b=p.seg(edge)
                    base.pdf_line(c,transform(a),transform(b),'#216c94',.65,[3,2])
                    base.svg_segment(root,transform(a),transform(b),'#216c94',[1.0,.7],.23)
                # Codes live only on material hidden underneath the mating face.
                # The full two-sided seam map belongs in the assembly guide.
                for edge,tab in p.tabs.items():
                    x,y=transform((tab.centroid.x,tab.centroid.y))
                    label(root,x,y-.5,p.edges[edge],1.6,'#6a7167')
            base.pdf_shape(c,unit.shape(),stroke=CUT,stroke_width=.65)
            base.svg_polygon(root,unit.shape(),'none',CUT,.23)
            if not unit.hinge_id:continue
            seam=next(s for s in seams if s['id']==unit.hinge_id)
            mate=seam['occurrences'][0];a,b=panels[mate['panel']].seg(mate['edge'])
            a,b=unit.transform(mate['panel'],a),unit.transform(mate['panel'],b)
            base.pdf_line(c,a,b,FOLD,.9,[4,2]);base.svg_segment(root,a,b,FOLD,[1.5,.8],.35)
        base.pdf_line(c,(15,10.5),(55,10.5),CUT,.8)
        base.svg_segment(root,(15,10.5),(55,10.5),CUT,width=.25)
        for x in (15,55):base.pdf_line(c,(x,8.7),(x,12.3),CUT,.7);base.svg_segment(root,(x,8.7),(x,12.3),CUT,width=.25)
        label(root,126,10,'40 mm | Actual Size / 100% - NO Fit to Page',2.2)
        label(root,108,15,f"{identity['model_id']} | r{request['revision']} | {identity['geometry_sha256'][:16]}",1.7)
        ET.ElementTree(root).write(out/f'svg_pages/page_{index+1:03d}.svg',encoding='utf-8',xml_declaration=True)
        c.showPage()
    c.save()
    (out/'model_spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2))
    (out/'template_preview.svg').write_text(preview_svg(t))
    # OBJ contains the real six-panel shell, deliberately open at the bottom.
    obj=['# '+canonical(identity)];vertex_offset=0
    for p in panels.values():
        obj.append('g '+p.id)
        obj.extend('v '+' '.join(str(v) for v in xyz) for xyz in p.vertices)
        obj.append('f '+' '.join(str(vertex_offset+i+1) for i in range(len(p.vertices))))
        vertex_offset+=len(p.vertices)
    (out/'model.obj').write_text('\n'.join(obj)+'\n')
    # SVG-to-PDF conversion uses the exported vector preview, not an AI image.
    with fitz.open(stream=preview_svg(t).encode(),filetype='svg') as svgdoc:
        preview_bytes=svgdoc.convert_to_pdf()
    with fitz.open(stream=preview_bytes,filetype='pdf') as preview:
        preview[0].get_pixmap(matrix=fitz.Matrix(2,2)).save(out/'model_3d_preview.png')
    base.contact_sheet(pdf,out/'printable_preview.png',identity['model_id'])
    guide=canvas.Canvas(str(out/'assembly_guide.pdf'),pagesize=(base.PAGE_W*base.PT,base.PAGE_H*base.PT),invariant=1)
    guide.setTitle('Hướng dẫn - '+t['name']);guide.setSubject(canonical(identity))
    def gt(x,y,text,size=9,bold=False):base.pdf_text(guide,x,y,text,size,bold)
    gt(12,264,'HƯỚNG DẪN LẮP NHÀ BÁNH GỪNG',14,True);gt(12,253,t['name'],11)
    guide.drawImage(str(out/'model_3d_preview.png'),45*base.PT,151*base.PT,width=125*base.PT,height=95*base.PT,preserveAspectRatio=True,mask='auto')
    steps=[f"Kích thước: {t['width']} × {t['depth']} × {t['wall_height']+t['roof_rise']:g} mm. Đáy mở.",
           f'1. In {paper_name} ở Actual Size / 100%. Đo vạch chuẩn 40 mm.',
           '2. Cắt theo viền ĐEN. Giữ lại tai dán màu vàng nhạt.',
           '3. Gấp các cụm tường, mặt in hướng ra ngoài.',
           '4. Dán các cạnh đứng có cùng mã để khép bốn tường.',
           '5. Gấp các cụm mái theo nét tím; ghép các mã còn lại.',
           '6. Đối chiếu mã trên tai dán với sơ đồ ghép ở cuối hướng dẫn.',
           '7. Giữ nhẹ và đợi keo khô. Nhà không có đáy.',
           'Cửa, cửa sổ và kẹo là họa tiết IN; không cắt khoét.',
           'Chưa thử lắp bằng giấy thật: physical_assembly = NOT_TESTED.']
    if t.get('bay_count',1) > 1:
        steps[6]='6. Ghép cụm mái: đỉnh mỗi gian LỒI, thung mái giữa các gian LÕM.'
    for i,text in enumerate(steps):gt(12,139-i*10,text,8)
    gt(12,19,'Giấy gợi ý: cardstock 160–220 gsm. Ướm thử trước khi dán.',8)
    gt(12,10,identity['model_id']+' | '+identity['geometry_sha256'][:16],6)
    guide.showPage();gt(12,264,'MÃ GHÉP & NẾP GẤP',14,True)
    y=246
    for s in seams:
        if y<48:
            guide.showPage();gt(12,264,'MÃ GHÉP & NẾP GẤP (tiếp)',14,True);y=246
        mates=' + '.join(m['panel'] for m in s['occurrences'])
        text=f"{s['id']}: {mates} | "+(f"GẤP LIỀN {s['fold_degrees']:.1f}°" if s['hinge'] else 'DÁN')
        if s.get('fold_direction')=='VALLEY_FROM_PRINTED_OUTSIDE':text+=' — THUNG MÁI LÕM'
        gt(12,y,text,7);y-=9
    gt(12,y-5,'Góc ghi ở trên là góc quay từ tờ giấy phẳng, nhìn mặt in bên ngoài.',7.5)
    gt(12,y-17,'Nét tím: gấp liền. Nét xanh đứt: chân tai dán. Nét đen: cắt.',8)
    gt(12,10,identity['model_id']+' | '+identity['geometry_sha256'][:16],6)
    for index,page in enumerate(pages):
        guide.showPage()
        gt(12,base.PAGE_H-13.4,f'SƠ ĐỒ GHÉP — TRANG IN {index+1}/{len(pages)}',12,True)
        gt(12,base.PAGE_H-21.4,'Chỉ để tra mã cạnh. KHÔNG dùng trang này làm mẫu cắt.',8)
        for unit in page['units']:
            for pid in unit.ids:
                p=panels[pid]
                shape=Polygon([unit.transform(pid,q) for q in p.points])
                base.pdf_shape(guide,shape,fill='#f5f2e8',stroke='#657366',stroke_width=.5)
                center=shape.centroid
                base.pdf_text(guide,center.x,center.y,pid,7,True,center=True)
                for edge,sid in p.edges.items():
                    a,b=p.seg(edge);dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
                    point=((a[0]+b[0])/2-6*dy/length,(a[1]+b[1])/2+6*dx/length)
                    x,y=unit.transform(pid,point)
                    base.pdf_text(guide,x,y,sid,6,True,center=True)
            base.pdf_shape(guide,unit.shape(),stroke=CUT,stroke_width=.65)
        gt(12,10,identity['model_id']+' | Sơ đồ tham khảo, mã đầy đủ hai đầu ghép.',7)
    guide.save()
    progress('QA')
    tests=validate(t,panels,seams,units,pages,boundary,out)
    from .accessories import export as export_accessories, scene
    tests.extend(export_accessories(t,out,identity,len(pages)))
    from .roof_cap import metadata as cap_metadata
    cap_info=cap_metadata(t)
    spec['roof_cap']=cap_info
    spec['house_sheet_count']=len(pages)
    spec['sheet_count']=len(pages)+2+cap_info['sheet_count']
    spec['scene_accessories']=scene(t)
    spec['accessory_cut_pieces']=5+cap_info['cut_pieces']
    (out/'model_spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2))
    # Export the complete display as a separate OBJ; house OBJ stays reusable.
    scene_obj=list(obj)
    for panel in spec['scene_accessories']['panels']:
        scene_obj.append('g '+panel['id'])
        scene_obj.extend('v '+' '.join(str(v) for v in xyz) for xyz in panel['vertices_3d_mm'])
        scene_obj.append('f '+' '.join(str(vertex_offset+i+1) for i in range(len(panel['vertices_3d_mm']))))
        vertex_offset+=len(panel['vertices_3d_mm'])
    (out/'display_scene.obj').write_text('\n'.join(scene_obj)+'\n')
    base.contact_sheet(pdf,out/'printable_preview.png',identity['model_id'])
    for path in out.glob('*.png'):
        with Image.open(path) as image:
            info=PngImagePlugin.PngInfo();info.add_text('provenance',canonical(identity));image.save(path,pnginfo=info)
    from .coloring import export as export_coloring
    tests.extend(export_coloring(t,out,identity,panels,units,pages))
    report={**identity,'overall_status':'PASS' if all(x['status']=='PASS' for x in tests) else 'FAIL','physical_assembly':'NOT_TESTED','tests':tests,
            'summary':{'sheets':spec['sheet_count'],'accessory_cut_pieces':spec['accessory_cut_pieces'],'cut_pieces':len(units)+spec['accessory_cut_pieces'],'fold_hinges':sum(bool(u.hinge_id) for u in units),'glue_seams':sum(not s['hinge'] for s in seams),'accessory_fold_hinges':10+cap_info['fold_hinges'],'accessory_glue_seams':14+cap_info['glue_seams'],'flat_continuous_joins':0,'faces_or_tiles':len(panels)}}
    (out/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if report['overall_status']!='PASS':raise RuntimeError(canonical([t for t in tests if t['status']=='FAIL']))
    manifest={**identity,'input':request,'template':t,'qa_status':'PASS','algorithm':'gable-house-1.0; v1.2 rigid pairing + shelf packing','physical_assembly':'NOT_TESTED','artifacts':[]}
    for path in sorted(out.rglob('*')):
        if path.is_file():manifest['artifacts'].append({'path':path.relative_to(out).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**identity})
    (out/'generation_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(out/'project.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name!='project.zip':archive.write(path,path.relative_to(out))
    progress('Complete')
    return report


def validate(t,panels,seams,units,pages,boundary,out):
    import fitz
    tests=[]
    def check(name,ok,detail):tests.append({'name':name,'status':'PASS' if bool(ok) else 'FAIL','detail':detail})
    check('all_faces_placed_once',Counter(pid for u in units for pid in u.ids)==Counter(panels.keys()),f'{len(panels)} panels')
    check('open_bottom_boundary_only',len(boundary)==4 and all(abs(v[2])<1e-6 for b in boundary for v in b['endpoints']),'Intentional open-bottom shell')
    check('seam_pairs_unique',len({s['id'] for s in seams})==len(seams) and all(len(s['occurrences'])==2 for s in seams),len(seams))
    lengths=[];endpoints=[]
    for s in seams:
        mates=s['occurrences'];points=[]
        for m in mates:
            p=panels[m['panel']];i=int(m['edge'])
            points.append((p.vertices[i],p.vertices[(i+1)%len(p.vertices)]))
            lengths.append(abs(math.dist(*p.seg(m['edge']))-s['length_mm'])<1e-5)
        endpoints.append(math.dist(points[0][0],points[1][1])<1e-5 and math.dist(points[0][1],points[1][0])<1e-5)
    check('seam_2d_lengths',all(lengths),'Exact matching seam lengths')
    check('seam_3d_endpoints',all(endpoints),'Reverse-winding shared 3D endpoints')
    check('rigid_unfold_area',all(abs(Polygon([u.transform(pid,p) for p in panels[pid].points]).area-panels[pid].square.area)<1e-5 for u in units for pid in u.ids),'No scaling or reflection')
    check('tabs_only_on_glue_seams',all(sum(m['edge'] in panels[m['panel']].tabs for m in s['occurrences'])==(0 if s['hinge'] else 1) for s in seams),'No hinge tabs; one tab per glue seam')
    check('valid_connected_outlines',all(u.shape().is_valid and u.shape().geom_type=='Polygon' for u in units),'Connected cut polygons')
    from shapely.geometry import LineString
    hinges=[]
    for u in units:
        if not u.hinge_id:continue
        s=next(s for s in seams if s['id']==u.hinge_id)
        segments=[[u.transform(m['panel'],p) for p in panels[m['panel']].seg(m['edge'])] for m in s['occurrences']]
        hinges.append(math.dist(segments[0][0],segments[1][1])<1e-5 and math.dist(segments[0][1],segments[1][0])<1e-5 and u.shape().boundary.intersection(LineString(segments[0])).length<1e-5)
    check('hinges_coincident_and_not_cut',all(hinges),'Three interior uncut creases')
    check('face_plus_tab_area_conserved',abs(sum(p.square.area+sum(tab.area for tab in p.tabs.values()) for p in panels.values())-sum(u.shape().area for u in units))<1e-5,'No overlaps within connected units')
    check('no_inter_piece_overlap',all(a.shape().intersection(b.shape()).area<1e-5 for i,a in enumerate(units) for b in units[i+1:] if a.sheet==b.sheet),'No page collisions')
    check('printable_bounds',all(base.BODY[0]-1e-5<=b[0] and base.BODY[1]-1e-5<=b[1] and b[2]<=base.BODY[2]+1e-5 and b[3]<=base.BODY[3]+1e-5 for b in [u.shape().bounds for u in units]),base.BODY)
    xyz=np.array([v for p in panels.values() for v in p.vertices]);dims=np.ptp(xyz,axis=0)
    check('finished_dimensions_mm',np.allclose(dims,[t['width'],t['depth'],t['wall_height']+t['roof_rise']]),dims.tolist())
    pdf_cuts=[];pdf_cal=[];words=Counter();clipped=[];pdf_hinges=[];label_errors=[]
    with fitz.open(out/printable_filename(base.PAPER_NAME)) as doc:
        check('pdf_page_count',len(doc)==len(pages),len(doc))
        check('pdf_paper_dimensions',all(abs(p.rect.width/base.PT-base.PAGE_W)<.001 and abs(p.rect.height/base.PT-base.PAGE_H)<.001 for p in doc),f'{base.PAGE_W} × {base.PAGE_H} mm')
        for index,p in enumerate(doc):
            cuts=[];cal=0;hinges=0
            for drawing in p.get_drawings():
                color=drawing.get('color');width=drawing.get('width',0)
                if color and math.dist(color,(22/255,37/255,46/255))<.02 and abs(width-.65)<.03:
                    pts=[]
                    for item in drawing['items']:
                        if item[0]=='l':pts.append((item[1].x/base.PT,base.PAGE_H-item[1].y/base.PT))
                        elif item[0]=='qu':
                            quad=item[1]
                            pts.extend((q.x/base.PT,base.PAGE_H-q.y/base.PT) for q in [quad.ul,quad.ur,quad.lr,quad.ll])
                        elif item[0]=='re':
                            rect=item[1]
                            pts.extend((q.x/base.PT,base.PAGE_H-q.y/base.PT) for q in [rect.tl,rect.tr,rect.br,rect.bl])
                    if pts:cuts.append(Polygon(pts))
                if color and math.dist(color,(154/255,57/255,113/255))<.02 and abs(width-.9)<.03:hinges+=1
                for item in drawing['items']:
                    if item[0]=='l' and abs(abs(item[2].x-item[1].x)/base.PT-40)<.005 and abs(item[1].y-item[2].y)<.01:cal+=1
            targets=[u.shape() for u in pages[index]['units']]
            pdf_cuts.append(len(cuts)==len(targets) and all(g.is_valid and min(g.symmetric_difference(q).area for q in targets)<.05 for g in cuts))
            pdf_cal.append(cal>0);pdf_hinges.append(hinges==sum(bool(u.hinge_id) for u in pages[index]['units']))
            for word in p.get_text('words'):
                words[word[4]]+=1
                if word[4] in {s['id'] for s in seams}:
                    box=Polygon([(word[0]/base.PT,base.PAGE_H-word[1]/base.PT),(word[2]/base.PT,base.PAGE_H-word[1]/base.PT),(word[2]/base.PT,base.PAGE_H-word[3]/base.PT),(word[0]/base.PT,base.PAGE_H-word[3]/base.PT)])
                    tabs=[Polygon([u.transform(pid,q) for q in tab.exterior.coords]) for u in pages[index]['units'] for pid in u.ids for edge,tab in panels[pid].tabs.items() if panels[pid].edges[edge]==word[4]]
                    if not any(tab.buffer(.02).covers(box) for tab in tabs):label_errors.append(word[4])
                if word[0]<7.7*base.PT or word[2]>(base.PAGE_W-7.7)*base.PT or word[1]<7.7*base.PT or word[3]>(base.PAGE_H-7.7)*base.PT:clipped.append([index+1,word[4]])
    check('pdf_cut_vectors_match_geometry',all(pdf_cuts),pdf_cuts)
    check('pdf_fold_count',all(pdf_hinges),pdf_hinges)
    check('pdf_40mm_calibration',all(pdf_cal),pdf_cal)
    check('pdf_codes_on_glue_tabs_only',all(words[s['id']]==(0 if s['hinge'] else 1) for s in seams) and not label_errors,label_errors or 'One concealed code per glue tab; none on decorated faces')
    check('pdf_no_face_names_on_artwork',all(words[pid]==0 for pid in panels),'Panel names moved to assembly map')
    check('pdf_text_margins',not clipped,clipped)
    svg_checks=[]
    for i,path in enumerate(sorted((out/'svg_pages').glob('*.svg'))):
        root=ET.parse(path).getroot();targets=[u.shape() for u in pages[i]['units']]
        cuts=[n for n in root if n.tag.endswith('polygon') and n.get('stroke')==CUT]
        polys=[Polygon([(float(x),base.PAGE_H-float(y)) for x,y in (p.split(',') for p in n.get('points').split())]) for n in cuts]
        cal=any(n.tag.endswith('line') and abs(abs(float(n.get('x2','0'))-float(n.get('x1','0')))-40)<.001 and n.get('y1')==n.get('y2') for n in root)
        svg_checks.append(root.get('width')==f'{base.PAGE_W}mm' and root.get('height')==f'{base.PAGE_H}mm' and len(polys)==len(targets) and all(g.is_valid and min(g.symmetric_difference(q).area for q in targets)<.05 for g in polys) and cal)
    check('svg_size_vectors_calibration',len(svg_checks)==len(pages) and all(svg_checks),svg_checks)
    with fitz.open(out/'assembly_guide.pdf') as guide:
        clipped_guide=[word[4] for p in guide for word in p.get_text('words') if word[0]<0 or word[1]<0 or word[2]>p.rect.width or word[3]>p.rect.height]
        map_words=Counter(w[4] for p in list(guide)[2:] for w in p.get_text('words'))
        check('guide_seam_map_has_both_mates',all(map_words[s['id']]==2 for s in seams),'All seam pairs labeled on reference diagrams')
        check('guide_complete_within_page',len(guide)==2+len(pages) and not clipped_guide,clipped_guide)
    return tests
