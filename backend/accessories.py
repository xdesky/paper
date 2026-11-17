"""Buildable display accessories; all dimensions and exports are in millimetres."""
import math
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from shapely.geometry import Polygon, box, LineString
from shapely.ops import unary_union


def poly(points,fill,stroke=None,width=0):return dict(type='polygon',points=list(points),fill=fill,stroke=stroke,width=width)
def line(points,color,width=.5):return dict(type='line',points=points,stroke=color,width=width)
def circle(x,y,r,color):return dict(type='circle',center=[x,y],radius=r,fill=color)


def base_art(t):
    from .confectionery import Painter,CREAM
    w,d=t['width']+60,t['depth']+70
    p=Painter(box(0,0,w,d));p.rect(0,0,w,d,'#dbe7ef');p.rect(1.5,1.5,w-3,d-3,'#fffaf2')
    # Printed snow drifts and stepping stones; the base cut rectangle is unchanged.
    for y in range(5,35,6):
        centers=[w/2]
        if t.get('bay_count',1) > 1:
            edges=[0]+(t.get('bay_splits') or [t['bay_split']])+[1]
            centers=[30+t['width']*(a+b)/2 for a,b in zip(edges,edges[1:])]
        for cx in centers:
            pts=[(cx+7*math.cos(i*math.tau/32),y+2.4*math.sin(i*math.tau/32)) for i in range(33)]
            p.polygon([(x+.4,yy-.5) for x,yy in pts],'#ccb4a6');p.polygon(pts,'#be8964')
            for dx,dy in [(-3,.5),(1,-.5),(3,.8)]:p.circle(cx+dx,y+dy,.35,'#99623e')
    for x in range(7,int(w)-5,9):
        for y in (3,d-3):
            p.circle(x+.3,y-.3,3.6,'#dce6ef');p.circle(x,y+.3,3.4,'#ffffff')
    for y in range(10,int(d)-5,10):
        for x in (3,w-3):p.circle(x+.2,y-.3,3,'#dce6ef');p.circle(x,y+.2,2.8,'#ffffff')
    for x,y in [(13,13),(w-13,13),(13,d-13),(w-13,d-13)]:p.shrub(x,y,4.5)
    p.line([(30,35),(30+t['width'],35),(30+t['width'],35+t['depth']),(30,35+t['depth']),(30,35)],'#d6dcd6',.25)
    return p.shapes


def tree_piece(slot_top,style='classic'):
    outline=[(12,0),(20,0),(20,6),(32,6),(24,21),(29,21),(21,36),(25,36),(18,51),(22,51),(16,65),(10,51),(14,51),(7,36),(11,36),(3,21),(8,21),(0,6),(12,6)]
    shape=Polygon(outline)
    if style=='slim':
        outline=[(12,0),(20,0),(20,6),(27,6),(21,24),(24,24),(19,43),(21,43),(16,65),(11,43),(13,43),(8,24),(11,24),(5,6),(12,6)]
        shape=Polygon(outline)
    elif style=='rounded':
        from shapely.geometry import Point
        shape=unary_union([box(12,0,20,9),Point(16,20).buffer(14,resolution=12),Point(16,36).buffer(11,resolution=12),Point(16,51).buffer(8,resolution=12),Polygon([(11,54),(21,54),(16,65)])])
    elif style=='tiered':
        shape=Polygon([(12,0),(20,0),(20,6),(32,6),(23,17),(29,17),(22,29),(26,29),(20,42),(23,42),(16,65),(9,42),(12,42),(6,29),(10,29),(3,17),(9,17),(0,6),(12,6)])
    elif style=='star':
        shape=unary_union([box(12,0,20,9),Polygon([(1,6),(31,6),(16,58)]),Polygon([(16,65),(18,59),(24,59),(19,55),(21,49),(16,53),(11,49),(13,55),(8,59),(14,59)])])
    elif style=='candy':
        shape=Polygon([(12,0),(20,0),(20,6),(31,6),(26,15),(29,18),(22,29),(25,32),(19,46),(21,49),(16,65),(11,49),(13,46),(7,32),(10,29),(3,18),(6,15),(1,6),(12,6)])
    # 0.6 mm slot suits two layers of typical cardstock; glue if loose.
    return shape.difference(box(15.7,32.5 if slot_top else -1,16.3,66 if slot_top else 32.5))


