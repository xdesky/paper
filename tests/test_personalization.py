import json,time,unicodedata
from pathlib import Path
import pytest
from tests.support import TestClient
from shapely.geometry import Polygon,box
from tests.support import create_app
from backend.template_catalog import TEMPLATES
from backend.gingerbread import model,decorations,digest
from backend.personalization import normalize_name,nameplate

@pytest.mark.parametrize('template',TEMPLATES,ids=lambda t:t['id'])
@pytest.mark.parametrize('name',['Gia đình Nguyễn','W'*24])
def test_nameplate_fits_every_house(template,name):
    panels=model(template)[0];front=panels['FRONT']
    shaped=nameplate({**template,'personal_name':name},front)
    plaque=next(s for s in shaped if s['type']=='polygon')
    assert front.square.buffer(-6).covers(Polygon(plaque['points']))
    assert Polygon(plaque['points']).bounds[2]-Polygon(plaque['points']).bounds[0] <= 42.01
    paths=[s for s in shaped if s['type']=='path']
    assert paths and ''.join(s['label'] for s in paths).replace(' ','')==name.replace(' ','')
    for p in paths:
        bounds=Polygon(p['points'])
        assert front.square.buffer(-1).covers(bounds)
        assert bounds.bounds[3]-bounds.bounds[1]>1
    assert nameplate({**template,'personal_name':name},panels['RIGHT'])==[]


def test_plaque_resizes_for_short_names_and_keeps_padding():
    template=next(t for t in TEMPLATES if t['id']=='gb_classic')
    front=model(template)[0]['FRONT']
    sizes=[]
    for name in ('Lily', 'Isabella'):
        shapes=nameplate({**template,'personal_name':name},front)
        plaque=Polygon(next(s for s in shapes if s['type']=='polygon')['points'])
        glyph=Polygon(next(s for s in shapes if s['type']=='path')['points'])
        left,_,right,_=plaque.bounds
        text_left,_,text_right,_=glyph.bounds
        assert plaque.area>0 and text_left-left>=5.2 and right-text_right>=5.2
        assert next(s for s in shapes if s['type']=='polygon')['fill']=='#ad2534'
        sizes.append(right-left)
    assert sizes[0]<sizes[1]<=42.01


def test_name_lifecycle_and_export(tmp_path):
    with TestClient(create_app(tmp_path,seed=False)) as c:
        name='Gia đình Nguyễn'
        p=c.post('/api/projects',json={'name':'Personal house','preset':'gb_classic','personal_name':unicodedata.normalize('NFD',name)}).json();pid=p['id']
        assert p['personal_name']==name
        preview=c.post('/api/templates/gb_classic/personalize-preview',json={'personal_name':name})
        assert preview.status_code==200 and 'data-personal-name=' in preview.text
        jid=c.post(f'/api/projects/{pid}/generate').json()['id']
        for _ in range(600):
            job=c.get(f'/api/jobs/{jid}').json()
            if job['status'] in ('FAILED','SUCCEEDED'):break
            time.sleep(.1)
        assert job['status']=='SUCCEEDED',job
        spec=c.get(f'/api/projects/{pid}/geometry').json()
        assert spec['personalization']['name']==name
        assert 'data-personal-name' in spec['appearance']['panels']['FRONT']
        assert 'data-personal-name' in c.get(f'/api/projects/{pid}/print').text
        manifest=c.get(f'/api/projects/{pid}/artifacts/generation_manifest.json').json()
        assert manifest['input']['personal_name']==manifest['template']['personal_name']==name
        assert c.post(f'/api/projects/{pid}/duplicate').json()['personal_name']==name
        same=c.patch(f'/api/projects/{pid}',json={'personal_name':name}).json()
        assert same['status']=='READY'
        changed=c.patch(f'/api/projects/{pid}',json={'personal_name':''}).json()
        assert changed['status']=='STALE' and changed['personal_name']==''
        assert c.get(f'/api/projects/{pid}/print').status_code==409
        for invalid in ('<script>alert(1)</script>','x'*25,'😀'):
            assert c.patch(f'/api/projects/{pid}',json={'personal_name':invalid}).status_code==422
            assert c.post('/api/templates/gb_classic/personalize-preview',json={'personal_name':invalid}).status_code==422
