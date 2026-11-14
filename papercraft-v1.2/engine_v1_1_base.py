#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Papercraft Engine v1.1: deterministic multi-page panel unfolding for cubes.

Based on v1.0: fixed 3D face geometry, vector output, cut/fold/glue semantics,
machine-checkable Model Spec, and physical-scale PDF verification.

Version 1.1 adds per-face panel subdivision at the printable-page limit,
3D-coordinate based seam pairing, one glue tab per seam, cross-page matching IDs,
first-fit shelf packing, multi-page PDF + per-page SVG, a Vietnamese assembly guide,
and machine-readable detailed QA.

This is a CUBE generator, not arbitrary mesh unfolding or image-to-3D.
Run: python generate_papercraft_v1_1.py --sizes 100 200 300 --out /path/to/output
Dependencies: reportlab shapely trimesh numpy PyMuPDF matplotlib Pillow.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import fitz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from shapely.affinity import translate
from shapely.geometry import Polygon
from shapely.ops import unary_union
import trimesh

VERSION = '1.1.0'
PAGE_W, PAGE_H = 215.9, 279.4
MARGIN = 8.0
BODY_X0, BODY_X1 = 8.0, 207.9
BODY_Y0, BODY_Y1 = 20.0, 255.0
GAP = 4.0
TAB_DEPTH = 7.0
PT = 72.0/25.4
CALIBRATION_LENGTH = 40.0
FACES = ['FRONT','RIGHT','BACK','LEFT','TOP','BOTTOM']
FACE_SHORT = {'FRONT':'FR','RIGHT':'RI','BACK':'BA','LEFT':'LE','TOP':'TO','BOTTOM':'BO'}
FACE_COLORS = {'FRONT':'#e8f2f7','RIGHT':'#ecf2e7','BACK':'#f0edf8','LEFT':'#f7eede','TOP':'#e3f2ed','BOTTOM':'#f2e9ef'}
COLORS = {'ink':'#233241','muted':'#65798c','rule':'#c7d4dc','cut':'#16252e', 'fold_flat':'#b27d19','fold_corner':'#216c94','tab':'#fff2d3'}
FONT = 'PCEDejaVu'
FONT_BOLD = 'PCEDejaVuBold'


def install_fonts():
    if FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT, '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))


def canon(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',',':'))


def sha(data):
    return hashlib.sha256(canon(data).encode('utf-8')).hexdigest()


def nice(v):
    return round(float(v), 7)


def point3(face, u, v, side):
    """Face local 2D is CCW when seen from outside, origin bottom left."""
    h=side/2
    return {
        'FRONT':(u-h,-h,v-h),
        'RIGHT':(h,u-h,v-h),
        'BACK':(h-u,h,v-h),
        'LEFT':(-h,h-u,v-h),
        'TOP':(u-h,v-h,h),
        'BOTTOM':(u-h,h-v,-h),
    }[face]


def coordinate_key(p):
    return tuple(round(float(v),5) for v in p)


def key_for_segment(a,b):
    return tuple(sorted([coordinate_key(a),coordinate_key(b)]))


def edge_uv(x0,y0,x1,y1,edge):
    return {
        'S':((x0,y0),(x1,y0)),
        'E':((x1,y0),(x1,y1)),
        'N':((x1,y1),(x0,y1)),
        'W':((x0,y1),(x0,y0))
    }[edge]


def full_uv(side, edge):
    return edge_uv(0.0,0.0,side,side,edge)


def outer_local(edge, tile_size):
    return edge_uv(0,0,tile_size,tile_size,edge)


def flap_for_edge(a,b,depth=TAB_DEPTH):
    dx=b[0]-a[0];dy=b[1]-a[1]
    length=math.hypot(dx,dy)
    assert length>2*depth
    ux,uy=dx/length,dy/length
    # Points are CCW around panel; right normal points outside.
    nx,ny=uy,-ux
    chamfer=min(8.0,length*.17)
    return Polygon([a,b,(b[0]-chamfer*ux+depth*nx,b[1]-chamfer*uy+depth*ny),
                  (a[0]+chamfer*ux+depth*nx,a[1]+chamfer*uy+depth*ny)])


@dataclass
class Panel:
    id: str
    face: str
    row: int
    col: int
    x0: float
    y0: float
    size: float
    edge_ids: dict = field(default_factory=dict)
    tabs: dict = field(default_factory=dict)
    outline: Polygon | None = None
    sheet: int | None = None
    px: float = 0.0
    py: float = 0.0
    @property
    def square(self):
        s=self.size
        return Polygon([(0,0),(s,0),(s,s),(0,s)])
    def pos(self,p):
        return (self.px+p[0],self.py+p[1])
    def placed(self):
        return translate(self.outline,self.px,self.py)
    def to_json(self):
        return {'id':self.id,'face':self.face,'row':self.row+1,'column':self.col+1,
                'face_uv_origin_mm':[nice(self.x0),nice(self.y0)], 'dimensions_mm':[nice(self.size),nice(self.size)],
                'sheet':self.sheet+1, 'placement_mm':[nice(self.px),nice(self.py)],
                'outline_bounds_mm':[nice(z) for z in self.placed().bounds],
                'boundary_seam_ids':{e:self.edge_ids[e] for e in ('S','E','N','W')},
                'glue_tabs':sorted(self.tabs)}


class ShelfPage:
    def __init__(self): self.shelves=[]; self.positions=[]
    def place(self,panel):
        bounds=panel.outline.bounds
        w,h=bounds[2]-bounds[0],bounds[3]-bounds[1]
        for shelf in self.shelves:
            if h<=shelf['height']+1e-8 and shelf['next_x']+w<=BODY_X1+1e-8:
                x=shelf['next_x'];y=shelf['y'];shelf['next_x']+=w+GAP
                self.positions.append((panel.id,x,y,w,h));return (x-bounds[0],y-bounds[1])
        new_y=BODY_Y0 if not self.shelves else self.shelves[-1]['y']+self.shelves[-1]['height']+GAP
        if new_y+h<=BODY_Y1+1e-8 and BODY_X0+w<=BODY_X1+1e-8:
            self.shelves.append({'y':new_y,'height':h,'next_x':BODY_X0+w+GAP})
            self.positions.append((panel.id,BODY_X0,new_y,w,h))
            return (BODY_X0-bounds[0],new_y-bounds[1])
        return None


