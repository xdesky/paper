import json
import xml.etree.ElementTree as ET
import pymupdf as fitz
import pytest
from tests.support import TestClient
from tests.support import create_app
from backend.gingerbread import generate
from backend.template_catalog import TEMPLATES

@pytest.mark.parametrize('template',TEMPLATES[-6:],ids=lambda t:t['id'])
@pytest.mark.parametrize('paper',['A4','US Letter'])
def test_complex_color_and_coloring(template,paper,tmp_path):
    report=generate(dict(preset=template['id'],paper=paper,project_id='complex',revision=1,personal_name='Gia đình Nguyễn'),tmp_path)
    assert report['overall_status']=='PASS'
    normal=sorted((tmp_path/'svg_pages').glob('*.svg'));outline=sorted((tmp_path/'coloring_svg_pages').glob('*.svg'))
    assert len(normal)==len(outline)>0
    for a,b in zip(normal,outline):
        ca,cb=ET.parse(a).getroot(),ET.parse(b).getroot()
        assert ca.get('viewBox')==cb.get('viewBox')
        for n in cb.iter():
            assert n.get('fill') in (None,'none','#ffffff','#222222')
            assert n.get('stroke') in (None,'none','#222222')
    stem='printable_a4' if paper=='A4' else 'printable_us_letter'
    with fitz.open(tmp_path/(stem+'.pdf')) as color,fitz.open(tmp_path/(stem+'_coloring.pdf')) as blank:
        assert len(color)==len(blank)==len(normal)
        assert abs(color[0].rect.width-blank[0].rect.width)<.02
    assert 'data-personal-name' in ''.join(p.read_text() for p in outline)
    assert (tmp_path/'project.zip').exists()

def test_coloring_routes_validate_style_and_old_revisions(tmp_path):
    with TestClient(create_app(tmp_path,seed=False)) as c:
        p=c.post('/api/projects',json={'name':'old','preset':'gb_classic'}).json()['id']
        assert c.get(f'/api/projects/{p}/print?style=invalid').status_code==422
        assert c.get(f'/api/projects/{p}/pages?style=coloring').status_code==409
