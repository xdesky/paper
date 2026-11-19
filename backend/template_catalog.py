"""Versioned, local catalog of printable Christmas houses."""
CATALOG_VERSION = '5.0.0'
TEMPLATES = [
    dict(id='gb_classic', name='Ngôi nhà bánh gừng', subtitle='Noel cổ điển', collection='Truyền thống', width=90, depth=70, wall_height=85, roof_rise=45, wall='#b97946', roof='#8b4139', accent='#bf443d', trim='#fff5dc', background='#f4e8d7', motif='classic', difficulty='Dễ', description='Bánh gừng nâu ấm, mái đỏ và những đường kem trắng. Mẫu mở đầu cho một ngôi làng Noel trên bàn.'),
    dict(id='gb_candy', name='Tiệm kẹo Giáng sinh', subtitle='Candy Cane Lane', collection='Kẹo ngọt', width=100, depth=70, wall_height=85, roof_rise=42, wall='#d99478', roof='#d25762', accent='#bc3046', trim='#fff7e7', background='#f9e7e8', motif='candy', difficulty='Dễ', description='Mái hồng dâu, cửa viền kẹo gậy và ô cửa sáng vàng. Những viên kẹo được in trực tiếp trên mặt giấy.'),
    dict(id='gb_forest', name='Căn nhà rừng thông', subtitle='Evergreen Cottage', collection='Thiên nhiên', width=85, depth=65, wall_height=95, roof_rise=50, wall='#a7774f', roof='#356657', accent='#2a6851', trim='#fff7e7', background='#e5ede2', motif='forest', difficulty='Dễ', description='Mái xanh thông, vòng nguyệt quế và họa tiết cây thông. Phù hợp phối thành một góc rừng mùa đông.'),
    dict(id='gb_chalet', name='Chalet phủ tuyết', subtitle='Alpine Christmas', collection='Thiên nhiên', width=110, depth=70, wall_height=70, roof_rise=40, wall='#a56d47', roof='#63554b', accent='#9c403c', trim='#fff9ec', background='#eee9df', motif='chalet', difficulty='Dễ', description='Dáng nhà rộng, mái thấp và họa tiết gỗ với kem tuyết. Một ngôi nhà nhỏ để đặt cạnh cây thông.'),
    dict(id='gb_frost', name='Ngôi nhà băng đường', subtitle='Sugar & Snow', collection='Kẹo ngọt', width=75, depth=65, wall_height=115, roof_rise=37.5, wall='#b9cdd3', roof='#668da3', accent='#6f90a9', trim='#fffdf3', background='#e7eff3', motif='snow', difficulty='Dễ', description='Dáng nhà cao, xanh băng và bông tuyết bằng đường. Cửa và các chi tiết đều là họa tiết trang trí in màu.'),
    dict(id='gb_mini', name='Nhà bánh gừng mini', subtitle='Little Christmas Village', collection='Mini', width=60, depth=50, wall_height=60, roof_rise=30, wall='#c98d55', roof='#a94839', accent='#37816a', trim='#fff7e6', background='#f3ecdb', motif='mini', difficulty='Dễ', description='Một căn nhà nhỏ 60 × 50 × 90 mm cho kệ sách và tiểu cảnh Noel. Có thể tạo nhiều bản để dựng thành làng.'),
]
# Ten architectural silhouettes, two curated Christmas finishes each.
AMERICAN_MODELS = [
    ('cape_cod','Cape Cod',90,65,70,45,[(0,0),(.5,1),(1,0)],'shingle'),
    ('colonial','Colonial',85,65,105,30,[(0,0),(.5,1),(1,0)],'brick'),
    ('saltbox','New England Saltbox',95,65,65,55,[(0,0),(.72,1),(1,.42)],'siding'),
    ('dutch','Dutch Colonial',90,65,80,48,[(0,0),(.18,.72),(.5,1),(.82,.72),(1,0)],'shingle'),
    ('craftsman','Craftsman Bungalow',105,65,64,28,[(0,0),(.5,1),(1,0)],'timber'),
    ('farmhouse','American Farmhouse',78,72,105,48,[(0,0),(.5,1),(1,0)],'board'),
    ('ranch','Mid-century Ranch',115,60,58,20,[(0,0),(.5,1),(1,0)],'brick'),
    ('brownstone','Brooklyn Brownstone',65,65,135,8,[(0,1),(1,1)],'brick'),
    ('a_frame','Mountain A-frame',90,65,28,100,[(0,0),(.5,1),(1,0)],'timber'),
    ('modern','Modern Shed House',95,65,68,38,[(0,0),(1,1)],'board'),
]
FINISHES = [
 ('heritage','Heritage Christmas','#b97946','#943f4a','#bf394a','#fff7e5','#ebe9df'),
 ('midnight','Midnight & Gold','#344c60','#29313f','#bb8648','#f5e8c6','#e5e9ee'),
]
for model_id,title,w,d,h,r,profile,material in AMERICAN_MODELS:
    for finish,label,wall,roof,accent,trim,bg in FINISHES:
        TEMPLATES.append(dict(id=f'gb_us_{model_id}_{finish}',name=f'{title} · {label}',
            subtitle=f'{title} / {label}',collection='American Premium',model_family=model_id,
            architecture=title,finish=label,profile=[list(point) for point in profile],material=material,premium=True,
            width=w,depth=d,wall_height=h,roof_rise=r,wall=wall,roof=roof,accent=accent,
            trim=trim,background=bg,motif='american',difficulty='Trung bình',
            description=f'Nhà lấy cảm hứng từ {title}: mặt đứng {material}, cửa chia ô, vòng lá Noel và mái lợp chi tiết. Phiên bản {label}.'))
