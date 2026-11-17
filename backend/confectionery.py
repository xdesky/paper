"""Reference-inspired confectionery illustration. Changes ink only, never geometry."""
import math
from .coloring import COLORING
from shapely.geometry import Polygon,Point,LineString,box

CREAM='#fff9ed';SHADOW='#9a4826';RED='#d51932';GREEN='#167448'


def mix(a,b,f):
    aa=[int(a[i:i+2],16) for i in (1,3,5)];bb=[int(b[i:i+2],16) for i in (1,3,5)]
    return '#'+''.join(f'{round(x+(y-x)*f):02x}' for x,y in zip(aa,bb))


class Painter:
    def __init__(self,shape):self.shape=shape;self.shapes=[]
    def polygon(self,points,color):
        if COLORING.get() and color in (SHADOW,'#b46640','#a35a39','#bd772d','#874223','#ccb4a6','#dce6ef'):return
        g=Polygon(points).intersection(self.shape)
        for p in [g] if g.geom_type=='Polygon' else getattr(g,'geoms',[]):
            if p.geom_type=='Polygon' and p.area>1e-6:self.shapes.append(dict(type='polygon',points=list(p.exterior.coords),fill='#ffffff' if COLORING.get() else color,**({'stroke':'#222222','width':.25} if COLORING.get() else {})))
    def rect(self,x,y,w,h,color):self.polygon([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],color)
    def line(self,points,color,width):
        if COLORING.get():
            if color in ('#9d4e2d','#81272a'):return
            if width>1:
                outline=LineString(points).buffer(width/2).intersection(self.shape.buffer(-.15))
                for shape in [outline] if outline.geom_type=='Polygon' else getattr(outline,'geoms',[]):
                    if shape.geom_type=='Polygon':
                        from shapely.geometry.polygon import orient
                        shape=orient(shape)
                        self.shapes.append(dict(type='compound',points=list(shape.exterior.coords),rings=[list(shape.exterior.coords)]+[list(r.coords) for r in shape.interiors],fill='#ffffff',stroke='#222222',width=.25))
                return
            color='#222222';width=.25
        g=LineString(points).intersection(self.shape.buffer(-width/2-.015))
        for p in [g] if g.geom_type=='LineString' else getattr(g,'geoms',[]):
            if p.geom_type=='LineString' and p.length>.01:self.shapes.append(dict(type='line',points=list(p.coords),stroke=color,width=width))
    def circle(self,x,y,r,color):
        if COLORING.get() and color in (SHADOW,'#a35a39','#dce6ef'):return
        if self.shape.buffer(.00001).covers(Point(x,y).buffer(r)):
            self.shapes.append(dict(type='circle',center=[x,y],radius=r,fill='#ffffff' if COLORING.get() else color,**({'stroke':'#222222','width':.25} if COLORING.get() else {})))
    def pipe(self,pts,width=1.8):
        if COLORING.get():self.line(pts,'#222222',width);return
        self.line([(x+.35,y-.5) for x,y in pts],'#b46640',width+.65)
        self.line(pts,'#edd5bf',width+.25)
        self.line([(x-.12,y+.15) for x,y in pts],CREAM,width)
        self.line([(x-.22,y+.36) for x,y in pts],'#ffffff',max(.25,width*.22))
    def jewel(self,x,y,r,color=RED):
        if COLORING.get():self.circle(x,y,r,'#ffffff');return
        self.circle(x+.25,y-.35,r+.17,'#a35a39')
        for i in range(6):
            self.circle(x-i*r*.035,y+i*r*.045,r*(1-i*.095),mix(color,'#ffffff',i*.055))
        self.circle(x-r*.32,y+r*.38,r*.27,'#fffdf5')
        self.circle(x+r*.35,y-r*.3,r*.1,mix(color,'#ffffff',.5))
    def heart(self,x,y,r,color=CREAM):
        pts=[]
        for i in range(61):
            a=i*math.tau/60
            pts.append((x+r*math.sin(a)**3,y+r*(13*math.cos(a)-5*math.cos(2*a)-2*math.cos(3*a)-math.cos(4*a))/16))
        self.polygon([(xx+.2,yy-.35) for xx,yy in pts],SHADOW);self.polygon(pts,color)
    def peppermint(self,x,y,r):
        self.circle(x+.35,y-.45,r+.2,SHADOW);self.circle(x,y,r,CREAM)
        for k in range(6):
            pts=[(x,y)]
            for i in range(0 if COLORING.get() else 16):
                rr=r*i/15;angle=k*math.tau/6+rr/r*.8
                pts.append((x+rr*math.cos(angle),y+rr*math.sin(angle)))
            for i in range(15,-1,-1):
                rr=r*i/15;angle=k*math.tau/6+.43+rr/r*.8
                pts.append((x+rr*math.cos(angle),y+rr*math.sin(angle)))
            self.polygon(pts,RED)
        self.circle(x-r*.35,y+r*.5,r*.16,'#ffffff')
    def sparkle(self,x,y,r=1.5):
        pts=[(x,y+r),(x+r*.22,y+r*.22),(x+r,y),(x+r*.22,y-r*.22),(x,y-r),(x-r*.22,y-r*.22),(x-r,y),(x-r*.22,y+r*.22)]
        self.polygon([(a+.2,b-.25) for a,b in pts],'#bd772d')
        self.polygon(pts,'#fff8d4');self.circle(x,y,.35,'#ffffff')
    def snowflake(self,x,y,r):
        for i in range(6):
            a=i*math.tau/6;dx,dy=math.cos(a),math.sin(a)
            self.pipe([(x,y),(x+r*dx,y+r*dy)],.8)
            for sign in (-1,1):
                bx,by=math.cos(a+sign*.7),math.sin(a+sign*.7)
                self.pipe([(x+r*.6*dx,y+r*.6*dy),(x+r*.6*dx-r*.24*bx,y+r*.6*dy-r*.24*by)],.65)
        self.jewel(x,y,.8,'#dfb538')
    def leaf(self,x,y,angle,size):
        pts=[(-1,0),(-.45,.24),(-.6,.55),(-.1,.45),(.2,.8),(.42,.35),(1,0),(.42,-.35),(.2,-.8),(-.1,-.45),(-.6,-.55),(-.45,-.24)]
        def trans(a,b):return (x+size*(a*math.cos(angle)-b*math.sin(angle)),y+size*(a*math.sin(angle)+b*math.cos(angle)))
        self.polygon([trans(a,b) for a,b in pts],GREEN)
        self.line([trans(-.8,0),trans(.8,0)],'#54a66a',.45)
    def holly(self,x,y,size=3):
        self.leaf(x-size,y+.6,.4,size);self.leaf(x+size,y+.6,-.4,size)
        for dx,dy in [(-.6,0),(.6,0),(0,-1)]:self.jewel(x+dx,y+dy,.8,RED)
    def snow(self,x,y,width):
        points=[(x+width*i/40,y-.8*math.sin(i*math.pi/10)**2) for i in range(41)]
        self.pipe(points,2.8)
        for i in range(1,max(2,int(width/4))):
            xx=x+width*i/max(2,int(width/4));self.pipe([(xx,y),(xx,y-1.1-(i%3)*.55)],2)
    def shrub(self,x,y,r):
        for dx,dy,rr in [(-r*.5,0,r*.7),(r*.5,0,r*.7),(0,r*.55,r*.7)]:
            self.circle(x+dx+.3,y+dy-.2,rr,SHADOW);self.circle(x+dx,y+dy,rr,GREEN)
            self.pipe([(x+dx-rr*.6,y+dy+rr*.5),(x+dx,y+dy+rr*.65),(x+dx+rr*.55,y+dy+rr*.4)],1.3)
        for dx,dy in [(-.5,0),(.45,.1),(0,.55)]:self.jewel(x+dx*r,y+dy*r,.8,RED)


