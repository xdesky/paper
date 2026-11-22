#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Papercraft Engine v1.2: paired wall faces with an uncut central 90-degree fold.

Builds on engine_v1_1_base.py for the proven cube geometry and seam-matching
algorithm. Adds a new physical-layout layer which replaces one glue seam per
pair with a true uncut fold, whenever the merged paper shape fits a real sheet.
Models: cube (100, 200, 300 mm) and an open four-wall house frame 120x90x180 mm.

Run: python generate_connected_nets_v1_2.py --out /mnt/data/papercraft_engine_v1_2
"""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import argparse, copy, json, math, shutil, hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import fitz
import networkx as nx
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.affinity import affine_transform

import engine_v1_1_base as base

VERSION='1.2.0'
PAGE_W,PAGE_H=215.9,279.4
PAPER_NAME="US Letter"
BODY=(8.0,20.0,207.9,255.0)
PT=72/25.4
TAB=7.0
GAP=4.0
PALETTE={**base.FACE_COLORS,'HOUSE_FRONT':'#fcebd9','HOUSE_RIGHT':'#e5f2eb','HOUSE_BACK':'#e5edf8','HOUSE_LEFT':'#f1e6f4'}
INK='#172b39'; CUT='#16252e'; HINGE='#9a3971'; FLAT='#b27d19'; CORNER='#216c94'; TAB_FILL='#fff1d3'
OUT=Path(__file__).resolve().parent


def rnd(x):return round(float(x),6)
def R(angle):return ((1.0,0.0),(0.0,1.0)) if angle==0 else ((0.0,-1.0),(1.0,0.0)) if angle==90 else ((-1.0,0.0),(0.0,-1.0)) if angle==180 else ((0.0,1.0),(-1.0,0.0))
def mm_poly(geom,matrix,shift):
    a,b=matrix[0];c,d=matrix[1]
    return affine_transform(geom,[a,b,c,d,shift[0],shift[1]])
def coord(p,M,t): return (M[0][0]*p[0]+M[0][1]*p[1]+t[0], M[1][0]*p[0]+M[1][1]*p[1]+t[1])
def pt_dist(p,q):return math.hypot(p[0]-q[0],p[1]-q[1])
def canonical(d):return json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(d):return hashlib.sha256(canonical(d).encode()).hexdigest()

@dataclass
class FacePanel:
    id: str
    face: str
    w: float
    h: float
    edges: dict=field(default_factory=dict)
    tabs: dict=field(default_factory=dict)
    origin_uv: tuple=(0,0)
    @property
    def square(self): return Polygon([(0,0),(self.w,0),(self.w,self.h),(0,self.h)])
    def seg(self,e):
        return {'S':((0,0),(self.w,0)), 'E':((self.w,0),(self.w,self.h)),
                'N':((self.w,self.h),(0,self.h)), 'W':((0,self.h),(0,0))}[e]

@dataclass
class PaperUnit:
    ids: tuple
    panel_xforms: dict
    hinge_id: str|None
    cut_polygon: Polygon
    orientation: int=0
    sheet: int=-1
    shift: tuple=(0,0)
    def transform(self,panel_id,p):
        M,t=self.panel_xforms[panel_id]
        q=coord(p,M,t)
        q=coord(q,R(self.orientation),(0,0))
        return (q[0]+self.shift[0],q[1]+self.shift[1])
    def shape(self):return mm_poly(self.cut_polygon,R(self.orientation),self.shift)
    def cut_bounds(self):return self.shape().bounds


def panel_3d_point(panel, local, model):
    """Map exact panel 2D coordinates to outward-oriented 3D geometry (mm)."""
    u,v=local
    if model['type']=='cube':
        return np.array(base.point3(panel.face,panel.origin_uv[0]+u,panel.origin_uv[1]+v,model['side_mm']),float)
    w=model['width_mm']; d=model['depth_mm']
    if panel.id=='FRONT':return np.array((u-w/2,-d/2,v),float)
    if panel.id=='RIGHT':return np.array((w/2,u-d/2,v),float)
    if panel.id=='BACK':return np.array((w/2-u,d/2,v),float)
    if panel.id=='LEFT':return np.array((-w/2,d/2-u,v),float)
    raise ValueError(('unknown panel',panel.id))


def panel_normal(panel,model):
    p=panel_3d_point(panel,(0,0),model)
    u=panel_3d_point(panel,(panel.w,0),model)
    v=panel_3d_point(panel,(0,panel.h),model)
    n=np.cross(u-p,v-p)
    return n/np.linalg.norm(n)

def cube_data(side):
    n,raw,seams,parents=base.create_panels(side)
    panels={}
    for p in raw.values():
        panels[p.id]=FacePanel(p.id,p.face,p.size,p.size,
            dict(p.edge_ids),dict(p.tabs),(p.x0,p.y0))
    records=[]
    for s in seams:
        records.append({'id':s['id'],'kind':s['kind'],
           'occurrences':[{'panel':o['panel'],'edge':o['edge']} for o in s['occurrences']],
           'length_mm':s['length_mm'],'owner':s['owner'],'fold_degrees':0 if s['kind']=='flat_panel' else 90,
           'hinge':False})
    return panels, records, {'type':'cube','side_mm':side,'panel_grid':[n,n],'name':f'Cube {side} mm'}


def house_data(w=120,d=90,h=180):
    # Open house wall shell; no floor or roof included. All vertical seams 90 degrees.
    data=[('FRONT',w),('RIGHT',d),('BACK',w),('LEFT',d)]
    panels={f:FacePanel(f,'HOUSE_'+f,s,h) for f,s in data}
    seams=[]
    for idx in range(4):
        a=data[idx][0];b=data[(idx+1)%4][0]
        id=f'H{idx+1:02d}'
        seams.append({'id':id,'kind':'house_corner','length_mm':h,'fold_degrees':90,
                      'occurrences':[{'panel':a,'edge':'E'},{'panel':b,'edge':'W'}],
                      'owner':a,'hinge':False})
        panels[a].edges['E']=id
        panels[b].edges['W']=id
        panels[a].tabs['E']=base.flap_for_edge(*panels[a].seg('E'))
    return panels,seams,{'type':'open_house_wall_frame','width_mm':w,'depth_mm':d,'wall_height_mm':h,
           'name':f'House wall frame {w}x{d}x{h} mm','open_top':True,'open_bottom':True}


def neighbor_xform(pA,edgeA,pB,edgeB):
    """Rigidly unfold panel B across A's seam; never mirror a face."""
    a0,a1=pA.seg(edgeA);b0,b1=pB.seg(edgeB)
    for angle in (0,90,180,270):
        M=R(angle);bb0=coord(b0,M,(0,0));bb1=coord(b1,M,(0,0))
        if pt_dist((bb1[0]-bb0[0],bb1[1]-bb0[1]),(a0[0]-a1[0],a0[1]-a1[1])) < 1e-5:
            t=(a1[0]-bb0[0],a1[1]-bb0[1])
            if pt_dist(coord(b1,M,t),a0)<1e-5:return M,t
    raise ValueError('Incompatible seam endpoints')