def create_panels(side):
    # A square must fit within the shorter printable area after two glue tabs.
    usable_w=BODY_X1-BODY_X0
    max_tile=usable_w-2*TAB_DEPTH-2.0
    n=max(1,math.ceil(side/max_tile))
    tile=side/n
    panels={}; occurrences=defaultdict(list)
    physical_parent_edges={}
    for face in FACES:
        for edge in 'SENW':
            a,b=full_uv(side,edge)
            key=key_for_segment(point3(face,*a,side),point3(face,*b,side))
            physical_parent_edges.setdefault(key,[]).append((face,edge))
        for r in range(n):
            for c in range(n):
                pid=f'{FACE_SHORT[face]}-R{r+1}C{c+1}'
                x0=c*tile;y0=r*tile
                pan=Panel(pid,face,r,c,x0,y0,tile)
                panels[pid]=pan
                for edge in 'SENW':
                    (a,b)=edge_uv(x0,y0,x0+tile,y0+tile,edge)
                    ka=point3(face,*a,side);kb=point3(face,*b,side)
                    k=key_for_segment(ka,kb)
                    occurrences[k].append({'panel':pid,'face':face,'edge':edge,
                        'a3':ka,'b3':kb,'a_uv':a,'b_uv':b,'length_mm':math.dist(ka,kb)})
    assert len(physical_parent_edges)==12
    assert all(len(x)==2 for x in physical_parent_edges.values())
    parent_id={k:f'E{i:02d}' for i,k in enumerate(sorted(physical_parent_edges),1)}
    paired=[];unpaired=[]
    for k,occs in occurrences.items():
        if len(occs)!=2:
            unpaired.append((k,len(occs)))
            continue
        kind='flat_panel' if occs[0]['face']==occs[1]['face'] else 'cube_corner'
        if kind=='cube_corner':
            par=[]
            for o in occs:
                A,B=full_uv(side,o['edge'])
                par.append(key_for_segment(point3(o['face'],*A,side),point3(o['face'],*B,side)))
            if par[0]!=par[1]: raise AssertionError(('Outer edge mismatch',occs))
            pkey=par[0]
        else:pkey=None
        paired.append({'key':k,'kind':kind,'parent':pkey,'occurrences':occs})
    if unpaired: raise RuntimeError(f'Unpaired 3D edges: {unpaired[:5]}')
    corner_by_parent=defaultdict(list);flat=[]
    for p in paired:
        if p['kind']=='cube_corner':corner_by_parent[p['parent']].append(p)
        else:flat.append(p)
    seams=[]
    for idx,rec in enumerate(sorted(flat,key=lambda x:(FACES.index(x['occurrences'][0]['face']),x['key'])),1):
        rec['id']=f'F{idx:03d}';seams.append(rec)
    for parent in sorted(corner_by_parent):
        group=corner_by_parent[parent]
        A=np.array(parent[0],float);B=np.array(parent[1],float);V=B-A
        def segment_t(rec):
            point=np.mean(np.array(rec['key'],float),axis=0)
            return float(np.dot(point-A,V)/np.dot(V,V))
        for k,rec in enumerate(sorted(group,key=segment_t),1):
            rec['id']=f'{parent_id[parent]}.{k:02d}';seams.append(rec)
    for rec in seams:
        occs=rec['occurrences']
        if rec['kind']=='flat_panel':
            owner=min(occs,key=lambda o:o['panel'])
        else:
            owner=min(occs,key=lambda o:(FACES.index(o['face']),o['panel']))
        rec['owner']=owner['panel']
        rec['length_mm']=nice(occs[0]['length_mm'])
        for o in occs:
            panel=panels[o['panel']]
            assert o['edge'] not in panel.edge_ids
            panel.edge_ids[o['edge']]=rec['id']
        own_pan=panels[owner['panel']]
        tab=flap_for_edge(*outer_local(owner['edge'],own_pan.size))
        own_pan.tabs[owner['edge']]=tab
    for panel in panels.values():
        assert len(panel.edge_ids)==4
        panel.outline=unary_union([panel.square,*panel.tabs.values()])
        assert panel.outline.geom_type=='Polygon' and panel.outline.is_valid
    return n,panels,seams,parent_id


def pack_panels(panels):
    pages=[]
    for panel in sorted(panels.values(),key=lambda p:(-p.outline.area,FACES.index(p.face),p.row,p.col)):
        done=False
        for i,page in enumerate(pages):
            placed=page.place(panel)
            if placed:
                panel.sheet=i;panel.px,panel.py=placed;done=True;break
        if not done:
            page=ShelfPage();pos=page.place(panel)
            if pos is None: raise RuntimeError(f'Panel too big for sheet: {panel.id}')
            panel.sheet=len(pages);panel.px,panel.py=pos;pages.append(page)
    return pages


def mesh_for_cube(side):
    verts=sorted({coordinate_key(point3(face,u,v,side)) for face in FACES for u,v in [(0,0),(side,0),(side,side),(0,side)]})
    index={v:i for i,v in enumerate(verts)}
    quads={face:[index[coordinate_key(point3(face,u,v,side))] for u,v in [(0,0),(side,0),(side,side),(0,side)]] for face in FACES}
    tris=[]
    for f in FACES:
        a,b,c,d=quads[f];tris.extend([(a,b,c),(a,c,d)])
    mesh=trimesh.Trimesh(vertices=np.array(verts,float),faces=np.array(tris,int),process=False)
    return mesh,verts,quads


def write_obj(path,verts,quads,side):
    with open(path,'w',encoding='utf-8') as o:
        o.write(f'# Papercraft Engine {VERSION}, cube {side:g} mm - outward winding\n')
        for xyz in verts: o.write('v %.7f %.7f %.7f\n'%xyz)
        for f,inds in quads.items(): o.write(f'\ng {f}\nf '+ ' '.join(str(i+1) for i in inds)+'\n')


