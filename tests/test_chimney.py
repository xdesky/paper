import math
import pytest
from shapely.geometry import Polygon,box
from backend.template_catalog import TEMPLATES,has_two_roof_faces
from backend.chimney import geometry,piece,validate

@pytest.mark.parametrize('template',[t for t in TEMPLATES if t.get('chimney')],ids=lambda t:t['id'])
def test_buildable_chimney_matches_roof(template):
    g=geometry(template);p=piece(template)
    original=geometry({**template,'chimney_growth_mm':0})
    assert g['size']==pytest.approx(original['size']+10)
    assert g['top_mm']-max(z for _,_,z in g['footprint'])==pytest.approx(34)
    assert len(g['panels'])==4 and len(p['folds'])==8
    assert [s.get('fill') for s in p['art']].count(template['wall'])==4
    top=max(y for face in g['panels'] for _,y in face['points'])
    assert all(y>top-6 for s in p['art'] if s['type']=='line' for _,y in s['points'])
    assert len(p['tabs'])==5 and p['labels'][0][0]=='C1'
    for tab,(a,b) in zip(p['tabs'][1:],p['folds'][3:7]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        depth=max(abs(dx*(y-a[1])-dy*(x-a[0]))/length for x,y in tab.exterior.coords)
        assert depth == pytest.approx(7.5,abs=.01)
    assert all(x['status']=='PASS' for x in validate(template))
    assert p['shape'].is_valid and not p['shape'].interiors
    assert Polygon([(round(x,5),round(y,5)) for x,y in p['shape'].exterior.coords]).is_valid
    assert all(Polygon(face['points']).is_valid for face in g['panels'])
    # Independently interpolate the original roof at each foot; cap offset is .4 mm.
    w=template['width'];h=template['wall_height'];r=template['roof_rise']
    ridge=template.get('profile',[(0,0),(.5,1),(1,0)])
    for x,y,z in g['footprint']:
        a,b=next((a,b) for a,b in zip(ridge,ridge[1:]) if a[0]*w<=x+w/2<=b[0]*w)
        expected=h+a[1]*r+(x+w/2-a[0]*w)*(b[1]-a[1])*r/((b[0]-a[0])*w)+.4
        assert math.isclose(z,expected,abs_tol=1e-7)
    for page_width,page_height in [(210,297),(215.9,279.4)]:
        from shapely.affinity import translate
        assert box(8,20,page_width-8,page_height-24.4).covers(translate(p['shape'],xoff=25,yoff=100))

def test_old_snapshot_without_chimney_stays_unchanged():
    t={k:v for k,v in TEMPLATES[0].items() if k!='chimney'}
    assert geometry(t) is None and piece(t) is None and validate(t)==[]


def test_tall_houses_have_no_chimney():
    from backend.template_catalog import BY_ID
    for tid in ['gb_forest','gb_frost','gb_us_colonial_heritage','gb_us_farmhouse_heritage','gb_us_brownstone_heritage','gb_complex_tower_rose']:
        assert not BY_ID[tid].get('chimney'),tid
        assert geometry(BY_ID[tid]) is None

@pytest.mark.parametrize('mirrored',[False,True])
def test_chimney_uses_longest_actual_slope(mirrored):
    from backend.template_catalog import BY_ID
    t=dict(BY_ID['gb_us_saltbox_heritage'])
    if mirrored:t['profile']=[(1-x,z) for x,z in reversed(t['profile'])]
    g=geometry(t)
    ridge=[(x*t['width'],t['wall_height']+z*t['roof_rise']) for x,z in t['profile']]
    assert math.isclose(math.dist(*g['roof_segment']),max(math.dist(a,b) for a,b in zip(ridge,ridge[1:])))
    mean_x=sum(x for x,y,z in g['footprint'])/4
    assert (mean_x>0) == mirrored


def test_equal_slopes_use_right_side_and_old_snapshot_keeps_placement():
    from backend.template_catalog import BY_ID
    t=BY_ID['gb_classic']
    assert sum(x for x,y,z in geometry(t)['footprint'])>0
    old={k:v for k,v in BY_ID['gb_us_saltbox_heritage'].items() if k!='chimney_placement'}
    assert sum(x for x,y,z in geometry(old)['footprint'])>0


@pytest.mark.parametrize('paper', ['US Letter', 'A4'])
@pytest.mark.parametrize('template', [t for t in TEMPLATES if t.get('chimney')], ids=lambda t:t['id'])
def test_chimney_shares_roof_page_without_overlap(template, paper):
    from shapely.affinity import translate
    from shapely.geometry import box
    from backend.gingerbread import base
    from backend.paper import configure_engine
    from backend.accessories import layout
    from backend.roof_cap import metadata
    configure_engine(base, paper)
    pages=layout(template)
    roof=metadata(template)
    assert len(pages)<=2+roof['sheet_count']
    page=next(page for page in pages if any(piece['id']=='CHIMNEY' for piece,_,_ in page))
    chimney=next(translate(piece['shape'],xoff=x,yoff=y) for piece,x,y in page if piece['id']=='CHIMNEY')
    assert box(8,20,base.PAGE_W-8,base.PAGE_H-24.4).covers(chimney)
    for piece,x,y in page:
        if piece['id']!='CHIMNEY':
            assert chimney.distance(translate(piece['shape'],xoff=x,yoff=y))>=3-1e-6


@pytest.mark.parametrize('paper', ['US Letter', 'A4'])
def test_accessory_pages_are_compact_and_separated(paper):
    from shapely.affinity import translate
    from backend.gingerbread import base
    from backend.paper import configure_engine
    from backend.accessories import layout
    configure_engine(base,paper)
    for template in TEMPLATES:
        if template.get('category')=='blocky-characters':continue
        pages=layout(template)
        assert len(pages)==2,template['id']
        for page in pages:
            shapes=[translate(piece['shape'],xoff=x,yoff=y) for piece,x,y in page]
            assert all(box(8,20,base.PAGE_W-8,base.PAGE_H-24.4).buffer(1e-6).covers(shape) for shape in shapes)
            assert all(a.distance(b)>=3-1e-6 for i,a in enumerate(shapes) for b in shapes[i+1:])


@pytest.mark.parametrize('size',[16,20])
def test_gift_glue_tabs_are_eight_mm(size):
    from backend.accessories import gift_net
    p=gift_net(size,'A','#bb3f58')
    from shapely.geometry import LineString
    for tab in p['tabs']:
        segment=next(edge for edge in p['folds'] if LineString(edge).difference(tab.buffer(1e-6)).length < 1e-5)
        a,b=segment;dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        depth=max(abs(dx*(y-a[1])-dy*(x-a[0]))/length for x,y in tab.exterior.coords)
        assert depth == pytest.approx(8,abs=.01)

def test_chimney_requires_exactly_two_roof_faces():
    for template in TEMPLATES:
        if template.get('chimney'):
            assert has_two_roof_faces(template),template['id']
        if template.get('profile') and not has_two_roof_faces(template):
            legacy={**template,'chimney':True}
            assert geometry(legacy) is None,template['id']
            assert piece(legacy) is None,template['id']
