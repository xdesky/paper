import hashlib
import io
import json
import time
import zipfile
from pathlib import Path
import pytest
from tests.support import TestClient
from tests.support import create_app
from backend.template_catalog import TEMPLATES

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    with TestClient(create_app(tmp_path_factory.mktemp('templates'),seed=False)) as c:yield c

@pytest.mark.parametrize('template',TEMPLATES,ids=lambda t:t['id'])
def test_template_end_to_end(client,template):
    pid=client.post('/api/projects',json={'name':template['name'],'preset':template['id']}).json()['id']
    response=client.post(f'/api/projects/{pid}/generate');assert response.status_code==202
    jid=response.json()['id']
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        job=client.get(f'/api/jobs/{jid}').json()
        if job['status'] in ('SUCCEEDED','FAILED'):break
        time.sleep(.1)
    assert job['status']=='SUCCEEDED',job.get('error')
    spec=client.get(f'/api/projects/{pid}/geometry').json()
    report=client.get(f'/api/projects/{pid}/validation').json()
    assert spec['sheet_count']==spec['house_sheet_count']+2+spec['roof_cap']['sheet_count']+int(bool(template.get('chimney')))
    assert len(spec['scene_accessories']['panels'])==15+len(spec['geometry']['panels'])-4+4*int(bool(template.get('chimney')))
    assert spec['scene_accessories']['gift_sizes_mm']==[20,16]
    assert report['summary']['accessory_cut_pieces']==5+spec['roof_cap']['cut_pieces']+int(bool(template.get('chimney')))
    assert report['overall_status']=='PASS'
    print_view=client.get(f'/api/projects/{pid}/print')
    assert print_view.status_code==200 and 'window.print()' in print_view.text
    assert print_view.text.count('<section class="sheet">')==spec['sheet_count']
    assert 'size:215.9mm 279.4mm;margin:0' in print_view.text
    assert all(t['status']=='PASS' for t in report['tests'])
    assert len(spec['geometry']['panels'])==4+len(template.get('profile',[(0,0),(.5,1),(1,0)]))-1
    assert len(spec['geometry']['seams'])==3*len(spec['geometry']['panels'])-7
    assert report['summary']['fold_hinges']==sum(bool(u['fold_code']) for u in spec['print_units'])
    assert report['summary']['glue_seams']==len(spec['geometry']['seams'])-report['summary']['fold_hinges']
    assert spec['geometry']['model']['height_mm']==template['wall_height']+template['roof_rise']
    assert len(spec['appearance']['panels'])==4+len(template.get('profile',[(0,0),(.5,1),(1,0)]))-1
    archive=client.get(f'/api/projects/{pid}/artifacts/project.zip?download=true')
    assert archive.status_code==200 and archive.headers['content-type']=='application/zip'
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        manifest=json.loads(z.read('generation_manifest.json'))
        assert manifest['template']==template
        assert manifest['input']['template']==template
        for artifact in manifest['artifacts']:
            assert hashlib.sha256(z.read(artifact['path'])).hexdigest()==artifact['sha256']
        assert z.read('printable_us_letter.pdf').startswith(b'%PDF')
        assert b'ROOF' in z.read('model.obj')
    if template['id']=='gb_classic':
        from backend.gingerbread import model,digest
        first=model(template);second=model(template)
        assert [u.cut_bounds() for u in first[2]]==[u.cut_bounds() for u in second[2]]
        assert spec['geometry_sha256']==digest(spec['geometry'])
    assert client.patch(f'/api/projects/{pid}',json={'preset':'cube_100'}).json()['status']=='STALE'
    assert client.get(f'/api/projects/{pid}/artifacts/project.zip').status_code==409
    assert client.get(f'/api/projects/{pid}/print').status_code==409


def test_catalog_and_previews(client):
    catalog=client.get('/api/templates').json()
    assert len(catalog)==len(TEMPLATES)
    for t in catalog:
        assert t['sheet_count']>0 and t['physical_assembly']=='NOT_TESTED'
        r=client.get(t['preview_url'])
        assert r.status_code==200 and r.headers['content-type'].startswith('image/svg+xml')
        assert '<svg' in r.text and '<script' not in r.text
    assert client.get('/api/templates/missing/preview.svg').status_code==404
    assert client.post('/api/projects',json={'name':'Bad','preset':'gb_unknown'}).status_code==422
