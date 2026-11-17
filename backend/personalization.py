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
    if len(value)>MAX_NAME_LENGTH:raise ValueError('Tên tối đa 24 ký tự.')
    if any(not (c in " -.'&!,0123456789" or 'LATIN' in unicodedata.name(c,'')) for c in value):
        raise ValueError('Dùng chữ Latin/tiếng Việt, số, khoảng trắng hoặc dấu - . & ! , và dấu nháy.')
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
    cy=wh+(center_top-wh)*.22 if center_top-wh>16 else wh-7
    if t.get('bay_count') == 2:cy=wh-8.5
    bh=9;bw=min(64,w*.65)
    safe=panel.square.buffer(-2.6)
    while bw>16 and not safe.covers(box(w/2-bw/2,cy-bh/2,w/2+bw/2,cy+bh/2)):bw-=1
    if bw<=16:raise ValueError('Không đủ vùng an toàn để đặt bảng tên.')
    paint=Painter(panel.square)
    plaque=[(w/2-bw/2,cy-bh/2),(w/2+bw/2,cy-bh/2),(w/2+bw/2,cy+bh/2),(w/2-bw/2,cy+bh/2)]
    paint.polygon([(x+.3,y-.35) for x,y in plaque],'#874223')
    paint.polygon(plaque,'#a71d35');paint.pipe(plaque+[plaque[0]],.9)
    # Fit one or two centred lines. Outlines avoid font substitution in print/3D.
    def width(text):b=text_polygons(text)[1];return b[2]-b[0]
    lines=[name]
    if width(name)*3>bw-5:
        candidates=[i for i,c in enumerate(name) if c==' '] or list(range(1,len(name)))
        split=min(candidates,key=lambda i:max(width(name[:i].strip()),width(name[i:].strip())))
        lines=[name[:split].strip(),name[split:].strip()]
    scale=min(3,(bw-5)/max(width(line) for line in lines))
    for i,line in enumerate(lines):
        rings,bounds=text_polygons(line);x0,y0,x1,y1=bounds
        target_y=cy+(len(lines)-1-2*i)*1.8
        transformed=[[(w/2+(x-(x0+x1)/2)*scale,target_y+(y-(y0+y1)/2)*scale) for x,y in ring] for ring in rings]
        all_points=[q for ring in transformed for q in ring]
        xx=[q[0] for q in all_points];yy=[q[1] for q in all_points]
        paint.shapes.append(dict(type='path',rings=transformed,points=[(min(xx),min(yy)),(max(xx),min(yy)),(max(xx),max(yy)),(min(xx),max(yy))],fill="#222222" if COLORING.get() else CREAM,label=line))
    return paint.shapes