def arch(x,y,w,h):
    r=w/2
    return [(x-w/2,y),(x+w/2,y)]+[(x+r*math.cos(i*math.pi/32),y+h-r+r*math.sin(i*math.pi/32)) for i in range(33)]+[(x-w/2,y)]


def window(p,x,y,w,h):
    shape=arch(x,y,w,h);p.polygon(shape,'#e58c1d')
    glass=Painter(Polygon(shape).intersection(p.shape))
    for i in range(0 if COLORING.get() else 16):
        glass.rect(x-w/2+i*w/16,y,w/16+.25,h,mix('#ffb52d','#fff4a3',1-abs(i-7.5)/8))
    p.shapes.extend(glass.shapes)
    p.line([(x,y),(x,y+h-.7)],'#c77c24',.8)
    p.line([(x-w/2,y+h*.43),(x+w/2,y+h*.43)],'#c77c24',.9)
    p.pipe(shape,1.9)
    p.snow(x-w/2-1,y-.8,w+2)
    for i in range(3):p.jewel(x+(i-1)*w*.28,y-.5,1.05,RED if i==1 else GREEN)


def house_art(t,panel):
    if t.get('bay_count',1) > 1 and panel.id in ('FRONT','BACK'):
        from shapely.affinity import translate
        from .gingerbread import Panel
        w,h=panel.square.bounds[2:]
        fractions=t.get('bay_splits') or [t['bay_split']]
        if panel.id=='BACK':fractions=sorted(1-x for x in fractions)
        boundaries=[0]+[w*x for x in fractions]+[w]
        shapes=[]
        for left,right in zip(boundaries,boundaries[1:]):
            section=translate(panel.square.intersection(box(left,0,right,h+1)),xoff=-left)
            local=Panel(panel.id,list(section.exterior.coords)[:-1],[])
            bay={**t,'bay_count':1,'personal_name':'','width':right-left,'roof_rise':section.bounds[3]-t['wall_height']}
            for original in house_art(bay,local):
                shape=dict(original)
                if shape['type']=='circle':shape['center']=[shape['center'][0]+left,shape['center'][1]]
                else:shape['points']=[(x+left,y) for x,y in shape['points']]
                if 'rings' in shape:shape['rings']=[[(x+left,y) for x,y in ring] for ring in shape['rings']]
                shapes.append(shape)
        return shapes
    p=Painter(panel.square);w,h=panel.square.bounds[2:];roof=panel.id.startswith('ROOF')
    color=t['wall']
    # Soft baked colour bands and tiny sugar pores, all clipped to existing face.
    if COLORING.get():p.polygon(panel.points,'#ffffff')
    for i in range(0 if COLORING.get() else 28):p.rect(0,i*h/28,w,h/28+.5,mix(color,'#edb85e',.08+.18*math.sin(i*math.pi/28)))
    for i in range(0 if COLORING.get() else int(w*h/95)):
        x=2+(i*17.39)%(w-4);y=2+(i*11.71)%(h-4)
        p.circle(x,y,.18+(i%3)*.06,mix(color,'#653418',.15))
    if roof:
        style=t.get('design',{}).get('roof','classic')
        if style!='classic':
            from .design_art import roof as paint_roof
            paint_roof(p,w,h,style);return p.shapes
        for row,y in enumerate(range(6,int(h)-1,12)):
            pts=[(2+(w-4)*i/100,y+1.2*math.cos(i*(w-4)*math.pi/800)) for i in range(101)]
            p.pipe(pts,4.4)
            for i,x in enumerate(range(6,int(w)-3,10)):
                yy=y+1.2*math.cos((x-2)*math.pi/8)
                p.jewel(x,yy,1.65,RED if (i+row)%2==0 else GREEN)
        for y in range(17,int(h)-6,24):
            for x in range(17,int(w)-8,32):p.peppermint(x,y,3.2)
        return p.shapes
    wh=min(t['wall_height'],h)
    from .design_art import wall as paint_wall
    paint_wall(p,w,wh,t.get('design',{}).get('wall','classic'))
    # Candy cane corner posts, with shaded red diagonal stripes.
    for x in (3.5,w-3.5):
        p.line([(x,3),(x,wh-3)],'#9d4e2d',3.8)
        p.line([(x-.2,3),(x-.2,wh-3)],CREAM,3.2)
        for y in range(4,int(wh)-3,6):p.line([(x-1.2,y+2),(x+1,y)],RED,1.5)
    # Snow beads are deliberately kept away from the door and window interiors.
    for row,y in enumerate(range(9,int(wh)-5,10)):
        for x in range(9+(row%2)*4,int(w)-6,10):
            p.circle(x+.2,y-.3,.7,SHADOW);p.circle(x,y,.62,CREAM)
    front=panel.id=='FRONT';gable=panel.id in ('FRONT','BACK') and h-wh>15
    floors=3 if wh>125 else 2 if wh>92 else 1
    ww=min(17,w*.20);hh=min(25,wh*.37)
    for level in range(floors):
        yy=wh*(.41 if floors==1 else .14+level*.30)
        for xx in (w*.23,w*.77):window(p,xx,yy,ww,hh if floors==1 else min(21,hh))
    if front:
        dw=min(23,w*.27);dh=min(42,wh*.63);door=arch(w/2,3,dw,dh)
        p.polygon(door,'#b60f27')
        inset=Painter(Polygon(door).intersection(panel.square))
        for i in range(0 if COLORING.get() else 14):inset.rect(w/2-dw/2+i*dw/14,3,dw/14+.25,dh,mix('#a81025','#ee3940',math.sin(i*math.pi/14)*.8))
        for dx in (-.25,0,.25):inset.line([(w/2+dw*dx,3),(w/2+dw*dx,dh+3)],'#901023',.35)
        p.shapes.extend(inset.shapes);p.pipe(door,2.4);p.jewel(w/2+dw*.30,dh*.40,1.2,'#e7ad21')
        cy=dh*.72;r=min(4.2,dw*.23)
        for i in range(11):
            a=i*math.tau/11;p.jewel(w/2+r*math.cos(a),cy+r*math.sin(a),1.4,GREEN)
        p.heart(w/2,cy-r-1,1.5,RED)
        if wh>50:
            p.heart(w/2,dh+8,2.8)
            if wh-dh>28:p.holly(w/2,wh-11,3.2)
    for xx in (w*.38,w*.62):
        p.sparkle(xx,wh-18,1.5)
        p.sparkle(xx,wh-24,.8)
    for xx in (w*.14,w*.86):p.shrub(xx,5.5,min(4.8,w*.07))
    # Heavy scalloped icing follows the existing roof-facing silhouette.
    upper=list(panel.square.buffer(-3.5,join_style=2).exterior.coords)
    for a,b in zip(upper,upper[1:]):
        if min(a[1],b[1])>=wh-5:
            length=math.dist(a,b);n=max(2,int(length/3.7));pts=[]
            dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
            for i in range(n*10+1):
                f=i/(n*10);wave=.85*(1-math.cos(f*n*math.tau))
                pts.append((a[0]+f*(b[0]-a[0])+dy*wave,a[1]+f*(b[1]-a[1])-dx*wave))
            p.pipe(pts,2.5)
            for i in range(1,n,2):
                f=i/n;p.jewel(a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1]),1.25,RED if i%4==1 else GREEN)
    if gable and not (front and t.get('personal_name')):
        center=(w/2,wh+(h-wh)*.43);r=min(6,(h-wh)*.16,w*.09)
        if panel.square.buffer(-2).covers(Point(*center).buffer(r+2)):
            if panel.id=='BACK':p.snowflake(*center,r)
            else:p.peppermint(*center,r)
            p.holly(center[0],center[1]-r-2,min(3,r*.6))
        for xx,sign in [(w*.22,1),(w*.78,-1)]:
            pts=[]
            for i in range(55):
                a=i/54*math.pi*2.2;rr=3*(1-i/65)
                pts.append((xx+sign*rr*math.cos(a),wh+4+rr*math.sin(a)))
            p.pipe(pts,1)
    return p.shapes