def tree_art(shape,style='classic'):
    from .confectionery import tree_art as paint_tree
    return paint_tree(shape,style)


def gift_net(size,prefix,color,style='classic'):
    from .gingerbread import base
    s=size
    positions={'FRONT':(s,s),'RIGHT':(2*s,s),'BACK':(3*s,s),'LEFT':(0,s),'TOP':(s,2*s),'BOTTOM':(s,0)}
    maps={'FRONT':lambda u,v:(u-s/2,-s/2,v),'RIGHT':lambda u,v:(s/2,u-s/2,v),'BACK':lambda u,v:(s/2-u,s/2,v),'LEFT':lambda u,v:(-s/2,s/2-u,v),'TOP':lambda u,v:(u-s/2,v-s/2,s),'BOTTOM':lambda u,v:(u-s/2,s/2-v,0)}
    pts=[(0,0),(s,0),(s,s),(0,s)]
    faces={pid:box(x,y,x+s,y+s) for pid,(x,y) in positions.items()}
    occurrences=defaultdict(list)
    for pid,fn in maps.items():
        for i,a in enumerate(pts):
            b=pts[(i+1)%4];key=tuple(sorted((fn(*a),fn(*b))))
            x,y=positions[pid]
            occurrences[key].append((pid,[(a[0]+x,a[1]+y),(b[0]+x,b[1]+y)]))
    net=unary_union(list(faces.values()));folds=[];tabs=[];labels=[];seams=[];art=[]
    for mates in occurrences.values():
        assert len(mates)==2
        a,b=mates
        if LineString(a[1]).equals(LineString(b[1])):
            folds.append(a[1]);continue
        code=prefix+str(len(seams)+1);seams.append(dict(code=code,mates=mates))
        for pid,segment in mates:
            tab=base.base.flap_for_edge(*segment,depth=3)
            if tab.intersection(net).area<1e-6:
                tabs.append(tab);net=net.union(tab);folds.append(segment)
                labels.append((code,tab.centroid.x,tab.centroid.y));break
        else:raise ValueError('Gift tab collision')
    for pid,shape in faces.items():
        x,y=positions[pid]
        from .confectionery import gift_art
        for art_shape in gift_art(s,color,pid=='TOP',style):
            if art_shape['type']=='circle':art_shape['center']=[art_shape['center'][0]+x,art_shape['center'][1]+y]
            else:art_shape['points']=[(a+x,b+y) for a,b in art_shape['points']]
            if 'rings' in art_shape:art_shape['rings']=[[(a+x,b+y) for a,b in ring] for ring in art_shape['rings']]
            art.append(art_shape)
    art.extend(poly(tab.exterior.coords,'#fff1d3') for tab in tabs)
    return dict(id=prefix,shape=net,art=art,folds=folds,labels=labels,tabs=tabs,seams=seams,faces=faces,size=s,color=color,maps=maps)


def layout(t):
    bw,bd=t['width']+60,t['depth']+70
    base_piece=dict(id='BASE',shape=box(0,0,bw,bd),art=base_art(t),folds=[],labels=[])
    trees=[dict(id=f'TREE_{i+1}',shape=tree_piece(i==0,t.get('design',{}).get('tree','classic')),art=tree_art(tree_piece(i==0,t.get('design',{}).get('tree','classic')),t.get('design',{}).get('tree','classic')),folds=[],labels=[]) for i in range(2)]
    gifts=[gift_net(20,'A','#bb3f58',t.get('design',{}).get('gift','classic')),gift_net(16,'B','#397f76',t.get('design',{}).get('gift','classic'))]
    from .chimney import layout as chimney_layout
    from .roof_cap import layout as cap_layout
    return [[(base_piece,18,35)],[(trees[0],22,158),(trees[1],72,158),(gifts[0],18,55),(gifts[1],116,55)]]+cap_layout(t)+chimney_layout(t)


