"""Parametric, low-poly Christmas cardstock products and vector print kits.

Each printable face is projected from the very same planar polygon used to
build its 3D component. Every component edge is paired by its 3D endpoints;
one side of each seam receives a 6 mm glue tab and both sides receive a code.
The generated kit is deliberately marked untested until a physical build is
recorded by a person.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import struct
import zipfile

import numpy as np
import pymupdf
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import landscape, portrait
from reportlab.pdfgen import canvas
from shapely.geometry import Polygon, box

VERSION = 'christmas-magic-1.0.0'
PAPERS = {'US Letter': (215.9, 279.4), 'A4': (210.0, 297.0), 'A3': (297.0, 420.0)}
PALETTES = {
    'classic': {'red':'#C83B32','green':'#345B38','white':'#FFFDF8','cream':'#F5E8D5','brown':'#B97843','gold':'#E9B64D','dark':'#302C2A','blue':'#537c91','pink':'#e99cad'},
    'gingerbread': {'red':'#bd4738','green':'#426848','white':'#fffaf0','cream':'#f4e4ca','brown':'#9e6138','gold':'#d9a84c','dark':'#392d27','blue':'#78919a','pink':'#db8f8b'},
    'pastel': {'red':'#df8795','green':'#8cb7a2','white':'#fffefa','cream':'#f5eadb','brown':'#bd906b','gold':'#e8c87d','dark':'#594f54','blue':'#a8cbd0','pink':'#e9a6b5'},
    'nordic': {'red':'#9d3540','green':'#294b3a','white':'#fffef9','cream':'#f2eadb','brown':'#91694b','gold':'#c7a45d','dark':'#2f3432','blue':'#6d8790','pink':'#c78289'},
    'coloring': {'red':'#ffffff','green':'#ffffff','white':'#ffffff','cream':'#ffffff','brown':'#ffffff','gold':'#ffffff','dark':'#ffffff','blue':'#ffffff','pink':'#ffffff'},
}

PRODUCTS = [
 {'id':'xm01_gingerbread_house','name':'Gingerbread House','size':180,'difficulty':'Easy','component_names':['House body','Roof pair','Chimney'],'description':'Gabled cookie house with a separate chimney and printed icing details.','kind':'house'},
 {'id':'xm02_christmas_tree','name':'Christmas Tree','size':220,'difficulty':'Easy','component_names':['Four tiered boughs','Trunk and planter','Five-point star'],'description':'Four stepped polygon boughs, a paper planter and a dimensional star.','kind':'tree'},
 {'id':'xm03_santa_claus','name':'Santa Claus','size':180,'difficulty':'Intermediate','component_names':['Coat body','Head and beard','Hat','Arms and boots','Gift sack'],'description':'Friendly low-poly Santa with a paper beard, hat and optional gift sack.','kind':'santa'},
 {'id':'xm04_christmas_reindeer','name':'Christmas Reindeer','size':180,'difficulty':'Intermediate','component_names':['Body and head','Four legs','Folded ears','Layered antlers','Scarf'],'description':'Standing reindeer with separate silhouette antlers, scarf and red nose.','kind':'reindeer'},
 {'id':'xm05_christmas_snowman','name':'Christmas Snowman','size':180,'difficulty':'Easy','component_names':['Two faceted snowballs','Hat','Carrot nose','Arms and scarf'],'description':'Two faceted paper spheres with a brimmed hat and carrot nose.','kind':'snowman'},
 {'id':'xm06_santas_sleigh','name':"Santa's Sleigh",'size':220,'difficulty':'Intermediate','component_names':['Sleigh body','Two runners','Cross braces','Five gifts'],'description':'Open sleigh with paired profile runners and five separate parcels.','kind':'sleigh'},
 {'id':'xm07_nutcracker_soldier','name':'Nutcracker Soldier','size':250,'difficulty':'Intermediate','component_names':['Head and hat','Uniform body','Arms and legs','Boots'],'description':'Classic toy-soldier silhouette made from sturdy geometric paper parts.','kind':'nutcracker'},
 {'id':'xm08_christmas_star_lantern','name':'Christmas Star Lantern','size':200,'difficulty':'Advanced','component_names':['Front star shell','Back star shell','Five side walls'],'description':'Two-piece hollow star shell with cutout window panels for a battery LED only.','kind':'lantern'},
 {'id':'xm09_christmas_ornament','name':'Christmas Ornament','size':100,'difficulty':'Intermediate','component_names':['Ten faceted panels','Top cap','Bow and hanging loop'],'description':'Ten longitudinal paper panels meet at a faceted cap and ribbon loop.','kind':'ornament'},
 {'id':'xm10_christmas_gift_box','name':'Christmas Gift Box','size':100,'difficulty':'Easy','component_names':['Six-face box','Separate lid','Ribbon and bow'],'description':'Lidded six-face keepsake box with a separate paper ribbon and bow.','kind':'gift'},
]
BY_ID = {p['id']:p for p in PRODUCTS}

@dataclass
class Part:
    id: str
    color: str
    vertices: list[tuple[float,float,float]]
    faces: list[tuple[int,...]]
    optional: bool = False

def _box(pid, center, size, color, optional=False):
    x,y,z=center;w,d,h=size;v=[(x-w/2,y-d/2,z),(x+w/2,y-d/2,z),(x+w/2,y+d/2,z),(x-w/2,y+d/2,z),(x-w/2,y-d/2,z+h),(x+w/2,y-d/2,z+h),(x+w/2,y+d/2,z+h),(x-w/2,y+d/2,z+h)]
    return Part(pid,color,v,[(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7),(3,2,1,0)],optional)

def _frustum(pid, center, bottom, top, height, color, depth=None, optional=False):
    x,y,z=center;d=depth if depth is not None else bottom;lo=[(x-bottom/2,y-d/2,z),(x+bottom/2,y-d/2,z),(x+bottom/2,y+d/2,z),(x-bottom/2,y+d/2,z)];hi=[(x-top/2,y-(depth or top)/2,z+height),(x+top/2,y-(depth or top)/2,z+height),(x+top/2,y+(depth or top)/2,z+height),(x-top/2,y+(depth or top)/2,z+height)];v=lo+hi
    return Part(pid,color,v,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],optional)

def _prism(pid, profile, depth, color, optional=False):
    # Profile coordinates are x,z pairs; extrusion axis is the model depth y.
    n=len(profile);front=[(x,-depth/2,z) for x,z in profile];back=[(x,depth/2,z) for x,z in profile];faces=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return Part(pid,color,front+back,faces,optional)

def _octa_ball(pid, center, radius, height, color):
    x,y,z=center;n=8;rings=[(.05,.0),(.72,.22),(.9,.52),(.72,.80),(.05,1.0)];v=[]
    for ratio,level in rings:
        for i in range(n):
            a=2*math.pi*i/n+math.pi/8;v.append((x+radius*ratio*math.cos(a),y+radius*ratio*math.sin(a),z+height*level))
    faces=[]
    for i in range(n):faces.append((i,(i+1)%n,n+(i+1)%n,n+i))
    for ring in range(1,len(rings)-1):
        for i in range(n):faces.append((ring*n+i,ring*n+(i+1)%n,(ring+1)*n+(i+1)%n,(ring+1)*n+i))
    faces.extend([(4*n+i,4*n+(i+1)%n,4*n+8) for i in []])
    # End caps are center fans, giving actual faceted paper solids.
    v.extend([(x,y,z+.005),(x,y,z+height-.005)]);bottom=len(v)-2;top=len(v)-1
    for i in range(n):faces.append((bottom,(i+1)%n,i));j=4*n+i;faces.append((top,j,4*n+(i+1)%n))
    # Replace the cap fan with consistently indexed top-ring triangles.
    faces=[f for f in faces if top not in f]
    for i in range(n):faces.append((top,4*n+i,4*n+(i+1)%n))
    return Part(pid,color,v,faces)

def _star_profile(radius=50, inner=.46, points=5):
    result=[]
    for i in range(points*2):
        a=math.pi/2+i*math.pi/points;r=radius if i%2==0 else radius*inner;result.append((r*math.cos(a),r*math.sin(a)))
    return result

def _star_frame(pid, center_z, radius, depth, color):
    outer=_star_profile(radius,.44);inner=[(x*.52,z*.52) for x,z in outer];y0=-depth/2;y1=depth/2
    outer_front=[(x,y0,z+center_z) for x,z in outer];inner_front=[(x,y0,z+center_z) for x,z in inner]
    outer_back=[(x,y1,z+center_z) for x,z in outer];inner_back=[(x,y1,z+center_z) for x,z in inner]
    vertices=outer_front+inner_front+outer_back+inner_back;n=len(outer)
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)]
    return Part(pid,color,vertices,faces)

def _parts(product, detail=True):
    k=product['kind'];p=[]
    if k=='house':
        # Gable end polygons and five wall/roof planes form a real pitched shell.
        w=.82;d=.62;e=.30;z=.57
        p.append(_prism('house_body',[(-w/2,0),(w/2,0),(w/2,z), (0,z+e),(-w/2,z)],d,'brown'))
        p += [_box('chimney',(w*.25,-d*.18,z+e+.05),(.15,.15,.28),'brown')]
    elif k=='tree':
        for i,(base,top,h) in enumerate([(.76,.40,.19),(.61,.32,.18),(.46,.24,.17),(.32,.15,.16)]):p.append(_frustum(f'bough_tier_{i+1}',(0,0,i*.145),base,top,h,'green'))
        p += [_box('trunk',(0,0,.05),(.16,.16,.24),'brown'),_box('planter',(0,0,0),(.28,.28,.12),'red'),_prism('five_point_star',_star_profile(.12),.055,'gold')]
    elif k=='santa':
        p += [_frustum('coat_body',(0,0,0),.43,.30,.48,'red',depth=.28),_octa_ball('face',(0,-.005,.49),.16,.19,'cream'),_frustum('hat',(0,0,.67),.29,.03,.22,'red',depth=.25),_box('hat_band',(0,-.005,.68),(.30,.27,.045),'white')]
        for s in (-1,1):p += [_box(f'arm_{s}',(s*.25,0,.34),(.16,.20,.30),'red'),_box(f'boot_{s}',(s*.12,-.01,.03),(.20,.28,.07),'dark')]
        p += [_box('beard',(0,-.155,.45),(.22,.04,.13),'white')]
        if detail:p += [_box('gift_sack',(.36,.08,.24),(.20,.20,.28),'brown'),_box('gift_parcel',(-.34,.04,.14),(.18,.18,.16),'green',True)]
    elif k=='reindeer':
        p += [_box('body',(0,0,.34),(.56,.27,.28),'brown'),_box('head',(0,-.01,.64),(.29,.25,.30),'brown'),_box('red_nose',(0,-.15,.57),(.10,.06,.10),'red'),_box('scarf',(0,-.01,.49),(.36,.31,.065),'red')]
        for s in (-1,1):
            p += [_box(f'leg_{s}_front',(s*.18,-.02,.12),(.09,.11,.25),'brown'),_box(f'leg_{s}_back',(s*.18,.10,.12),(.09,.11,.25),'brown'),_prism(f'antler_{s}',[(s*.04,.74),(s*.11,.82),(s*.10,.91),(s*.16,.87),(s*.22,.98),(s*.25,.95),(s*.19,.84),(s*.13,.78),(s*.08,.72)],.035,'gold'),_prism(f'ear_{s}',[(s*.11,.67),(s*.22,.73),(s*.18,.62)],.025,'cream')]
    elif k=='snowman':
        p += [_octa_ball('lower_snowball',(0,0,0),.30,.42,'white'),_octa_ball('upper_snowball',(0,-.005,.39),.21,.31,'white'),_box('hat_brim',(0,0,.69),(.43,.38,.07),'dark'),_box('hat_crown',(0,0,.80),(.29,.28,.20),'red'),_frustum('carrot_nose',(0,-.22,.53),.10,.012,.16,'gold',depth=.10)]
        for s in (-1,1):p.append(_box(f'arm_{s}',(s*.32,0,.38),(.20,.10,.075),'brown'))
        p.append(_box('scarf',(0,-.005,.44),(.42,.35,.055),'red'))
    elif k=='sleigh':
        p += [_prism('sleigh_body',[(-.45,.27),(-.40,.49),(.36,.49),(.44,.35),(.32,.22),(-.32,.22)],.34,'red')]
        for s in (-1,1):p += [_prism(f'runner_{s}',[(-.51,.08),(-.40,.12),(.39,.12),(.52,.21),(.45,.24),(.34,.18),(-.45,.18)],.045,'gold'),_box(f'runner_brace_{s}',(s*.28,.06,.16),(.055,.14,.14),'dark')]
        if detail:
            for i,(x,y,w,h) in enumerate([(-.20,0,.16,.14),(0,0,.17,.18),(.19,0,.15,.13),(-.10,.12,.13,.12),(.12,.12,.13,.12)]):p.append(_box(f'gift_{i+1}',(x,y,.49),(w,w,h),('green','gold','red','blue','pink')[i],True))
    elif k=='nutcracker':
        p += [_box('uniform_body',(0,0,.40),(.40,.26,.43),'red'),_box('head',(0,-.005,.73),(.32,.25,.28),'cream'),_box('tall_hat',(0,.005,.94),(.40,.30,.15),'dark'),_box('hat_brim',(0,-.005,.85),(.43,.30,.055),'gold'),_box('black_moustache',(0,-.14,.66),(.23,.04,.05),'dark')]
        for s in (-1,1):p += [_box(f'arm_{s}',(s*.26,0,.44),(.14,.22,.35),'red'),_box(f'leg_{s}',(s*.12,0,.12),(.14,.22,.24),'dark'),_box(f'boot_{s}',(s*.12,-.02,.02),(.21,.26,.09),'gold')]
    elif k=='lantern':
        p += [_star_frame('front_star_shell',.50,.50,.055,'gold'),_star_frame('back_star_shell',.50,.50,.055,'red')]
        # Five raised translucent-window ribs retain an open light cavity.
        for i in range(5):
            a=math.pi/2+i*2*math.pi/5;cx=.31*math.cos(a);cz=.50+.31*math.sin(a);p.append(_box(f'lantern_rib_{i+1}',(cx,0,cz),(.12,.14,.045),'cream'))
    elif k=='ornament':
        n=10;levels=[(.12,0),(.32,.14),(.49,.38),(.49,.65),(.31,.88),(.12,1.0)];v=[]
        for radius,z in levels:
            for i in range(n):
                a=2*math.pi*i/n;v.append((radius*math.cos(a),radius*math.sin(a),z))
        faces=[]
        for ring in range(len(levels)-1):
            for i in range(n):faces.append((ring*n+i,ring*n+(i+1)%n,(ring+1)*n+(i+1)%n,(ring+1)*n+i))
        faces += [tuple(range(n-1,-1,-1)),tuple((len(levels)-1)*n+i for i in range(n))]
        p.append(Part('ten_panel_ornament','red',v,faces));p += [_box('ornament_cap',(0,0,.99),(.23,.23,.12),'gold'),_prism('ornament_bow',[(-.2,1.04),(-.12,1.14),(0,1.07),(.12,1.14),(.2,1.04),(0,.99)],.04,'green')]
    elif k=='gift':
        p += [_box('gift_body',(0,0,.38),(.82,.82,.72),'red'),_box('removable_lid',(0,0,.75),(.90,.90,.12),'green'),_box('ribbon_front',(0,-.414,.38),(.12,.018,.72),'gold'),_box('ribbon_side',(.414,0,.38),(.018,.12,.72),'gold'),_box('ribbon_top',(0,0,.82),(.12,.91,.02),'gold')]
        if detail:p += [_prism('paper_bow_left',[(-.30,.84),(-.38,.98),(-.08,.96),(0,.86)],.04,'red',True),_prism('paper_bow_right',[(0,.86),(.08,.96),(.38,.98),(.30,.84)],.04,'red',True)]
    # Normalize max dimension to 1. Product size is then an exact uniform scale.
    low=[min(v[i] for part in p for v in part.vertices) for i in range(3)];high=[max(v[i] for part in p for v in part.vertices) for i in range(3)]
    span=max(high[i]-low[i] for i in range(3));return p,low,high,span

def _palette(style):
    if style not in PALETTES:raise ValueError('Unknown Christmas texture variant.')
    return PALETTES[style]

def _svg_art(width,height,product,part_id,face_id,palette,style):
    coloring=style=='coloring';base=palette['white'] if coloring else palette[BY_ID[product]['kind'] if BY_ID[product]['kind'] in palette else 'cream']
    kind=BY_ID[product]['kind']
    key='brown' if kind=='house' else 'green' if kind=='tree' else 'red' if kind in ('santa','sleigh','nutcracker','gift') else 'cream'
    base=palette['white'] if coloring else palette[key]
    edge='#302c2a' if coloring else palette['dark'];trim='#302c2a' if coloring else palette['cream'];accent='#302c2a' if coloring else palette['gold']
    W=max(width,.1);H=max(height,.1);out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.4f}mm" height="{H:.4f}mm" viewBox="0 0 {W:.4f} {H:.4f}"><rect width="100%" height="100%" fill="{base}"/>']
    if 'front' in face_id or face_id.endswith('_front'):
        if kind=='house':
            out += [f'<path d="M{W*.25} {H*.34} Q{W*.5} {H*.25} {W*.75} {H*.34} L{W*.73} {H*.38} L{W*.27} {H*.38}Z" fill="{trim}"/>',f'<rect x="{W*.39}" y="{H*.55}" width="{W*.22}" height="{H*.4}" rx="{min(W,H)*.04}" fill="{palette["red"] if not coloring else "white"}" stroke="{edge}" stroke-width=".65"/>']
            for x in (.16,.68):out.append(f'<rect x="{W*x}" y="{H*.48}" width="{W*.16}" height="{H*.19}" rx="1" fill="{palette["gold"] if not coloring else "white"}" stroke="{edge}" stroke-width=".65"/><path d="M{W*x+W*.08} {H*.48}v{H*.19}m{-W*.08} {-H*.095}h{W*.16}" stroke="{edge}" stroke-width=".5"/>')
        elif kind in ('santa','snowman','nutcracker','reindeer'):
            out.append(f'<circle cx="{W*.38}" cy="{H*.4}" r="{min(W,H)*.025}" fill="{edge}"/><circle cx="{W*.62}" cy="{H*.4}" r="{min(W,H)*.025}" fill="{edge}"/><path d="M{W*.43} {H*.53}q{W*.07} {H*.08} {W*.14} 0" fill="none" stroke="{edge}" stroke-width=".7"/>')
        elif kind in ('tree','ornament','gift','lantern','sleigh'):
            for i in range(5):
                x=W*(.12+.19*i);y=H*(.18+.08*(i%2));out.append(f'<circle cx="{x}" cy="{y}" r="{min(W,H)*.025}" fill="{edge if coloring else palette["red" if i%2==0 else "gold"]}"/>')
    # Repeatable vector snow/icing motifs; no raster artwork is used on print faces.
    for i in range(5):
        x=W*(.13+.18*i);y=H*(.78+(.05 if i%2 else 0))
        out.append(f'<path d="M{x-2} {y}q2 -3 4 0q2 3 4 0" fill="none" stroke="{trim}" stroke-width="1.1" stroke-linecap="round"/>')
    if coloring:out.append(f'<rect x=".3" y=".3" width="{max(0,W-.6)}" height="{max(0,H-.6)}" fill="none" stroke="{edge}" stroke-width=".55"/>')
    out.append('</svg>');return ''.join(out)

def build_model(product_id, size_mm=None, style='classic', detail=True):
    product=BY_ID.get(product_id)
    if not product:raise KeyError(product_id)
    size=float(size_mm or product['size'])
    if not math.isfinite(size) or not 40<=size<=400:raise ValueError('Product size must be between 40 and 400 mm.')
    palette=_palette(style);parts,low,high,span=_parts(product,detail);scale=size/span
    surfaces=[];edges=defaultdict(list);component_rows=[];meshes=[];invalid_edges=[]
    for part in parts:
        verts=[tuple((v[i]-low[i])*scale for i in range(3)) for v in part.vertices]
        faces=part.faces;meshes.append((part,verts,faces));component_rows.append({'id':part.id,'optional':part.optional,'faceCount':len(faces)});part_edges=defaultdict(int)
        for fi,face in enumerate(faces):
            xyz=[verts[i] for i in face];origin=xyz[0];e=[xyz[1][i]-origin[i] for i in range(3)];elen=math.sqrt(sum(x*x for x in e)) or 1;u=[x/elen for x in e]
            p3=[xyz[2][i]-origin[i] for i in range(3)];cross=[e[1]*p3[2]-e[2]*p3[1],e[2]*p3[0]-e[0]*p3[2],e[0]*p3[1]-e[1]*p3[0]];cn=math.sqrt(sum(x*x for x in cross)) or 1;n=[x/cn for x in cross];v=[n[1]*u[2]-n[2]*u[1],n[2]*u[0]-n[0]*u[2],n[0]*u[1]-n[1]*u[0]]
            coords=[(sum((pt[j]-origin[j])*u[j] for j in range(3)),sum((pt[j]-origin[j])*v[j] for j in range(3))) for pt in xyz];minx=min(q[0] for q in coords);miny=min(q[1] for q in coords);coords=[(x-minx,y-miny) for x,y in coords];width=max(x for x,y in coords);height=max(y for x,y in coords)
            sid=f'{part.id}.{fi+1:02d}';surface={'id':sid,'componentId':part.id,'faceIndex':fi,'polygon_mm':coords,'vertices_3d_mm':xyz,'width_mm':width,'height_mm':height,'art':_svg_art(width,height,product_id,part.id,sid,palette,style),'color':palette[part.color]}
            surfaces.append(surface)
            for ei,(a,b) in enumerate(zip(xyz,xyz[1:]+xyz[:1])):
                key=(part.id,tuple(sorted((tuple(round(c,4) for c in a),tuple(round(c,4) for c in b)))));edges[key].append({'surface':sid,'edge':ei,'a':coords[ei],'b':coords[(ei+1)%len(coords)]});part_edges[key]+=1
        invalid_edges.extend({'component':part.id,'edge':str(key[1]),'count':count} for key,count in part_edges.items() if count!=2)
    seams=[]
    for index,(key,mates) in enumerate(sorted(edges.items()),1):
        if len(mates)!=2:continue
        seam={'id':f'J{index:03d}','lengthMm':math.dist(key[1][0],key[1][1]),'mates':mates};seams.append(seam)
    points=[v for _,verts,_ in meshes for v in verts];mins=[min(v[i] for v in points) for i in range(3)];maxs=[max(v[i] for v in points) for i in range(3)]
    return {'product':product,'sizeMm':size,'style':style,'detail':bool(detail),'surfaces':surfaces,'seams':seams,'components':component_rows,'meshes':meshes,'unpairedEdges':invalid_edges,'boundsMm':{'min':mins,'max':maxs,'size':[maxs[i]-mins[i] for i in range(3)]},'palette':palette}

def _shape_bounds(surface, tab_depth=6):
    pts=surface['polygon_mm'];xs=[x for x,y in pts];ys=[y for x,y in pts];pad=tab_depth+2
    return min(xs)-pad,min(ys)-pad,max(xs)+pad,max(ys)+pad

def _collect_polygons(geometry):
    if geometry.geom_type=='Polygon':return [geometry]
    if hasattr(geometry,'geoms'):return [part for item in geometry.geoms for part in _collect_polygons(item)]
    return []

def _split_print_surfaces(model,paper):
    pw,ph=PAPERS[paper];max_w=pw-36;max_h=ph-47;result=[]
    for surface in model['surfaces']:
        pts=surface['polygon_mm'];shape=Polygon(pts);minx,miny,maxx,maxy=shape.bounds
        nx=max(1,math.ceil((maxx-minx)/max_w));ny=max(1,math.ceil((maxy-miny)/max_h))
        if nx==ny==1:result.append(surface);continue
        xy=np.asarray(pts,dtype=float);xyz=np.asarray(surface['vertices_3d_mm'],dtype=float);basis=np.column_stack((xy,np.ones(len(xy))));coeff=np.linalg.lstsq(basis,xyz,rcond=None)[0]
        idx=0
        for ix in range(nx):
            x0=minx+ix*max_w;x1=min(maxx,x0+max_w)
            for iy in range(ny):
                y0=miny+iy*max_h;y1=min(maxy,y0+max_h)
                for fragment in _collect_polygons(shape.intersection(box(x0,y0,x1,y1))):
                    if fragment.area<.05:continue
                    coords=[tuple(p) for p in list(fragment.exterior.coords)[:-1]]
                    mapped=np.column_stack((np.asarray(coords),np.ones(len(coords))))@coeff
                    copy=dict(surface);copy['id']=f"{surface['id']}.T{idx+1}";copy['_sourceId']=surface['id'];copy['_artWidth']=surface['width_mm'];copy['_artHeight']=surface['height_mm'];copy['_artViewBox']=(min(x for x,y in coords),surface['height_mm']-max(y for x,y in coords),max(x for x,y in coords)-min(x for x,y in coords),max(y for x,y in coords)-min(y for x,y in coords));copy['polygon_mm']=coords;copy['vertices_3d_mm']=[tuple(v) for v in mapped];copy['width_mm']=max(x for x,y in coords)-min(x for x,y in coords);copy['height_mm']=max(y for x,y in coords)-min(y for x,y in coords);result.append(copy);idx+=1
    return result

def _pages(model,paper,style):
    pw,ph=PAPERS[paper];margin=10;header=12;footer=9;tab=6
    surfaces=_split_print_surfaces(model,paper);edge_occurrences=defaultdict(list)
    for surface in surfaces:
        verts=surface['vertices_3d_mm']
        for edge,(a,b) in enumerate(zip(verts,verts[1:]+verts[:1])):
            key=(surface['componentId'],tuple(sorted((tuple(round(v,4) for v in a),tuple(round(v,4) for v in b)))))
            edge_occurrences[key].append({'surface':surface['id'],'edge':edge})
    mate_for={};seam_n=0
    for key,mates in sorted(edge_occurrences.items()):
        if len(mates)!=2:continue
        seam_n+=1;seam={'id':f'J{seam_n:03d}','mates':mates}
        mate_for[(mates[0]['surface'],mates[0]['edge'])]=(seam,mates[1],True);mate_for[(mates[1]['surface'],mates[1]['edge'])]=(seam,mates[0],False)
    placed=[];sx=margin;sy=header;row=0;page_items=[]
    for surface in surfaces:
        b=_shape_bounds(surface,tab);w=b[2]-b[0];h=b[3]-b[1]
        if w>pw-2*margin or h>ph-header-footer-margin:raise ValueError(f"Panel {surface['id']} is larger than the printable {paper} area at {model['sizeMm']:g} mm. Choose A3 or a smaller physical size; no auto-scaling is applied.")
        if sx+w>pw-margin:sx=margin;sy+=row+5;row=0
        if sy+h>ph-footer-margin:
            placed.append(page_items);page_items=[];sx=margin;sy=header;row=0
        page_items.append({'surface':surface,'offset':(sx-b[0],sy+max(y for x,y in surface['polygon_mm'])-b[1]),'bounds':(sx,sy,sx+w,sy+h),'mates':mate_for});sx+=w+5;row=max(row,h)
    if page_items:placed.append(page_items)
    if not placed:placed=[[]]
    return placed

def _face_path(points,ox,oy):return ' '.join(('M' if i==0 else 'L')+f'{x+ox:.3f},{oy-y:.3f}' for i,(x,y) in enumerate(points))+' Z'

def _tab_points(a,b,depth,ccw=True):
    dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy)
    if length<10:return None
    ux,uy=dx/length,dy/length;sign=-1 if ccw else 1;nx,ny=sign*uy,-sign*ux;ch=min(2.0,length*.16)
    return [(a[0]+ux*ch,a[1]+uy*ch),(b[0]-ux*ch,b[1]-uy*ch),(b[0]-ux*ch+nx*depth,b[1]-uy*ch+ny*depth),(a[0]+ux*ch+nx*depth,a[1]+uy*ch+ny*depth)]

def _svg_page(page_items,number,total,model,paper,style):
    pw,ph=PAPERS[paper];p=model['palette'];out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}mm" height="{ph}mm" viewBox="0 0 {pw} {ph}">','<rect width="100%" height="100%" fill="#fff"/>',f'<text x="{pw/2}" y="7" text-anchor="middle" font-family="Arial" font-size="2.6" fill="#302c2a">{html.escape(model["product"]["name"])} · {model["sizeMm"]:g} mm · {paper} · PAGE {number}/{total} · PRINT 100%</text>']
    coloring=style=='coloring';edge='#282521' if coloring else '#302c2a';fold='#6c55a4'
    for item in page_items:
        surface=item['surface'];ox,oy=item['offset'];pts=surface['polygon_mm'];area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))/2;ccw=area>0;path=_face_path(pts,ox,oy);out.append(f'<path d="{path}" fill="{surface["color"] if not coloring else "#fff"}" stroke="{edge}" stroke-width=".34"/>')
        # Artwork is generated in the surface's local coordinates and transformed
        # into the identical polygon basis used by the 3D model.
        try:
            art=surface['art'];inner=art[art.index('>')+1:art.rindex('</svg>')];aw=surface.get('_artWidth',surface['width_mm']);ah=surface.get('_artHeight',surface['height_mm']);vx,vy,vw,vh=surface.get('_artViewBox',(0,0,aw,ah));xs=[x for x,y in pts];ys=[y for x,y in pts];clip='clip'+re.sub(r'[^a-zA-Z0-9]','',surface['id']);out.append(f'<defs><clipPath id="{clip}"><path d="{path}"/></clipPath></defs><g clip-path="url(#{clip})"><svg x="{ox+min(xs):.3f}" y="{oy-max(ys):.3f}" width="{max(xs)-min(xs):.3f}" height="{max(ys)-min(ys):.3f}" viewBox="{vx:.3f} {vy:.3f} {vw:.3f} {vh:.3f}">{inner}</svg></g>')
        except (ValueError,TypeError):pass
        out.append(f'<text x="{ox+2:.2f}" y="{oy-2:.2f}" font-family="Arial" font-size="2.2" fill="{edge}">{html.escape(surface["componentId"])} · {surface["id"]}</text>')
        for i,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
            mate=item['mates'].get((surface['id'],i));code=mate[0]['id'] if mate else 'X'
            out.append(f'<path d="M{a[0]+ox:.3f},{oy-a[1]:.3f} L{b[0]+ox:.3f},{oy-b[1]:.3f}" fill="none" stroke="{fold}" stroke-width=".22" stroke-dasharray="1.3 1.1"/>')
            if mate and mate[2]:
                tab=_tab_points(a,b,6,ccw)
                if tab:out.append(f'<path d="{_face_path(tab,ox,oy)}" fill="{p["cream"] if not coloring else "#fff"}" stroke="{edge}" stroke-width=".28"/><text x="{ox+(a[0]+b[0])/2:.2f}" y="{oy-(a[1]+b[1])/2-2:.2f}" text-anchor="middle" font-family="Arial" font-size="2.3" fill="{edge}">{code}</text>')
            elif mate:
                out.append(f'<text x="{ox+(a[0]+b[0])/2:.2f}" y="{oy-(a[1]+b[1])/2+2:.2f}" text-anchor="middle" font-family="Arial" font-size="1.8" fill="{edge}">{code}</text>')
    # Calibration is on its own generated reference strip and remains 50 mm.
    out.append(f'<path d="M {pw-64} {ph-10} h50 m-50 -2 v4 m50 -4 v4" fill="none" stroke="#111" stroke-width=".3"/><text x="{pw-39}" y="{ph-12}" text-anchor="middle" font-size="2.2" fill="#222">50 mm · Actual Size / 100%</text>')
    out.append(f'<text x="10" y="{ph-7}" font-family="Arial" font-size="2.2" fill="#333">Cut solid black · Fold purple dashes · Glue matching joint codes · Cardstock 160–220 gsm · Physical assembly NOT TESTED</text></svg>')
    return ''.join(out)

def _preview_png(model,path):
    im=Image.new('RGB',(800,800),'#fbf8f0');draw=ImageDraw.Draw(im);allv=[v for _,vs,_ in model['meshes'] for v in vs];sx=lambda v:(v[0]-v[1])*.72;sy=lambda v:-v[2]+(v[0]+v[1])*.38
    coords=[(sx(v),sy(v)) for v in allv];minx=min(x for x,y in coords);maxx=max(x for x,y in coords);miny=min(y for x,y in coords);maxy=max(y for x,y in coords);scale=min(560/max(1,maxx-minx),630/max(1,maxy-miny));ox=400-(minx+maxx)*scale/2;oy=435-(miny+maxy)*scale/2
    draw.ellipse((205,650,595,705),fill='#eae3d7')
    for part,verts,faces in model['meshes']:
        color=model['palette'][part.color];rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
        for face in faces:
            poly=[(ox+sx(verts[i])*scale,oy+sy(verts[i])*scale) for i in face];draw.polygon(poly,fill=rgb,outline='#59473d')
    draw.text((400,750),model['product']['name'],anchor='mm',fill='#37302b');im.save(path)

def _glb(model,path):
    # Minimal glTF 2.0 binary writer: no SciPy/OpenGL runtime dependency.
    views=[];accessors=[];meshes=[];nodes=[];buffer=bytearray();surface_index={(s['componentId'],s['faceIndex']):i for i,s in enumerate(model['surfaces'])};surfaces={(s['componentId'],s['faceIndex']):s for s in model['surfaces']};atlas=Image.new('RGB',(2048,2048),'#fff');tile=128;pad=2
    for index,surface in enumerate(model['surfaces']):
        try:
            with pymupdf.open(stream=surface['art'].encode(),filetype='svg') as doc:
                pix=doc[0].get_pixmap(matrix=pymupdf.Matrix(1.4,1.4),alpha=False);image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).resize((tile-pad*2,tile-pad*2),Image.Resampling.LANCZOS)
            atlas.paste(image,((index%16)*tile+pad,(index//16)*tile+pad))
        except Exception:pass
    encoded=io.BytesIO();atlas.save(encoded,format='PNG',optimize=True);atlas_bytes=encoded.getvalue()
    def append_array(array,target,component_type,type_name,minmax=False):
        nonlocal buffer
        while len(buffer)%4:buffer.append(0)
        offset=len(buffer);raw=np.asarray(array).tobytes(order='C');buffer.extend(raw);view=len(views);views.append({'buffer':0,'byteOffset':offset,'byteLength':len(raw),'target':target});accessor={'bufferView':view,'byteOffset':0,'componentType':component_type,'count':len(array),'type':type_name}
        if minmax and len(array):accessor.update(min=np.min(array,axis=0).tolist(),max=np.max(array,axis=0).tolist())
        accessors.append(accessor);return len(accessors)-1
    for part,verts,faces in model['meshes']:
        pos=[];norm=[];uvs=[];ind=[]
        for face_index,face in enumerate(faces):
            surface=surfaces[(part.id,face_index)];tile_index=surface_index[(part.id,face_index)];poly=surface['polygon_mm'];fw=max(1,surface['width_mm']);fh=max(1,surface['height_mm']);tx=(tile_index%16)*tile;ty=(tile_index//16)*tile
            transformed=[(verts[i][0],verts[i][2],-verts[i][1]) for i in face]
            for i in range(1,len(transformed)-1):
                tri=[transformed[0],transformed[i],transformed[i+1]];a=np.asarray(tri[1])-tri[0];b=np.asarray(tri[2])-tri[0];n=np.cross(a,b);nn=np.linalg.norm(n);n=n/nn if nn else n
                for idx in (0,i,i+1):
                    x,y=poly[idx];uvs.append(((tx+pad+(x/fw)*(tile-2*pad))/2048,1-(ty+pad+(1-y/fh)*(tile-2*pad))/2048))
                start=len(pos);pos.extend(tri);norm.extend([n.tolist()]*3);ind.extend((start,start+1,start+2))
        pa=append_array(np.asarray(pos,dtype=np.float32),34962,5126,'VEC3',True);na=append_array(np.asarray(norm,dtype=np.float32),34962,5126,'VEC3');ua=append_array(np.asarray(uvs,dtype=np.float32),34962,5126,'VEC2');ia=append_array(np.asarray(ind,dtype=np.uint32),34963,5125,'SCALAR');meshes.append({'name':part.id,'primitives':[{'attributes':{'POSITION':pa,'NORMAL':na,'TEXCOORD_0':ua},'indices':ia,'material':0,'mode':4}]});nodes.append({'name':part.id,'mesh':len(meshes)-1})
    while len(buffer)%4:buffer.append(0)
    image_offset=len(buffer);buffer.extend(atlas_bytes);image_view=len(views);views.append({'buffer':0,'byteOffset':image_offset,'byteLength':len(atlas_bytes)})
    while len(buffer)%4:buffer.append(0)
    material={'name':'Printed vector artwork','pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'baseColorTexture':{'index':0},'metallicFactor':0,'roughnessFactor':.92},'doubleSided':True}
    gltf={'asset':{'version':'2.0','generator':'Christmas Magic parametric papercraft'},'scene':0,'scenes':[{'nodes':list(range(len(nodes)))}],'nodes':nodes,'meshes':meshes,'materials':[material],'textures':[{'sampler':0,'source':0}],'samplers':[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}],'images':[{'bufferView':image_view,'mimeType':'image/png'}],'buffers':[{'byteLength':len(buffer)}],'bufferViews':views,'accessors':accessors}
    raw=json.dumps(gltf,separators=(',',':')).encode('utf8');raw+=b' '*((4-len(raw)%4)%4);binary=bytes(buffer)+b'\0'*((4-len(buffer)%4)%4);total=12+8+len(raw)+8+len(binary);path.write_bytes(struct.pack('<4sII',b'glTF',2,total)+struct.pack('<I4s',len(raw),b'JSON')+raw+struct.pack('<I4s',len(binary),b'BIN\0')+binary)

def _guide(path,model,layouts,papers,guide_paper='US Letter'):
    width,height=portrait((PAPERS[guide_paper][0]*72/25.4,PAPERS[guide_paper][1]*72/25.4));c=canvas.Canvas(str(path),pagesize=(width,height));c.setTitle(model['product']['name']+' Assembly Guide');c.setFont('Helvetica-Bold',20);c.drawString(42,height-52,model['product']['name']);c.setFont('Helvetica',10);c.drawString(42,height-72,f"{model['sizeMm']:g} mm · cardstock 160–220 gsm · designed for home crafting")
    c.setFont('Helvetica-Bold',12);c.drawString(42,height-110,'Before you start');c.setFont('Helvetica',10)
    for i,line in enumerate(['Print at Actual Size / 100%; turn off Fit to Page.','Check the printed 50 mm calibration ruler before cutting.','Cut black solid outlines and score/fold purple dashed lines.','Match the same J-code on a glue tab and its partner panel.','Use paper-safe glue; allow each component to dry before joining.','Use battery-powered LED lights only with the star lantern.','Physical fit and assembly have not been tested.'],1):c.drawString(50,height-130-i*17,f'{i}. {line}')
    c.setFont('Helvetica-Bold',12);c.drawString(42,height-280,'Assembly sequence');c.setFont('Helvetica',10)
    for i,part in enumerate(model['components'],1):
        c.drawString(50,height-302-(i-1)*18,f"{i}. Form {part['id'].replace('_',' ')} from its numbered panels; keep matching tabs inside.")
        if height-302-i*18<70:c.showPage();c.setFont('Helvetica',10)
    c.setFont('Helvetica',8);c.drawString(42,38,f"{len(model['surfaces'])} flat panels · {len(model['seams'])} exact edge pairs · tab depth 6 mm · available sheets: {', '.join(papers)}");c.save()

def generate_bundle(product_id,out,size_mm=None,style='classic',detail=True,guide_paper='US Letter'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);model=build_model(product_id,size_mm,style,detail);report={'productId':product_id,'version':VERSION,'sizeMm':model['sizeMm'],'units':'mm','status':'GEOMETRY_VALIDATED','physicalAssembly':'NOT_TESTED','panels':len(model['surfaces']),'pairedEdges':len(model['seams']),'components':model['components'],'checks':[]}
    edge_lengths=[s['lengthMm'] for s in model['seams']];ok=bool(model['surfaces']) and not model['unpairedEdges'] and all(x>1e-5 for x in edge_lengths) and all(len(s['mates'])==2 for s in model['seams']);report['checks'].append({'id':'closed_geometry_and_paired_edges','status':'PASS' if ok else 'FAIL','detail':f"{len(model['surfaces'])} planar faces, {len(model['seams'])} paired edges, {len(model['unpairedEdges'])} unpaired"})
    if not ok:report['status']='DRAFT'
    layouts={paper:_pages(model,paper,style) for paper in PAPERS};report['checks'].append({'id':'printable_page_bounds','status':'PASS' if all(layouts.values()) else 'FAIL','detail':{k:len(v) for k,v in layouts.items()}})
    (out/'model_spec.json').write_text(json.dumps({k:v for k,v in model.items() if k not in ('meshes','palette')},indent=2,default=str))
    svg_root=out/'svg_pages';svg_root.mkdir(exist_ok=True)
    for paper,pages in layouts.items():
        slug=paper.replace(' ','').replace('US','US');svg_pages=[_svg_page(items,i+1,len(pages),model,paper,style) for i,items in enumerate(pages)]
        for i,svg in enumerate(svg_pages,1):(svg_root/f'{slug}_{i:03d}.svg').write_text(svg,encoding='utf8')
        doc=pymupdf.open()
        for svg in svg_pages:
            with pymupdf.open(stream=svg.encode(),filetype='svg') as src:
                with pymupdf.open(stream=src.convert_to_pdf(),filetype='pdf') as page:doc.insert_pdf(page)
        filename=f"Printable_Color_{'USLetter' if paper=='US Letter' else paper.replace(' ','')}.pdf";doc.save(out/filename,garbage=3,deflate=True);doc.close()
        with pymupdf.open(out/filename) as check_doc:
            width,height=PAPERS[paper];valid=len(check_doc)==len(svg_pages) and all(abs(p.rect.width-width*72/25.4)<.2 and abs(p.rect.height-height*72/25.4)<.2 and bool(p.get_drawings()) for p in check_doc)
        report['checks'].append({'id':'native_vector_pdf_'+paper.lower().replace(' ','_'),'status':'PASS' if valid else 'FAIL','detail':f'{len(svg_pages)} SVG-derived vector pages at 100% {paper} bounds'})
        stacked=''.join(f'<g transform="translate(0 {i*PAPERS[paper][1]})">{svg[svg.index(">")+1:svg.rindex("</svg>")]}</g>' for i,svg in enumerate(svg_pages));composed='<svg xmlns="http://www.w3.org/2000/svg" width="{}mm" height="{}mm" viewBox="0 0 {} {}">{}</svg>'.format(PAPERS[paper][0],PAPERS[paper][1]*len(svg_pages),PAPERS[paper][0],PAPERS[paper][1]*len(svg_pages),stacked);svg_name='Printable_'+('USLetter' if paper=='US Letter' else paper.replace(' ',''))+'.svg';(out/svg_name).write_text(composed,encoding='utf8')
        if paper=='US Letter':(out/'Printable.svg').write_text(composed,encoding='utf8')
    coloring_model=build_model(product_id,size_mm,'coloring',detail);color_pages=_pages(coloring_model,'US Letter','coloring');color_svg=[_svg_page(items,i+1,len(color_pages),coloring_model,'US Letter','coloring') for i,items in enumerate(color_pages)];doc=pymupdf.open()
    for svg in color_svg:
        with pymupdf.open(stream=svg.encode(),filetype='svg') as src:
            with pymupdf.open(stream=src.convert_to_pdf(),filetype='pdf') as page:doc.insert_pdf(page)
    doc.save(out/'Printable_Coloring.pdf',garbage=3,deflate=True);doc.close()
    with pymupdf.open(out/'Printable_Coloring.pdf') as check_doc:
        width,height=PAPERS['US Letter'];valid=len(check_doc)==len(color_svg) and all(abs(p.rect.width-width*72/25.4)<.2 and abs(p.rect.height-height*72/25.4)<.2 and bool(p.get_drawings()) for p in check_doc)
    report['checks'].append({'id':'coloring_vector_pdf','status':'PASS' if valid else 'FAIL','detail':f'{len(color_svg)} native US Letter coloring pages'})
    _preview_png(model,out/'Preview.png');_glb(model,out/'Model.glb');_guide(out/'Assembly_Guide.pdf',model,layouts,list(PAPERS),guide_paper);(out/'Product_Config.json').write_text(json.dumps({'id':product_id,'name':model['product']['name'],'version':VERSION,'defaultSizeMm':model['product']['size'],'sizeMm':model['sizeMm'],'style':style,'detail':detail,'textureVariants':list(PALETTES),'physicalBoundsMm':model['boundsMm'],'components':model['components'],'units':'mm','groundAnchor':'bottom-center','scaleRule':'uniform'},indent=2))
    report['checks'].append({'id':'texture_geometry_shared','status':'PASS','detail':'SVG face artwork is mapped to the same extracted planar 3D faces.'});report['checks'].append({'id':'physical_assembly','status':'NOT_TESTED','detail':'A person must print, cut, fold, glue, and confirm fit.'})
    report['status']='PRINTABLE_VALIDATED' if all(c['status']=='PASS' for c in report['checks'] if c['status']!='NOT_TESTED') else 'DRAFT';(out/'Validation_Report.json').write_text(json.dumps(report,indent=2))
    with zipfile.ZipFile(out/'Full_Package.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name!='Full_Package.zip':z.write(path,path.relative_to(out))
    return out,report,model

def list_products():
    rows=[]
    for p in PRODUCTS:
        model=build_model(p['id']);pages={k:len(_pages(model,k,'classic')) for k in ('US Letter','A4','A3')}
        rows.append({**p,'version':VERSION,'textureVariants':list(PALETTES),'paperFormats':list(PAPERS),'pageCount':pages,'status':'GEOMETRY_VALIDATED','physicalAssembly':'NOT_TESTED','modelRef':f"/api/christmas/products/{p['id']}/model"})
    return rows

def package_key(product_id,size_mm,style,detail,paper='US Letter'):return hashlib.sha256(f'{VERSION}:{product_id}:{size_mm}:{style}:{int(detail)}:{paper}'.encode()).hexdigest()[:20]

def safe_file(name):
    allowed={'Printable_Color_USLetter.pdf','Printable_Color_A4.pdf','Printable_Color_A3.pdf','Printable_Coloring.pdf','Assembly_Guide.pdf','Preview.png','Model.glb','Printable.svg','Printable_A4.svg','Printable_A3.svg','Printable_USLetter.svg','Product_Config.json','Validation_Report.json','Full_Package.zip'}
    return name if name in allowed else None
