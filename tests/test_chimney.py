import math
import pytest
from shapely.geometry import Polygon,box
from backend.template_catalog import TEMPLATES
from backend.chimney import geometry,piece,validate

@pytest.mark.parametrize('template',[t for t in TEMPLATES if t.get('chimney')],ids=lambda t:t['id'])
def test_buildable_chimney_matches_roof(template):
    g=geometry(template);p=piece(template)
    assert len(g['panels'])==4 and len(p['folds'])==8
    assert len(p['tabs'])==5 and p['labels'][0][0]=='C1'
    assert all(x['status']=='PASS' for x in validate(template))
    assert p['shape'].is_valid and not p['shape'].interiors
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
