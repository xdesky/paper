#!/usr/bin/env python3
"""Independent file-level verification of v1.2 output, without generating files again."""
import sys, json, hashlib
from pathlib import Path
import fitz
import xml.etree.ElementTree as ET

def sha_json(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def verify(folder):
    root=Path(folder);spec=json.loads((root/'model_spec.json').read_text())
    report=json.loads((root/'validation_report.json').read_text())
    expected={'US Letter':(215.9,279.4),'A4':(210.0,297.0)}[spec['paper']['name']]
    pdf=root/('printable_a4.pdf' if spec['paper']['name']=='A4' and (root/'printable_a4.pdf').exists() else 'printable_us_letter.pdf')
    svgs=sorted((root/'svg_pages').glob('page_*.svg'))
    errors=[]
    def check(v,msg):
        if not v:errors.append(msg)
    check(spec.get('locked') is True,'not locked')
    check(spec.get('units')=='mm','not in millimetres')
    check(len(spec.get('print_units',[]))==report['summary']['cut_pieces'],'print unit count mismatch')
    check(spec['geometry_sha256']==sha_json(spec['geometry']),'geometry hash mismatch')
    check(spec['model_id']==report['model_id'],'model ID mismatch')
    check(report['model_geometry_sha256']==spec['geometry_sha256'],'report hash mismatch')
    check(all(t['status']=='PASS' for t in report['tests']),'saved test failure')
    with fitz.open(pdf) as d:
        check(len(d)==spec['sheet_count'],'PDF page count')
        for i,p in enumerate(d):
            check(abs(p.rect.width/72*25.4-expected[0])<.001 and abs(p.rect.height/72*25.4-expected[1])<.001,f'PDF page size #{i+1}')
    check(len(svgs)==spec['sheet_count'],'SVG page count')
    for f in svgs:
        r=ET.parse(f).getroot()
        check(r.get('width')==f'{expected[0]}mm' and r.get('height')==f'{expected[1]}mm',f'SVG page dimensions {f.name}')
    result={'folder':str(root),'status':'PASS' if not errors else 'FAIL','issues':errors,
            'pages':spec['sheet_count'],'geometry_hash':spec['geometry_sha256']}
    print(json.dumps(result,ensure_ascii=False))
    return not errors

if __name__=='__main__':
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.')
    folders=[p for p in root.iterdir() if p.is_dir() and (p/'model_spec.json').exists()]
    if not folders and (root/'model_spec.json').exists():folders=[root]
    assert folders,'No model_spec.json files found'
    sys.exit(0 if all(verify(p) for p in sorted(folders)) else 1)