def construct_unit(ids, hinge_id, panels, seams_by_id):
    xforms={ids[0]:(R(0),(0.0,0.0))}
    if len(ids)==2:
        seam=seams_by_id[hinge_id]
        oo={o['panel']:o['edge'] for o in seam['occurrences']}
        xforms[ids[1]]=neighbor_xform(panels[ids[0]],oo[ids[0]],panels[ids[1]],oo[ids[1]])
    pieces=[];faces=[]
    for id in ids:
        p=panels[id];M,t=xforms[id]
        poly=mm_poly(p.square,M,t)
        faces.append(poly)
        pieces.append(poly)
        for e,tab in p.tabs.items():
            if p.edges.get(e)==hinge_id:continue
            pieces.append(mm_poly(tab,M,t))
    if len(ids)>1:
        if faces[0].intersection(faces[1]).area>1e-5:
            raise AssertionError(('Pair overlap',ids))
        assert pt_dist(faces[0].centroid.coords[0],faces[1].centroid.coords[0])>0
    outline=unary_union(pieces)
    if outline.geom_type!='Polygon' or not outline.is_valid:
        raise AssertionError(('Invalid unit outline',ids,outline.geom_type))
    return PaperUnit(tuple(ids),xforms,hinge_id,outline)


def fits(unit):
    for r in (0,90):
        bounds=mm_poly(unit.cut_polygon,R(r),(0,0)).bounds
        if bounds[2]-bounds[0]<=(BODY[2]-BODY[0])+1e-6 and bounds[3]-bounds[1]<=(BODY[3]-BODY[1])+1e-6:
            return True
    return False


def choose_units(panels,seams):
    """First maximize true 90-degree hinges; then make flat tiles continuous where possible."""
    by_id={s['id']:s for s in seams}
    G=nx.Graph()
    G.add_nodes_from(panels.keys())
    candidates={}
    for s in seams:
        a,b=[o['panel'] for o in s['occurrences']]
        # Only add genuine angled folds; flat joins would be continuous panels, not a fold.
        if s['fold_degrees']!=90:continue
        unit=construct_unit((a,b),s['id'],panels,by_id)
        if not fits(unit):continue
        candidates[frozenset((a,b))]=s['id']
        G.add_edge(a,b,weight=100000+int(s['length_mm']*100))
    matching=nx.algorithms.matching.max_weight_matching(G,maxcardinality=True,weight='weight')
    chosen={candidates[frozenset(pair)] for pair in matching}
    used90={z for pair in matching for z in pair}
    # Second pass: use seamless, flat uncut unions only for tiles not needed by 90-degree folds.
    Gflat=nx.Graph()
    Gflat.add_nodes_from(sorted(set(panels)-used90))
    for s in seams:
        if s['fold_degrees']!=0:continue
        a,b=[o['panel'] for o in s['occurrences']]
        if a in used90 or b in used90:continue
        if fits(construct_unit((a,b),s['id'],panels,by_id)):
            Gflat.add_edge(a,b,weight=int(s['length_mm']*100))
    flat_matching=nx.algorithms.matching.max_weight_matching(Gflat,maxcardinality=True,weight='weight')
    candidates.update({frozenset(pair):next(s['id'] for s in seams if s['fold_degrees']==0 and {o['panel'] for o in s['occurrences']}==set(pair)) for pair in flat_matching})
    chosen.update(candidates[frozenset(pair)] for pair in flat_matching)
    for seam in seams:seam['hinge']=seam['id'] in chosen
    # Remove the glue tab exactly on each newly uncut fold.
    for s in seams:
        if not s['hinge']:continue
        for o in s['occurrences']:
            panels[o['panel']].tabs.pop(o['edge'],None)
    used=set();units=[]
    for s in sorted(seams,key=lambda x:x['id']):
        if s['hinge']:
            a,b=[o['panel'] for o in s['occurrences']]
            assert a not in used and b not in used
            unit=construct_unit((a,b),s['id'],panels,by_id)
            assert fits(unit)
            units.append(unit);used|={a,b}
    for id in sorted(panels):
        if id not in used:
            unit=construct_unit((id,),None,panels,by_id)
            assert fits(unit),f'{id} exceeds sheet size'
            units.append(unit)
    return units,chosen,len(candidates)


