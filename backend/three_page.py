"""Placement solver for the single-roof, three-page house layout.

Coordinates are millimetres in PDF space. Shapes are never scaled.
"""
from dataclasses import dataclass, replace
from functools import cached_property, lru_cache
from math import ceil

from shapely.affinity import rotate, translate
from shapely.geometry import box

@dataclass(frozen=True)
class Placement:
    id: str
    source: object
    angle: int
    dx: float
    dy: float

    def transform(self, point):
        x,y=point
        if self.angle==90:
            x,y=-y,x
        elif self.angle==180:
            x,y=-x,-y
        elif self.angle==270:
            x,y=y,-x
        return x+self.dx,y+self.dy

    @cached_property
    def shape(self):
        return translate(rotate(self.source,self.angle,origin=(0,0)),xoff=self.dx,yoff=self.dy)


def pack_fixed(items, fixed, width, height, gap=3, step=4):
    """Find non-overlapping placements, trying both quarter-turn orientations."""
    # Palette variants have identical cut geometry.
    result=_pack_fixed(tuple(items),tuple(fixed),width,height,gap,step)
    if result is None:
        raise ValueError('Parts do not fit without scaling')
    return list(result)


@lru_cache(maxsize=128)
def _pack_fixed(items, fixed, width, height, gap, step):
    available=box(8,20,width-8,height-24.4).buffer(1e-6)
    if not all(available.covers(item.shape) for item in fixed):
        return None
    fixed_shapes=[item.shape for item in fixed]
    candidate_sets={}
    for name,shape in items:
        variants=[]
        for angle in (0,90):
            rotated=rotate(shape,angle,origin=(0,0))
            x0,y0,x1,y1=rotated.bounds
            for x in range(8,ceil(width-8-(x1-x0)+1e-7),step):
                for y in range(20,ceil(height-24.4-(y1-y0)+1e-7),step):
                    placed=translate(rotated,xoff=x-x0,yoff=y-y0)
                    if all(placed.distance(obstacle)>=gap-1e-6 for obstacle in fixed_shapes):
                        variants.append(Placement(name,shape,angle,x-x0,y-y0))
        if not variants:
            return None
        candidate_sets[name]=variants
    # Hardest parts first, retaining all valid candidates for backtracking.
    order=sorted(items,key=lambda pair:len(candidate_sets[pair[0]]))
    def search(index,placed):
        if index==len(order):return placed
        name,_=order[index]
        for candidate in candidate_sets[name]:
            candidate_shape=candidate.shape
            if all(candidate_shape.distance(p.shape)>=gap-1e-6 for p in placed):
                result=search(index+1,placed+[candidate])
                if result is not None:return result
        return None
    result=search(0,[])
    return fixed+tuple(result) if result is not None else None


def plan_classic(template, structure=None, accessories=None):
    """Place walls, a connected roof cap, and the display parts at actual size."""
    from .gingerbread import model,base
    from .roof_cap import layout as roof_layout
    from .accessories import display_pieces
    from .chimney import piece as chimney_piece

    _,_,units,_,_=structure if structure is not None else model(template)
    walls=[u for u in units if not any(pid.startswith('ROOF') for pid in u.ids)]
    if len(walls)!=2:
        raise ValueError('This layout needs two separate wall units')
    front=next(u for u in walls if 'FRONT' in u.ids)
    back=next(u for u in walls if 'BACK' in u.ids)
    if accessories is None:
        roofs=roof_layout(template)
        if len(roofs)!=1 or len(roofs[0])!=1:
            raise ValueError('This layout needs one connected roof unit')
        base_piece,trees,gifts=display_pieces(template)
        chimney=chimney_piece(template)
        accessories=(roofs[0][0][0],base_piece,trees,gifts,chimney)
    roof,base_piece,trees,gifts,chimney=accessories
    def pack_around_wall(items, name, unit):
        shape=unit.shape()
        placements=[Placement(name,shape,0,0,0)]
        for angle in (0,180,90,270):
            left,bottom,_,_=rotate(shape,angle,origin=(0,0)).bounds
            placement=Placement(name,shape,angle,8-left,20-bottom)
            if placement!=placements[0]:
                placements.append(placement)
        for placement in placements:
            try:
                return pack_fixed(items,[placement],base.PAGE_W,base.PAGE_H)
            except ValueError:
                continue
        raise ValueError(f'Parts do not fit around {name}')

    p1=pack_around_wall([('ROOF',roof['shape'])],'FRONT_WALLS',front)
    extras=gifts+([chimney] if chimney is not None else [])
    p2=pack_around_wall([(p['id'],p['shape']) for p in extras],'BACK_WALLS',back)
    tree_items=[(f'TREE_{i+1}',tree['shape']) for i,tree in enumerate(trees)]
    support=next((u for u in units if u not in walls),None) if structure is not None else None
    if support is not None:
        tree_items.append(('SUPPORT',support.shape()))
    base_placements=[Placement('BASE',base_piece['shape'],0,18,35)]
    try:
        p3=pack_fixed(tree_items,base_placements,base.PAGE_W,base.PAGE_H)
    except ValueError:
        p3=pack_fixed(tree_items,[Placement('BASE',base_piece['shape'],0,8,20)],base.PAGE_W,base.PAGE_H)
    return [p1,p2,p3]


def compact_layout(template, structure):
    """Return the three-sheet layout when the parts fit the selected paper."""
    from .accessories import display_pieces
    from .chimney import piece as chimney_piece
    from .roof_cap import layout as roof_layout

    units=structure[2]
    if (template.get('category')!='gingerbread-houses' or not template.get('roof_overhang_mm')
            or len(units)!=(2 if template.get('single_layer_roof') else 3)):
        return template,None
    compact={**template,'roof_corner_radius_mm':template.get('roof_corner_radius_mm',4)}
    try:
        roofs=roof_layout(compact)
        if len(roofs)!=1 or len(roofs[0])!=1:
            return template,None
        roof=roofs[0][0][0]
        base_piece,trees,gifts=display_pieces(compact)
        chimney=chimney_piece(compact)
        plan=plan_classic(compact,structure,(roof,base_piece,trees,gifts,chimney))
    except ValueError:
        return template,None

    wall_units={f'{pid}_WALLS':u for u in units for pid in ('FRONT','BACK') if pid in u.ids}
    if not template.get('single_layer_roof'):
        wall_units['SUPPORT']=next(u for u in units if any(pid.startswith('ROOF') for pid in u.ids))
    pieces={'ROOF':roof,'BASE':base_piece,**{f'TREE_{i+1}':p for i,p in enumerate(trees)},
            **{p['id']:p for p in gifts}}
    if chimney is not None:
        pieces['CHIMNEY']=chimney
    pages=[]
    for index,placements in enumerate(plan):
        page={'units':[],'accessories':[]}
        for placement in placements:
            if placement.id in wall_units:
                unit=wall_units[placement.id]
                # Compose the rigid placement with the unit's existing page transform.
                page['units'].append(replace(unit,sheet=index,orientation=(unit.orientation+placement.angle)%360,
                                             shift=placement.transform(unit.shift)))
            else:
                page['accessories'].append((pieces[placement.id],placement))
        pages.append(page)
    return compact,pages