def draw_3d(path,side,verts,quads):
    fig=plt.figure(figsize=(5.5,4.5),facecolor='white')
    ax=fig.add_subplot(111,projection='3d',proj_type='ortho')
    cube_polys=[]
    for name in FACES:
        cube_polys.append(np.array([verts[i] for i in quads[name]],float))
    pc=Poly3DCollection(cube_polys,edgecolors='#314657',linewidths=1.1,alpha=1.0)
    pc.set_facecolor([FACE_COLORS[x] for x in FACES])
    ax.add_collection3d(pc)
    for f,poly in zip(FACES,cube_polys):
        # Only label the three visible faces in the chosen projection.
        if f not in ('FRONT','RIGHT','TOP'): continue
        ctr=poly.mean(axis=0)
        normal=np.cross(poly[1]-poly[0],poly[2]-poly[1]);normal=normal/np.linalg.norm(normal)
        ctr=ctr+normal*side*.012
        ax.text(*ctr,f,size=8,ha='center',va='center',weight='bold',color='#152b3b')
    m=side*.64
    ax.set(xlim=(-m,m),ylim=(-m,m),zlim=(-m,m))
    ax.set_box_aspect((1,1,1))
    ax.view_init(elev=23,azim=-55)
    ax.set_axis_off()
    fig.tight_layout(pad=0.5)
    fig.savefig(path,dpi=170,bbox_inches='tight',facecolor='white')
    plt.close(fig)


def set_rgb_pdf(c,hexstr): c.setStrokeColor(colors.HexColor(hexstr))

def polygon_pdf(c,points,fill=None,stroke=None,width_pt=.42):
    path=c.beginPath();p=points[0];path.moveTo(p[0]*PT,p[1]*PT)
    for p in points[1:]:path.lineTo(p[0]*PT,p[1]*PT)
    path.close()
    if fill is not None:c.setFillColor(colors.HexColor(fill))
    if stroke is not None:c.setStrokeColor(colors.HexColor(stroke));c.setLineWidth(width_pt)
    c.drawPath(path,stroke=int(stroke is not None),fill=int(fill is not None))


def pdf_text(c,x,y,txt,size=8,bold=False,color=COLORS['ink'],center=False):
    c.setFillColor(colors.HexColor(color))
    c.setFont(FONT_BOLD if bold else FONT,size)
    if center:c.drawCentredString(x*PT,y*PT,txt)
    else:c.drawString(x*PT,y*PT,txt)


def pdf_line(c,a,b,color=COLORS['rule'],width_pt=.5,dash=None):
    c.saveState();c.setStrokeColor(colors.HexColor(color));c.setLineWidth(width_pt)
    if dash:c.setDash(dash)
    c.line(a[0]*PT,a[1]*PT,b[0]*PT,b[1]*PT);c.restoreState()


def label_position(panel,edge):
    a,b=outer_local(edge,panel.size)
    dx=b[0]-a[0];dy=b[1]-a[1]
    L=math.hypot(dx,dy);nx,ny=dy/L,-dx/L
    # Label on the material side of the seam, not on the tab.
    return panel.pos(((a[0]+b[0])/2-5.0*nx,(a[1]+b[1])/2-5.0*ny))


def draw_panel_pdf(c,panel,by_id):
    material=panel.square
    poly=list(material.exterior.coords)[:-1]
    polygon_pdf(c,[panel.pos(p) for p in poly],fill=FACE_COLORS[panel.face])
    for edge,tab in panel.tabs.items():
        polygon_pdf(c,[panel.pos(p) for p in list(tab.exterior.coords)[:-1]],fill=COLORS['tab'])
    polygon_pdf(c,[panel.pos(p) for p in list(panel.outline.exterior.coords)[:-1]],stroke=COLORS['cut'],width_pt=.54)
    for edge,tab in panel.tabs.items():
        a,b=outer_local(edge,panel.size)
        seam=by_id[panel.edge_ids[edge]]
        pdf_line(c,panel.pos(a),panel.pos(b),COLORS['fold_flat'] if seam['kind']=='flat_panel' else COLORS['fold_corner'],.58,[3,2.2])
    mx=panel.px+panel.size/2;my=panel.py+panel.size/2
    pdf_text(c,mx,my+5,panel.face,size=12,bold=True,center=True)
    pdf_text(c,mx,my-3,f'{panel.id}  |  {panel.size:g} × {panel.size:g} mm',size=7.0,center=True,color=COLORS['muted'])
    pdf_text(c,mx,my-11,'OUTSIDE / MẶT NGOÀI',size=6.3,center=True,color=COLORS['muted'])
    for edge,seam_id in panel.edge_ids.items():
        x,y=label_position(panel,edge)
        pdf_text(c,x,y-1.5,seam_id,size=6.8,bold=True,center=True,
                 color=COLORS['fold_flat'] if by_id[seam_id]['kind']=='flat_panel' else COLORS['fold_corner'])


def write_pdf(path,side,panels,pages,seams):
    c=canvas.Canvas(str(path),pagesize=(PAGE_W*PT,PAGE_H*PT),pageCompression=1)
    c.setTitle(f'Papercraft Engine v1.1 - Cube {side:g} mm - US Letter')
    by_id={s['id']:s for s in seams}
    for idx in range(len(pages)):
        pdf_text(c,8,270.5,f'PAPERCRAFT ENGINE 1.1   |   CUBE {side:g} mm',size=10.5,bold=True)
        c.setFont(FONT_BOLD,10);c.setFillColor(colors.HexColor(COLORS['ink']))
        c.drawRightString(207.9*PT,270.5*PT,f'PAGE {idx+1:02d}/{len(pages):02d}')
        pdf_text(c,8,263.1,'US Letter | Actual size 100% | Cut BLACK | Fold AMBER = flat | Fold BLUE = corner',size=7.4,color=COLORS['muted'])
        pdf_line(c,(8,258.5),(207.9,258.5),COLORS['rule'],.6)
        for pan in panels.values():
            if pan.sheet==idx:draw_panel_pdf(c,pan,by_id)
        pdf_line(c,(8,17.2),(207.9,17.2),COLORS['rule'],.5)
        # A known, explicit 40 mm PDF vector line, independent of page content.
        pdf_line(c,(15,10.5),(55,10.5),COLORS['cut'],.8)
        pdf_line(c,(15,8.7),(15,12.3),COLORS['cut'],.8)
        pdf_line(c,(55,8.7),(55,12.3),COLORS['cut'],.8)
        pdf_text(c,60,9.0,'40 mm scale check – Measure before cutting',size=7,color=COLORS['muted'])
        c.drawRightString(207.9*PT,9.0*PT,'DO NOT FIT TO PAGE  ·  100%',)
        c.showPage()
    c.save()