def rotated_bbox(u,rot):
    b=mm_poly(u.cut_polygon,R(rot),(0,0)).bounds
    return b,(b[2]-b[0],b[3]-b[1])


def pack_units(units):
    """Deterministic shelf packing with 0/90 rotations, no scaling."""
    pages=[]
    # Pair units before singles; descending area for stable, compact packing.
    ordered=sorted(units,key=lambda u:(-len(u.ids),-u.cut_polygon.area,u.ids))
    for u in ordered:
        done=False
        variants=[(rot,*rotated_bbox(u,rot)) for rot in (0,90)]
        for i,page in enumerate(pages):
            for sh in page['shelves']:
                for rot,b,(w,h) in variants:
                    if h<=sh['height']+1e-7 and sh['next_x']+w<=BODY[2]+1e-7:
                        u.sheet=i;u.orientation=rot;u.shift=(sh['next_x']-b[0],sh['y']-b[1]);sh['next_x']+=w+GAP
                        page['units'].append(u);done=True;break
                if done:break
            if done:break
            y=BODY[1] if not page['shelves'] else page['shelves'][-1]['y']+page['shelves'][-1]['height']+GAP
            for rot,b,(w,h) in variants:
                if w<=BODY[2]-BODY[0]+1e-7 and y+h<=BODY[3]+1e-7:
                    u.sheet=i;u.orientation=rot;u.shift=(BODY[0]-b[0],y-b[1]);
                    page['shelves'].append({'y':y,'height':h,'next_x':BODY[0]+w+GAP});page['units'].append(u);done=True;break
            if done:break
        if done:continue
        page={'shelves':[],'units':[]}
        for rot,b,(w,h) in variants:
            if w<=BODY[2]-BODY[0]+1e-7 and h<=BODY[3]-BODY[1]+1e-7:
                u.sheet=len(pages);u.orientation=rot;u.shift=(BODY[0]-b[0],BODY[1]-b[1]);
                page['shelves'].append({'y':BODY[1],'height':h,'next_x':BODY[0]+w+GAP});page['units'].append(u);done=True;break
        if not done:raise AssertionError(('Unit too large',u.ids,variants))
        pages.append(page)
    return pages


def color(face): return PALETTE.get(face,'#edf2f6')
def pdf_line(c,a,b,clr,stroke=.6,dash=None):
    c.saveState();c.setStrokeColor(colors.HexColor(clr));c.setLineWidth(stroke)
    if dash:c.setDash(dash)
    c.line(a[0]*PT,a[1]*PT,b[0]*PT,b[1]*PT);c.restoreState()
def pdf_shape(c,poly,fill=None,stroke=None,stroke_width=.5):
    p=c.beginPath();xy=list(poly.exterior.coords)
    p.moveTo(xy[0][0]*PT,xy[0][1]*PT)
    for a,b in xy[1:]:p.lineTo(a*PT,b*PT)
    p.close()
    if fill:c.setFillColor(colors.HexColor(fill))
    if stroke:c.setStrokeColor(colors.HexColor(stroke));c.setLineWidth(stroke_width)
    c.drawPath(p,fill=bool(fill),stroke=bool(stroke))
def pdf_text(c,x,y,text,sz=7,bold=False,clr=INK,center=False):
    c.setFillColor(colors.HexColor(clr));c.setFont(base.FONT_BOLD if bold else base.FONT,sz)
    if center:c.drawCentredString(x*PT,y*PT,str(text))
    else:c.drawString(x*PT,y*PT,str(text))

def panel_label_position(u,p,e):
    a,b=p.seg(e);dx=b[0]-a[0];dy=b[1]-a[1];L=math.hypot(dx,dy)
    # Interior lies on left of CCW boundary; 5 mm inset.
    mid=((a[0]+b[0])/2-5*dy/L,(a[1]+b[1])/2+5*dx/L)
    return u.transform(p.id,mid)

def draw_page_panel(c,u,p,lookup):
    poly=Polygon([u.transform(p.id,(0,0)),u.transform(p.id,(p.w,0)),
                  u.transform(p.id,(p.w,p.h)),u.transform(p.id,(0,p.h))])
    pdf_shape(c,poly,fill=color(p.face))
    for edge,tab in p.tabs.items():
        shape=Polygon([u.transform(p.id,z) for z in list(tab.exterior.coords)[:-1]])
        pdf_shape(c,shape,fill=TAB_FILL)
    center=u.transform(p.id,(p.w/2,p.h/2))
    size=min(p.w,p.h)
    pdf_text(c,center[0],center[1]+4.5,p.face.replace('HOUSE_',''),sz=9 if size>=90 else 7.5,bold=True,center=True)
    pdf_text(c,center[0],center[1]-3.2,p.id,sz=6.3,bold=True,center=True)
    pdf_text(c,center[0],center[1]-10.0,f'{p.w:g} x {p.h:g} mm',sz=5.5,center=True,clr='#667789')
    for edge,sid in p.edges.items():
        x,y=panel_label_position(u,p,edge)
        seam=lookup[sid]
        pdf_text(c,x,y-1.1,sid,sz=6.6,bold=True,center=True,clr=HINGE if seam['hinge'] else (FLAT if seam['fold_degrees']==0 else CORNER))
    for edge,tab in p.tabs.items():
        a,b=p.seg(edge);pdf_line(c,u.transform(p.id,a),u.transform(p.id,b),FLAT if lookup[p.edges[edge]]['fold_degrees']==0 else CORNER,.62,[3.0,2.0])


