import hashlib
import io
import json
from pathlib import Path
import time
import zipfile
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def studio(tmp_path_factory):
    data = tmp_path_factory.mktemp('studio')
    with TestClient(create_app(data, seed=False)) as client:
        yield client, data


def generate(client, pid):
    response = client.post(f'/api/projects/{pid}/generate')
    assert response.status_code == 202, response.text
    jid = response.json()['id']
    deadline = time.monotonic()+180
    while time.monotonic() < deadline:
        job = client.get(f'/api/jobs/{jid}').json()
        if job['status'] in ('SUCCEEDED', 'FAILED'):
            assert job['status'] == 'SUCCEEDED', job
            return job
        time.sleep(.15)
    pytest.fail('Job did not finish')


@pytest.mark.parametrize('preset,folder,pages,folds,glue', [
    ('cube_100','cube_100mm',3,3,9), ('cube_200','cube_200mm',12,8,36),
    ('cube_300','cube_300mm',24,0,48), ('house_frame','house_frame_120x90x180mm',2,2,2)])
def test_real_pipeline_regression(studio, preset, folder, pages, folds, glue):
    client, data = studio
    r = client.post('/api/projects', json={'name':preset,'preset':preset})
    assert r.status_code == 201
    pid = r.json()['id']
    assert client.get(f'/api/projects/{pid}/geometry').status_code == 409
    job = generate(client, pid)
    spec = client.get(f'/api/projects/{pid}/geometry').json()
    qa = client.get(f'/api/projects/{pid}/validation').json()
    original = json.loads((ROOT/'papercraft-v1.2'/folder/'model_spec.json').read_text())
    assert spec['geometry_sha256'] == original['geometry_sha256']
    assert spec['geometry'] == original['geometry']
    assert spec['print_units'] == original['print_units']
    assert spec['sheet_count'] == pages
    assert qa['summary']['fold_hinges'] == folds
    assert qa['summary']['glue_seams'] == glue
    assert qa['overall_status'] == 'PASS'
    assert all(t['status']=='PASS' for t in qa['tests'])
    assert qa['physical_assembly']=='NOT_TESTED'
    assert len(client.get(f'/api/projects/{pid}/pages').json()) == pages
    root = data / pid / str(job['revision']) / 'artifacts'
    manifest = json.loads((root/'generation_manifest.json').read_text())
    for artifact in manifest['artifacts']:
        r = client.get(f'/api/projects/{pid}/artifacts/{artifact["path"]}?download=true')
        assert r.status_code == 200
        assert hashlib.sha256(r.content).hexdigest() == artifact['sha256']
        assert artifact['geometry_sha256'] == spec['geometry_sha256']
    r = client.get(f'/api/projects/{pid}/artifacts/printable_us_letter.pdf?download=true')
    assert r.headers['content-type']=='application/pdf'
    assert 'attachment' in r.headers['content-disposition']
    assert client.get(f'/api/projects/{pid}/artifacts/svg_pages/page_001.svg').headers['content-type'].startswith('image/svg+xml')
    z = zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{pid}/artifacts/project.zip').content))
    assert 'assembly_guide.pdf' in z.namelist()
    assert json.loads(z.read('generation_manifest.json')) == manifest
    assert client.get(f'/api/projects/{pid}/artifacts/%2e%2e%2frequest.json').status_code == 404
    assert client.get(f'/api/projects/{pid}/artifacts/%2Fetc%2Fpasswd').status_code == 404
    if preset == 'cube_100':
        old_pdf=(root/'printable_us_letter.pdf').read_bytes()
        second=generate(client,pid)
        assert second['revision']==job['revision']+1
        spec2=client.get(f'/api/projects/{pid}/geometry').json()
        assert spec2['geometry_sha256']==spec['geometry_sha256']
        assert spec2['print_units']==spec['print_units']
        assert (root/'printable_us_letter.pdf').read_bytes()==old_pdf
        assert client.patch(f'/api/projects/{pid}',json={'preset':'cube_200'}).json()['status']=='STALE'
        assert client.get(f'/api/projects/{pid}/artifacts/project.zip').status_code==409


def test_project_management_and_invalid_inputs(studio):
    client,_=studio
    for bad in ({'name':'','preset':'cube_100'}, {'name':'X','preset':'image'}, {'name':'X','preset':'cube_150'}, {'name':'X','size':999}):
        assert client.post('/api/projects',json=bad).status_code == 422
    pid=client.post('/api/projects',json={'name':'Original'}).json()['id']
    assert client.patch(f'/api/projects/{pid}',json={'name':'Renamed'}).json()['name']=='Renamed'
    copy=client.post(f'/api/projects/{pid}/duplicate').json()
    assert copy['id'] != pid and copy['preset']=='cube_100' and copy['status']=='DRAFT'
    assert client.delete(f'/api/projects/{pid}').status_code==204
    assert client.get(f'/api/projects/{pid}').status_code==404
    assert client.get('/api/jobs/nonexistent').status_code==404
    assert client.post('/api/projects/nonexistent/generate').status_code==404
    assert client.get('/api/health').json()['engine']=='1.2.0'
    assert '/api/projects/{pid}/generate' in client.get('/openapi.json').json()['paths']


def test_timeout_is_persisted_and_download_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv('PPM_JOB_TIMEOUT','0')
    with TestClient(create_app(tmp_path, seed=False)) as client:
        pid=client.post('/api/projects',json={'name':'Timeout'}).json()['id']
        jid=client.post(f'/api/projects/{pid}/generate').json()['id']
        for _ in range(100):
            job=client.get(f'/api/jobs/{jid}').json()
            if job['status']=='FAILED':break
            time.sleep(.02)
        assert job['status']=='FAILED' and 'timeout' in job['error']
        assert client.get(f'/api/projects/{pid}/artifacts/project.zip').status_code==409
    with TestClient(create_app(tmp_path, seed=False)) as client:
        assert client.get(f'/api/jobs/{jid}').json()['status']=='FAILED'