def tree_art(shape,style='classic'):
    p=Painter(shape)
    if style!='classic':
        from .design_art import tree as paint_tree
        paint_tree(p,style);return p.shapes
    p.polygon(shape.exterior.coords,'#155936')
    for y,half in [(9,12),(23,9),(38,6),(52,3)]:
        pts=[(16-half+2*half*i/40,y+1.6*math.cos(i*math.pi/10)) for i in range(41)]
        p.pipe(pts,2)
    for i,(x,y) in enumerate([(6,9),(24,9),(10,24),(22,25),(13,39),(19,41),(16,55),(16,17),(10,13),(20,29)]):
        p.jewel(x,y,1.45,RED if i%3 else '#e7ae2c')
    return p.shapes


def gift_art(size,color,top=False,style='classic'):
    p=Painter(box(0,0,size,size))
    if style!='classic':
        from .design_art import gift as paint_gift
        paint_gift(p,size,style,top);return p.shapes
    if COLORING.get():p.rect(0,0,size,size,'#ffffff')
    for i in range(0 if COLORING.get() else 20):p.rect(i*size/20,0,size/20+.25,size,mix(color,'#ffffff',.18*math.sin(i*math.pi/20)))
    for x in (.15,.32,.68,.85):
        for y in (.18,.4,.65,.85):p.circle(size*x,size*y,.55,CREAM)
    ribbon=GREEN if color.startswith('#bb') else RED
    p.rect(size*.40,0,size*.20,size,ribbon);p.rect(0,size*.40,size,size*.20,ribbon)
    p.line([(size*.43,0),(size*.43,size)],'#76b278',.5);p.line([(0,size*.57),(size,size*.57)],'#76b278',.5)
    if top:
        for sign in (-1,1):
            pts=[(size/2+sign*size*.23*(1-math.cos(i*math.tau/40)),size/2+size*.14*math.sin(i*math.tau/40)) for i in range(41)]
            p.line([(x+.3,y-.3) for x,y in pts],'#81272a',2.2);p.line(pts,ribbon,1.8);p.line([(x-.2,y+.2) for x,y in pts],mix(ribbon,'#ffffff',.4),.5)
        p.jewel(size/2,size/2,1.2,ribbon)
    return p.shapes