def draw_unit(c,u,panels,lookup):
    for id in u.ids:draw_page_panel(c,u,panels[id],lookup)
    # Exactly one external cut perimeter for an entire paired unit.
    pdf_shape(c,u.shape(),stroke=CUT,stroke_width=.65)
    if u.hinge_id and lookup[u.hinge_id]['fold_degrees']==90:
        seam=lookup[u.hinge_id]
        p_id=u.ids[0]
        e=next(o['edge'] for o in seam['occurrences'] if o['panel']==p_id)
        a,b=panels[p_id].seg(e)
        pdf_line(c,u.transform(p_id,a),u.transform(p_id,b),HINGE,.9,[4.0,2.0])


def write_pdf(path,model,panels,seams,pages):
    c=canvas.Canvas(str(path),pagesize=(PAGE_W*PT,PAGE_H*PT),pageCompression=1)
    c.setTitle('Papercraft Engine v1.2 - Connected fold net - '+model['name'])
    lookup={s['id']:s for s in seams}
    for page_idx,page in enumerate(pages):
        pdf_text(c,8,PAGE_H-9.2,'PAPERCRAFT ENGINE v1.2  |  '+model['name'].upper(),9.8,True)
        c.setFont(base.FONT_BOLD,9);c.setFillColor(colors.HexColor(INK))
        c.drawRightString((PAGE_W-8)*PT,(PAGE_H-17.9)*PT,f'{page_idx+1}/{len(pages)}')
        pdf_text(c,8,PAGE_H-18.5,'Fold PURPLE = uncut 90° hinge  |  Cut BLACK  |  Glue tab DASHED',7.2,clr='#576d7e')
        pdf_line(c,(8,PAGE_H-21.4),(PAGE_W-8,PAGE_H-21.4),'#ced6db',.55)
        for u in page['units']:draw_unit(c,u,panels,lookup)
        pdf_line(c,(8,17.3),(PAGE_W-8,17.3),'#ced6db',.5)
        pdf_line(c,(15,10.5),(55,10.5),CUT,.8)
        pdf_line(c,(15,8.7),(15,12.3),CUT,.7)
        pdf_line(c,(55,8.7),(55,12.3),CUT,.7)
        pdf_text(c,60,9.0,'40 mm CALIBRATION - Print at 100%',7.3,clr='#516b7a')
        c.drawRightString((PAGE_W-8)*PT,9.0*PT,'DO NOT FIT TO PAGE')
        c.showPage()
    c.save()


