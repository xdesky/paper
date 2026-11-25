import json
from pathlib import Path
import struct

import pymupdf

from backend import christmas_collection as collection
from tests.support import TestClient, create_app


def test_all_products_are_parametric_closed_meshes_and_uniformly_sized():
    assert len(collection.PRODUCTS)==10
    for product in collection.PRODUCTS:
        model=collection.build_model(product['id'])
        assert model['unpairedEdges']==[],product['id']
        assert model['surfaces'] and model['components']
        assert max(model['boundsMm']['size'])==product['size']
        assert all(len(face['vertices_3d_mm'])>=3 for face in model['surfaces'])
        scaled=collection.build_model(product['id'],product['size']/2)
        assert max(scaled['boundsMm']['size'])==product['size']/2
        assert len(collection._pages(model,'US Letter','classic'))>0


def test_product_package_has_native_vector_pdfs_svg_glb_guide_and_status(tmp_path):
    out,report,model=collection.generate_bundle('xm10_christmas_gift_box',tmp_path,100,'pastel',True,'A4')
    assert report['status']=='PRINTABLE_VALIDATED'
    assert report['physicalAssembly']=='NOT_TESTED'
    for name,paper in [('Printable_Color_USLetter.pdf','US Letter'),('Printable_Color_A4.pdf','A4'),('Printable_Color_A3.pdf','A3')]:
        with pymupdf.open(out/name) as doc:
            width,height=collection.PAPERS[paper]
            assert len(doc)==len(collection._pages(model,paper,'pastel'))
            assert all(abs(page.rect.width-width*72/25.4)<.2 and abs(page.rect.height-height*72/25.4)<.2 for page in doc)
            assert all(page.get_drawings() for page in doc)
    with pymupdf.open(out/'Printable_Coloring.pdf') as coloring:
        assert len(coloring)>0 and '100%' in ' '.join(coloring[0].get_text().split())
    assert (out/'Assembly_Guide.pdf').is_file() and (out/'Printable.svg').is_file()
    assert (out/'Preview.png').read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'
    glb=(out/'Model.glb').read_bytes();assert glb[:4]==b'glTF' and struct.unpack('<I',glb[8:12])[0]==len(glb)
    config=json.loads((out/'Product_Config.json').read_text());assert config['sizeMm']==100 and config['scaleRule']=='uniform'
    assert (out/'Full_Package.zip').is_file()


def test_christmas_collection_and_city_builder_share_real_product_geometry(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        products=client.get('/api/christmas/products').json()
        assert len(products)==10
        printable=client.get('/api/christmas/products/xm01_gingerbread_house/files/Printable.svg')
        assert printable.status_code==200
        assert printable.headers['content-type'].startswith('image/svg+xml')
        assert printable.headers['content-disposition'].startswith('inline;')
        product=next(item for item in products if item['id']=='xm02_christmas_tree')
        model=client.get(product['modelRef']+'?size_mm=200&style=nordic').json()
        assert model['sizeMm']==200 and len(model['surfaces'])>20
        assets=client.get('/api/city/assets').json()
        shared=next(item for item in assets if item['id']==product['id'])
        assert shared['revision']==collection.VERSION and shared['category']=='christmas-collection'
        city_model=client.get(shared['modelRef']).json()
        assert city_model['assetRevision']==collection.VERSION and len(city_model['surfaces'])==len(collection.build_model(product['id'])['surfaces'])
