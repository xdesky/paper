"""Versioned, local catalog of printable Christmas houses."""
CATALOG_VERSION = '1.0.0'
TEMPLATES = [
    dict(id='gb_classic', name='Ngôi nhà bánh gừng', subtitle='Noel cổ điển', collection='Truyền thống', width=90, depth=70, wall_height=85, roof_rise=45, wall='#b97946', roof='#8b4139', accent='#bf443d', trim='#fff5dc', background='#f4e8d7', motif='classic', difficulty='Dễ', description='Bánh gừng nâu ấm, mái đỏ và những đường kem trắng. Mẫu mở đầu cho một ngôi làng Noel trên bàn.'),
    dict(id='gb_candy', name='Tiệm kẹo Giáng sinh', subtitle='Candy Cane Lane', collection='Kẹo ngọt', width=100, depth=70, wall_height=85, roof_rise=42, wall='#d99478', roof='#d25762', accent='#bc3046', trim='#fff7e7', background='#f9e7e8', motif='candy', difficulty='Dễ', description='Mái hồng dâu, cửa viền kẹo gậy và ô cửa sáng vàng. Những viên kẹo được in trực tiếp trên mặt giấy.'),
    dict(id='gb_forest', name='Căn nhà rừng thông', subtitle='Evergreen Cottage', collection='Thiên nhiên', width=85, depth=65, wall_height=95, roof_rise=50, wall='#a7774f', roof='#356657', accent='#2a6851', trim='#fff7e7', background='#e5ede2', motif='forest', difficulty='Dễ', description='Mái xanh thông, vòng nguyệt quế và họa tiết cây thông. Phù hợp phối thành một góc rừng mùa đông.'),
    dict(id='gb_chalet', name='Chalet phủ tuyết', subtitle='Alpine Christmas', collection='Thiên nhiên', width=110, depth=70, wall_height=70, roof_rise=40, wall='#a56d47', roof='#63554b', accent='#9c403c', trim='#fff9ec', background='#eee9df', motif='chalet', difficulty='Dễ', description='Dáng nhà rộng, mái thấp và họa tiết gỗ với kem tuyết. Một ngôi nhà nhỏ để đặt cạnh cây thông.'),
    dict(id='gb_frost', name='Ngôi nhà băng đường', subtitle='Sugar & Snow', collection='Kẹo ngọt', width=75, depth=65, wall_height=115, roof_rise=37.5, wall='#b9cdd3', roof='#668da3', accent='#6f90a9', trim='#fffdf3', background='#e7eff3', motif='snow', difficulty='Dễ', description='Dáng nhà cao, xanh băng và bông tuyết bằng đường. Cửa và các chi tiết đều là họa tiết trang trí in màu.'),
    dict(id='gb_mini', name='Nhà bánh gừng mini', subtitle='Little Christmas Village', collection='Mini', width=60, depth=50, wall_height=60, roof_rise=30, wall='#c98d55', roof='#a94839', accent='#37816a', trim='#fff7e6', background='#f3ecdb', motif='mini', difficulty='Dễ', description='Một căn nhà nhỏ 60 × 50 × 90 mm cho kệ sách và tiểu cảnh Noel. Có thể tạo nhiều bản để dựng thành làng.'),
]
BY_ID = {t['id']: t for t in TEMPLATES}


def public_template(t):
    return {**t, 'version': CATALOG_VERSION, 'dimensions_mm': [t['width'], t['depth'], t['wall_height'] + t['roof_rise']],
            'paper': 'US Letter', 'physical_assembly': 'NOT_TESTED',
            'construction': 'Nhà mái hai dốc, đáy mở; cửa và cửa sổ là họa tiết in, không khoét rỗng.',
            'preview_url': f"/api/templates/{t['id']}/preview.svg"}