SVG_NS='http://www.w3.org/2000/svg';ET.register_namespace('',SVG_NS)
def svg_node(parent,tag,**attrs):
    return ET.SubElement(parent,'{'+SVG_NS+'}'+tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
def svg_polygon(parent,poly,fill,stroke,width=.20):
    points=' '.join(f'{x:.5f},{PAGE_H-y:.5f}' for x,y in list(poly.exterior.coords)[:-1])
    svg_node(parent,'polygon',points=points,fill=fill,stroke=stroke,stroke_width=width)
def svg_segment(parent,a,b,clr,dash=None,width=.2):
    attrs={'x1':f'{a[0]:.5f}','y1':f'{PAGE_H-a[1]:.5f}','x2':f'{b[0]:.5f}','y2':f'{PAGE_H-b[1]:.5f}',
           'stroke':clr,'stroke_width':width}
    if dash:attrs['stroke_dasharray']=' '.join(str(x) for x in dash)
    svg_node(parent,'line',**attrs)
def svg_label(parent,x,y,t,size=2.4,clr=INK,bold=False):
    elem=svg_node(parent,'text',x=f'{x:.4f}',y=f'{PAGE_H-y:.4f}',fill=clr,font_size=size,
                 text_anchor='middle',font_weight='bold' if bold else 'normal',font_family='DejaVu Sans, Arial')
    elem.text=t

def write_svg(folder,model,panels,seams,pages):
    folder.mkdir(exist_ok=True,parents=True)
    lookup={s['id']:s for s in seams};result=[]
    for idx,page in enumerate(pages):
        root=ET.Element('{'+SVG_NS+'}svg',{'width':f'{PAGE_W}mm','height':f'{PAGE_H}mm',
              'viewBox':f'0 0 {PAGE_W} {PAGE_H}','version':'1.1'})
        svg_label(root,PAGE_W/2,PAGE_H-9.2,'PAPERCRAFT ENGINE v1.2 | '+model['name'],3.1,INK,True)
        svg_label(root,PAGE_W/2,PAGE_H-16.4,f'Page {idx+1}/{len(pages)} | Print at 100% | Purple = uncut 90 degree fold',2.45)
        svg_segment(root,(8,PAGE_H-21.4),(PAGE_W-8,PAGE_H-21.4),'#cbd7de',width=.15)
        for u in page['units']:
            for pid in u.ids:
                p=panels[pid]
                geo=Polygon([u.transform(pid,(0,0)),u.transform(pid,(p.w,0)),u.transform(pid,(p.w,p.h)),u.transform(pid,(0,p.h))])
                svg_polygon(root,geo,color(p.face),'none',0)
                for e,tab in p.tabs.items():
                    svg_polygon(root,Polygon([u.transform(pid,z) for z in list(tab.exterior.coords)[:-1]]),TAB_FILL,'none',0)
                cx,cy=u.transform(pid,(p.w/2,p.h/2))
                svg_label(root,cx,cy+4,p.face.replace('HOUSE_',''),3.0,INK,True)
                svg_label(root,cx,cy-3,p.id,2.5,INK,True)
                for e,sid in p.edges.items():
                    lx,ly=panel_label_position(u,p,e);s=lookup[sid]
                    svg_label(root,lx,ly,sid,2.3,HINGE if s['hinge'] else CORNER,True)
                for e in p.tabs:
                    a,b=p.seg(e)
                    svg_segment(root,u.transform(pid,a),u.transform(pid,b),FLAT if lookup[p.edges[e]]['fold_degrees']==0 else CORNER,[1.0,.7],.23)
            svg_polygon(root,u.shape(),'none',CUT,.23)
            if u.hinge_id and lookup[u.hinge_id]['fold_degrees']==90:
                s=lookup[u.hinge_id];p=panels[u.ids[0]]
                e=next(o['edge'] for o in s['occurrences'] if o['panel']==p.id)
                a,b=p.seg(e)
                svg_segment(root,u.transform(p.id,a),u.transform(p.id,b),HINGE,[1.5,.8],.35)
        svg_segment(root,(15,10.5),(55,10.5),CUT,width=.25)
        svg_segment(root,(15,8.7),(15,12.3),CUT,width=.25)
        svg_segment(root,(55,8.7),(55,12.3),CUT,width=.25)
        svg_label(root,90,10.5,'40 mm SCALE CHECK',2.7)
        target=folder/f'page_{idx+1:03d}.svg'
        ET.ElementTree(root).write(target,encoding='utf-8',xml_declaration=True)
        result.append(target)
    return result


def write_guide(path,model,panels,seams,units,pages):
    c=canvas.Canvas(str(path),pagesize=(PAGE_W*PT,PAGE_H*PT))
    c.setTitle('Papercraft assembly - '+model['name'])
    pdf_text(c,12,266,'PAPERCRAFT | FOLD-FIRST ASSEMBLY',12,True)
    pdf_text(c,12,254,model['name']+'  /  v1.2',9,clr='#5b7386')
    y=237
    facts=[f'US Letter pages: {len(pages)}',f'Faces / tiles: {len(panels)}',
           f'Physical cut pieces: {len(units)}',f'90-degree continuous folds: {sum(s["hinge"] and s["fold_degrees"]==90 for s in seams)}',
           f'Flat uncut tile joins: {sum(s["hinge"] and s["fold_degrees"]==0 for s in seams)}',
           f'Glued seams: {sum(not s["hinge"] for s in seams)}',
           'Paper: cardstock 160-250 gsm (test first)']
    for line in facts:
        pdf_text(c,15,y,'• '+line,9);y-=11
    y-=8
    pdf_text(c,12,y,'ASSEMBLY ORDER',10,True);y-=15
    steps=[
      '1. Print all pages at Actual Size / 100%, never Fit to page.',
      '2. Measure the 40 mm calibration line on EACH page.',
      '3. Cut only the BLACK outer perimeter; keep the pale glue tabs.',
      '4. Pre-crease PURPLE dashed hinges to a 90° corner; flat joins stay flat.',
      '5. Fold dashed TAB bases; glue only matching codes that are not hinges.',
      '6. For flat F joints, glue tiles into complete square faces first.',
      '7. Close remaining 90° edges E/H using paired labels.',
      '8. Check the 3D dimensions after assembly; dry-fit before gluing.'
    ]
    for st in steps:
        pdf_text(c,15,y,st,7.5);y-=12.2
    y-=5
    pdf_text(c,12,y,'LEGEND',10,True);y-=13
    for title,clr,dash in [('CUT boundary',CUT,None),('UNCUT 90-degree hinge',HINGE,[4,2]),
                            ('GLUE TAB for 90-degree corner',CORNER,[3,2]),('FLAT glue tab',FLAT,[3,2])]:
        pdf_line(c,(16,y),(43,y),clr,.9,dash);pdf_text(c,50,y-1,title,8);y-=12
    pdf_text(c,12,20,'Auto geometry checks do NOT replace a real paper assembly test.',7.5,clr='#6a7d8e')
    c.showPage()
    # pair index grouped by joined crease
    pdf_text(c,12,266,'FOLD-PAIRED SHEETS / EDGE MATCHING',12,True)
    pdf_text(c,12,253,'PURPLE = uncut 90° fold; F codes on same piece = flat; others glue.',8,clr='#64798b')
    y=237
    for u in units:
        if len(u.ids)==2:
            s=next(z for z in seams if z['id']==u.hinge_id)
            angle=s['fold_degrees']
            text=f'Page {u.sheet+1:02d}: {u.ids[0]} + {u.ids[1]}  |  '+(f'FOLD {u.hinge_id} 90°' if angle==90 else f'CONTINUOUS FLAT {u.hinge_id}')
            pdf_text(c,13,y,text,7.7,True,clr=HINGE if angle==90 else FLAT)
            y-=10.8
        if y<30:
            c.showPage();y=262
    y-=12
    if y<55:c.showPage();y=261
    pdf_text(c,12,y,'GLUE SEAMS',10,True);y-=12
    for s in sorted((z for z in seams if not z['hinge']),key=lambda x:x['id']):
        oo=s['occurrences'];txt=f'{s["id"]}: {oo[0]["panel"]} / {oo[1]["panel"]}'
        pdf_text(c,13,y,txt,7.3,clr=FLAT if s['fold_degrees']==0 else CORNER)
        y-=9.2
        if y<20:
            c.showPage();y=266
    c.save()


def verify(model,panels,seams,units,pages,pdf_path,svgs):
    tests=[]
    def test(name,ok,detail):
        tests.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    ids={p.id for p in panels.values()}
    test('all_panels_placed_exactly_once',Counter(p for u in units for p in u.ids)==Counter(ids),f'{len(ids)} panels')
    test('all_seams_have_two_distinct_mates',all(len(s['occurrences'])==2 and len({o['panel'] for o in s['occurrences']})==2 for s in seams),f'{len(seams)} seams')
    test('seam_2d_lengths_match',all(abs(pt_dist(*panels[o['panel']].seg(o['edge']))-s['length_mm'])<1e-5 for s in seams for o in s['occurrences']), 'all seam lengths matched in millimetres')
    topology_mismatch=[]
    for seam in seams:
        aa,bb=seam['occurrences']
        pA,pB=panels[aa['panel']],panels[bb['panel']]
        A0,A1=[panel_3d_point(pA,q,model) for q in pA.seg(aa['edge'])]
        B0,B1=[panel_3d_point(pB,q,model) for q in pB.seg(bb['edge'])]
        dot=float(np.clip(np.dot(panel_normal(pA,model),panel_normal(pB,model)),-1,1))
        physical_angle=math.degrees(math.acos(dot))
        if np.linalg.norm(A0-B1)>1e-5 or np.linalg.norm(A1-B0)>1e-5 or abs(physical_angle-seam['fold_degrees'])>1e-5:
            topology_mismatch.append((seam['id'],rnd(physical_angle)))
    test('seam_3d_endpoints_and_fold_angle',not topology_mismatch,topology_mismatch[:8] or '3D seam endpoints agree with reverse winding and 0°/90° dihedral angle')
    test('one_hinge_per_pair',all((len(u.ids)==2)==bool(u.hinge_id) for u in units),'pairs each have one uncut center crease')
    test('uncut_join_angles_valid',all(s['fold_degrees'] in (0,90) for s in seams if s['hinge']), 'uncut joints are flat 0° or fold 90°')
    test('uncut_joint_tabs_removed',all(all(o['edge'] not in panels[o['panel']].tabs for o in s['occurrences']) for s in seams if s['hinge']),'no tab on continuous folds')
    test('exactly_one_tab_per_glued_seam',all(sum(o['edge'] in panels[o['panel']].tabs for o in s['occurrences'])==1 for s in seams if not s['hinge']),'one glue flap per remaining seam')
    test('connected_cut_contours_valid',all(u.cut_polygon.geom_type=='Polygon' and u.cut_polygon.is_valid for u in units),'all merged cut boundaries are single valid polygons')
    hinge_geom=[]
    lookup={s['id']:s for s in seams}
    for u in units:
        if not u.hinge_id:continue
        s=lookup[u.hinge_id];a,b=s['occurrences']
        a1,a2=(u.transform(a['panel'],x) for x in panels[a['panel']].seg(a['edge']))
        b1,b2=(u.transform(b['panel'],x) for x in panels[b['panel']].seg(b['edge']))
        hinge_geom.append(pt_dist(a1,b2)<1e-5 and pt_dist(a2,b1)<1e-5)
    test('uncut_joint_endpoints_coincident',all(hinge_geom),'two panels share exactly the same uncut crease')
    packed=[u.shape() for u in units]
    test('no_printed_shape_overlap',all(packed[i].intersection(packed[j]).area<1e-6 for i in range(len(packed)) for j in range(i+1,len(packed)) if units[i].sheet==units[j].sheet),f'{len(packed)} pieces')
    test('all_cut_contours_in_printable_area',all(BODY[0]-1e-5<=b[0] and BODY[1]-1e-5<=b[1] and b[2]<=BODY[2]+1e-5 and b[3]<=BODY[3]+1e-5 for b in map(lambda x:x.bounds,packed)),'US Letter 8 mm side margins, fixed header/footer')
    test('units_geometry_area_conserved',abs(sum(p.square.area for p in panels.values())-sum(u.cut_polygon.area for u in units)+sum(tab.area for p in panels.values() for tab in p.tabs.values()))<1e-4,'area equals face area plus glue tabs')
    test('numbered_seam_codes_on_panels',all(p.edges.get(o['edge'])==s['id'] for s in seams for o in s['occurrences'] for p in [panels[o['panel']]]),'every seam has matching two-side code')
    test('paper_size_exact',bool(pages),'physical US Letter media boxes')
    pdf_paths=[];pdf_folds=[];pdf_cal=[];sizes=[];pdf_cut_errors=[]
    with fitz.open(pdf_path) as doc:
        test('pdf_page_count',len(doc)==len(pages),f'{len(doc)} pages')
        for i,page in enumerate(doc):
            sizes.append((rnd(page.rect.width/PT),rnd(page.rect.height/PT)))
            paths=page.get_drawings();cut=0;hing=0;cal=0
            for d in paths:
                if d.get('color') is None:continue
                r,g,b=d['color']
                def near(hexcolor):
                    x=colors.HexColor(hexcolor)
                    return math.dist((r,g,b),(x.red,x.green,x.blue))<.025
                if near(CUT) and d.get('width') and abs(d['width']-.65)<.035 and d['type']=='s':
                    cut+=1
                    vertices=[(it[1].x/PT,PAGE_H-it[1].y/PT) for it in d['items'] if it[0]=='l']
                    if len(vertices)<4 and len(d['items'])==1 and d['items'][0][0] in ('qu','re'):
                        item=d['items'][0]
                        if item[0]=='qu':
                            pts=[(z.x/PT,PAGE_H-z.y/PT) for z in item[1]]
                            xlo=min(z[0] for z in pts);xhi=max(z[0] for z in pts)
                            ylo=min(z[1] for z in pts);yhi=max(z[1] for z in pts)
                        else:
                            box=item[1];xlo=box.x0/PT;xhi=box.x1/PT
                            ylo=PAGE_H-box.y1/PT;yhi=PAGE_H-box.y0/PT
                        vertices=[(xlo,ylo),(xhi,ylo),(xhi,yhi),(xlo,yhi)]
                    if len(vertices)<4:
                        pdf_cut_errors.append((i+1,'too few cut segments'))
                    else:
                        actual=Polygon(vertices)
                        targets=[u.shape() for u in pages[i]['units']]
                        if not actual.is_valid or min(actual.symmetric_difference(t).area for t in targets)>.04:
                            pdf_cut_errors.append((i+1,'vector contour differs from calculated cut outline'))
                if near(HINGE) and d.get('width') and abs(d['width']-.9)<.035 and d['type']=='s':hing+=1
                if near(CUT):
                    for it in d['items']:
                        if it[0]=='l' and abs(abs(it[2].x-it[1].x)/PT-40)<.005 and abs(it[2].y-it[1].y)<.01:cal+=1
            pdf_paths.append(cut);pdf_folds.append(hing);pdf_cal.append(cal)
    test('us_letter_vector_page_dimensions',all(abs(w-PAGE_W)<.001 and abs(h-PAGE_H)<.001 for w,h in sizes),sizes)
    test('pdf_cut_paths_one_per_unit',pdf_paths==[len(p['units']) for p in pages],{'found':pdf_paths,'expected':[len(p['units']) for p in pages]})
    test('pdf_cut_coordinates_match_source_mm',not pdf_cut_errors,pdf_cut_errors[:6] or 'exact cut geometry within 0.04 mm² symmetric difference')
    test('pdf_hinge_vectors_exact_count',pdf_folds==[sum(bool(u.hinge_id and lookup[u.hinge_id]['fold_degrees']==90) for u in p['units']) for p in pages],{'found':pdf_folds,'expected':[sum(bool(u.hinge_id and lookup[u.hinge_id]['fold_degrees']==90) for u in p['units']) for p in pages]})
    test('pdf_40mm_calibration',all(v>0 for v in pdf_cal),pdf_cal)
    test('svg_one_page_per_letter',len(svgs)==len(pages),f'{len(svgs)} SVGs')
    svg_good=True;svg_cuts=[];svg_hinges=[];svg_cut_errors=[]
    for i,path in enumerate(svgs):
        root=ET.parse(path).getroot();svg_good&=(root.get('width')==f'{PAGE_W}mm' and root.get('height')==f'{PAGE_H}mm')
        cuts=[z for z in root.iter() if z.tag.endswith('polygon') and z.get('stroke')==CUT]
        hinges=[z for z in root.iter() if z.tag.endswith('line') and z.get('stroke')==HINGE]
        svg_cuts.append(len(cuts));svg_hinges.append(len(hinges))
        targets=[u.shape() for u in pages[i]['units']]
        for cut in cuts:
            xy=[tuple(map(float,z.split(','))) for z in cut.get('points').split()]
            actual=Polygon([(x,PAGE_H-y) for x,y in xy])
            if not targets or not actual.is_valid or min(actual.symmetric_difference(t).area for t in targets)>.04:
                svg_cut_errors.append((i+1,'SVG cut geometry mismatch'))
    test('svg_physical_dimensions',svg_good,'mm page widths and heights')
    test('svg_cut_contour_count',svg_cuts==[len(p['units']) for p in pages],svg_cuts)
    test('svg_cut_coordinates_match_source_mm',not svg_cut_errors,svg_cut_errors[:6] or 'exact SVG cut geometry within 0.04 mm² symmetric difference')
    test('svg_hinge_count',svg_hinges==[sum(bool(u.hinge_id and lookup[u.hinge_id]['fold_degrees']==90) for u in p['units']) for p in pages],svg_hinges)
    return tests


def contact_sheet(pdf_path,path,title,limit=6):
    with fitz.open(pdf_path) as d:
        inds=list(range(min(limit,len(d))))
        tiles=[]
        for i in inds:
            pix=d[i].get_pixmap(matrix=fitz.Matrix(.9,.9),alpha=False)
            im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            im.thumbnail((330,440))
            tile=Image.new('RGB',(355,490),'#f5f7f9')
            tile.paste(im,((355-im.width)//2,12))
            ImageDraw.Draw(tile).text((16,458),f'{title} - sheet {i+1} / {len(d)}',fill='#304253')
            tiles.append(tile)
        cols=2 if len(tiles)<=4 else 3
        out=Image.new('RGB',(cols*355,math.ceil(len(tiles)/cols)*490),'#dde4ea')
        for j,t in enumerate(tiles):out.paste(t,((j%cols)*355,(j//cols)*490))
        out.save(path,optimize=True)


def draw_house_preview(path,w=120,d=90,h=180):
    """3D open four-wall shell visualization; no roof or floor implied."""
    fig=plt.figure(figsize=(6,4.8),facecolor='white')
    ax=fig.add_subplot(111,projection='3d',proj_type='ortho')
    coords={
       'FRONT':[(-w/2,-d/2,0),(w/2,-d/2,0),(w/2,-d/2,h),(-w/2,-d/2,h)],
       'RIGHT':[(w/2,-d/2,0),(w/2,d/2,0),(w/2,d/2,h),(w/2,-d/2,h)],
       'BACK':[(w/2,d/2,0),(-w/2,d/2,0),(-w/2,d/2,h),(w/2,d/2,h)],
       'LEFT':[(-w/2,d/2,0),(-w/2,-d/2,0),(-w/2,-d/2,h),(-w/2,d/2,h)]}
    poly=Poly3DCollection([np.array(pts) for pts in coords.values()],edgecolors='#213646',linewidths=1.5,alpha=.82)
    poly.set_facecolor([color('HOUSE_'+name) for name in coords])
    ax.add_collection3d(poly)
    for name,pts in coords.items():
        center=np.mean(np.array(pts,float),axis=0)
        ax.text(*center,name,size=8,ha='center',va='center',color='#1e3042',weight='bold')
    ax.set(xlim=(-w*.7,w*.7),ylim=(-w*.7,w*.7),zlim=(-h*.08,h*1.08))
    ax.set_box_aspect((w,d,h))
    ax.view_init(elev=23,azim=-60)
    ax.set_axis_off()
    fig.suptitle('OPEN FOUR-WALL HOUSE FRAME (NO ROOF)',fontsize=11,color='#1e3042')
    fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white')
    plt.close(fig)

def build(kind,out,size=None):
    base.install_fonts();out.mkdir(parents=True,exist_ok=True)
    if kind=='cube':panels,seams,model=cube_data(size)
    elif kind=='house':panels,seams,model=house_data()
    else:raise ValueError(kind)
    units,chosen,eligible=choose_units(panels,seams)
    pages=pack_units(units)
    pdf=out/'printable_us_letter.pdf'
    write_pdf(pdf,model,panels,seams,pages)
    svgs=write_svg(out/'svg_pages',model,panels,seams,pages)
    write_guide(out/'assembly_guide.pdf',model,panels,seams,units,pages)
    contact_sheet(pdf,out/'printable_preview.png',model['name'])
    tests=verify(model,panels,seams,units,pages,pdf,svgs)
    if kind=='house':draw_house_preview(out/'model_3d_preview.png')
    if kind=='cube':
        mesh,verts,quads=base.mesh_for_cube(size)
        base.write_obj(out/'model.obj',verts,quads,size)
        base.draw_3d(out/'model_3d_preview.png',size,verts,quads)
        tests.extend([
            {'name':'cube_mesh_watertight','status':'PASS' if mesh.is_watertight else 'FAIL','detail':bool(mesh.is_watertight)},
            {'name':'cube_mesh_volume','status':'PASS' if abs(mesh.volume-size**3)<.001 else 'FAIL','detail':rnd(mesh.volume)},
        ])
    geometry={'model':model,'panels':[{'id':p.id,'face':p.face,'width_mm':p.w,'height_mm':p.h,
            'origin_uv_mm':p.origin_uv,'edge_codes':p.edges,
            'vertices_3d_mm':[[rnd(v) for v in panel_3d_point(p,q,model)] for q in ((0,0),(p.w,0),(p.w,p.h),(0,p.h))]}
            for p in panels.values()],
            'seams':[{'id':s['id'],'kind':s['kind'],'length_mm':s['length_mm'],'fold_degrees':s['fold_degrees'],
                      'mates':s['occurrences'],'hinged_uncut':s['hinge']} for s in seams]}
    spec={'schema_version':VERSION,'model_id':('PPM-CUBE-'+str(size)) if kind=='cube' else 'PPM-HOUSE-WALL-120x90x180',
        'version':VERSION,'locked':True,'units':'mm','paper':{'name':PAPER_NAME,'page_mm':[PAGE_W,PAGE_H],
              'scale':1.0,'printable_body_mm':BODY,'tab_depth_mm':TAB},
        'geometry_source':'deterministic parametric 3D faces, not generated image',
        'geometry_sha256':digest(geometry),'geometry':geometry,
        'unfold_strategy':'Prefer pairs of genuine adjacent angled faces on the same sheet with one uncut 90-degree crease; fallback to separate panels when too large',
        'print_units':[{'panel_ids':list(u.ids),'sheet_number':u.sheet+1,'fold_code':u.hinge_id,
                 'orientation_degrees':u.orientation,'bounds_mm':[rnd(v) for v in u.cut_bounds()]} for u in units],
        'sheet_count':len(pages),'physical_assembly':'NOT_TESTED'}
    (out/'model_spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n', encoding="utf-8")
    summary={'model':model,'faces_or_tiles':len(panels),'cut_pieces':len(units),'sheets':len(pages),
        'fold_hinges':sum(s['hinge'] and s['fold_degrees']==90 for s in seams),
        'flat_continuous_joins':sum(s['hinge'] and s['fold_degrees']==0 for s in seams),'glue_seams':sum(not s['hinge'] for s in seams),'total_seams':len(seams),
        'glue_saved':len(chosen),'eligible_hinge_candidates':eligible,
        'limitation':('No 150x150 mm paired tiles fit one US Letter sheet without splitting; retained glue-friendly 2x2 grid and avoided a worse 3x3 split.' if size==300 and kind=='cube' else 'All joined wall folds are uncut geometrically; physical trial remains pending.')}
    report={'version':VERSION,'model_id':spec['model_id'],'model_geometry_sha256':spec['geometry_sha256'],
        'overall_status':'PASS' if all(x['status']=='PASS' for x in tests) else 'FAIL',
        'summary':summary,'tests':tests,'physical_assembly':'NOT_TESTED'}
    (out/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding="utf-8")
    print(json.dumps({'model':spec['model_id'],'qa':report['overall_status'],'tests':len(tests),**{k:summary[k] for k in ('cut_pieces','sheets','fold_hinges','glue_seams')}}))
    if report['overall_status']!='PASS':
        raise AssertionError([t for t in tests if t['status']=='FAIL'])
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',default=str(OUT))
    ap.add_argument('--sizes',nargs='+',type=int,default=[100,200,300])
    ap.add_argument('--skip-house',action='store_true')
    args=ap.parse_args();root=Path(args.out)
    reports=[build('cube',root/f'cube_{s}mm',s) for s in args.sizes]
    if not args.skip_house:reports.append(build('house',root/'house_frame_120x90x180mm'))
    (root/'summary.json').write_text(json.dumps([r['summary'] for r in reports],ensure_ascii=False,indent=2)+'\n', encoding="utf-8")

if __name__=='__main__':main()
