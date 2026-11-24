"""A real, printable over-roof: retain structural shell, glue a larger cap above it."""
import math
import numpy as np
from shapely.geometry import Polygon, Point


def build(t):
    from .gingerbread import model,Panel,base
    e=float(t.get('roof_overhang_mm',0))
    if not e:return {},[],[],[]
    rake=float(t.get('roof_rake_mm',6));lift=.4
    shell,seams,_,_,_=model(t)
    caps={}
    for pid,p in shell.items():
        if not pid.startswith('ROOF'):continue
        side_edges={int(m['edge']) for seam in seams for m in seam['occurrences'] if m['panel']==pid and any(o['panel'] in ('LEFT','RIGHT') for o in seam['occurrences'])}
        width,height=p.square.bounds[2:]
        low=-e if 0 in side_edges else 0
        high=height+e if 2 in side_edges else height
        pts=[(0,0),(width+2*rake,0),(width+2*rake,high-low),(0,high-low)]
        basis=np.linalg.lstsq(np.column_stack([p.points,np.ones(len(p.points))]),np.array(p.vertices),rcond=None)[0]
        xyz=[(np.array([x-rake,y+low,1])@basis+np.array([0,0,lift])).tolist() for x,y in pts]
        capid='CAP_'+pid;caps[capid]=Panel(capid,pts,xyz)
    capseams=[]
    for s in seams:
        if not all('CAP_'+m['panel'] in caps for m in s['occurrences']):continue
        mates=[dict(panel='CAP_'+m['panel'],edge=m['edge']) for m in s['occurrences']]
        capseams.append(dict(id='R'+str(len(capseams)+1),occurrences=mates,length_mm=t['depth']+2*rake,fold_degrees=s['fold_degrees'],hinge=False))
    lookup={s['id']:s for s in capseams}
    used=set()
    for s in capseams:
        ids=tuple(m['panel'] for m in s['occurrences'])
        # A fold-connected blank is optional when the full-size roof exceeds the sheet.
        s['hinge']=not used.intersection(ids) and base.fits(base.construct_unit(ids,s['id'],caps,lookup))
        if s['hinge']:used.update(ids)
        for m in s['occurrences']:caps[m['panel']].edges[m['edge']]=s['id']
        if not s['hinge']:
            owner=s['occurrences'][0];p=caps[owner['panel']]
            p.tabs[owner['edge']]=base.base.flap_for_edge(*p.seg(owner['edge']),depth=3)
    units=[base.construct_unit(tuple(m['panel'] for m in s['occurrences']),s['id'],caps,lookup) for s in capseams if s['hinge']]
    placed={pid for u in units for pid in u.ids}
    units.extend(base.construct_unit((pid,),None,caps,lookup) for pid in caps if pid not in placed)
    if not all(base.fits(u) for u in units):raise ValueError('Over-roof exceeds paper: no scaling allowed')
    pages=base.pack_units(units)
    return caps,capseams,units,pages


