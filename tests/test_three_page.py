import pytest
from shapely.geometry import box
from backend.gingerbread import base
from backend.paper import configure_engine
from backend.template_catalog import BY_ID
from backend.three_page import plan_classic


@pytest.mark.parametrize('paper',['US Letter','A4'])
def test_classic_three_page_placement(paper):
    configure_engine(base,paper)
    template={**BY_ID['gb_classic'],'roof_overhang_mm':10,'roof_rake_mm':10}
    pages=plan_classic(template)
    assert [{p.id for p in page} for page in pages]==[
        {'FRONT_WALLS','ROOF'},
        {'BACK_WALLS','A','B','CHIMNEY'},
        {'BASE','TREE_1','TREE_2'},
    ]
    printable=box(8,20,base.PAGE_W-8,base.PAGE_H-24.4)
    for page in pages:
        assert all(printable.buffer(1e-6).covers(p.shape) for p in page)
        assert all(a.shape.distance(b.shape)>=3-1e-6 for i,a in enumerate(page) for b in page[i+1:])

@pytest.mark.parametrize('paper',['US Letter','A4'])
def test_compact_roof_dimensions_and_support(paper):
    from backend.gingerbread import model
    from backend.roof_cap import layout
    from backend.three_page import compact_layout

    configure_engine(base,paper)
    template=BY_ID['gb_classic']
    original=layout(template)[0][0][0]['shape']
    revised,pages=compact_layout(template,model(template))
    assert len(pages)==3
    roof=pages[0]['accessories'][0][0]['shape']
    dimensions=lambda shape: (shape.bounds[2]-shape.bounds[0],shape.bounds[3]-shape.bounds[1])
    assert dimensions(roof)==pytest.approx(tuple(d+10 for d in dimensions(original)))
    assert roof.equals(roof.envelope)
    assert {placement.id for _,placement in pages[1]['accessories']}=={'A','B','CHIMNEY'}
    assert any(pid.startswith('ROOF') for unit in pages[2]['units'] for pid in unit.ids)