SVG_NS='http://www.w3.org/2000/svg'
ET.register_namespace('',SVG_NS)
def svg_tag(root,name,**attrs):
    return ET.SubElement(root,f'{{{SVG_NS}}}{name}',{k.replace('_','-'):str(v) for k,v in attrs.items()})


def svg_poly(root,coords,fill='none',stroke='none',width=.18):
    pts=' '.join(f'{x:.5f},{PAGE_H-y:.5f}' for x,y in coords)
    svg_tag(root,'polygon',points=pts,fill=fill,stroke=stroke,stroke_width=f'{width:.3f}',stroke_linejoin='round')

def svg_line(root,a,b,color,width=.18,dash=None):
    attr={'x1':f'{a[0]:.5f}','y1':f'{PAGE_H-a[1]:.5f}', 'x2':f'{b[0]:.5f}','y2':f'{PAGE_H-b[1]:.5f}',
          'stroke':color,'stroke_width':width}
    if dash:attr['stroke_dasharray']=dash
    svg_tag(root,'line',**attr)

def svg_text(root,x,y,txt,size=3,bold=False,color=COLORS['ink'],anchor='start'):
    e=svg_tag(root,'text',x=f'{x:.4f}',y=f'{PAGE_H-y:.4f}',fill=color,font_size=f'{size:.3f}',
       font_family='DejaVu Sans, Noto Sans, sans-serif',font_weight='700' if bold else '400',text_anchor=anchor)
    e.text=str(txt)


def write_svg_pages(folder,side,panels,pages,seams):
    folder.mkdir(exist_ok=True,parents=True)
    by_id={s['id']:s for s in seams}
    files=[]
    for idx,page in enumerate(pages):
        root=ET.Element(f'{{{SVG_NS}}}svg',{'width':f'{PAGE_W}mm','height':f'{PAGE_H}mm','viewBox':f'0 0 {PAGE_W} {PAGE_H}'})
        svg_tag(root,'rect',x='0',y='0',width=f'{PAGE_W}',height=f'{PAGE_H}',fill='#ffffff')
        svg_text(root,8,270.5,f'PAPERCRAFT ENGINE 1.1 | CUBE {side:g} mm',3.6,True)
        svg_text(root,207.9,270.5,f'PAGE {idx+1:02d}/{len(pages):02d}',3.3,True,anchor='end')
        svg_text(root,8,263.1,'US Letter | Actual size 100% | Cut BLACK | Fold AMBER = flat | Fold BLUE = corner',2.25,color=COLORS['muted'])
        svg_line(root,(8,258.5),(207.9,258.5),COLORS['rule'],.15)
        for pan in panels.values():
            if pan.sheet!=idx:continue
            svg_poly(root,[pan.pos(p) for p in list(pan.square.exterior.coords)[:-1]],fill=FACE_COLORS[pan.face])
            for edge,tab in pan.tabs.items():svg_poly(root,[pan.pos(p) for p in list(tab.exterior.coords)[:-1]],fill=COLORS['tab'])
            svg_poly(root,[pan.pos(p) for p in list(pan.outline.exterior.coords)[:-1]],stroke=COLORS['cut'],width=.19)
            for edge,tab in pan.tabs.items():
                a,b=outer_local(edge,pan.size)
                seam=by_id[pan.edge_ids[edge]]
                svg_line(root,pan.pos(a),pan.pos(b),COLORS['fold_flat'] if seam['kind']=='flat_panel' else COLORS['fold_corner'],.21,'1.1,0.8')
            mx=pan.px+pan.size/2;my=pan.py+pan.size/2
            svg_text(root,mx,my+5,pan.face,4.0,True,anchor='middle')
            svg_text(root,mx,my-3,f'{pan.id} | {pan.size:g} x {pan.size:g} mm',2.45,color=COLORS['muted'],anchor='middle')
            svg_text(root,mx,my-11,'OUTSIDE / MAT NGOAI',2.1,color=COLORS['muted'],anchor='middle')
            for edge,seam_id in pan.edge_ids.items():
                x,y=label_position(pan,edge)
                svg_text(root,x,y-1.5,seam_id,2.4,True,
                    COLORS['fold_flat'] if by_id[seam_id]['kind']=='flat_panel' else COLORS['fold_corner'],anchor='middle')
        svg_line(root,(8,17.2),(207.9,17.2),COLORS['rule'],.16)
        svg_line(root,(15,10.5),(55,10.5),COLORS['cut'],.26)
        for x in (15,55):svg_line(root,(x,8.7),(x,12.3),COLORS['cut'],.26)
        svg_text(root,60,9.0,'40 mm scale check - Measure before cutting',2.45,color=COLORS['muted'])
        svg_text(root,207.9,9.0,'DO NOT FIT TO PAGE - 100%',2.45,color=COLORS['muted'],anchor='end')
        path=folder/f'page_{idx+1:03d}.svg';ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
        files.append(path)
    return files


