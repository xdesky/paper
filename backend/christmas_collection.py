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

VERSION = 'christmas-magic-1.2.0'
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
 {'id':'xm05_christmas_snowman','name':'Christmas Snowman','size':180,'difficulty':'Easy','component_names':['Three stacked box blocks','Top hat and holly','Carrot nose','Twig arms and scarf'],'description':'A friendly snowman prototype built around three stacked cuboid snow blocks, with a top hat, scarf, twig arms, and carrot nose.','kind':'snowman'},
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

def _radial_frustum(pid,center,bottom,top,height,color,sides=8,optional=False):
    x,y,z=center;phase=-math.pi/2-math.pi/sides;low=[];high=[]
    for i in range(sides):
        angle=phase+2*math.pi*i/sides;low.append((x+bottom*.5*math.cos(angle),y+bottom*.5*math.sin(angle),z));high.append((x+top*.5*math.cos(angle),y+top*.5*math.sin(angle),z+height))
    vertices=low+high;faces=[tuple(range(sides-1,-1,-1)),tuple(range(sides,2*sides))]
    faces += [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
    return Part(pid,color,vertices,faces,optional)

def _prism(pid, profile, depth, color, optional=False, center_y=0):
    # Profile coordinates are x,z pairs; extrusion axis is the model depth y.
    n=len(profile);front=[(x,center_y-depth/2,z) for x,z in profile];back=[(x,center_y+depth/2,z) for x,z in profile];faces=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]
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

def _faceted_star(pid,center_z,radius,depth,color,optional=False):
    outline=_star_profile(radius,.42);n=len(outline);front=[(x,-depth/2,center_z+z) for x,z in outline];back=[(x,depth/2,center_z+z) for x,z in outline];vertices=front+back+[(0,-depth*.85,center_z)];center=2*n;faces=[]
    for i in range(n):
        j=(i+1)%n;faces.extend([(center,i,j),(i,j,n+j,n+i)])
    faces.append(tuple(range(2*n-1,n-1,-1)))
    return Part(pid,color,vertices,faces,optional)

