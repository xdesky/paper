import json
from pathlib import Path

import pymupdf
import pytest

from tests.support import TestClient, create_app
from backend.template_catalog import CATALOG_VERSION, TEMPLATES

HOUSE=next(t['id'] for t in TEMPLATES if t.get('category')=='gingerbread-houses')


def make_project(client,*,objects=None,name='Test Village'):
    response=client.post('/api/city/projects',json={'schemaVersion':1,'name':name,'grid':{'columns':8,'rows':8,'cellSizeMm':100},'objects':objects or []})
    assert response.status_code==201,response.text
    return response.json()


def placed(x,z,identifier='house'):
    return {'id':identifier,'assetId':HOUSE,'assetRevision':CATALOG_VERSION,'xCell':x,'zCell':z,'rotationDeg':0}


def test_city_asset_adapter_and_model_use_v1_registry_geometry(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        catalog=client.get('/api/city/assets');assert catalog.status_code==200
        asset=next(item for item in catalog.json() if item['id']==HOUSE)
        template=next(t for t in TEMPLATES if t['id']==HOUSE)
        assert asset['physicalSizeMm']=={'width':template['width'],'depth':template['depth'],'height':template['wall_height']+template['roof_rise']}
        assert asset['footprintMm']=={'width':template['width']+60,'depth':template['depth']+70}
        assert asset['revision']==CATALOG_VERSION and asset['printStatus']=='ready'
        model=client.get(asset['modelRef']).json()
        assert model['assetRevision']==CATALOG_VERSION and len(model['surfaces'])>6
        assert {s['id'] for s in model['surfaces']} >= {'FRONT','RIGHT','ROOF_LEFT','DISPLAY_BASE'}
        assert all(len(s['vertices_3d_mm'])>=3 and s['art'].startswith('<svg') for s in model['surfaces'])
        assert client.get('/api/city/assets/not-a-house/model').status_code==404


def test_city_project_persists_with_owner_and_rejects_overlaps(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as owner,TestClient(app) as other:
        other.post('/api/auth/logout')
        registered=other.post('/api/auth/register',json={'email':'other-city@example.com','password':'a-different-test-password','display_name':'Other builder'})
        assert registered.status_code==201
        project=make_project(owner,objects=[placed(0,0)])
        pid=project['id']
        assert owner.get('/api/city/projects').json()[0]['objects']==project['objects']
        assert other.get(f'/api/city/projects/{pid}').status_code==404
        duplicate=owner.put(f'/api/city/projects/{pid}',json={'schemaVersion':1,'name':'Overlap','grid':project['grid'],'objects':[placed(0,0,'one'),placed(1,0,'two')]})
        assert duplicate.status_code==422 and 'overlap' in duplicate.text.lower()
        unknown={'id':'future-model','assetId':'future-asset','assetRevision':'future-v2','xCell':5,'zCell':5,'rotationDeg':90}
        saved=owner.put(f'/api/city/projects/{pid}',json={'schemaVersion':1,'name':'Recovered','grid':project['grid'],'objects':[unknown]})
        assert saved.status_code==200 and saved.json()['objects']==[unknown]
        assert owner.get('/api/city/projects').json()[0]['name']=='Recovered'


def test_reproducible_demo_village_uses_current_printable_assets(tmp_path):
    project=json.loads((Path(__file__).parents[1]/'docs/examples/christmas-village.json').read_text())
    with TestClient(create_app(tmp_path)) as client:
        response=client.post('/api/city/projects',json=project)
        assert response.status_code==201,response.text
        saved=response.json()
        assert len(saved['objects'])==4
        assert {item['assetId'] for item in saved['objects']}=={'gb_forest','gb_classic','gb_frost','gb_candy'}
        preflight=client.post(f"/api/city/projects/{saved['id']}/preflight",json={'project_id':saved['id'],'paper':'US Letter'})
        assert preflight.status_code==200,preflight.text
        assert preflight.json()['selectedObjectCount']==4


def test_combined_city_pdf_repeats_complete_vector_sets_at_native_size(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        project=make_project(client,objects=[placed(0,0,'first'),placed(2,0,'second')],name='Two Houses')
        body={'project_id':project['id'],'paper':'A4','selected_object_ids':None}
        preflight=client.post(f"/api/city/projects/{project['id']}/preflight",json=body)
        assert preflight.status_code==200,preflight.text
        info=preflight.json();assert info['selectedObjectCount']==2
        assert info['items'][0]['quantity']==2 and info['items'][0]['pagesPerCopy']>0
        assert info['items'][0]['guidePages']>0
        assert info['totalPages']==1+2*info['items'][0]['pagesPerCopy']+info['items'][0]['guidePages']
        assert any('not a printable base' in warning.lower() for warning in info['warnings'])
        response=client.post(f"/api/city/projects/{project['id']}/export",json=body)
        assert response.status_code==200,response.text[:500]
        assert response.headers['content-type']=='application/pdf'
        with pymupdf.open(stream=response.content,filetype='pdf') as document:
            assert len(document)==info['totalPages']
            assert all(abs(page.mediabox.width-210*72/25.4)<.2 and abs(page.mediabox.height-297*72/25.4)<.2 for page in document)
            first_page=' '.join(document[0].get_text().split()).lower()
            assert 'reference map' in first_page and 'not a printable base' in first_page and '50 mm calibration ruler' in first_page
            assert 'print inventory' in first_page and 'cell 1,1' in first_page and 'r0' in first_page
            assert 'guide pages' in first_page and '90 x 70 x 130 mm' in first_page
        single=client.post(f"/api/city/projects/{project['id']}/preflight",json={**body,'selected_object_ids':['first']})
        assert single.status_code==200 and single.json()['selectedObjectCount']==1
        assert single.json()['totalPages']==1+info['items'][0]['pagesPerCopy']+info['items'][0]['guidePages']