def guide_pdf(path,side,n,panels,seams,sheets,preview_path):
    c=canvas.Canvas(str(path),pagesize=(PAGE_W*PT,PAGE_H*PT),pageCompression=1)
    c.setTitle(f'Assembly Guide - Cube {side:g} mm - v1.1')
    # page 1
    pdf_text(c,13,265,'HƯỚNG DẪN LẮP RÁP',size=16,bold=True)
    pdf_text(c,13,255,f'Hình lập phương {side:g} × {side:g} × {side:g} mm | Bản v1.1.0',size=9,color=COLORS['muted'])
    pdf_line(c,(13,250),(203,250))
    if preview_path.exists():
        c.drawImage(str(preview_path),15*PT,158*PT,width=88*PT,height=85*PT, preserveAspectRatio=True,anchor='c',mask='auto')
    pdf_text(c,110,235,'THÔNG SỐ',size=11,bold=True)
    facts=[f'- {len(panels)} tấm giấy / panel',f'- {sheets} tờ US Letter',f'- {len(seams)} mối nối được đánh mã',
           f'- {sum(s["kind"]=="flat_panel" for s in seams)} mối ghép phẳng (F...)',
           f'- {sum(s["kind"]=="cube_corner" for s in seams)} mối ghép góc (E...)',
           f'- Chia {n} × {n} tấm trên mỗi mặt']
    for i,t in enumerate(facts):pdf_text(c,110,223-i*10.1,t,8.4)
    pdf_line(c,(13,151),(203,151))
    pdf_text(c,13,141,'THỨ TỰ THAO TÁC',size=11,bold=True)
    steps=[
      '1. In toàn bộ PDF tại 100% / Actual Size; KHÔNG chọn Fit to page.',
      '2. Đo vạch 40 mm ở từng tờ để xác nhận tỷ lệ in.',
      '3. Cắt theo đường VIỀN ĐEN của từng panel. Không cắt đường gấp.',
      '4. Gấp tai dán theo NÉT ĐỨT ở phía có tai, hướng vào trong.',
      '5. Nối các cạnh cùng mã Fxxx để ráp các tấm thành 6 MẶT PHẲNG.',
      '6. Nối các cạnh cùng mã Exx.yy thành khối hộp, góc 90°.',
      '7. Để keo khô, rồi đo ba chiều thành phẩm theo mm.'
    ]
    for i,st in enumerate(steps):pdf_text(c,13,128-i*10.1,st,7.9)
    pdf_line(c,(13,51),(203,51))
    pdf_text(c,13,41,'CHÚ GIẢI',size=9.4,bold=True)
    pdf_line(c,(13,32),(29,32),COLORS['cut'],.75);pdf_text(c,33,30.5,'Nét đen liên tục: CẮT',7.4)
    pdf_line(c,(104,32),(120,32),COLORS['fold_flat'],.75,[3,2]);pdf_text(c,124,30.5,'Nét vàng: gập tai nối phẳng',7.4)
    pdf_line(c,(13,23),(29,23),COLORS['fold_corner'],.75,[3,2]);pdf_text(c,33,21.5,'Nét xanh: gập tai góc 90°',7.4)
    pdf_text(c,13,10.2,'Kiểm tra bằng mã không thay thế việc cắt/dán thử bằng giấy thật.',size=7,color=COLORS['muted'])
    c.showPage()
    # page 2: color-coded face assembly
    pdf_text(c,13,264,'SƠ ĐỒ 6 MẶT & MÃ PANEL',size=14,bold=True)
    pdf_text(c,13,253,'Mỗi mặt được ghép từ các ô cùng tiền tố. Đọc mã cạnh ngay trên từng tấm.',size=8,color=COLORS['muted'])
    positions={'TOP':(79,170),'FRONT':(79,103),'BOTTOM':(79,36),'LEFT':(12,103),'RIGHT':(146,103),'BACK':(146,36)}
    L=63.0
    for name,(x,y) in positions.items():
        # Diagram only, not a scale-cut template.
        c.setFillColor(colors.HexColor(FACE_COLORS[name]));c.setStrokeColor(colors.HexColor(COLORS['rule']))
        c.rect(x*PT,y*PT,L*PT,L*PT,fill=1,stroke=1)
        for i in range(1,n):
            v=x+L*i/n;pdf_line(c,(v,y),(v,y+L),COLORS['rule'],.45)
            v=y+L*i/n;pdf_line(c,(x,v),(x+L,v),COLORS['rule'],.45)
        for r in range(n):
            for col in range(n):
                pid=f'{FACE_SHORT[name]}-R{r+1}C{col+1}'
                size=6.2 if n==1 else 5.3
                pdf_text(c,x+(col+.5)*L/n,y+(r+.5)*L/n-1.1,pid,size=size,bold=True,center=True)
        pdf_text(c,x+L/2,y+L+2.8,name,size=6.5,bold=True,center=True)
    pdf_text(c,13,14,'Sơ đồ vị trí là minh họa. Dán theo MÃ CẠNH trên trang in và bảng mã ở trang tiếp.',size=7.0,color=COLORS['muted'])
    c.showPage()
    # page(s) with joint pair lookup; table grouped by type; columns.
    ordered=sorted(seams,key=lambda s:(0 if s['kind']=='flat_panel' else 1,s['id']))
    per_page=48  # 2 columns, 24 entries per column, rows at 9.3 mm.
    for offset in range(0,len(ordered),per_page):
        subset=ordered[offset:offset+per_page]
        pdf_text(c,13,264,'BẢNG TRA MỐI GHÉP',size=14,bold=True)
        pdf_text(c,13,253,'Hai cạnh trùng mã sẽ nối với nhau. F = ghép phẳng; E = ghép góc vuông.',size=8,color=COLORS['muted'])
        for i,s in enumerate(subset):
            col=i//24;row=i%24
            x=13+col*97;y=237-row*9.3
            pair=[o['panel'] for o in s['occurrences']]
            text=f'{s["id"]}  {pair[0]} ↔ {pair[1]}'
            pdf_text(c,x,y,text,6.8,bold=True,color=COLORS['fold_flat'] if s['kind']=='flat_panel' else COLORS['fold_corner'])
        pdf_text(c,13,10.5,f'Mã nối {offset+1} - {offset+len(subset)} / {len(ordered)} | bản v1.1.0',7.5,color=COLORS['muted'])
        c.showPage()
    c.save()


