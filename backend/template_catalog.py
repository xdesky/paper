"""Versioned, local catalog of printable Christmas houses."""
CATALOG_VERSION = '4.0.0'
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
for template in TEMPLATES:
    template.update(roof_overhang_mm=4,roof_rake_mm=6)
BY_ID = {t['id']: t for t in TEMPLATES}


def public_template(t):
    return {**t, 'version': CATALOG_VERSION, 'dimensions_mm': [t['width'], t['depth'], t['wall_height'] + t['roof_rise']],
            'paper': 'US Letter', 'accessories': ['Mái đua phủ tuyết', 'Đế tuyết', 'Cây thông ghép chéo', '2 hộp quà 3D'], 'physical_assembly': 'NOT_TESTED',
            'construction': 'Nhà đáy mở, mái phủ hai lớp đua 6 mm trước/sau và 4 mm theo dốc bên ngoài. Cửa, cửa sổ, phào và vật liệu là họa tiết in. Không có hiên, ống khói hoặc nội thất rời.',
            'preview_url': f"/api/templates/{t['id']}/preview.svg"}
