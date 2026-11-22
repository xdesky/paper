import pytest
from shapely.geometry import Polygon,Point,LineString
from backend.template_catalog import BY_ID,TEMPLATES
from backend.roof_cap import build,validate,artwork
from backend.paper import configure_engine
from backend.gingerbread import base

@pytest.mark.parametrize('paper',['A4','US Letter'])
@pytest.mark.parametrize('template',[t for t in TEMPLATES if t['category']!='blocky-characters'],ids=lambda t:t['id'])
def test_real_roof_cap_geometry(template,paper):
    configure_engine(base,paper)
    caps,seams,units,pages=build(template)
    assert caps and pages
    assert template['roof_rake_mm']==template['roof_overhang_mm']==10
    assert all(c['status']=='PASS' for c in validate(template))
    assert sum(len(u.ids) for u in units)==len(caps)
    assert all(base.fits(u) for u in units)
    for p in caps.values():
        for art in artwork(template,p):
            if art['type']=='circle':shape=Point(art['center']).buffer(art['radius'])
            elif art['type']=='line':shape=LineString(art['points']).buffer(art.get('width',0)/2)
            else:shape=Polygon(art['points'])
            assert p.square.buffer(.001).covers(shape)


def test_legacy_flush_snapshot_stays_flush():
    t={k:v for k,v in TEMPLATES[0].items() if k not in ('roof_overhang_mm','roof_rake_mm')}
    assert build(t)==({},[],[],[])

def test_a_frame_full_overhang_fits_one_letter_sheet():
    configure_engine(base,'US Letter')
    _,seams,units,pages=build(BY_ID['gb_us_a_frame_heritage'])
    assert len(pages)==1 and len(units)==2
    assert len(seams)==1 and not seams[0]['hinge']
