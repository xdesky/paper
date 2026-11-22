"""Safe personalized nameplates, rendered as shared vector glyph outlines."""
import math
import unicodedata
from functools import lru_cache
from pathlib import Path
from shapely.geometry import box,LineString

MAX_NAME_LENGTH=24

def normalize_name(value):
    if value is None or not isinstance(value,str):return value
    value=' '.join(unicodedata.normalize('NFC',value).split())
    if len(value)>MAX_NAME_LENGTH:raise ValueError('Use no more than 24 characters.')
    if any(not (c in " -.'&!,0123456789" or 'LATIN' in unicodedata.name(c,'')) for c in value):
        raise ValueError('Use Latin letters (including accented letters), numbers, spaces, or - . & ! , and apostrophes.')
    return value

@lru_cache(maxsize=128)
def text_polygons(text):
    import matplotlib
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    font=FontProperties(fname=str(Path(matplotlib.get_data_path())/'fonts/ttf/DejaVuSans-Bold.ttf'))
    path=TextPath((0,0),text,size=1,prop=font)
    bounds=path.get_extents()
    return [p.tolist() for p in path.to_polygons()],(bounds.x0,bounds.y0,bounds.x1,bounds.y1)


def nameplate(t,panel):
    name=normalize_name(t.get('personal_name',''))
    if not name or panel.id!='FRONT':return []
    from .confectionery import Painter,CREAM
    from .coloring import COLORING
    w=panel.square.bounds[2];wh=t['wall_height']
    center_top=LineString([(w/2,0),(w/2,1000)]).intersection(panel.square).bounds[3]
    # Reserve space for the house's printed icing and its cut/fold outline.
    preferred=wh+(center_top-wh)*.30 if center_top-wh>18 else wh-9
    if t.get('bay_count',1)>1:preferred=wh-10
    bh=8.4
    # 20 CSS px at 96 dpi correspond to about 5.3 mm in the print artwork.
    name_bounds=text_polygons(name)[1]
    desired_width=(name_bounds[2]-name_bounds[0])*2.7+2*(20*25.4/96)
    safe=panel.square.buffer(-6.0)
    placement=None
    for cy in (preferred, wh-10, wh-13, wh-16):
        bw=min(42,w*.48,max(17,desired_width))
        while bw>=17:
            if safe.covers(box(w/2-bw/2,cy-bh/2,w/2+bw/2,cy+bh/2)):
                placement=(cy,bw)
                break
            bw-=1
        if placement:break
    if not placement:raise ValueError('There is not enough space for the nameplate.')
    cy,bw=placement
    text_padding = 20*25.4/96 if bw >= desired_width-0.01 else 2.0
    paint=Painter(panel.square)
    # A small rounded enamel plaque and a fine inset border keep the name legible.
    plaque=box(w/2-bw/2,cy-bh/2,w/2+bw/2,cy+bh/2).buffer(-1.15,join_style=1).buffer(1.15,join_style=1)
    paint.polygon(plaque.exterior.coords,'#ad2534')
    inset=box(w/2-bw/2+.65,cy-bh/2+.65,w/2+bw/2-.65,cy+bh/2-.65).buffer(-.7,join_style=1).buffer(.7,join_style=1)
    paint.line(list(inset.exterior.coords),'#f9e8d9',.25)
    # Small snowflakes sit in the side padding, clear of both text and outline.
    for x in (w/2-bw/2+1.6,w/2+bw/2-1.6):
        for dx,dy in ((1,0),(.5,.866),(.5,-.866)):
            paint.line([(x-dx*.48,cy+bh/2-1.2-dy*.48),(x+dx*.48,cy+bh/2-1.2+dy*.48)],CREAM,.22)

    # Fit one or two centred lines. Outlines avoid font substitution in print/3D.
    def width(text):b=text_polygons(text)[1];return b[2]-b[0]
    lines=[name]
    if width(name)*2.7>bw-2*text_padding:
        candidates=[i for i,c in enumerate(name) if c==' '] or list(range(1,len(name)))
        split=min(candidates,key=lambda i:max(width(name[:i].strip()),width(name[i:].strip())))
        lines=[name[:split].strip(),name[split:].strip()]
    if len(lines)==2 and min(2.7,max(1,bw-2*text_padding)/max(width(line) for line in lines))<1.5:
        candidates=[i for i,c in enumerate(name) if c==' '] or list(range(1,len(name)))
        triples=[(name[:i].strip(),name[i:j].strip(),name[j:].strip()) for i in candidates for j in candidates if i<j and name[:i].strip() and name[i:j].strip() and name[j:].strip()]
        if triples:lines=list(min(triples,key=lambda parts:max(width(line) for line in parts)))
    scale=min(2.7 if len(lines)<3 else 2.0,max(1,bw-2*text_padding)/max(width(line) for line in lines))
    for i,line in enumerate(lines):
        rings,bounds=text_polygons(line);x0,y0,x1,y1=bounds
        target_y=cy+(len(lines)-1-2*i)*(1.15 if len(lines)==3 else 1.45)
        transformed=[[(w/2+(x-(x0+x1)/2)*scale,target_y+(y-(y0+y1)/2)*scale) for x,y in ring] for ring in rings]
        all_points=[q for ring in transformed for q in ring]
        xx=[q[0] for q in all_points];yy=[q[1] for q in all_points]
        paint.shapes.append(dict(type='path',rings=transformed,points=[(min(xx),min(yy)),(max(xx),min(yy)),(max(xx),max(yy)),(min(xx),max(yy))],fill="#222222" if COLORING.get() else CREAM,label=line))
    return paint.shapes

