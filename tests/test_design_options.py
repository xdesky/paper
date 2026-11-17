import json,time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box
from backend.app import create_app
from backend.design_options import DesignOptions,OPTIONS
from backend.gingerbread import generate
from backend.accessories import tree_piece

@pytest.mark.parametrize('index',range(5))
def test_new_accessories_and_patterns_export(index,tmp_path):
    design=dict(roof=OPTIONS['roof'][index][0],wall=OPTIONS['wall'][index][0],tree=OPTIONS['tree'][index+1][0],gift=OPTIONS['gift'][index+1][0])
    for slot in (True,False):
        shape=tree_piece(slot,design['tree'])
        assert shape.is_valid and shape.geom_type=='Polygon' and not shape.interiors
        assert shape.intersection(box(15.7,32.5 if slot else -1,16.3,66 if slot else 32.5)).area<1e-7
    report=generate(dict(preset='gb_classic',project_id='design',revision=1,paper='A4',design=design,personal_name='Nhà của An'),tmp_path)
    assert report['overall_status']=='PASS'
    manifest=json.loads((tmp_path/'generation_manifest.json').read_text())
    assert manifest['template']['design']==design
    assert (tmp_path/'printable_a4_coloring.pdf').exists()
    spec=json.loads((tmp_path/'model_spec.json').read_text())
    assert 'data-personal-name' in spec['appearance']['panels']['FRONT']


def test_empty_start_and_design_lifecycle(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/api/projects').json()==[]
        options=c.get('/api/design-options').json()
        assert len(options['tree'])==len(options['gift'])==6
        design=dict(roof='stars',wall='brick',tree='star',gift='holly')
        p=c.post('/api/projects',json={'name':'My own house','preset':'gb_classic','design':design}).json();pid=p['id']
        assert p['design']==design
        assert c.get(f'/api/projects/{pid}').json()['design']==design
        assert c.post(f'/api/projects/{pid}/duplicate').json()['design']==design
        same=c.patch(f'/api/projects/{pid}',json={'design':design}).json()
        assert same['revision']==1
        design['gift']='stars'
        changed=c.patch(f'/api/projects/{pid}',json={'design':design}).json()
        assert changed['revision']==2 and changed['status']=='STALE'
        assert c.patch(f'/api/projects/{pid}',json={'design':{'tree':'bad'}}).status_code==422
        preview=c.post('/api/templates/gb_classic/personalize-preview',json={'design':design})
        assert preview.status_code==200
        job=c.post(f'/api/projects/{pid}/generate').json()['id']
        for _ in range(600):
            state=c.get(f'/api/jobs/{job}').json()
            if state['status'] in ('SUCCEEDED','FAILED'):break
            time.sleep(.1)
        assert state['status']=='SUCCEEDED',state
        manifest=c.get(f'/api/projects/{pid}/artifacts/generation_manifest.json').json()
        assert manifest['input']['design']==manifest['template']['design']==design
    with TestClient(create_app(tmp_path)) as c:
        assert c.get(f'/api/projects/{pid}').json()['design']==design
