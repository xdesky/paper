from typing import Literal
from pydantic import BaseModel,ConfigDict

class DesignOptions(BaseModel):
    model_config=ConfigDict(extra='forbid')
    roof: Literal['classic','snowflake','peppermint','stars','hearts']='classic'
    wall: Literal['classic','brick','timber','holly','hearts']='classic'
    tree: Literal['classic','slim','rounded','tiered','star','candy']='classic'
    gift: Literal['classic','stripes','dots','snowflake','holly','stars']='classic'

OPTIONS={
 'roof':[('classic','Icing & Candy'),('snowflake','Snowflakes'),('peppermint','Peppermint'),('stars','Starry Night'),('hearts','Christmas Hearts')],
 'wall':[('classic','Classic Gingerbread'),('brick','Icing Bricks'),('timber','Timber'),('holly','Holly'),('hearts','Sugar Hearts')],
 'tree':[('classic','Classic Evergreen'),('slim','Slim Spruce'),('rounded','Round Fir'),('tiered','Layered Pine'),('star','Star Tree'),('candy','Candy Tree')],
 'gift':[('classic','Classic Gift'),('stripes','Candy Stripes'),('dots','Polka Dots'),('snowflake','Snowflake Gift'),('holly','Holly Gift'),('stars','Golden Stars')],
}

def apply_design(t,design):
    values=DesignOptions(**(design or {})).model_dump()
    return {**t,'design':values} if values!=DesignOptions().model_dump() else dict(t)


def thumbnail(kind,style):
    from .gingerbread import svg_art,Panel,decorations,model
    from .template_catalog import BY_ID
    from .confectionery import tree_art,gift_art
    from .accessories import tree_piece
    if kind=='tree':return svg_art(tree_art(tree_piece(False,style),style),32,65)
    if kind=='gift':return svg_art(gift_art(24,'#bb3f58',True,style),24,24)
    t=apply_design(BY_ID['gb_classic'],{kind:style})
    if kind=='roof':
        p=Panel('ROOF_SAMPLE',[(0,0),(60,0),(60,48),(0,48)],[])
    else:p=model(t)[0]['FRONT']
    return svg_art(decorations(t,p),p.square.bounds[2],p.square.bounds[3])