def validate_geometry(side,n,panels,seams,pages,mesh,verts,quads):
    checks=[]
    def test(name,condition,detail,measurement=None):
        checks.append({'check':name,'status':'PASS' if bool(condition) else 'FAIL',
                       'detail':detail,**({'measured':measurement} if measurement is not None else {})})
    test('mesh_vertices_faces_edges',len(verts)==8 and len(quads)==6 and len(mesh.edges_unique)==18,
         '8 vertices, 6 quad faces; triangulated mesh has 18 edges',{'vertices':len(verts),'quad_faces':len(quads),'triangle_edges':len(mesh.edges_unique)})
    test('mesh_closed_and_watertight',mesh.is_watertight,'3D mesh is watertight')
    test('mesh_positive_winding',mesh.is_winding_consistent and mesh.volume>0,'Face winding consistent, volume positive',{'volume_mm3':nice(mesh.volume)})
    test('mesh_dimensions',np.allclose(mesh.extents,[side]*3,atol=1e-8),'All three dimensions equal selected edge length',mesh.extents.tolist())
    test('mesh_volume',abs(mesh.volume-side**3)<1e-5*side**3,'Volume equals side^3')
    expected=6*n*n
    test('panel_count',len(panels)==expected,f'Six faces divided into {n} by {n} panels',len(panels))
    areas=sum(p.square.area for p in panels.values())
    test('panel_area_conservation',abs(areas-6*side*side)<1e-5,'2D material squares cover exactly six cube surfaces',nice(areas))
    for face in FACES:
        ps=[p for p in panels.values() if p.face==face]
        q=[Polygon([(p.x0,p.y0),(p.x0+p.size,p.y0),(p.x0+p.size,p.y0+p.size),(p.x0,p.y0+p.size)]) for p in ps]
        u=unary_union(q)
        test('face_coverage_'+face,u.geom_type=='Polygon' and abs(u.area-side*side)<1e-5 and len(ps)==n*n,
             'Each cube face covered exactly, without gap or area overlap',{'panels':len(ps),'area_mm2':nice(u.area)})
    flat=[s for s in seams if s['kind']=='flat_panel'];corner=[s for s in seams if s['kind']=='cube_corner']
    test('flat_seam_count',len(flat)==12*n*(n-1),'All adjacent panel edges within each face paired',len(flat))
    test('corner_seam_count',len(corner)==12*n,'All physical cube edges paired, split into n aligned segments',len(corner))
    test('unique_seam_ids',len(set(s['id'] for s in seams))==len(seams),'Every seam has a unique stable ID')
    test('paired_occurrences',all(len(s['occurrences'])==2 for s in seams),'Exactly two mating edges per seam')
    test('edge_lengths_match',all(abs(s['occurrences'][0]['length_mm']-s['occurrences'][1]['length_mm'])<1e-7 for s in seams),
         'Mating edge segments have identical length in 3D')
    test('all_panel_edges_accounted',all(len(p.edge_ids)==4 for p in panels.values()),'Every panel edge has a seam assignment')
    test('one_tab_per_seam',sum(len(p.tabs) for p in panels.values())==len(seams),'Exactly one glue tab created for each mating edge')
    test('tab_owner_correct',all(sum(s['id'] in [p.edge_ids[e] for e in p.tabs] for p in panels.values())==1 for s in seams),
         'Each seam has exactly one owner of the glue tab')
    test('tabs_valid',all(tab.is_valid and tab.area>1e-7 for p in panels.values() for tab in p.tabs.values()),
         'Every glue tab is a valid positive-area trapezoid')
    test('panel_outlines_valid',all(p.outline.is_valid and p.outline.geom_type=='Polygon' for p in panels.values()),
         'Cut boundary of each panel and attached tabs is one valid polygon')
    test('sheet_assignment',all(p.sheet is not None and 0<=p.sheet<len(pages) for p in panels.values()),
         'All panels assigned to exactly one US Letter page',{'pages':len(pages)})
    xs=[];ys=[]
    for p in panels.values():
        b=p.placed().bounds;xs.extend([b[0],b[2]]);ys.extend([b[1],b[3]])
    test('printable_bounds',all(p.placed().bounds[0]>=BODY_X0-1e-7 and p.placed().bounds[1]>=BODY_Y0-1e-7 and
                 p.placed().bounds[2]<=BODY_X1+1e-7 and p.placed().bounds[3]<=BODY_Y1+1e-7 for p in panels.values()),
         'All cuts and tabs remain inside defined printable body',{'max_x':max(xs),'max_y':max(ys)})
    collisions=[]
    for sheet in range(len(pages)):
        p_here=[p for p in panels.values() if p.sheet==sheet]
        for i,p in enumerate(p_here):
            for q in p_here[i+1:]:
                if p.placed().intersection(q.placed()).area>1e-6:
                    collisions.append((sheet+1,p.id,q.id))
    test('no_panel_or_tab_overlaps',len(collisions)==0,'Actual cut polygons on each page do not overlap',collisions[:8])
    test('1_to_1_scale',all(abs(p.size*n-side)<1e-8 for p in panels.values()),
         '2D panel dimensions reconstruct the exact requested cube side')
    # Cross-face seams should never mate two segments with differing 3D line endpoints.
    test('cross_face_3d_alignment',all(
         key_for_segment(s['occurrences'][0]['a3'],s['occurrences'][0]['b3'])==
         key_for_segment(s['occurrences'][1]['a3'],s['occurrences'][1]['b3']) for s in corner),
         'Each cube edge pair is physically identical in 3D')
    return checks