def _star_frame(pid, center_z, radius, depth, color):
    outer=_star_profile(radius,.44);inner=[(x*.20,z*.20) for x,z in outer];y0=-depth/2;y1=depth/2
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
        # Leave a clear pot below four overlapping, progressively narrower boughs.
        # The gaps between starts are smaller than each tier's height, like layered cardstock skirts.
        for i,(base,top,h) in enumerate([(.76,.40,.21),(.61,.32,.20),(.46,.24,.19),(.32,.15,.18)]):p.append(_radial_frustum(f'bough_tier_{i+1}',(0,0,.18+i*.16),base,top,h,'green',8))
        p += [_box('trunk',(0,0,.08),(.16,.16,.26),'brown'),_radial_frustum('planter',(0,0,0),.30,.25,.18,'red',8),_faceted_star('five_point_star',.99,.13,.10,'gold')]
    elif k=='santa':
        p += [_frustum('coat_body',(0,0,0),.43,.30,.48,'red',depth=.28),_octa_ball('head_shape',(0,-.005,.49),.16,.19,'cream'),_prism('face_print',[(-.13,.455),(.13,.455),(.15,.51),(.15,.59),(.12,.64),(.07,.675),(-.07,.675),(-.12,.64),(-.15,.59),(-.15,.51)],.012,'cream',center_y=-.23),_prism('hat',[(-.15,.68),(.15,.68),(.14,.78),(.08,.85),(.12,.89),(.06,.90),(-.02,.86),(-.10,.82),(-.15,.76)],.25,'red'),_box('hat_band',(0,-.005,.68),(.30,.27,.045),'white'),_octa_ball('hat_pom',(.12,-.01,.88),.045,.07,'white')]
        p += [_prism('raised_arm',[(-.20,.40),(-.30,.47),(-.40,.59),(-.48,.68),(-.55,.64),(-.48,.48),(-.37,.32),(-.23,.29)],.16,'red',center_y=-.015),_prism('gift_arm',[(.20,.43),(.33,.42),(.42,.32),(.37,.24),(.27,.30),(.19,.34)],.16,'red',center_y=-.04)]
        for s in (-1,1):p.append(_box(f'boot_{s}',(s*.12,-.01,.03),(.20,.28,.07),'dark'))
        p += [_prism('beard',[(-.16,.47),(-.14,.52),(-.10,.50),(-.05,.53),(0,.51),(.05,.53),(.10,.50),(.14,.52),(.16,.47),(.14,.40),(.09,.36),(.045,.39),(0,.34),(-.045,.39),(-.09,.36),(-.14,.40)],.035,'white',center_y=-.245),_prism('waving_mitten',[(-.55,.62),(-.57,.68),(-.53,.73),(-.49,.70),(-.46,.73),(-.42,.68),(-.45,.61),(-.50,.57)],.055,'dark',center_y=-.06)]
        if detail:p += [_frustum('gift_sack',(.37,.09,.37),.27,.19,.33,'green',depth=.23),_box('gift_parcel',(-.35,.04,.14),(.18,.18,.16),'gold',True)]
    elif k=='reindeer':
        p += [_octa_ball('body',(0,0,.22),.26,.38,'brown'),_prism('head',[(-.14,.79),(.14,.79),(.19,.69),(.17,.58),(.10,.51),(0,.48),(-.10,.51),(-.17,.58),(-.19,.69)],.25,'brown'),_octa_ball('red_nose',(0,-.14,.59),.048,.07,'red'),_prism('scarf',[(-.18,.48),(.18,.48),(.18,.42),(.08,.40),(.10,.22),(.02,.20),(-.02,.41),(-.18,.42)],.08,'red',center_y=-.15)]
        for s in (-1,1):
            p += [_box(f'leg_{s}_front',(s*.18,-.02,.12),(.09,.11,.25),'brown'),_box(f'leg_{s}_back',(s*.18,.10,.12),(.09,.11,.25),'brown'),_prism(f'antler_{s}',[(s*.04,.74),(s*.11,.82),(s*.10,.91),(s*.16,.87),(s*.22,.98),(s*.25,.95),(s*.19,.84),(s*.13,.78),(s*.08,.72)],.035,'brown'),_prism(f'ear_{s}',[(s*.11,.67),(s*.22,.73),(s*.18,.62)],.025,'brown')]
    elif k=='snowman':
        # The three clean cuboids are the structural body: a broad base, torso,
        # and smaller head. Their shallow overlaps make a stable paper stack.
        p += [_box('snow_block_lower',(0,0,0),(.58,.46,.34),'white'),_box('snow_block_middle',(0,0,.32),(.46,.38,.30),'white'),_box('snow_block_head',(0,0,.59),(.34,.32,.27),'white'),_prism('face_print',[(-.13,.65),(.13,.65),(.15,.70),(.14,.79),(.10,.835),(.05,.85),(-.05,.85),(-.10,.835),(-.14,.79),(-.15,.70)],.012,'white',center_y=-.17),_box('hat_brim',(0,0,.83),(.43,.38,.06),'dark'),_box('hat_crown',(0,0,.88),(.29,.28,.19),'dark'),_box('hat_band',(0,-.005,.90),(.30,.29,.045),'red'),_prism('carrot_nose',[(-.035,.72),(.075,.75),(-.035,.78)],.17,'gold',center_y=-.245)]
        p += [_prism('hat_holly_leaf_left',[(-.10,.98),(-.19,1.03),(-.13,1.06),(-.08,1.04),(-.04,1.08),(0,1.04)],.025,'green',center_y=-.16),_prism('hat_holly_leaf_right',[(.10,.98),(.19,1.03),(.13,1.06),(.08,1.04),(.04,1.08),(0,1.04)],.025,'green',center_y=-.16),_octa_ball('hat_holly_berries',(0,-.18,1.02),.025,.04,'red')]
        for s in (-1,1):p.append(_octa_ball(f'coal_eye_{s}',(s*.065,-.19,.785),.018,.024,'dark'))
        p.append(_prism('coal_smile',[(-.05,.70),(-.04,.68),(0,.675),(.04,.68),(.05,.70),(.035,.69),(0,.685),(-.035,.69)],.018,'dark',center_y=-.185))
        for s in (-1,1):
            hand=[(.40,.44),(.39,.48),(.43,.52),(.47,.50),(.51,.54),(.55,.50),(.59,.52),(.63,.48),(.62,.44),(.51,.34)]
            twig=[(.21,.49),(.25,.45),(.32,.55),(.34,.64),(.38,.66),(.36,.56),(.29,.47),(.39,.49),(.43,.54),(.46,.52),(.42,.45),(.29,.39),(.23,.42)]
            p += [_prism(f'arm_{s}',twig if s>0 else [(-x,z) for x,z in twig],.075,'brown',center_y=-.035),_prism(f'mitten_{s}',hand if s>0 else [(-x,z) for x,z in hand],.06,'red',center_y=-.11)]
        p += [_box('scarf',(0,-.005,.57),(.48,.40,.065),'red'),_prism('scarf_tail',[(-.08,.58),(.01,.58),(.06,.34),(.01,.30),(-.07,.33)],.065,'red',center_y=-.205)]
        for i,z in enumerate((.51,.42,.34),1):p.append(_box(f'coal_button_{i}',(0,-.205,z),(.055,.025,.055),'dark'))
    elif k=='sleigh':
        p += [_prism('sleigh_body',[(-.45,.27),(-.40,.49),(.36,.49),(.44,.35),(.32,.22),(-.32,.22)],.34,'red')]
        for s in (-1,1):p += [_prism(f'runner_{s}',[(-.51,.08),(-.40,.12),(.39,.12),(.52,.21),(.45,.24),(.34,.18),(-.45,.18)],.045,'gold'),_box(f'runner_brace_{s}',(s*.28,.06,.16),(.055,.14,.14),'dark')]
        if detail:
            for i,(x,y,w,h) in enumerate([(-.20,0,.16,.14),(0,0,.17,.18),(.19,0,.15,.13),(-.10,.12,.13,.12),(.12,.12,.13,.12)]):p.append(_box(f'gift_{i+1}',(x,y,.49),(w,w,h),('green','gold','red','blue','pink')[i],True))
    elif k=='nutcracker':
        p += [_frustum('uniform_body',(0,0,.19),.44,.36,.46,'red',depth=.27),_frustum('head',(0,-.005,.66),.30,.27,.28,'cream',depth=.24),_box('tall_hat',(0,.005,.94),(.40,.30,.15),'dark'),_box('hat_brim',(0,-.005,.85),(.43,.30,.055),'gold')]
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
        p.append(Part('ten_panel_ornament','red',v,faces));p += [_box('ornament_cap',(0,0,.99),(.23,.23,.12),'gold'),_prism('ornament_hanging_loop',[(-.025,1.07),(-.12,1.18),(-.11,1.29),(-.06,1.34),(0,1.30),(.06,1.34),(.11,1.29),(.12,1.18),(.025,1.07),(.01,1.18),(.045,1.25),(0,1.28),(-.045,1.25),(-.01,1.18)],.035,'gold'),_prism('ornament_bow_left',[(-.02,.99),(-.10,1.02),(-.27,1.12),(-.20,1.18),(-.04,1.10),(.015,1.04)],.065,'green'),_prism('ornament_bow_right',[(.02,.99),(.10,1.02),(.27,1.12),(.20,1.18),(.04,1.10),(-.015,1.04)],.065,'green')]
    elif k=='gift':
        p += [_box('gift_body',(0,0,.38),(.82,.82,.72),'red'),_box('removable_lid',(0,0,.75),(.90,.90,.12),'green'),_box('ribbon_front',(0,-.414,.38),(.12,.018,.72),'gold'),_box('ribbon_side',(.414,0,.38),(.018,.12,.72),'gold'),_box('ribbon_top',(0,0,.82),(.12,.91,.02),'gold')]
        if detail:p += [_prism('paper_bow_left',[(-.04,.89),(-.16,.91),(-.34,1.07),(-.26,1.15),(-.06,1.06),(.01,.98)],.075,'red',True,center_y=-.05),_prism('paper_bow_right',[(.04,.89),(.16,.91),(.34,1.07),(.26,1.15),(.06,1.06),(-.01,.98)],.075,'red',True,center_y=-.05),_box('paper_bow_knot',(0,-.06,.99),(.13,.09,.12),'gold',True)]
    # Normalize max dimension to 1. Product size is then an exact uniform scale.
    low=[min(v[i] for part in p for v in part.vertices) for i in range(3)];high=[max(v[i] for part in p for v in part.vertices) for i in range(3)]
    span=max(high[i]-low[i] for i in range(3));return p,low,high,span

