"""A second ink layer on the same printable layout; never scale or re-pack."""
from contextvars import ContextVar
import copy
import xml.etree.ElementTree as ET

COLORING = ContextVar('coloring_artwork', default=False)


def export(t,out,identity,panels,units,pages):
    import pymupdf as fitz
    from .gingerbread import decorations,draw_shapes,draw_placed_art,base,NS
    from .accessories import layout
    from .paper import printable_filename
    folder=out/'coloring_svg_pages';folder.mkdir(exist_ok=True)
    token=COLORING.set(True)
    try:
        replacements=[]
        accessory_pages=layout(t)
        mixed=any(page.get('accessories') for page in pages)
        pieces_by_id={p['id']:p for page in accessory_pages for p,_,_ in page}
        for page in pages:
            groups=ET.Element('art')
            for unit in page['units']:
                for pid in unit.ids:
                    transform=lambda q,pid=pid,u=unit:(u.transform(pid,q)[0],base.PAGE_H-u.transform(pid,q)[1])
                    draw_shapes(None,groups,decorations(t,panels[pid]),transform,1)
                    for tab in panels[pid].tabs.values():
                        draw_shapes(None,groups,[dict(type='polygon',points=list(tab.exterior.coords),fill='#fff1d3')],transform,1)
            for piece,placement in page.get('accessories',[]):
                draw_placed_art(None,groups,pieces_by_id[piece['id']],placement,clip=False)
            replacements.append(list(groups))
        for pieces in ([] if mixed else accessory_pages):
            groups=ET.Element('art')
            for piece,x,y in pieces:
                draw_shapes(None,groups,piece['art'],lambda q,x=x,y=y:(q[0]+x,base.PAGE_H-q[1]-y),1)
            replacements.append(list(groups))
    finally:
        COLORING.reset(token)
    originals=sorted((out/'svg_pages').glob('*.svg'))
    assert len(originals)==len(replacements)
    checks=[];doc=fitz.open()
    for source,new_groups in zip(originals,replacements):
        root=ET.parse(source).getroot()
        old_groups=[n for n in root if n.get('data-artwork')=='true']
        assert len(old_groups)==len(new_groups),(source,len(old_groups),len(new_groups))
        for old,new in zip(old_groups,new_groups):
            index=list(root).index(old);root.remove(old);root.insert(index,new)
        # Geometry, dash patterns, label positions and ruler are retained verbatim.
        for node in root.iter():
            fill=node.get('fill');stroke=node.get('stroke')
            if fill:node.set('data-original-fill',fill)
            if stroke:node.set('data-original-stroke',stroke)
            if fill and fill!='none':
                node.set('fill','#ffffff' if fill.lower() in ('#ffffff','#fff1d3') else '#222222')
            if stroke and stroke!='none':node.set('stroke','#222222')
        original=ET.parse(source).getroot()
        def construction(tree):
            return [(n.tag,tuple(sorted((k,v) for k,v in n.attrib.items() if k not in ('fill','stroke','data-original-fill','data-original-stroke'))),n.text) for n in tree if n.get('data-artwork')!='true']
        checks.append(dict(name='coloring_layout_'+source.stem,status='PASS' if construction(root)==construction(original) else 'FAIL',detail='Identical cut/fold paths, codes, page size and 40 mm ruler'))
        for node in root.iter():
            if node.text:node.text=node.text.replace('FOLD purple','FOLD dashed').replace('Fold dashed lines','Fold dashed lines')
        root.set('data-print-style','coloring')
        data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        (folder/source.name).write_bytes(data)
        with fitz.open(stream=data,filetype='svg') as svg:
            with fitz.open(stream=svg.convert_to_pdf(),filetype='pdf') as page:doc.insert_pdf(page)
    filename=printable_filename(base.PAPER_NAME).replace('.pdf','_coloring.pdf')
    doc.set_metadata({'title':t['name']+' — Coloring pages','subject':'Same physical layout; black outlines on white paper'})
    doc.save(out/filename,garbage=4,deflate=True)
    expected=(base.PAGE_W*base.PT,base.PAGE_H*base.PT)
    ok=len(doc)==len(originals) and all(abs(p.rect.width-expected[0])<.02 and abs(p.rect.height-expected[1])<.02 for p in doc)
    checks.append(dict(name='coloring_pdf_page_size',status='PASS' if ok else 'FAIL',detail=f'{len(doc)} pages; {base.PAPER_NAME}; 100% scale'))
    doc.close()
    return checks