def scene(t):
    """Assembled positions match the printable parts, with 1:1 UV coordinates."""
    from .gingerbread import svg_art
    panels=[];art={};artwork={}
    def add(pid,pts,vertices,shapes):
        bounds=Polygon(pts).bounds;ww,hh=bounds[2],bounds[3]
        panels.append(dict(id=pid,face=pid,polygon_mm=pts,vertices_3d_mm=vertices,width_mm=ww,height_mm=hh))
        art[pid]=svg_art(shapes,ww,hh);artwork[pid]=shapes
    bw,bd=t['width']+60,t['depth']+70
    pts=[(0,0),(bw,0),(bw,bd),(0,bd)]
    add('DISPLAY_BASE',pts,[(x-bw/2,y-bd/2,-.4) for x,y in pts],base_art(t))
    tx,ty=-t['width']/2-12,-t['depth']/2-16
    for i in range(2):
        shape=tree_piece(i==0,t.get('design',{}).get('tree','classic'));pts=list(shape.exterior.coords)[:-1]
        xyz=[(tx+x-16,ty,z) if i==0 else (tx,ty+x-16,z) for x,z in pts]
        add(f'TREE_{i+1}',pts,xyz,tree_art(shape,t.get('design',{}).get('tree','classic')))
    for k,(size,color,cy) in enumerate([(20,'#bb3f58',-t['depth']/2-14),(16,'#397f76',-t['depth']/2+8)]):
        net=gift_net(size,chr(65+k),color);cx=t['width']/2+13
        pts=[(0,0),(size,0),(size,size),(0,size)]
        for face,fn in net['maps'].items():
            verts=[(fn(x,y)[0]+cx,fn(x,y)[1]+cy,fn(x,y)[2]) for x,y in pts]
            from .confectionery import gift_art
            shapes=gift_art(size,color,face=='TOP',t.get('design',{}).get('gift','classic'))
            add(f'GIFT_{k+1}_{face}',pts,verts,shapes)
    from .roof_cap import build,artwork as cap_art
    caps,_,_,_=build(t)
    for pid,p in caps.items():add(pid,p.points,p.vertices,cap_art(t,p))
    from .chimney import geometry as chimney_geometry,artwork as chimney_art
    chimney=chimney_geometry(t)
    if chimney:
        for p in chimney['panels']:add(p['id'],p['points'],p['vertices'],chimney_art(p))
    return dict(panels=panels,appearance=art,artwork=artwork,base_mm=[bw,bd],tree_height_mm=65,gift_sizes_mm=[20,16])


