"""Open-top brick chimney: one strip net, sloping feet on the actual roof plane."""
import math
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union


def geometry(t):
    if not t.get('chimney'):return None
    w,d,h,r=(t[k] for k in ('width','depth','wall_height','roof_rise'))
    ridge=[(x*w,h+z*r) for x,z in t.get('profile',[(0,0),(.5,1),(1,0)])]
    segments=list(zip(ridge,ridge[1:]))
    if t.get('chimney_placement')=='longest_slope':
        # Compare physical slope lengths; equal roofs use the right-hand face.
        a,b=max(segments,key=lambda ab:(round(math.dist(*ab),9),(ab[0][0]+ab[1][0])/2))
    else:
        # Preserve already-generated v4.3 snapshots.
        a,b=max((ab for ab in segments if (ab[0][0]+ab[1][0])/2>=w/2),key=lambda ab:ab[1][0]-ab[0][0])
    size=min(14,(b[0]-a[0])*.42,d*.22)
    cx=(a[0]+b[0])/2-w/2;cy=d*.18
    slope=(b[1]-a[1])/(b[0]-a[0])
    def z(x):return a[1]+(x+w/2-a[0])*slope+(.4 if t.get('roof_overhang_mm') else 0)
    corners=[(cx-size/2,cy-size/2),(cx+size/2,cy-size/2),(cx+size/2,cy+size/2),(cx-size/2,cy+size/2)]
    lows=[z(x) for x,y in corners];bottom=min(lows);top=max(lows)+24
    panels=[]
    for i,name in enumerate(('FRONT','RIGHT','BACK','LEFT')):
        j=(i+1)%4
        pts=[(0,lows[i]-bottom),(size,lows[j]-bottom),(size,top-bottom),(0,top-bottom)]
        xyz=[(*corners[i],lows[i]),(*corners[j],lows[j]),(*corners[j],top),(*corners[i],top)]
        panels.append(dict(id='CHIMNEY_'+name,points=pts,vertices=xyz))
    return dict(roof_segment=[a,b],size=size,panels=panels,footprint=[(*p,z(p[0])) for p in corners],top_mm=top)


def artwork(panel):
    from .confectionery import Painter,CREAM
    p=Painter(Polygon(panel['points']));w,h=p.shape.bounds[2:]
    p.polygon(panel['points'],'#ab593e')
    for row,y in enumerate(range(0,math.ceil(h),4)):
        p.line([(0,y),(w,y)],CREAM,.35)
        for x in range(-4 if row%2 else 0,math.ceil(w),8):p.line([(x,y),(x,y+4)],CREAM,.35)
    p.rect(0,h-3.5,w,3.5,CREAM)
    p.snow(.7,h-3,w-1.4)
    return p.shapes


def piece(t):
    g=geometry(t)
    if not g:return None
    from .gingerbread import base
    from .wide_tabs import flap
    size=g['size'];faces=[];art=[];folds=[];tabs=[];labels=[]
    for i,p in enumerate(g['panels']):
        dx=i*size
        faces.append(Polygon([(x+dx,y) for x,y in p['points']]))
        for s in artwork(p):
            s=dict(s)
            if s['type']=='circle':s['center']=[s['center'][0]+dx,s['center'][1]]
            else:s['points']=[(x+dx,y) for x,y in s['points']]
            if 'rings' in s:s['rings']=[[(x+dx,y) for x,y in ring] for ring in s['rings']]
            art.append(s)
        if i:folds.append([(dx,p['points'][0][1]),(dx,p['points'][3][1])])
    net=unary_union(faces)
    # Make the outer feet before the final inner foot to retain their full depth.
    for index in (0,1,3,2):
        face=faces[index]
        a,b=list(face.exterior.coords)[:2]
        tab=flap(a,b,depth=7.5).difference(net)
        if tab.geom_type=='MultiPolygon':
            tab=max(tab.geoms,key=lambda part:part.intersection(LineString([a,b])).length)
        if tab.geom_type!='Polygon' or tab.area<1:raise ValueError('Invalid chimney foot tab')
        tabs.append(tab);net=net.union(tab);folds.append([a,b])
    p=g['panels'][-1];x=4*size;low=p['points'][1][1];high=p['points'][2][1]
    tab=Polygon([(x,low+2),(x+8,low+4),(x+8,high-2),(x,high)])
    tabs.append(tab);net=net.union(tab);folds.append([(x,low+2),(x,high)])
    labels.append(('C1',tab.centroid.x,tab.centroid.y))
    art.extend(dict(type='polygon',points=list(tab.exterior.coords),fill='#fff1d3') for tab in tabs)
    return dict(id='CHIMNEY',shape=net,art=art,folds=folds,tabs=[tabs[-1]]+tabs[:-1],labels=labels,
                guide=[('C1',2,g['panels'][0]['points'][3][1]/2),('C1',x-2,(low+high)/2)],faces=faces)


def layout(t):
    p=piece(t)
    return [[(p,25,100)]] if p else []



def merge_with_roof_pages(pages, t):
    """Place the chimney on an existing roof page when it fits without scaling."""
    from .gingerbread import base
    from shapely.affinity import translate
    p=piece(t)
    if not p:return pages
    pages=[list(page) for page in pages]
    xmin,ymin,xmax,ymax=p['shape'].bounds
    width,height=xmax-xmin,ymax-ymin
    left,bottom,right,top=8.0,20.0,base.PAGE_W-8.0,base.PAGE_H-24.4
    for page in pages:
        occupied=[translate(item['shape'],xoff=x,yoff=y).buffer(1.5,join_style=2) for item,x,y in page]
        # Try candidate grid points with a 3 mm gap between cut outlines.
        y=bottom
        while y+height<=top+1e-6:
            x=left
            while x+width<=right+1e-6:
                tx,ty=x-xmin,y-ymin
                shape=translate(p['shape'],xoff=tx,yoff=ty)
                if all(shape.buffer(1.5,join_style=2).disjoint(other) for other in occupied):
                    page.append((p,tx,ty))
                    return pages
                x+=2
            y+=2
    pages.extend(layout(t))
    return pages

def validate(t):
    g=geometry(t)
    if not g:return []
    p=piece(t);panels=g['panels']
    checks={
        'chimney_net_area':abs(sum(f.area for f in p['faces'])+sum(f.area for f in p['tabs'])-p['shape'].area)<1e-6,
        'chimney_closed_wall_seams':all(math.dist(panels[i]['vertices'][1],panels[(i+1)%4]['vertices'][0])<1e-6 and math.dist(panels[i]['vertices'][2],panels[(i+1)%4]['vertices'][3])<1e-6 for i in range(4)),
        'chimney_roof_contact':all(math.dist(panel['vertices'][0],g['footprint'][i])<1e-6 for i,panel in enumerate(panels)),
        'chimney_open_top_level':all(abs(v[2]-g['top_mm'])<1e-6 for panel in panels for v in panel['vertices'][2:]),
        'chimney_fold_edges_uncut':all(p['shape'].boundary.intersection(LineString(edge)).length<1e-5 for edge in p['folds']),
    }
    return [dict(name=k,status='PASS' if v else 'FAIL',detail='One open-top chimney; sloped feet glued onto roof cap') for k,v in checks.items()]
