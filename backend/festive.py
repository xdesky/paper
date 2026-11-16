"""Piped icing, jewel lights and confectionery ornaments as printable vectors."""
import math
import numpy as np
from shapely.geometry import Point, LineString, Polygon


def embellish(t, panel, shapes):
    safe=panel.square.buffer(-1.4,join_style=2)
    w,h=panel.square.bounds[2:];cream='#fff8e9';gold='#edbe62'
    colors=['#e95461','#6fcab0','#f7cf68','#f5a2c9']
    def line(points,color=cream,width=.7):
        if safe.covers(LineString(points).buffer(width/2)):
            shapes.append(dict(type='line',points=points,stroke=color,width=width))
    def circle(x,y,r,color):
        if safe.covers(Point(x,y).buffer(r)):
            shapes.append(dict(type='circle',center=[x,y],radius=r,fill=color))
    def star(x,y,r,color=gold):
        pts=[(x+math.sin(i*math.pi/5)*r*(1 if i%2==0 else .4),y+math.cos(i*math.pi/5)*r*(1 if i%2==0 else .4)) for i in range(10)]
        if safe.covers(Polygon(pts)):
            shapes.append(dict(type='polygon',points=pts,fill=color))
    roof=panel.id.startswith('ROOF')
    if roof:
        # Larger icing scallops replace the severe architectural roof grid.
        for row,y in enumerate(np.arange(8,h-3,10)):
            pts=[(float(x),float(y+2*math.cos(x*math.pi/9))) for x in np.linspace(3,w-3,80)]
            line(pts,cream,1.25)
            for j,x in enumerate(np.arange(8+(row%2)*5,w-4,13)):
                circle(float(x),float(y+1),1.8,colors[(row+j)%4])
                circle(float(x)-.5,float(y)+1.5,.45,'#ffffff')
        for x in np.arange(5,w-3,7):
            line([(float(x),3),(float(x),5.5+(int(x)%4))],cream,1.3)
        line([(3,3),(w-3,3)],cream,2.1)
        for x in np.arange(10,w-6,24):star(float(x),h-6,2.4)
    else:
        wh=min(t['wall_height'],h)
        # Tiny piped pearls trace the actual silhouette, including broken roofs.
        border=panel.square.buffer(-2.8,join_style=2).exterior
        for distance in np.arange(0,border.length,3.5):
            q=border.interpolate(distance);circle(q.x,q.y,.65,cream)
        for x in [4.5,w-4.5]:
            line([(x,5),(x,wh-5)],cream,2.2)
            for y in np.arange(7,wh-6,5):line([(x-.65,float(y)),(x+.65,float(y+1.4))],'#d94b58',.9)
        # Drooping evergreen garlands, snow caps and jewel-coloured bulbs.
        for x in np.linspace(8,w-8,max(3,int(w/4))):
            yy=wh-5-2.5*math.sin((x-8)/max(w-16,1)*math.pi*3)**2
            circle(float(x),yy,1.4,'#245944');circle(float(x),yy+.8,.6,'#5f9772')
        for i,x in enumerate(np.linspace(9,w-9,max(3,int(w/8)))):
            yy=wh-9-2*math.sin(x/w*math.pi*3)**2
            circle(float(x),yy,1.25,colors[i%4]);circle(float(x)-.3,yy+.35,.35,'#fffce9')
        for x in np.arange(6,w-5,5):circle(float(x),3.6,1.2,cream)
        if panel.id in ('FRONT','BACK') and t['roof_rise']>25:
            star(w*.28,wh+t['roof_rise']*.27,2.1)
            star(w*.72,wh+t['roof_rise']*.27,2.1)
            for x in (w*.35,w*.65):
                circle(x,wh+t['roof_rise']*.48,.75,cream)
    return shapes
