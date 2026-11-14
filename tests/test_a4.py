import io,json,time
import pytest
import fitz
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.template_catalog import TEMPLATES

@pytest.fixture(scope='module')
def studio(tmp_path_factory):
 with TestClient(create_app(tmp_path_factory.mktemp('a4'),seed=False)) as c:yield c

@pytest.mark.parametrize('preset',['cube_100','cube_200','cube_300','house_frame']+[t['id'] for t in TEMPLATES])
def test_a4_pipeline(studio,preset):
 c=studio
 p=c.post('/api/projects',json={'name':'A4 '+preset,'preset':preset,'paper':'A4'}).json();pid=p['id']
 assert p['paper']=='A4'
 jid=c.post(f'/api/projects/{pid}/generate').json()['id']
 deadline=time.monotonic()+120
 while time.monotonic()<deadline:
  job=c.get(f'/api/jobs/{jid}').json()
  if job['status'] in ['FAILED','SUCCEEDED']:break
  time.sleep(.1)
 assert job['status']=='SUCCEEDED',job.get('error')
 spec=c.get(f'/api/projects/{pid}/geometry').json()
 assert spec['paper']['name']=='A4' and spec['paper']['page_mm']==[210,297] and spec['paper']['scale']==1
 report=c.get(f'/api/projects/{pid}/validation').json()
 assert report['overall_status']=='PASS'
 data=c.get(f'/api/projects/{pid}/artifacts/printable_a4.pdf').content
 with fitz.open(stream=data,filetype='pdf') as doc:
  assert len(doc)==spec['sheet_count']
  for page in doc:
   assert abs(page.rect.width/72*25.4-210)<.01 and abs(page.rect.height/72*25.4-297)<.01
   assert any(i[0]=='l' and abs(abs(i[2].x-i[1].x)/72*25.4-40)<.01 for d in page.get_drawings() for i in d['items'])
 assert c.get(f'/api/projects/{pid}/artifacts/printable_us_letter.pdf').status_code==404
 view=c.get(f'/api/projects/{pid}/print')
 assert 'size:210mm 297mm;margin:0' in view.text
 clone=c.post(f'/api/projects/{pid}/duplicate').json();assert clone['paper']=='A4'
 if preset=='gb_classic':
  oldrev=p['revision'];edited=c.patch(f'/api/projects/{pid}',json={'paper':'US Letter'}).json()
  assert edited['status']=='STALE' and edited['revision']>oldrev
  assert c.get(f'/api/projects/{pid}/print').status_code==409
  assert c.get(f'/api/projects/{pid}/artifacts/printable_a4.pdf').status_code==409
 assert c.patch(f'/api/projects/{pid}',json={'paper':'A3'}).status_code==422