def artwork(t,p):
    from .gingerbread import Panel
    from .confectionery import house_art, Painter, CREAM, RED, GREEN
    if t.get('motif')=='gingerbread_village':
        from .coloring import COLORING
        # This collection follows the baked-cookie village reference: scored
        # shingles and a clean overhang instead of piped icing and candy.
        brush=Painter(p.square)
        brush.polygon(p.points,'#ffffff' if COLORING.get() else t['roof'])
        width,height=p.square.bounds[2:]
        for row,y in enumerate(np.arange(5,height-2,7)):
            brush.line([(2,float(y)),(width-2,float(y))],'#7c442c',.55)
            for x in np.arange(8+(row%2)*5,width-4,13):
                brush.line([(float(x),float(y)),(float(x),float(min(y+3,height-2)))],'#7c442c',.45)
        brush.line([(1,1),(width-1,1)],t['trim'],.9)
        return brush.shapes
    # Use roof artwork rather than the wall motifs selected by CAP_ IDs.
    result=house_art(t,Panel('ROOF_CAP',p.points,p.vertices))
    brush=Painter(p.square);w,h=p.square.bounds[2:]
    # Thick sculpted icing and suspended icicles along the true outside perimeter.
    for x in np.arange(3,w-2,4.8):
        brush.pipe([(float(x),2),(float(x),4.2+1.2*math.sin(x))],2)
    brush.pipe([(2,2),(w-2,2)],3.1)
    for side in (2.4,w-2.4):
        brush.pipe([(side,2),(side,h-2)],2.6)
        for i,y in enumerate(np.arange(6,h-3,8)):
            brush.jewel(side,float(y),1.1,RED if i%2 else GREEN)
    from .chimney import geometry as chimney_geometry
    chimney=chimney_geometry(t)
    if chimney:
        basis=np.linalg.lstsq(np.column_stack([p.points,np.ones(len(p.points))]),np.array(p.vertices),rcond=None)[0]
        local=[np.linalg.lstsq(basis.T,np.array(v),rcond=None)[0] for v in chimney['footprint']]
        if all(abs(q[2]-1)<1e-6 and p.square.buffer(1e-6).covers(Point(q[0],q[1])) for q in local):
            brush.line([(q[0],q[1]) for q in local]+[(local[0][0],local[0][1])],'#666666',.25)
    return result+brush.shapes


def layout(t):
    from .gingerbread import base
    caps,seams,units,pages=build(t)
    result=[]
    for page in pages:
        pieces=[]
        for i,u in enumerate(page['units']):
            art=[];folds=[];labels=[];tabs=[];guide=[]
            for pid in u.ids:
                p=caps[pid]
                for original in artwork(t,p):
                    shape=dict(original)
                    if shape['type']=='circle':shape['center']=u.transform(pid,shape['center'])
                    else:shape['points']=[u.transform(pid,q) for q in shape['points']]
                    if 'rings' in shape:shape['rings']=[[u.transform(pid,q) for q in ring] for ring in shape['rings']]
                    art.append(shape)
                for edge,tab in p.tabs.items():
                    transformed=Polygon([u.transform(pid,q) for q in tab.exterior.coords])
                    art.append(dict(type='polygon',points=list(transformed.exterior.coords),fill='#fff1d3'))
                    tabs.append(transformed);labels.append((p.edges[edge],transformed.centroid.x,transformed.centroid.y))
                    folds.append([u.transform(pid,q) for q in p.seg(edge)])
                for edge,code in p.edges.items():
                    a,b=p.seg(edge);mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
                    center=p.square.centroid;dx,dy=center.x-mid[0],center.y-mid[1];length=math.hypot(dx,dy)
                    guide.append((code,*u.transform(pid,(mid[0]+dx/length*4,mid[1]+dy/length*4))))
            if u.hinge_id:
                s=next(s for s in seams if s['id']==u.hinge_id);m=s['occurrences'][0]
                folds.append([u.transform(m['panel'],q) for q in caps[m['panel']].seg(m['edge'])])
            outline=u.shape()
            radius=t.get('roof_corner_radius_mm',0)
            if radius:
                outline=outline.buffer(-radius,join_style=2).buffer(radius,quad_segs=8)
            pieces.append((dict(id='CAP_'+str(i),shape=outline,art=art,folds=folds,labels=labels,tabs=tabs,guide=guide),0,0))
        result.append(pieces)
    return result


def metadata(t):
    caps,seams,units,pages=build(t)
    from .chimney import merge_with_roof_pages
    shape_pages=[[(dict(id='CAP',shape=u.shape()),0,0) for u in page['units']] for page in pages]
    accessory_roof_pages=len(merge_with_roof_pages(shape_pages,t))
    return dict(sheet_count=len(pages),accessory_sheet_count=accessory_roof_pages,cut_pieces=len(units),fold_hinges=sum(s['hinge'] for s in seams),glue_seams=sum(not s['hinge'] for s in seams),
                rake_mm=t.get('roof_rake_mm',6),slope_extension_mm=t.get('roof_overhang_mm',0),layer_offset_mm=.4,corner_radius_mm=t.get('roof_corner_radius_mm',0))