# Two connected bays: one continuous shell, two genuine roof peaks and a valley.
TWO_BAY_MODELS = [
    ('twins', 'Nhà 2 gian song đôi', 112, 52, 60, 36,
     [(0,0),(.25,1),(.5,0),(.75,1),(1,0)], .5, 'Twin Gable'),
    ('cottage', 'Nhà 2 gian cổ tích', 118, 54, 64, 40,
     [(0,0),(.29,1),(.58,0),(.79,.72),(1,0)], .58, 'Main & Side Cottage'),
    ('farmstead', 'Nông trại Noel 2 gian', 120, 56, 68, 38,
     [(0,0),(.24,1),(.48,0),(.74,.86),(1,0)], .48, 'Double Gable Farmhouse'),
]
for model_id,title,w,d,h,r,profile,split,architecture in TWO_BAY_MODELS:
    for finish,label,wall,roof,accent,trim,bg in FINISHES:
        TEMPLATES.append(dict(id=f'gb_two_{model_id}_{finish}',name=f'{title} · {label}',
            subtitle=f'{architecture} / {label}',collection='Nhà 2 gian',model_family=f'two_bay_{model_id}',
            architecture=architecture,finish=label,profile=[list(point) for point in profile],
            bay_split=split,bay_count=2,material='board',premium=True,
            width=w,depth=d,wall_height=h,roof_rise=r,wall=wall,roof=roof,accent=accent,
            trim=trim,background=bg,motif='american',difficulty='Trung bình',
            description=f'Hai gian liền nhau với hai chóp mái thật, cửa riêng và thung mái ở giữa. {label}: kem tuyết, kẹo Noel và cửa sổ sáng ấm. Chung thân nhà, không có vách ngăn bên trong.'))
COMPLEX_MODELS = [
    ('tower','Tháp kẹo mái gãy',80,60,108,42,
     [(0,0),(.14,.72),(.3,1),(.7,1),(.86,.72),(1,0)],[], 'Mansard Candy Tower'),
    ('manor','Biệt thự mái kép',118,54,65,40,
     [(0,0),(.09,.72),(.25,1),(.41,.72),(.5,0),(.59,.72),(.75,1),(.91,.72),(1,0)],[.5], 'Double Gambrel Manor'),
    ('village','Nhà 3 gian Giáng sinh',120,52,62,36,
     [(0,0),(1/6,.8),(1/3,0),(.5,1),(2/3,0),(5/6,.8),(1,0)],[1/3,2/3], 'Triple Gable Village'),
]
for model_id,title,w,d,h,r,profile,splits,architecture in COMPLEX_MODELS:
    for finish,label,wall,roof,accent,trim,bg in [
        ('rose','Rose Candy','#e5a7ae','#d36e88','#b92c52','#fff9ef','#f8e9ed'),
        ('mint','Peppermint Mint','#99c8b5','#579d87','#ce3045','#fff9ef','#e5f3ec')]:
        TEMPLATES.append(dict(id=f'gb_complex_{model_id}_{finish}',name=f'{title} · {label}',
            subtitle=f'{architecture} / {label}',collection='Noel nâng cao',model_family=f'complex_{model_id}',
            architecture=architecture,finish=label,profile=[list(point) for point in profile],
            bay_count=len(splits)+1,bay_splits=splits,**({'bay_split':splits[0]} if splits else {}),
            material='board',premium=True,width=w,depth=d,wall_height=h,roof_rise=r,
            wall=wall,roof=roof,accent=accent,trim=trim,background=bg,motif='american',difficulty='Nâng cao',
            description=f'{title}: {len(profile)-1} mặt mái thật, nhiều nếp gấp và mối ghép hơn. {label} với kem tuyết, kẹo và cửa vòm. Có bản màu và bản nét để tự tô; không có ống khói rời.'))
