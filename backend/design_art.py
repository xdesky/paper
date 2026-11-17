"""Composable seasonal patterns on the same printable surfaces."""
import math

def roof(p,w,h,style):
    from .confectionery import RED,GREEN
    for y in range(7,int(h)-3,14):
        p.pipe([(3,y),(w-3,y)],1.4)
        for x in range(9,int(w)-5,18):
            if style=='snowflake':p.snowflake(x,y+3,3.6)
            elif style=='peppermint':p.peppermint(x,y+3,4)
            elif style=='stars':p.sparkle(x,y+3,4);p.jewel(x+6,y+3,1,'#dfac38')
            elif style=='hearts':p.heart(x,y+3,3.5,RED);p.holly(x+7,y+2,1.4)

def wall(p,w,h,style):
    from .confectionery import CREAM,RED
    if style=='brick':
        for row,y in enumerate(range(4,int(h),6)):
            p.line([(3,y),(w-3,y)],CREAM,.45)
            for x in range(5+(row%2)*5,int(w)-3,10):p.line([(x,y),(x,y+6)],CREAM,.45)
    elif style=='timber':
        for x in range(7,int(w)-3,7):
            p.line([(x,3),(x,h-3)],'#824629',.55)
            p.line([(x+2,8),(x+3,h*.4),(x+1,h-6)],'#e3bd85',.3)
    elif style in ('holly','hearts'):
        for x in range(10,int(w)-5,16):
            if style=='holly':p.holly(x,10,2.5)
            else:p.heart(x,11,3,RED)

def tree(p,style):
    from .confectionery import RED,GREEN
    p.polygon(p.shape.exterior.coords,{'slim':'#22695a','rounded':'#32835c','tiered':'#174f3c','star':'#285268','candy':'#d57b99'}[style])
    for y,half in [(12,11),(26,8),(40,5),(53,2)]:
        p.pipe([(16-half+2*half*i/30,y+1.5*math.sin(i*math.pi/10)) for i in range(31)],1.7)
        for x in (16-half*.55,16+half*.55):
            if style=='star':p.sparkle(x,y+3,2.2)
            elif style=='candy':p.peppermint(x,y+3,2.4)
            elif style=='slim':p.snowflake(x,y+3,1.8)
            elif style=='rounded':p.heart(x,y+3,2,RED)
            else:p.jewel(x,y+3,1.5,RED)

def gift(p,size,style,top):
    from .confectionery import CREAM,RED,GREEN
    colors={'stripes':'#c83a4b','dots':'#24795d','snowflake':'#7caecb','holly':'#f4e4c7','stars':'#36446e'}
    p.rect(0,0,size,size,colors[style])
    if style=='stripes':
        for x in range(-int(size),int(size)*2,5):p.line([(x,0),(x+size,size)],CREAM,1.5)
    else:
        for x in (size*.2,size*.8):
            for y in (size*.2,size*.8):
                if style=='dots':p.circle(x,y,1,CREAM)
                elif style=='snowflake':p.snowflake(x,y,1.6)
                elif style=='holly':p.holly(x,y,1.3)
                else:p.sparkle(x,y,1.8)
    ribbon='#e1b243' if style=='stars' else RED
    p.rect(size*.42,0,size*.16,size,ribbon);p.rect(0,size*.42,size,size*.16,ribbon)
    if top:
        for sign in (-1,1):
            p.pipe([(size/2+sign*size*.2*(1-math.cos(i*math.tau/32)),size/2+size*.12*math.sin(i*math.tau/32)) for i in range(33)],1)
        p.jewel(size/2,size/2,1.2,ribbon)