def export(t,out,identity,first_page):
    """Return accessory QA; append two pages to the main PDF/SVG and guide."""
    import pymupdf as fitz
    from reportlab.pdfgen import canvas
    from .gingerbread import base,draw_shapes,NS,canonical,CUT,FOLD
    from .paper import printable_filename
    pages=layout(t);checks=[]
    pdf=out/'accessories.pdf';c=canvas.Canvas(str(pdf),pagesize=(base.PAGE_W*base.PT,base.PAGE_H*base.PT),invariant=1)
    c.setSubject(canonical(identity))
    def txt(root,x,y,text,size=7):
        base.pdf_text(c,x,y,text,size,center=True)
        base.svg_label(root,x,y,text,size/base.PT)
    for index,pieces in enumerate(pages):
        root=ET.Element('{'+NS+'}svg',width=f'{base.PAGE_W}mm',height=f'{base.PAGE_H}mm',viewBox=f'0 0 {base.PAGE_W} {base.PAGE_H}')
        ET.SubElement(root,'{'+NS+'}metadata').text=canonical(identity)
        txt(root,base.PAGE_W/2,base.PAGE_H-13,'ĐẾ TUYẾT' if index==0 else 'CÂY THÔNG & HỘP QUÀ' if index==1 else 'ỐNG KHÓI 3D' if pieces[0][0]['id']=='CHIMNEY' else 'MÁI ĐUA PHỦ TUYẾT',11)
        txt(root,base.PAGE_W/2,base.PAGE_H-20,'Cắt nét đen · Gấp nét tím · In 100% · Phụ kiện '+str(index+1)+'/'+str(len(pages)))
        translated=[]
        for piece,x,y in pieces:
            transform=lambda q:(q[0]+x,q[1]+y)
            shape=Polygon([transform(q) for q in piece['shape'].exterior.coords]);translated.append(shape)
            draw_shapes(c,None,piece['art'],transform)
            draw_shapes(None,root,piece['art'],lambda q:(q[0]+x,base.PAGE_H-q[1]-y),1)
            base.pdf_shape(c,shape,stroke=CUT,stroke_width=.65);base.svg_polygon(root,shape,'none',CUT,.23)
            for a,b in piece['folds']:
                base.pdf_line(c,transform(a),transform(b),FOLD,.9,[4,2]);base.svg_segment(root,transform(a),transform(b),FOLD,[1.5,.8],.35)
            for label,lx,ly in piece['labels']:txt(root,lx+x,ly+y-.4,label,4)
            checks.append((piece['id']+'_valid_cut',shape.is_valid and shape.geom_type=='Polygon' and not shape.interiors))
            checks.append((piece['id']+'_bounds',box(8,20,base.PAGE_W-8,base.PAGE_H-24.4).buffer(1e-6).covers(shape)))
        checks.append((f'accessory_page_{index+1}_no_overlap',all(a.intersection(b).area<1e-7 for i,a in enumerate(translated) for b in translated[i+1:])))
        if index==0:
            txt(root,base.PAGE_W/2,25,'Cắt đế, dán lên bìa cứng. Đặt nhà trên khung mờ ở giữa.')
        elif index==1:
            txt(root,base.PAGE_W/2,140,'Ghép 2 cây theo khe giữa; mở vuông góc để cây tự đứng.')
            txt(root,base.PAGE_W/2,35,'Quà A: 20 mm · Quà B: 16 mm · Tra mã ghép trong hướng dẫn.')
        base.pdf_line(c,(15,10.5),(55,10.5),CUT,.8);base.svg_segment(root,(15,10.5),(55,10.5),CUT,width=.25)
        txt(root,126,10,'40 mm | Actual Size / 100% - NO Fit to Page')
        ET.ElementTree(root).write(out/f'svg_pages/page_{first_page+index+1:03d}.svg',encoding='utf-8',xml_declaration=True)
        c.showPage()
    c.save()
    # Independent exported-page dimensions, ruler and text boundary checks.
    with fitz.open(pdf) as doc:
        checks.append(('accessory_pdf_dimensions',len(doc)==len(pages) and all(abs(p.rect.width/base.PT-base.PAGE_W)<.001 and abs(p.rect.height/base.PT-base.PAGE_H)<.001 for p in doc)))
        checks.append(('accessory_pdf_text_bounds',all(w[0]>7*base.PT and w[2]<(base.PAGE_W-7)*base.PT and w[1]>7*base.PT and w[3]<(base.PAGE_H-7)*base.PT for p in doc for w in p.get_text('words'))))
        checks.append(('accessory_pdf_rulers',all(any(item[0]=='l' and abs(abs(item[2].x-item[1].x)/base.PT-40)<.005 for d in p.get_drawings() for item in d['items']) for p in doc)))
        from shapely.affinity import translate
        for index,page in enumerate(doc):
            cuts=[]
            for drawing in page.get_drawings():
                if not drawing.get('color') or math.dist(drawing['color'],(22/255,37/255,46/255))>.02 or abs(drawing.get('width',0)-.65)>.03:continue
                points=[]
                for item in drawing['items']:
                    if item[0]=='l':points.append(item[1])
                    elif item[0]=='qu':points.extend([item[1].ul,item[1].ur,item[1].lr,item[1].ll])
                    elif item[0]=='re':points.extend([item[1].tl,item[1].tr,item[1].br,item[1].bl])
                if points:cuts.append(Polygon([(q.x/base.PT,base.PAGE_H-q.y/base.PT) for q in points]))
            targets=[translate(piece['shape'],xoff=x,yoff=y) for piece,x,y in pages[index]]
            checks.append((f'accessory_pdf_{index+1}_cuts_match',len(cuts)==len(targets) and all(cut.is_valid and min(cut.symmetric_difference(target).area for target in targets)<.05 for cut in cuts)))
            code_tabs={code:translate(tab,xoff=x,yoff=y) for piece,x,y in pages[index] for (code,_,_),tab in zip(piece['labels'],piece.get('tabs',[]))}
            words=page.get_text('words');counts={code:0 for code in code_tabs};codes_inside=True
            for word in words:
                if word[4] in code_tabs:
                    counts[word[4]]+=1
                    bounds=box(word[0]/base.PT,base.PAGE_H-word[3]/base.PT,word[2]/base.PT,base.PAGE_H-word[1]/base.PT)
                    codes_inside &= code_tabs[word[4]].buffer(.02).covers(bounds)
            checks.append((f'accessory_pdf_{index+1}_hidden_codes',codes_inside and all(n==1 for n in counts.values())))

    for piece,_,_ in pages[1]:
        if 'seams' in piece:
            checks.append((piece['id']+'_cube_topology',len(piece['seams'])==7 and len(piece['faces'])==6 and len(piece['folds'])==12))
    # The assembly reference labels both mates; visible surfaces stay code-free.
    gp=out/'accessories_guide.pdf';g=canvas.Canvas(str(gp),pagesize=(base.PAGE_W*base.PT,base.PAGE_H*base.PT),invariant=1)
    def gt(x,y,text,size=9):base.pdf_text(g,x,y,text,size)
    gt(12,base.PAGE_H-15,'LẮP ĐẾ, CÂY THÔNG VÀ HỘP QUÀ',13)
    instructions=['1. In đúng khổ giấy, tỷ lệ 100%; đo vạch 40 mm.',
      '2. Cắt đế tuyết; dán lên bìa cứng phẳng để đế không cong.',
      '3. Đặt nhà trên khung mờ; cố định từ mặt trong bằng băng dính.',
      '4. Cắt 2 cây theo viền đen, gồm khe giữa rộng 0.6 mm.',
      '5. Luồn khe trên vào khe dưới, xoay hai mảnh vuông góc.',
      '   Khe dành cho giấy 160–220 gsm; chấm keo nếu khe bị lỏng.',
      '6. Cắt hai lưới hộp quà, giữ tai dán; miết tất cả nét tím.',
      '7. Dán mã A với A, B với B theo sơ đồ; đóng nắp sau cùng.',
      '8. Đặt cây bên trái, quà bên phải; cố định vào đế nếu cần.',
      'Cây in một mặt; có thể tô xanh mặt sau trước khi lắp.',
      'Phụ kiện chưa được thử lắp giấy thật.']
    for i,text in enumerate(instructions):gt(12,base.PAGE_H-30-i*10,text,8)
    gt(12,130,'SƠ ĐỒ MÃ HỘP QUÀ — KHÔNG DÙNG LÀM MẪU CẮT',9)
    for piece,x,y in pages[1][2:]:
        x,y=x,40
        from shapely.affinity import translate
        base.pdf_shape(g,translate(piece['shape'],xoff=x,yoff=y),stroke=CUT,stroke_width=.5)
        for seam in piece['seams']:
            for pid,(a,b) in seam['mates']:
                midpoint=((a[0]+b[0])/2,(a[1]+b[1])/2)
                center=piece['faces'][pid].centroid;dx,dy=center.x-midpoint[0],center.y-midpoint[1];length=math.hypot(dx,dy)
                gt(x+midpoint[0]+dx/length*3-1.5,y+midpoint[1]+dy/length*3,seam['code'],5)
    if len(pages)>2:
        g.showPage()
        gt(12,base.PAGE_H-15,'LẮP MÁI ĐUA PHỦ TUYẾT',13)
        notes=['1. Lắp tường và mái khung như hướng dẫn nhà trước đó.',
               '2. Cắt lớp mái phủ; gấp nét tím, mặt trang trí hướng ra ngoài.',
               '3. Nếu mái nhiều mảnh: ghép mã R theo sơ đồ ở trang sau.',
               '4. Đặt thử lên mái khung, căn trùng sống mái và các nếp gãy.',
               '5. Căn mép trước/sau đua đều 6 mm; mép ngoài dài thêm 4 mm theo dốc.',
               '6. Bôi keo mỏng lên mái KHUNG rồi đặt mái phủ; không bôi lên mép đua.',
               '7. Giữ nhẹ đến khi keo khô. Không kéo mép đua dính vào tường.',
               'Lớp mái phủ là một bộ phận thật, không thay đổi khung tường hoặc đế.',
               'Khe 0.4 mm trong 3D minh họa độ dày giấy/keo; ướm thử trước khi dán.',
               'Chưa thử lắp giấy thật; dùng cardstock để mép mái không bị võng.']
        if t.get('bay_count',1) > 1:
            notes[3]='4. Các đỉnh mái LỒI, mối nối giữa các gian LÕM; ướm theo mái khung.'
        for i,text in enumerate(notes):gt(12,base.PAGE_H-32-i*12,text,8)
        for page in pages[2:]:
            chimney_page=page[0][0]['id']=='CHIMNEY'
            g.showPage();gt(12,base.PAGE_H-14,'LẮP ỐNG KHÓI — SƠ ĐỒ THAM KHẢO' if chimney_page else 'SƠ ĐỒ MÁI PHỦ — KHÔNG DÙNG LÀM MẪU CẮT',10)
            if chimney_page:
                for i,line in enumerate(['Gấp 3 cạnh đứng; dán mép cùng mã để khép ống, miệng trên để mở.', 'Gấp 4 tai chân vào trong. Chân vát phải khớp độ dốc mái.', 'Đặt lên khung định vị in trên mặt mái đã chọn, gần phía sau nhà.', 'Ướm thử, bôi keo vào tai chân rồi dán lên mái phủ. Không khoét mái.']):
                    gt(12,base.PAGE_H-30-i*10,line,8)
            for piece,x,y in page:
                from shapely.affinity import translate
                base.pdf_shape(g,translate(piece['shape'],xoff=x,yoff=y),stroke=CUT,stroke_width=.5)
                for a,b in piece['folds']:base.pdf_line(g,(a[0]+x,a[1]+y),(b[0]+x,b[1]+y),FOLD,.6,[3,2])
                for code,cx,cy in piece['guide']:gt(cx+x-1.5,cy+y,code,6)
    g.save()
    with fitz.open(gp) as guide:
        text=' '.join(p.get_text() for p in guide)
        from .roof_cap import build as build_cap
        checks.append(('roof_cap_guide_both_mates',all(text.split().count(s['id'])==2 for s in build_cap(t)[1])))
        if t.get('chimney'):checks.append(('chimney_guide_both_mates',text.split().count('C1')==2))
        checks.append(('gift_guide_both_mates',all(text.split().count(chr(65+k)+str(i))==2 for k in range(2) for i in range(1,8))))
        checks.append(('accessory_guide_text_bounds',all(w[0]>=0 and w[1]>=0 and w[2]<=p.rect.width and w[3]<=p.rect.height for p in guide for w in p.get_text('words'))))
    def append(target,extra):
        with fitz.open(target) as dest,fitz.open(extra) as src:
            dest.insert_pdf(src);temp=target.with_suffix('.merged.pdf');dest.save(temp)
        temp.replace(target)
    append(out/printable_filename(base.PAPER_NAME),pdf)
    append(out/'assembly_guide.pdf',gp)
    from .roof_cap import validate as validate_cap
    from .chimney import validate as validate_chimney
    return [dict(name=name,status='PASS' if ok else 'FAIL',detail='Accessories: actual-size cut/fold parts') for name,ok in checks]+validate_cap(t)+validate_chimney(t)