def verify_artifacts(pdf_path,svgs,guide_path,side,panels,seams,pages):
    checks=[]
    def test(n,cond,detail,measurement=None): checks.append({'check':n,'status':'PASS' if bool(cond) else 'FAIL',
         'detail':detail,**({'measured':measurement} if measurement is not None else {})})
    pdf_cut_mismatches=[];pdf_fold_mismatches=[];line_counts=[]
    ink=colors.HexColor(COLORS['cut'])
    rgb_expected=np.array((ink.red,ink.green,ink.blue))
    fold_rgbs=[]
    for c in (COLORS['fold_flat'],COLORS['fold_corner']):
        ink_fold=colors.HexColor(c);fold_rgbs.append(np.array((ink_fold.red,ink_fold.green,ink_fold.blue)))
    with fitz.open(pdf_path) as doc:
        test('pdf_pages',len(doc)==len(pages),'Number of PDF sheets equals planned sheets',len(doc))
        sizes=[(p.rect.width/PT,p.rect.height/PT) for p in doc]
        test('pdf_us_letter_dimensions',all(abs(w-PAGE_W)<1e-3 and abs(h-PAGE_H)<1e-3 for w,h in sizes),
             'Every PDF MediaBox is precisely US Letter in mm',sizes[0] if sizes else None)
        words=Counter()
        for page_idx,page in enumerate(doc):
            for item in page.get_text('words'):words[item[4]]+=1
            candidates=[];cuts=[];folds=[]
            for d in page.get_drawings():
                for item in d['items']:
                    if item[0]=='l':
                        length=math.hypot(item[2].x-item[1].x,item[2].y-item[1].y)/PT
                        if abs(length-CALIBRATION_LENGTH)<.005:candidates.append(length)
                if d['type'] in ('s','fs') and d['color'] and np.linalg.norm(np.array(d['color'])-rgb_expected)<.02:
                    coords=[(item[1].x/PT, PAGE_H-item[1].y/PT) for item in d['items'] if item[0]=='l']
                    if len(coords)>=4:cuts.append(Polygon(coords))
                    elif len(d['items'])==1 and d['items'][0][0]=='re':
                        r=d['items'][0][1]
                        cuts.append(Polygon([(r.x0/PT,PAGE_H-r.y1/PT),(r.x1/PT,PAGE_H-r.y1/PT),
                                             (r.x1/PT,PAGE_H-r.y0/PT),(r.x0/PT,PAGE_H-r.y0/PT)]))
                if d['type']=='s' and d['color'] and d['width'] and abs(d['width']-.58)<.03 and len(d['items'])==1 and any(np.linalg.norm(np.array(d['color'])-rgb)<.02 for rgb in fold_rgbs):
                    folds.append(d)
            line_counts.append(len(candidates))
            panel_list=[p for p in panels.values() if p.sheet==page_idx]
            if len(cuts)!=len(panel_list):pdf_cut_mismatches.append((page_idx+1,'path count',len(cuts),len(panel_list)))
            else:
                for geo in cuts:
                    if min(geo.symmetric_difference(p.placed()).area for p in panel_list)>.03:
                        pdf_cut_mismatches.append((page_idx+1,'vector cut differs from source geometry'))
            tabcount=sum(len(p.tabs) for p in panel_list)
            if len(folds)!=tabcount:pdf_fold_mismatches.append((page_idx+1,len(folds),tabcount))
        test('pdf_40mm_calibration',all(v>=1 for v in line_counts),
             'Every PDF sheet contains an actual 40.000 mm vector calibration line',line_counts)
        misses={s['id']:words.get(s['id'],0) for s in seams if words.get(s['id'],0)!=2}
        test('pdf_two_seam_labels',not misses,'Each seam code appears precisely once on each of its two mating panels',misses)
    test('pdf_cut_vectors_exact',not pdf_cut_mismatches,'Extracted PDF cut polygons match calculated panel outline geometry',pdf_cut_mismatches[:8])
    test('pdf_fold_vector_count',not pdf_fold_mismatches,'Every fold base is represented by a PDF vector dashed line',pdf_fold_mismatches[:8])
    test('svg_sheet_count',len(svgs)==len(pages),'One physical-size SVG generated per US Letter page',len(svgs))
    bad=[];cut_svg_mismatches=[]
    for i,f in enumerate(svgs):
        root=ET.parse(f).getroot()
        if root.attrib.get('width')!=f'{PAGE_W}mm' or root.attrib.get('height')!=f'{PAGE_H}mm':bad.append(f.name)
        drawn=[]
        for node in root.iter():
            if not node.tag.endswith('polygon') or node.attrib.get('stroke')!=COLORS['cut']:continue
            coords=[]
            for p in node.attrib['points'].split():
                x,y=map(float,p.split(','));coords.append((x,PAGE_H-y))
            drawn.append(Polygon(coords))
        targets=[p.placed() for p in panels.values() if p.sheet==i]
        if len(drawn)!=len(targets) or any(min(g.symmetric_difference(t).area for t in targets)>.03 for g in drawn):
            cut_svg_mismatches.append((i+1,len(drawn),len(targets)))
    test('svg_physical_size',not bad,'Every SVG has explicit millimeter page dimensions',bad)
    test('svg_cut_vectors_exact',not cut_svg_mismatches,'SVG cut paths match computed panel outline geometry in physical mm',cut_svg_mismatches[:8])
    with fitz.open(guide_path) as g:
        test('assembly_guide_created',len(g)==3,'Assembly guide contains instructions, face diagram and mating-edge index',len(g))
    return checks