def _palette(style):
    if style not in PALETTES:raise ValueError('Unknown Christmas texture variant.')
    return PALETTES[style]

def _svg_art(width,height,product,part_id,face_id,palette,style,base_color='cream',front=False):
    """Print-ready face art keyed to the actual component, shared by SVG and GLB."""
    kind=BY_ID[product]['kind'];coloring=style=='coloring';W=max(width,.1);H=max(height,.1);m=min(W,H)
    base=palette['white'] if coloring else palette.get(base_color,palette['cream']);edge='#302c2a' if coloring else palette['dark'];cream='#302c2a' if coloring else palette['cream'];red='#302c2a' if coloring else palette['red'];green='#302c2a' if coloring else palette['green'];gold='#302c2a' if coloring else palette['gold'];white='#fff' if coloring else palette['white'];brown='#302c2a' if coloring else palette['brown']
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.4f}mm" height="{H:.4f}mm" viewBox="0 0 {W:.4f} {H:.4f}"><rect x="0" y="0" width="{W:.4f}" height="{H:.4f}" fill="{base}"/>']
    for i in range(8):
        x=W*((i*.173+.07)%1);y=H*((i*.293+.11)%1);out.append(f'<path d="M{x:.2f} {y:.2f}l{m*.025:.2f} {-m*.018:.2f}" stroke="{edge}" stroke-width=".18" opacity=".10"/>')
    # Product-specific printed details, positioned on front-facing geometry faces.
    if kind=='house':
        if part_id=='house_body' and front:
            out += [f'<path d="M{W*.12} {H*.37} Q{W*.5} {H*.26} {W*.88} {H*.37}" fill="none" stroke="{cream}" stroke-width="{m*.025:.2f}" stroke-linecap="round"/>',f'<path d="M{W*.18} {H*.43}l{W*.12} {-H*.08}l{W*.12} {H*.08} M{W*.58} {H*.43}l{W*.12} {-H*.08}l{W*.12} {H*.08}" fill="none" stroke="{cream}" stroke-width="{m*.018:.2f}"/>']
            out.append(f'<rect x="{W*.39}" y="{H*.60}" width="{W*.22}" height="{H*.39}" rx="{m*.035:.2f}" fill="{red}" stroke="{edge}" stroke-width="{m*.012:.2f}"/><circle cx="{W*.57}" cy="{H*.79}" r="{m*.012:.2f}" fill="{gold}"/>')
            for x in (.17,.67):out.append(f'<rect x="{W*x}" y="{H*.49}" width="{W*.16}" height="{H*.19}" rx="{m*.018:.2f}" fill="{gold}" stroke="{cream}" stroke-width="{m*.018:.2f}"/><path d="M{W*(x+.08)} {H*.49}v{H*.19}m{-W*.08} {-H*.095}h{W*.16}" stroke="{edge}" stroke-width="{m*.012:.2f}"/>')
            out.append(f'<path d="M{W*.33} {H*.64}l{W*.035} {H*.05}l{-W*.035} {H*.05}l{W*.035} {H*.05}l{-W*.035} {H*.05} M{W*.67} {H*.64}l{W*.035} {H*.05}l{-W*.035} {H*.05}l{W*.035} {H*.05}l{-W*.035} {H*.05}" fill="none" stroke="{red}" stroke-width="{m*.025:.2f}" stroke-linecap="round"/>')
        elif part_id=='house_body' and int(face_id.rsplit('.',1)[-1]) in (4,5):
            for row in range(5):
                yy=H*(.12+row*.17);out.append(f'<path d="M0 {yy:.2f}h{W:.2f}" stroke="{cream}" stroke-width="{m*.018:.2f}"/>')
                for x in ((.25,.75) if row%2==0 else (.05,.55)):out.append(f'<path d="M{W*x:.2f} {yy:.2f}v{H*.17:.2f}" stroke="{cream}" stroke-width="{m*.014:.2f}"/>')
            out.append(f'<path d="M0 {H*.88:.2f}q{W*.08} {H*.13:.2f} {W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0" fill="none" stroke="{white}" stroke-width="{m*.09:.2f}"/>')
    elif kind=='tree':
        if part_id.startswith('bough_tier_'):
            out.append(f'<path d="M0 {H*.82:.2f} q{W*.08} {H*.23:.2f} {W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0" fill="none" stroke="{cream}" stroke-width="{H*.22:.2f}"/>')
            out.append(f'<path d="M{W*.06} {H*.35} Q{W*.5} {H*.65} {W*.94} {H*.35}" fill="none" stroke="{white}" stroke-width="{m*.025:.2f}" stroke-dasharray="{m*.012:.2f} {m*.028:.2f}" stroke-linecap="round"/>')
            for x,y,c in ((.22,.48,'red'),(.75,.53,'gold'),(.49,.68,'red')):out.append(f'<circle cx="{W*x:.2f}" cy="{H*y:.2f}" r="{m*.055:.2f}" fill="{palette[c] if not coloring else "white"}" stroke="{cream}" stroke-width="{m*.014:.2f}"/><path d="M{W*x:.2f} {H*(y-.06):.2f}v{-H*.035:.2f}" stroke="{gold}" stroke-width="{m*.015:.2f}"/>')
            if H>22:out.append(f'<path d="M{W*.39} {H*.19}q{W*.11} {-H*.1} {W*.22} 0q{-W*.11} {H*.12} {-W*.22} 0m{W*.11} {-H*.045}v{H*.13}" fill="{red}" stroke="{edge}" stroke-width="{m*.012:.2f}"/>')
        elif part_id=='planter':out.append(f'<path d="M0 {H*.72}h{W} M0 {H*.82}h{W}" stroke="{gold}" stroke-width="{m*.08:.2f}"/>')
        elif part_id=='five_point_star':out.append(f'<path d="M{W*.5} {H*.12}L{W*.57} {H*.42}L{W*.9} {H*.43}L{W*.64} {H*.61}L{W*.75} {H*.91}L{W*.5} {H*.72}L{W*.25} {H*.91}L{W*.36} {H*.61}L{W*.1} {H*.43}L{W*.43} {H*.42}Z" fill="none" stroke="{cream}" stroke-width="{m*.018:.2f}"/>')
    elif kind in ('santa','snowman','nutcracker'):
        if kind=='snowman' and part_id.startswith('snow_block_'):
            # Light snowflake engraving gives the three white blocks a clear
            # winter surface without competing with the face or coal buttons.
            for cx,cy in ((.30,.34),(.72,.68)):
                out.append(f'<path d="M{W*cx:.2f} {H*(cy-.10):.2f}v{H*.20:.2f}m{-W*.08:.2f} {-H*.10:.2f}h{W*.16:.2f}m{-W*.055:.2f} {-H*.07:.2f}l{W*.11:.2f} {H*.14:.2f}m0 {-H*.14:.2f}l{-W*.11:.2f} {H*.14:.2f}" fill="none" stroke="{palette["blue"] if not coloring else edge}" stroke-width="{m*.016:.2f}" stroke-linecap="round" opacity=".65"/>')
        if part_id in ('face','head','face_print') and front:
            out += [f'<path d="M{W*.25} {H*.38}q{W*.08} {-H*.06} {W*.16} 0 M{W*.59} {H*.38}q{W*.08} {-H*.06} {W*.16} 0" fill="none" stroke="{edge}" stroke-width="{m*.045:.2f}" stroke-linecap="round"/>',f'<circle cx="{W*.34}" cy="{H*.46}" r="{m*.035:.2f}" fill="{edge}"/><circle cx="{W*.66}" cy="{H*.46}" r="{m*.035:.2f}" fill="{edge}"/><circle cx="{W*.23}" cy="{H*.57}" r="{m*.07:.2f}" fill="{red}" opacity=".62"/><circle cx="{W*.77}" cy="{H*.57}" r="{m*.07:.2f}" fill="{red}" opacity=".62"/>']
            if kind=='santa':out.append(f'<path d="M{W*.40} {H*.55}q{W*.10} {H*.08} {W*.20} 0q{-W*.10} {H*.15} {-W*.20} 0Z" fill="{white}"/><circle cx="{W*.5}" cy="{H*.55}" r="{m*.06:.2f}" fill="{red}"/>')
            elif kind=='snowman':out.append(f'<path d="M{W*.5} {H*.49}l{W*.28} {H*.04}l{-W*.28} {H*.06}Z" fill="{palette["gold"] if not coloring else "white"}" stroke="{edge}" stroke-width="{m*.012:.2f}"/><path d="M{W*.36} {H*.67}q{W*.14} {H*.12} {W*.28} 0" fill="none" stroke="{edge}" stroke-width="{m*.025:.2f}"/>')
            else:out.append(f'<path d="M{W*.5} {H*.55}q{W*.05} {H*.08} {W*.10} 0q{W*.04} {H*.09} {W*.08} 0" fill="none" stroke="{edge}" stroke-width="{m*.04:.2f}"/>')
        if part_id=='coat_body' or part_id=='uniform_body':
            out.append(f'<path d="M{W*.18} {H*.67}h{W*.64}" stroke="{palette["dark"] if not coloring else edge}" stroke-width="{H*.12:.2f}"/><path d="M{W*.5} {H*.62}v{H*.27}" stroke="{gold}" stroke-width="{m*.025:.2f}"/>')
            for i in range(3):out.append(f'<circle cx="{W*.5}" cy="{H*(.30+i*.13):.2f}" r="{m*.035:.2f}" fill="{gold}"/>')
            out.append(f'<path d="M0 {H*.88}q{W*.08} {H*.18} {W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0" fill="none" stroke="{white}" stroke-width="{H*.12:.2f}"/>')
        elif part_id in ('hat','hat_band','hat_brim'):out.append(f'<path d="M0 {H*.78}h{W}" stroke="{cream}" stroke-width="{H*.18:.2f}"/>')
        elif part_id=='beard':out.append(f'<path d="M0 {H*.35}q{W*.08} {H*.25} {W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0t{W*.16} 0" fill="none" stroke="{cream}" stroke-width="{H*.22:.2f}"/>')
    elif kind=='reindeer':
        if part_id=='head' and front:out += [f'<circle cx="{W*.34}" cy="{H*.40}" r="{m*.04:.2f}" fill="{edge}"/><circle cx="{W*.66}" cy="{H*.40}" r="{m*.04:.2f}" fill="{edge}"/><path d="M{W*.5} {H*.53}q{W*.18} {H*.18} {W*.30} 0" fill="none" stroke="{edge}" stroke-width="{m*.025:.2f}"/>']
        if part_id=='body' and front:out.append(f'<path d="M{W*.28} {H*.28}q{W*.22} {-H*.18} {W*.44} 0v{H*.45}q{-W*.22} {H*.15} {-W*.44} 0Z" fill="{cream}"/>')
        if part_id=='scarf':out.append(f'<path d="M{W*.15} {H*.15}v{H*.7} M{W*.35} {H*.15}v{H*.7} M{W*.55} {H*.15}v{H*.7} M{W*.75} {H*.15}v{H*.7}" stroke="{cream}" stroke-width="{m*.06:.2f}"/>')
        if part_id.startswith('antler'):out.append(f'<path d="M{W*.5} {H*.2}v{H*.6}m0 {-H*.3}l{-W*.25} {-H*.28}m{W*.25} {H*.13}l{W*.25} {-H*.3}" fill="none" stroke="{gold}" stroke-width="{m*.04:.2f}"/>')
    elif kind in ('sleigh','gift'):
        if kind=='sleigh' and part_id=='sleigh_body':
            out.append(f'<path d="M{W*.08} {H*.75}q{W*.10} {H*.18} {W*.2} 0t{W*.2} 0t{W*.2} 0t{W*.2} 0t{W*.2} 0" fill="none" stroke="{cream}" stroke-width="{H*.10:.2f}"/>')
            out.append(f'<circle cx="{W*.5}" cy="{H*.42}" r="{m*.16:.2f}" fill="{palette["green"] if not coloring else "white"}" stroke="{cream}" stroke-width="{m*.025:.2f}"/><circle cx="{W*.43}" cy="{H*.39}" r="{m*.035:.2f}" fill="{red}"/><circle cx="{W*.57}" cy="{H*.39}" r="{m*.035:.2f}" fill="{red}"/>')
        elif part_id.startswith('gift_') or part_id=='gift_body':
            for x,y in ((.22,.24),(.73,.28),(.34,.63),(.76,.75),(.16,.83)):out.append(f'<circle cx="{W*x:.2f}" cy="{H*y:.2f}" r="{m*.035:.2f}" fill="{gold}"/>')
            out.append(f'<path d="M{W*.5} 0v{H} M0 {H*.5}h{W}" stroke="{cream}" stroke-width="{m*.055:.2f}"/>')
        elif part_id.startswith('runner'):out.append(f'<path d="M0 {H*.82}q{W*.18} {H*.20} {W*.36} 0t{W*.36} 0t{W*.28} 0" fill="none" stroke="{cream}" stroke-width="{m*.08:.2f}"/>')
        elif part_id in ('removable_lid','ribbon_top','paper_bow_left','paper_bow_right'):
            for i in range(3):out.append(f'<path d="M{W*(.2+i*.3):.2f} 0l{W*.2:.2f} {H:.2f}" stroke="{gold}" stroke-width="{m*.018:.2f}"/>')
    elif kind=='lantern':
        for i in range(5):
            a=2*math.pi*i/5;cx=W*(.5+.29*math.cos(a));cy=H*(.5+.29*math.sin(a));out.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{m*.045:.2f}" fill="{red}"/><path d="M{cx:.2f} {cy-m*.11:.2f}v{m*.22:.2f}m{-m*.11:.2f} {-m*.11:.2f}h{m*.22:.2f}" stroke="{gold}" stroke-width="{m*.018:.2f}"/>')
    elif kind=='ornament':
        out.append(f'<path d="M{W*.08} {H*.16}h{W*.84} M{W*.05} {H*.83}h{W*.90}" stroke="{gold}" stroke-width="{m*.025:.2f}"/>')
        for i in range(6):
            x=W*(.18+.13*i);out.append(f'<path d="M{x:.2f} {H*.28:.2f}v{H*.4:.2f}" stroke="{cream}" stroke-width="{m*.012:.2f}"/>')
        out.append(f'<path d="M{W*.5} {H*.38}v{H*.24}m{-W*.11} {-H*.12}h{W*.22}m{-W*.08} {-H*.08}l{W*.16} {H*.16}m0 {-H*.16}l{-W*.16} {H*.16}" stroke="{white}" stroke-width="{m*.025:.2f}" stroke-linecap="round"/>')
    # Subtle printed snow, edge rules and a clean coloring-book outline.
    if kind not in ('tree','house') and part_id not in ('face','head'):out.append(f'<circle cx="{W*.12}" cy="{H*.14}" r="{m*.018:.2f}" fill="{cream}"/><circle cx="{W*.88}" cy="{H*.86}" r="{m*.018:.2f}" fill="{cream}"/>')
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
            sid=f'{part.id}.{fi+1:02d}';surface={'id':sid,'componentId':part.id,'faceIndex':fi,'polygon_mm':coords,'vertices_3d_mm':xyz,'width_mm':width,'height_mm':height,'art':_svg_art(width,height,product_id,part.id,sid,palette,style,part.color,n[1]<-.35),'color':palette[part.color]}
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
    width=height=800;im=Image.new('RGB',(width,height),'#fbf8f0');draw=ImageDraw.Draw(im);allv=[v for _,vs,_ in model['meshes'] for v in vs];sx=lambda v:(v[0]+v[1])*.72;sy=lambda v:-v[2]+(v[0]-v[1])*.38
    coords=[(sx(v),sy(v)) for v in allv];minx=min(x for x,y in coords);maxx=max(x for x,y in coords);miny=min(y for x,y in coords);maxy=max(y for x,y in coords);scale=min(560/max(1,maxx-minx),630/max(1,maxy-miny));ox=400-(minx+maxx)*scale/2;oy=435-(miny+maxy)*scale/2
    draw.ellipse((205,650,595,705),fill='#eae3d7');pixels=np.asarray(im).copy();depth_buffer=np.full((height,width),-np.inf,dtype=np.float32);surfaces={(s['componentId'],s['faceIndex']):s for s in model['surfaces']};textures={}
    for part,verts,faces in model['meshes']:
        for fi,face in enumerate(faces):
            surface=surfaces[(part.id,fi)];key=(part.id,fi)
            if key not in textures:
                try:
                    with pymupdf.open(stream=surface['art'].encode(),filetype='svg') as doc:
                        pix=doc[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False);textures[key]=np.asarray(Image.frombytes('RGB',(pix.width,pix.height),pix.samples))
                except Exception:textures[key]=None
            texture=textures[key];projected=[(ox+sx(verts[j])*scale,oy+sy(verts[j])*scale) for j in face]
            if texture is None:continue
            src=[(surface['polygon_mm'][j][0]/max(surface['width_mm'],.001)*(texture.shape[1]-1),(1-surface['polygon_mm'][j][1]/max(surface['height_mm'],.001))*(texture.shape[0]-1)) for j in range(len(face))];view_depth=[verts[j][0]-verts[j][1]+.76*verts[j][2] for j in face]
            for i in range(1,len(face)-1):
                tri=[projected[j] for j in (0,i,i+1)];uv=[src[j] for j in (0,i,i+1)];zd=[view_depth[j] for j in (0,i,i+1)];left=max(0,math.floor(min(x for x,y in tri)));right=min(width,math.ceil(max(x for x,y in tri)));top=max(0,math.floor(min(y for x,y in tri)));bottom=min(height,math.ceil(max(y for x,y in tri)))
                if right<=left or bottom<=top:continue
                den=(tri[1][1]-tri[2][1])*(tri[0][0]-tri[2][0])+(tri[2][0]-tri[1][0])*(tri[0][1]-tri[2][1])
                if abs(den)<1e-7:continue
                gx,gy=np.meshgrid(np.arange(left,right)+.5,np.arange(top,bottom)+.5);w0=((tri[1][1]-tri[2][1])*(gx-tri[2][0])+(tri[2][0]-tri[1][0])*(gy-tri[2][1]))/den;w1=((tri[2][1]-tri[0][1])*(gx-tri[2][0])+(tri[0][0]-tri[2][0])*(gy-tri[2][1]))/den;w2=1-w0-w1;inside=(w0>=0)&(w1>=0)&(w2>=0);z=w0*zd[0]+w1*zd[1]+w2*zd[2];current=depth_buffer[top:bottom,left:right];visible=inside&(z>=current)
                if not visible.any():continue
                u=np.clip(np.rint(w0*uv[0][0]+w1*uv[1][0]+w2*uv[2][0]).astype(int),0,texture.shape[1]-1);v=np.clip(np.rint(w0*uv[0][1]+w1*uv[1][1]+w2*uv[2][1]).astype(int),0,texture.shape[0]-1);crop=pixels[top:bottom,left:right];crop[visible]=texture[v[visible],u[visible]];current[visible]=z[visible]
    im=Image.fromarray(pixels);draw=ImageDraw.Draw(im)
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
