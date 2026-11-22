"""Process-isolated adapter. Geometry and layout remain owned by upstream v1.2."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mpl-cache'))
sys.path.insert(0, str(ROOT / 'papercraft-v1.2'))


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def generate(request, out, progress=lambda stage: None):
    if request['preset'].startswith('pc_'):
        from .blocky import generate as generate_blocky
        return generate_blocky(request,out,progress)
    if request['preset'].startswith('gb_'):
        from .gingerbread import generate as generate_house
        return generate_house(request, out, progress)
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import fitz
    from PIL import Image, PngImagePlugin
    import generate_connected_nets_v1_2 as engine
    from .paper import configure_engine, printable_filename
    paper_name = request.get('paper', 'US Letter')
    configure_engine(engine, paper_name)
    from verify_package_v1_2 import verify as independent_verify
    import jsonschema

    def fonts():
        folder = Path(matplotlib.get_data_path()) / 'fonts' / 'ttf'
        for name, filename in [(engine.base.FONT, 'DejaVuSans.ttf'), (engine.base.FONT_BOLD, 'DejaVuSans-Bold.ttf')]:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
    engine.base.install_fonts = fonts
    captured = {}
    originals = {}
    # The upstream heading extends into the 8 mm top margin. Move only its
    # baseline down; preserve every cut/fold/calibration coordinate.
    for name in ('pdf_text', 'svg_label'):
        original = getattr(engine, name)
        originals[name] = original
        def safe_heading(target, x, y, *args, _original=original, **kwargs):
            return _original(target, x, engine.PAGE_H-11 if abs(y-(engine.PAGE_H-9.2))<.001 else y, *args, **kwargs)
        setattr(engine, name, safe_heading)
    stages = {'cube_data': 'Build Geometry', 'house_data': 'Build Geometry', 'choose_units': 'Choose Hinges / Unfold / Add Tabs', 'pack_units': 'Pack Pages', 'write_pdf': 'Export', 'verify': 'QA'}
    for name, stage in stages.items():
        original = getattr(engine, name)
        originals[name] = original
        def wrapped(*args, _original=original, _name=name, _stage=stage, **kwargs):
            progress(_stage)
            if _name == 'verify':
                captured['verify_args'] = args
            return _original(*args, **kwargs)
        setattr(engine, name, wrapped)
    try:
        preset = request['preset']
        size = int(preset.split('_')[1]) if preset.startswith('cube_') else None
        if preset not in ('cube_100', 'cube_200', 'cube_300', 'house_frame'):
            raise ValueError('Unsupported Phase A preset')
        progress('Validate Input')
        report = engine.build('cube' if size else 'house', out, size)
    finally:
        for name, original in originals.items():
            setattr(engine, name, original)
    spec = json.loads((out / 'model_spec.json').read_text(encoding="utf-8"))
    identity = {'model_id': spec['model_id'], 'version': spec['version'], 'project_id': request['project_id'], 'revision': request['revision'], 'geometry_sha256': spec['geometry_sha256'], 'source_spec_hash': sha(request)}
    spec.update(identity)
    report.update(identity)
    label = f"{identity['model_id']} | v{identity['version']} | r{identity['revision']} | {identity['geometry_sha256'][:16]}"
    progress('Verify exported files')
    # Upstream guide page 1 overflows below the page. Reflow only that page;
    # retain the engine's fold-pair / seam index and exact printable geometry.
    from io import BytesIO
    from reportlab.pdfgen import canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(engine.PAGE_W*engine.PT, engine.PAGE_H*engine.PT))
    engine.pdf_text(c, 12, 266, 'PAPERCRAFT | FOLD-FIRST ASSEMBLY', 12, True)
    engine.pdf_text(c, 12, 254, spec['geometry']['model']['name'] + ' / v1.2', 9)
    summary = report['summary']
    facts = [f"{paper_name} pages: {summary['sheets']}", f"Faces / tiles: {summary['faces_or_tiles']}",
             f"Physical cut pieces: {summary['cut_pieces']}", f"90-degree continuous folds: {summary['fold_hinges']}",
             f"Flat uncut joins: {summary['flat_continuous_joins']}", f"Glued seams: {summary['glue_seams']}",
             'Paper: cardstock 160-250 gsm (test first)']
    for i, text in enumerate(facts):
        engine.pdf_text(c, 15, 237-i*9, text, 9)
    engine.pdf_text(c, 12, 164, 'ASSEMBLY ORDER', 10, True)
    steps = ['1. Print all pages at Actual Size / 100%, never Fit to Page.',
             '2. Measure the 40 mm calibration line on EACH page.',
             '3. Cut only the BLACK perimeter; keep the pale glue tabs.',
             '4. Pre-crease PURPLE hinges to 90 degrees; flat joins stay flat.',
             '5. Fold dashed TAB bases; glue only matching non-hinge codes.',
             '6. Join flat F seams to assemble complete faces first.',
             '7. Close remaining E/H seams using paired labels.',
             '8. Dry-fit before gluing; check dimensions after assembly.']
    for i, text in enumerate(steps):
        engine.pdf_text(c, 15, 151-i*10, text, 8)
    engine.pdf_text(c, 12, 65, 'LEGEND', 10, True)
    legends = [('CUT boundary', engine.CUT, None), ('UNCUT 90-degree hinge', engine.HINGE, [4, 2]),
               ('GLUE TAB - corner', engine.CORNER, [3, 2]), ('GLUE TAB - flat join', engine.FLAT, [3, 2])]
    for i, (title, color, dash) in enumerate(legends):
        y = 54-i*9
        engine.pdf_line(c, (16, y), (43, y), color, .9, dash)
        engine.pdf_text(c, 50, y-1, title, 8)
    engine.pdf_text(c, 12, 14, 'Physical assembly: NOT_TESTED. Geometry checks do not replace a paper trial.', 7)
    c.save()
    guide_path = out / 'assembly_guide.pdf'
    with fitz.open(stream=buffer.getvalue(), filetype='pdf') as replacement, fitz.open(guide_path) as original:
        replacement.insert_pdf(original, from_page=1)
        repaired = guide_path.with_suffix('.reflow.pdf')
        replacement.save(repaired)
    repaired.replace(guide_path)
    # Metadata and footer occupy reserved margin; no changes to geometry or scale.
    for path in out.glob('*.pdf'):
        with fitz.open(path) as doc:
            doc.set_metadata({**doc.metadata, 'subject': json.dumps(identity), 'keywords': identity['source_spec_hash']})
            if path.name == 'assembly_guide.pdf':
                page = doc.new_page(width=engine.PAGE_W * engine.PT, height=engine.PAGE_H * engine.PT)
                page.insert_text((30, 40), '3D MODEL / NOT A CUT TEMPLATE', fontsize=12)
                page.insert_image(fitz.Rect(30, 60, 580, 570), filename=str(out / 'model_3d_preview.png'))
                page.insert_text((30, 600), 'Physical assembly: NOT_TESTED', fontsize=10)
            for index, page in enumerate(doc):
                footer_y = 14.5 if path.name == 'printable_us_letter.pdf' else 9
                page.insert_text((8 * engine.PT, page.rect.height - footer_y * engine.PT), f'{label} | Page {index+1}/{len(doc)}', fontsize=5)
            temp = path.with_suffix('.tmp.pdf')
            doc.save(temp)
        temp.replace(path)
    for path in sorted((out / 'svg_pages').glob('*.svg')):
        tree = ET.parse(path)
        root = tree.getroot()
        ET.SubElement(root, '{http://www.w3.org/2000/svg}metadata').text = json.dumps(identity)
        engine.svg_label(root, 108, 14.5, label, 1.8)
        tree.write(path, encoding='utf-8', xml_declaration=True)
    if (out / 'model.obj').exists():
        path = out / 'model.obj'
        path.write_text('# ' + json.dumps(identity) + '\n' + path.read_text(encoding="utf-8"), encoding="utf-8")
    # Regenerate printable preview after final PDF stamping.
    engine.contact_sheet(out / 'printable_us_letter.pdf', out / 'printable_preview.png', spec['model_id'])
    for path in out.glob('*.png'):
        with Image.open(path) as im:
            info = PngImagePlugin.PngInfo()
            info.add_text('provenance', json.dumps(identity))
            im.save(path, pnginfo=info)
    report['tests'] = engine.verify(*captured['verify_args']) + [t for t in report['tests'] if t['name'].startswith('cube_mesh')]
    def check(name, ok, detail):
        report['tests'].append({'name': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})
    words = Counter()
    clipped = []
    with fitz.open(out / 'printable_us_letter.pdf') as doc:
        for i, page in enumerate(doc):
            for word in page.get_text('words'):
                words[word[4]] += 1
                if not (word[0] >= 7.8 * engine.PT and word[2] <= (engine.PAGE_W-7.8)*engine.PT and word[1] >= 7.8 * engine.PT and word[3] <= page.rect.height-7.8*engine.PT):
                    clipped.append([i+1, word[4]])
    check('pdf_seam_labels_exactly_twice', all(words[s['id']] == 2 for s in spec['geometry']['seams']), 'Reopened PDF seam labels')
    check('pdf_text_within_page_margins', not clipped, clipped)
    with fitz.open(out / 'assembly_guide.pdf') as guide:
        guide_clipped = [(i+1, w[4]) for i, p in enumerate(guide) for w in p.get_text('words')
                         if w[0] < 0 or w[1] < 0 or w[2] > p.rect.width or w[3] > p.rect.height]
        guide_text = guide[0].get_text()
    check('guide_text_bounds_and_complete_legend', not guide_clipped and all(title in guide_text for title, _, _ in legends), guide_clipped or 'All four legend entries present within page')
    cal = []
    for path in sorted((out / 'svg_pages').glob('*.svg')):
        root = ET.parse(path).getroot()
        cal.append(any(n.tag.endswith('line') and abs(abs(float(n.get('x2','0'))-float(n.get('x1','0')))-40)<.001 and n.get('y1')==n.get('y2') for n in root))
    check('svg_40mm_calibration', all(cal), cal)
    jsonschema.validate(spec, json.loads((ROOT / 'papercraft-v1.2/model_spec.schema.json').read_text(encoding="utf-8")))
    check('model_spec_schema', True, 'Upstream schema 1.2.0')
    report['overall_status'] = 'PASS' if all(t['status']=='PASS' for t in report['tests']) else 'FAIL'
    for filename, value in [('model_spec.json', spec), ('validation_report.json', report)]:
        (out / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    if report['overall_status'] != 'PASS' or not independent_verify(out):
        raise RuntimeError('Export QA failed; artifacts are not certified')
    if paper_name == 'A4':
        (out / 'printable_us_letter.pdf').rename(out / printable_filename(paper_name))
    manifest = {**identity, 'input': request, 'algorithm': 'papercraft-v1.2 paired fold-first + shelf packing (heuristic)', 'qa_status': report['overall_status'], 'physical_assembly': 'NOT_TESTED', 'artifacts': []}
    for path in sorted(out.rglob('*')):
        if path.is_file():
            manifest['artifacts'].append({'path': path.relative_to(out).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **identity})
    (out / 'generation_manifest.json').write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    from .project_archive import create_download_archive
    create_download_archive(out)
    progress('Complete')
    return report


if __name__ == '__main__':
    request_path, output_path, progress_path = map(Path, sys.argv[1:])
    def progress(stage):
        temp = progress_path.with_suffix('.tmp')
        temp.write_text(json.dumps({'stage': stage}), encoding="utf-8")
        temp.replace(progress_path)
    generate(json.loads(request_path.read_text(encoding="utf-8")), output_path, progress)
