"""Glue tabs with a fixed depth, including tabs deeper than half their edge."""
import math
from shapely.geometry import Polygon


def flap(a,b,depth,*,start_chamfer=0,end_chamfer=0):
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=math.hypot(dx,dy)
    if length<=0:raise ValueError('A tab needs a nonzero edge')
    ux,uy=dx/length,dy/length
    nx,ny=uy,-ux
    chamfer=min(2.0,length*.2)
    start=max(chamfer,start_chamfer)
    end=max(chamfer,end_chamfer)
    return Polygon([a,b,(b[0]-end*ux+depth*nx,b[1]-end*uy+depth*ny),
                    (a[0]+start*ux+depth*nx,a[1]+start*uy+depth*ny)])