def validate(t):
    from .gingerbread import model
    from shapely.geometry import Point,LineString
    caps,seams,units,pages=build(t)
    if not caps:return []
    shell,shell_seams,_,_,_=model(t)
    coverage=True;parallel=True;matching=True;hinges=True;overhang=True
    for pid,p in caps.items():
        source=shell[pid.removeprefix('CAP_')]
        origin=np.array(source.vertices[0]);normal=np.cross(np.subtract(source.vertices[1],origin),np.subtract(source.vertices[2],origin));normal/=np.linalg.norm(normal)
        parallel &= all(abs(np.dot(np.array(v)-origin-np.array([0,0,.4]),normal))<1e-5 for v in p.vertices)
        basis=np.linalg.lstsq(np.column_stack([p.points,np.ones(len(p.points))]),p.vertices,rcond=None)[0]
        for v in source.vertices:
            local=np.linalg.lstsq(basis.T,np.array(v)+[0,0,.4],rcond=None)[0]
            coverage &= p.square.buffer(1e-5).covers(Point(local[0],local[1]))
        rake=t.get('roof_rake_mm',6)
        overhang &= abs(min(v[1] for v in p.vertices)+t['depth']/2+rake)<1e-5
        overhang &= abs(max(v[1] for v in p.vertices)-t['depth']/2-rake)<1e-5
        slope_axis=np.subtract(source.vertices[3],source.vertices[0])
        slope_axis/=np.linalg.norm(slope_axis)
        offsets=[np.dot(np.array(v)-origin-[0,0,.4],slope_axis) for v in p.vertices]
        wall_edges={int(m['edge']) for seam in shell_seams for m in seam['occurrences']
                    if m['panel']==source.id and any(o['panel'] in ('LEFT','RIGHT') for o in seam['occurrences'])}
        extension=t['roof_overhang_mm']
        overhang &= abs(min(offsets)-(-extension if 0 in wall_edges else 0))<1e-5
        overhang &= abs(max(offsets)-(source.square.bounds[3]+(extension if 2 in wall_edges else 0)))<1e-5
    for s in seams:
        points=[]
        for m in s['occurrences']:
            p=caps[m['panel']];i=int(m['edge']);points.append((p.vertices[i],p.vertices[(i+1)%4]))
        matching &= math.dist(points[0][0],points[1][1])<1e-5 and math.dist(points[0][1],points[1][0])<1e-5
    for u in units:
        if not u.hinge_id:continue
        s=next(s for s in seams if s['id']==u.hinge_id)
        segments=[[u.transform(m['panel'],q) for q in caps[m['panel']].seg(m['edge'])] for m in s['occurrences']]
        hinges &= math.dist(segments[0][0],segments[1][1])<1e-5 and math.dist(segments[0][1],segments[1][0])<1e-5 and u.shape().boundary.intersection(LineString(segments[0])).length<1e-5
    area=abs(sum(p.square.area+sum(tab.area for tab in p.tabs.values()) for p in caps.values())-sum(u.shape().area for u in units))<1e-5
    tests=[('roof_cap_overhang_dimensions',overhang),('roof_cap_covers_support',coverage),('roof_cap_parallel_to_support',parallel),('roof_cap_3d_seams',matching),('roof_cap_uncut_hinges',hinges),('roof_cap_area_no_overlap',area)]
    return [dict(name=name,status='PASS' if ok else 'FAIL',detail=f"{t.get('roof_rake_mm',6):g} mm front/back; {t.get('roof_overhang_mm',0):g} mm along outer slope") for name,ok in tests]
