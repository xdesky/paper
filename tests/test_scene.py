from collections import Counter
import pytest
from shapely.geometry import Polygon,Point,LineString,box
from backend.template_catalog import TEMPLATES
from backend.gingerbread import model,decorations
from backend.accessories import scene,tree_piece,gift_net

@pytest.mark.parametrize('template',TEMPLATES,ids=lambda t:t['id'])
def test_scene_footprint_and_printed_art(template):
    panels,*_=model(template)
    for panel in panels.values():
        for art in decorations(template,panel):
            if art['type']=='circle':shape=Point(art['center']).buffer(art['radius'])
            elif art['type']=='line':shape=LineString(art['points']).buffer(art.get('width',0)/2)
            else:shape=Polygon(art['points'])
            assert panel.square.buffer(.001).covers(shape),(template['id'],panel.id,art)
    display=scene(template);w,d=display['base_mm']
    footprint=box(-w/2,-d/2,w/2,d/2)
    for panel in display['panels']:
        for x,y,z in panel['vertices_3d_mm']:
            assert footprint.buffer(.001).covers(Point(x,y))
            assert z>=-.4
    assert display['tree_height_mm']==65


def test_tree_slots_and_closed_gifts():
    upper,lower=tree_piece(True),tree_piece(False)
    assert upper.intersection(box(15.7,32.5,16.3,66)).area<1e-8
    assert lower.intersection(box(15.7,-1,16.3,32.5)).area<1e-8
    assert upper.contains(Point(16,10)) and lower.contains(Point(16,40))
    for size in (16,20):
        gift=gift_net(size,'A','#ffffff');edges=Counter();s=size
        for fn in gift['maps'].values():
            vertices=[fn(*p) for p in [(0,0),(s,0),(s,s),(0,s)]]
            for a,b in zip(vertices,vertices[1:]+vertices[:1]):edges[tuple(sorted((a,b)))]+=1
        assert len(edges)==12 and all(count==2 for count in edges.values())
        assert len(gift['seams'])==len(gift['tabs'])==7
