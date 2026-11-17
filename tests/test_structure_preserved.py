"""Reference artwork must not change any pre-existing physical part or seam."""
import json
from pathlib import Path
from backend.template_catalog import TEMPLATES
from backend.gingerbread import model,digest,base
from backend.accessories import layout
from backend.paper import configure_engine


def test_reference_art_preserves_all_26_structures():
    before=json.loads((Path(__file__).parent/'fixtures/structure-before-reference-art.json').read_text())
    configure_engine(base,'US Letter')
    assert set(before) <= {t['id'] for t in TEMPLATES}
    for t in TEMPLATES:
        if t['id'] not in before:continue
        panels,seams,units,pages,boundary=model(t)
        actual=digest({'panels':[(p.id,p.points,p.vertices) for p in panels.values()],
            'seams':seams,'units':[(u.ids,u.cut_bounds()) for u in units],
            'accessories':[[list(a['shape'].exterior.coords) for a,x,y in page] for page in layout(t)[:2]]})
        assert actual==before[t['id']],t['id']
