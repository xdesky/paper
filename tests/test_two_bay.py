"""Two-bay houses must have two real peaks and one concave roof junction."""
import json
import pytest
from backend.template_catalog import TEMPLATES
from backend.gingerbread import model, generate, base
from backend.paper import configure_engine
from backend.roof_cap import validate

HOUSES=[t for t in TEMPLATES if t['collection']=='Two-Bay Houses']

@pytest.mark.parametrize('template',HOUSES,ids=lambda t:t['id'])
def test_two_bay_roof_and_a4_export(template,tmp_path):
    configure_engine(base,'A4')
    panels,seams,units,pages,boundary=model(template)
    ridge=template['profile']
    assert sum(b[1]>a[1] and b[1]>c[1] for a,b,c in zip(ridge,ridge[1:],ridge[2:]))==2
    valleys=[s for s in seams if s.get('fold_direction')=='VALLEY_FROM_PRINTED_OUTSIDE']
    assert len(valleys)==1
    assert {m['panel'] for m in valleys[0]['occurrences']}=={'ROOF_2','ROOF_3'}
    assert len(panels)==8 and len(boundary)==4
    assert all(check['status']=='PASS' for check in validate(template))
    report=generate(dict(preset=template['id'],project_id='two-bay-test',revision=1,paper='A4',personal_name='Gia đình Nguyễn'),tmp_path)
    assert report['overall_status']=='PASS',report
    spec=json.loads((tmp_path/'model_spec.json').read_text())
    assert len([s for s in spec['geometry']['seams'] if s['fold_direction']=='VALLEY_FROM_PRINTED_OUTSIDE'])==1
    assert 'data-personal-name' in spec['appearance']['panels']['FRONT']
    assert (tmp_path/'printable_a4.pdf').read_bytes().startswith(b'%PDF')

@pytest.mark.parametrize('paper',['A4','US Letter'])
def test_all_house_roof_joints_use_wall_tabs(paper):
    configure_engine(base,paper)
    for template in TEMPLATES:
        if template['category']=='blocky-characters':
            continue
        panels,seams,units,_,_=model(template)
        for seam in seams:
            mates=seam['occurrences']
            roof=[mate for mate in mates if mate['panel'].startswith('ROOF')]
            if len(roof)==1:
                wall=next(mate for mate in mates if mate!=roof[0])
                assert wall['edge'] in panels[wall['panel']].tabs,template['id']
                assert roof[0]['edge'] not in panels[roof[0]['panel']].tabs,template['id']
        component_area=sum(panel.square.area+sum(tab.area for tab in panel.tabs.values()) for panel in panels.values())
        assert sum(unit.shape().area for unit in units)==pytest.approx(component_area,abs=1e-5)