for template in TEMPLATES:
    template.update(roof_overhang_mm=4,roof_rake_mm=6)
    if template['id'] in ('gb_classic','gb_candy','gb_forest','gb_chalet','gb_frost','gb_mini') or template.get('model_family') in ('cape_cod','colonial','saltbox','dutch','craftsman','farmhouse','ranch'):
        # Tall/slender houses keep their silhouette free of a chimney.
        if template['wall_height'] < 95 and template['wall_height']+template['roof_rise'] <= 140:
            template.update(chimney=True,chimney_placement='longest_slope')
# US English catalog presentation; dimensions and IDs remain stable.
ENGLISH_NAMES = {
 'gb_classic':'Classic Gingerbread House','gb_candy':'Christmas Candy Shop',
 'gb_forest':'Evergreen Cottage','gb_chalet':'Snowy Alpine Chalet',
 'gb_frost':'Sugar & Snow House','gb_mini':'Mini Gingerbread Cottage',
}
FAMILY_NAMES={'twins':'Twin Gable Cottage','cottage':'Storybook Duo','farmstead':'Christmas Farmstead',
              'tower':'Candy Mansard Tower','manor':'Double Gambrel Manor','village':'Triple Gable Village'}
for t in TEMPLATES:
    t['name']=ENGLISH_NAMES.get(t['id'],t.get('architecture',t['name'])+' · '+t.get('finish',''))
    for prefix in ('gb_two_','gb_complex_'):
        if t['id'].startswith(prefix):t['name']=FAMILY_NAMES[t['id'][len(prefix):].rsplit('_',1)[0]]+' · '+t['finish']
    t['collection']={'Truyền thống':'Classics','Kẹo ngọt':'Candy Lane','Thiên nhiên':'Woodland','Nhà 2 gian':'Two-Bay Houses','Noel nâng cao':'Advanced Christmas'}.get(t['collection'],t['collection'])
    t['difficulty']={'Dễ':'Easy','Trung bình':'Intermediate','Nâng cao':'Advanced'}[t['difficulty']]
    if t['id']=='gb_classic':t['subtitle']='A Christmas Classic'
    t['description']=f"{t.get('architecture',t['name'])} with festive icing, candy details, and glowing windows. Includes a snowy base, a slotted tree, and two gift boxes. Customize the patterns and add your own name."
BY_ID = {t['id']: t for t in TEMPLATES}


def public_template(t):
    return {**t, 'version': CATALOG_VERSION, 'dimensions_mm': [t['width'], t['depth'], t['wall_height'] + t['roof_rise']],
            'paper': 'US Letter', 'accessories': ['Overhanging snowy roof', 'Snowy base', 'Slotted tree', 'Two 3D gift boxes']+(['3D chimney'] if t.get('chimney') else []), 'physical_assembly': 'NOT_TESTED',
            'construction': 'Open-bottom paper house with a separate snowy base. The two-layer roof extends 6 mm at the front and back and 4 mm along the outer slopes. Doors and windows are printed details. No interior rooms or separate porch.' + (' Includes an open-top 3D chimney with sloped glue tabs and its own print page.' if t.get('chimney') else ''),
            'preview_url': f"/api/templates/{t['id']}/preview.svg"}
