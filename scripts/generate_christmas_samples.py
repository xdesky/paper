from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.worker import generate
from backend.template_catalog import TEMPLATES,CATALOG_VERSION
for t in TEMPLATES:
    target=Path('output/christmas')/t['id']
    if target.exists():raise SystemExit(f'Preserving existing snapshot: {target}')
    report=generate({'preset':t['id'],'project_id':'sample-'+t['id'],'revision':1,'template':t,'template_version':CATALOG_VERSION,'engine_version':'gingerbread-1.0.1','paper':'US Letter','scale':1.0},target)
    print(t['id'], report['overall_status'], report['summary'])