def make_spec(side,n,panels,seams,pages,verts,quads):
    core={'geometry':{'shape':'cube','side_mm':side,'vertices_mm':[[nice(v) for v in p] for p in verts],
          'faces':[{'id':f,'vertex_ids':[i+1 for i in quads[f]]} for f in FACES]},
          'panels':[{'id':p.id,'face':p.face,'row':p.row+1,'column':p.col+1,'size_mm':nice(p.size),
                     'origin_uv_mm':[nice(p.x0),nice(p.y0)]} for p in sorted(panels.values(),key=lambda p:p.id)],
          'seams':[{'id':s['id'],'kind':s['kind'],'owner':s['owner'], 'length_mm':s['length_mm'],
                    'mates':[{'panel':o['panel'],'edge':o['edge']} for o in s['occurrences']]}
                   for s in sorted(seams,key=lambda s:s['id'])]}
    spec={'schema_version':'1.1.0','model_id':f'PPM-CUBE-{side:03d}', 'version':VERSION,'locked':True,
          'units':'mm','name':f'Parametric cube {side:g} mm, US Letter multi-page',
          'source':{'kind':'parametric_3d','input':f'cube side {side} mm','confidence':'exact','ai_images_used':False},
          'dimensions_mm':{'width':side,'height':side,'depth':side},
          'paper':{'name':'US Letter','width_mm':PAGE_W,'height_mm':PAGE_H,'safe_margin_mm':MARGIN,
                    'print_scale':1.0,'body_mm':{'x_min':BODY_X0,'x_max':BODY_X1,'y_min':BODY_Y0,'y_max':BODY_Y1},
                    'glue_tab_depth_mm':TAB_DEPTH},
          'unfold_strategy':'individual planar face panels, each cube edge cut and glued; no uncut face-to-face hinges',
          'cut_style':'black solid perimeter',
          'fold_style':{'flat':'amber dashed, tab folded flat under next tile','corner':'blue dashed, tab folded inward 90 degrees'},
          'geometry_sha256':sha(core),
          'model_geometry':core['geometry'],
          'panel_grid':{'rows':n,'columns':n,'tile_mm':nice(side/n)},
          'panel_count':len(panels),'sheet_count':len(pages),
          'panels':[p.to_json() for p in sorted(panels.values(),key=lambda p:p.id)],
          'seams':core['seams'],
          'manufacturing':{'cardstock':'160-250 gsm recommended','physical_assembly_test':'NOT_TESTED'},
          'limitations':['All 12 cube edges are glue seams (no connected fold net).',
                         'Flat joins create slight paper thickness; ideal geometric dimensions neglect card thickness.',
                         'Manual cutting, gluing, calibration and physical fit remain untested.']}
    return spec


def create_contact_sheet(pdf_path,out_path,side,limit=8):
    doc=fitz.open(pdf_path)
    count=len(doc)
    if count<=limit:
        indices=list(range(count))
    else:
        indices=list(range(min(4,count)))+list(range(max(4,count-4),count))
    thumbs=[]
    for idx in indices:
        pg=doc[idx].get_pixmap(matrix=fitz.Matrix(1.0,1.0),alpha=False)
        im=Image.frombytes('RGB',[pg.width,pg.height],pg.samples)
        im.thumbnail((360,460))
        canv=Image.new('RGB',(390,525),'#f5f7f9')
        canv.paste(im,((390-im.width)//2,20))
        d=ImageDraw.Draw(canv)
        d.text((18,492),f'{side} mm   |   Page {idx+1}/{count}',fill='#183248')
        thumbs.append(canv)
    cols=2 if len(thumbs)<=4 else 4
    rows=math.ceil(len(thumbs)/cols)
    sheet=Image.new('RGB',(cols*390,rows*525),'#dfe7eb')
    for i,im in enumerate(thumbs):sheet.paste(im,((i%cols)*390,(i//cols)*525))
    sheet.save(out_path,optimize=True)
    doc.close()


def generate(side,out):
    install_fonts()
    out.mkdir(parents=True,exist_ok=True)
    n,panels,seams,parent_edges=create_panels(side)
    pages=pack_panels(panels)
    mesh,verts,quads=mesh_for_cube(side)
    write_obj(out/'model.obj',verts,quads,side)
    draw_3d(out/'model_3d_preview.png',side,verts,quads)
    pdf=out/'printable_us_letter.pdf';svgdir=out/'svg_pages';guide=out/'assembly_guide.pdf'
    write_pdf(pdf,side,panels,pages,seams)
    svgs=write_svg_pages(svgdir,side,panels,pages,seams)
    guide_pdf(guide,side,n,panels,seams,len(pages),out/'model_3d_preview.png')
    checks=validate_geometry(side,n,panels,seams,pages,mesh,verts,quads)
    checks+=verify_artifacts(pdf,svgs,guide,side,panels,seams,pages)
    spec=make_spec(side,n,panels,seams,pages,verts,quads)
    (out/'model_spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'model_id':spec['model_id'],'version':VERSION,'geometry_sha256':spec['geometry_sha256'],
            'overall_status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',
            'scope':'Automated parametric geometry, seam pairing, tabs, 2D packing, PDF/SVG scale and labels',
            'physical_assembly':{'status':'NOT_TESTED','calibration_by_human':'REQUIRED'},
            'summary':{'cube_side_mm':side,'panel_grid':[n,n], 'tile_mm':nice(side/n),
                      'panels':len(panels),'sheets':len(pages),'glue_seams':len(seams),
                      'flat_join_seams':sum(s['kind']=='flat_panel' for s in seams),
                      'corner_join_segments':sum(s['kind']=='cube_corner' for s in seams),
                      'glue_tabs':sum(len(p.tabs) for p in panels.values()),
                      'paper_size_mm':[PAGE_W,PAGE_H], 'physical_volume_mm3':nice(mesh.volume)},
            'checks':checks,
            'limitations':spec['limitations']+['First-fit shelf packing is not globally page-optimal.',
              'This engine currently supports cubes only, not arbitrary triangulated mesh or image reconstruction.']}
    (out/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    create_contact_sheet(pdf,out/'printable_contact_sheet.png',side)
    print(json.dumps({'side':side,'status':report['overall_status'],'checks':len(checks),'pages':len(pages),
                      'panels':len(panels),'seams':len(seams)},ensure_ascii=False))
    if report['overall_status']!='PASS':
        raise AssertionError([c for c in checks if c['status']!='PASS'])
    return report


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--sizes',nargs='+',type=int,default=[100,200,300])
    a.add_argument('--out',default=str(Path(__file__).resolve().parent))
    args=a.parse_args()
    output=Path(args.out)
    reports=[]
    for s in args.sizes:
        if s<=0:raise ValueError('Side must be >0')
        reports.append(generate(s,output/f'cube_{s}mm'))
    summary={'engine':'Papercraft Engine 1.1','version':VERSION,
             'paper':'US Letter','sizes_mm':args.sizes,'models':[{'model_id':r['model_id'],
              'status':r['overall_status'],**r['summary'],'automated_checks':len(r['checks'])} for r in reports]}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary

if __name__=='__main__':main()
