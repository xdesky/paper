"""Mini City Builder adapters and vector-preserving city print export."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import threading
import uuid

import pymupdf
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .template_catalog import CATALOG_VERSION, TEMPLATES, thumbnail_name

MAX_OBJECTS = 100
MAX_GRID = 32
MAX_CELL_MM = 500
MIN_CELL_MM = 60
MAX_EXPORT_PAGES = 200
MAX_EXPORT_BYTES = 100 * 1024 * 1024
EXPORT_LOCK = threading.Lock()
HOUSE_TEMPLATES = {t['id']: t for t in TEMPLATES if t.get('category') in ('gingerbread-houses', 'miniature-worlds')}


class CityGrid(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    columns: int = Field(ge=1, le=MAX_GRID)
    rows: int = Field(ge=1, le=MAX_GRID)
    cell_size_mm: int = Field(default=100, alias='cellSizeMm', ge=MIN_CELL_MM, le=MAX_CELL_MM)


class CityObject(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    id: str = Field(min_length=1, max_length=64)
    asset_id: str = Field(alias='assetId', min_length=1, max_length=96)
    asset_revision: str = Field(alias='assetRevision', min_length=1, max_length=40)
    x_cell: int = Field(alias='xCell', ge=0, le=MAX_GRID)
    z_cell: int = Field(alias='zCell', ge=0, le=MAX_GRID)
    rotation_deg: int = Field(alias='rotationDeg')

    @model_validator(mode='after')
    def allowed_rotation(self):
        if self.rotation_deg not in (0, 90, 180, 270):
            raise ValueError('Rotation must be 0, 90, 180, or 270 degrees.')
        return self


class CityProjectInput(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    schema_version: int = Field(default=1, alias='schemaVersion', ge=1, le=1)
    name: str = Field(min_length=1, max_length=100)
    grid: CityGrid
    objects: list[CityObject] = Field(max_length=MAX_OBJECTS)

    @model_validator(mode='after')
    def unique_ids_and_bounds(self):
        ids=[o.id for o in self.objects]
        if len(ids)!=len(set(ids)):
            raise ValueError('City object IDs must be unique.')
        for item in self.objects:
            if item.x_cell >= self.grid.columns or item.z_cell >= self.grid.rows:
                raise ValueError('An object begins outside the city grid.')
        return self


class CityCreate(CityProjectInput):
    pass


class CityPreflight(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: str = Field(min_length=1, max_length=80)
    selected_object_ids: list[str] | None = Field(default=None, max_length=MAX_OBJECTS)
    paper: str = Field(default='US Letter', pattern='^(US Letter|A4)$')


def _asset_size(asset_id: str):
    t=HOUSE_TEMPLATES.get(asset_id)
    if not t:return None
    return (t['width']+60,t['depth']+70)


def _span(item: CityObject, cell_size: int):
    size=_asset_size(item.asset_id)
    if not size:return (1,1)
    w,d=size
    if item.rotation_deg in (90,270):w,d=d,w
    return math.ceil(w/cell_size),math.ceil(d/cell_size)


def validate_city_occupancy(project: CityProjectInput):
    occupied={}
    for item in project.objects:
        sw,sh=_span(item,project.grid.cell_size_mm)
        if item.x_cell+sw>project.grid.columns or item.z_cell+sh>project.grid.rows:
            raise HTTPException(422,f'{item.asset_id} at ({item.x_cell}, {item.z_cell}) extends beyond the city grid.')
        if item.asset_id not in HOUSE_TEMPLATES:continue  # unresolved assets remain visible for recovery
        for x in range(item.x_cell,item.x_cell+sw):
            for z in range(item.z_cell,item.z_cell+sh):
                if (x,z) in occupied:
                    raise HTTPException(422,f'Objects overlap at grid cell ({x}, {z}).')
                occupied[(x,z)]=item.id


def serialize_city(row):
    payload=json.loads(row['scene_json'])
    return {'schemaVersion':1,'id':row['id'],'name':row['name'],'grid':payload['grid'],'objects':payload['objects'],'updatedAt':row['updated_at']}


def list_city_assets():
    items=[]
    for t in HOUSE_TEMPLATES.values():
        items.append({'id':t['id'],'revision':CATALOG_VERSION,'name':t['name'],'category':t['category'],
            'thumbnailUrl':f"/api/templates/{t['id']}/{thumbnail_name(t)}.jpg",
            'modelRef':f"/api/city/assets/{t['id']}/model",'templateRef':f"/api/city/assets/{t['id']}/pdf",
            'physicalSizeMm':{'width':t['width'],'depth':t['depth'],'height':t['wall_height']+t['roof_rise']},
            'footprintMm':{'width':t['width']+60,'depth':t['depth']+70},'pivot':'bottom-center',
            'allowedRotations':[0,90,180,270],'supportedPaperFormats':['US Letter','A4'],'printStatus':'ready'})
    return items


def asset_model(asset_id: str):
    t=HOUSE_TEMPLATES.get(asset_id)
    if not t:raise HTTPException(404,'City asset not found.')
    from .gingerbread import model,decorations,svg_art
    from .accessories import scene
    surfaces=[]
    panels,_,_,_,_=model(t)
    for panel in panels.values():
        bounds=panel.square.bounds
        surfaces.append({'id':panel.id,'polygon_mm':panel.points,'vertices_3d_mm':panel.vertices,
            'width_mm':bounds[2]-bounds[0],'height_mm':bounds[3]-bounds[1],
            'art':svg_art(decorations(t,panel),bounds[2]-bounds[0],bounds[3]-bounds[1])})
    accessory=scene(t)
    for panel in accessory['panels']:
        surfaces.append({**panel,'art':accessory['appearance'][panel['id']]})
    all_xyz=[v for surface in surfaces for v in surface['vertices_3d_mm']]
    mins=[min(p[i] for p in all_xyz) for i in range(3)]
    maxs=[max(p[i] for p in all_xyz) for i in range(3)]
    return {'assetId':asset_id,'assetRevision':CATALOG_VERSION,'units':'mm','source':'V1 gingerbread model and accessories geometry',
        'boundsMm':{'min':mins,'max':maxs,'size':[maxs[i]-mins[i] for i in range(3)]},'surfaces':surfaces}


def _template_pdf(data: Path, asset_id: str, paper: str) -> Path:
    if asset_id not in HOUSE_TEMPLATES:raise HTTPException(422,f'No printable house template is registered for {asset_id}.')
    digest=hashlib.sha256(f'{CATALOG_VERSION}:{asset_id}:{paper}'.encode()).hexdigest()[:20]
    folder=data/'city-template-cache'/digest
    from .paper import printable_filename
    target=folder/printable_filename(paper)
    if target.is_file() and target.stat().st_size>0:
        try:
            with pymupdf.open(target) as cached:
                expected_w,expected_h=((210,297) if paper=='A4' else (215.9,279.4))
                if len(cached)>0 and all(abs(page.mediabox.width-expected_w*72/25.4)<=.2 and abs(page.mediabox.height-expected_h*72/25.4)<=.2 for page in cached):return target
        except Exception:
            pass
        target.unlink(missing_ok=True)
    folder.mkdir(parents=True,exist_ok=True)
    from .gingerbread import generate
    request={'project_id':'CITY-'+asset_id,'revision':1,'preset':asset_id,'paper':paper}
    try:
        with EXPORT_LOCK:
            if not target.is_file():generate(request,folder)
    except Exception as exc:
        raise HTTPException(422,f'Print template for {HOUSE_TEMPLATES[asset_id]["name"]} could not be generated: {exc}')
    if not target.is_file() or target.stat().st_size==0:
        raise HTTPException(422,f'Print template for {HOUSE_TEMPLATES[asset_id]["name"]} is missing or empty.')
    width_mm,height_mm=(210,297) if paper=='A4' else (215.9,279.4)
    try:
        with pymupdf.open(target) as document:
            if not len(document):raise ValueError('PDF has no pages')
            for page in document:
                rect=page.mediabox
                if abs(rect.width-width_mm*72/25.4)>.2 or abs(rect.height-height_mm*72/25.4)>.2:
                    raise ValueError(f'Expected {paper} media boxes at native size; got {rect.width:.2f} × {rect.height:.2f} pt')
    except Exception as exc:
        raise HTTPException(422,f'Print template for {HOUSE_TEMPLATES[asset_id]["name"]} failed PDF preflight: {exc}')
    return target


def _guide_pdf(data: Path, asset_id: str, paper: str) -> Path:
    # _template_pdf runs the existing V1 generator and also creates its full
    # assembly guide; reuse that exact versioned output for one guide per asset.
    _template_pdf(data,asset_id,paper)
    digest=hashlib.sha256(f'{CATALOG_VERSION}:{asset_id}:{paper}'.encode()).hexdigest()[:20]
    target=data/'city-template-cache'/digest/'assembly_guide.pdf'
    if not target.is_file() or target.stat().st_size==0:
        raise HTTPException(422,f'Assembly instructions for {HOUSE_TEMPLATES[asset_id]["name"]} are unavailable.')
    width_mm,height_mm=(210,297) if paper=='A4' else (215.9,279.4)
    try:
        with pymupdf.open(target) as document:
            if not len(document):raise ValueError('PDF has no pages')
            for page in document:
                rect=page.mediabox
                if abs(rect.width-width_mm*72/25.4)>.2 or abs(rect.height-height_mm*72/25.4)>.2:
                    raise ValueError(f'Expected {paper} guide pages at native size; got {rect.width:.2f} × {rect.height:.2f} pt')
    except Exception as exc:
        raise HTTPException(422,f'Assembly instructions for {HOUSE_TEMPLATES[asset_id]["name"]} failed PDF preflight: {exc}')
    return target


def _layout_dimensions(project, paper):
    page_w,page_h=(612,792) if paper=='US Letter' else (595.2756,841.8898)
    grid=project['grid'];cell=grid['cellSizeMm'];map_h=page_h*.36
    scale=min((page_w-68)/(grid['columns']*cell),map_h/(grid['rows']*cell))
    map_bottom=85+grid['rows']*cell*scale
    inventory_start=map_bottom+93
    first_rows=max(1,int((page_h-21-inventory_start-10)//24))
    continuation_rows=max(1,int((page_h-100-10)//24))
    return page_w,page_h,first_rows*2,continuation_rows*2


def _layout_page_count(project, paper, item_count):
    _,_,first_capacity,continuation_capacity=_layout_dimensions(project,paper)
    remaining=max(0,item_count-first_capacity)
    return 1+math.ceil(remaining/continuation_capacity)


def _layout_pdf(project, items, paper, selected_ids):
    page_w,page_h,first_capacity,continuation_capacity=_layout_dimensions(project,paper)
    doc=pymupdf.open();page=doc.new_page(width=page_w,height=page_h)
    page.insert_text((34,32),'MINI CITY BUILDER | PRINT & ASSEMBLY REFERENCE',fontsize=14,fontname='hebo')
    page.insert_text((34,49),f"{project['name']} · {len(project['objects'])} placed models",fontsize=9)
    page.insert_text((34,66),'REFERENCE MAP — REDUCED OVERVIEW, NOT A PRINTABLE BASE',fontsize=9,color=(.61,.25,.28))
    grid=project['grid'];cell=grid['cellSizeMm'];map_h=page_h*.36;scale=min((page_w-68)/(grid['columns']*cell),map_h/(grid['rows']*cell))
    origin_x=(page_w-grid['columns']*cell*scale)/2;origin_y=85
    rect=pymupdf.Rect(origin_x,origin_y,origin_x+grid['columns']*cell*scale,origin_y+grid['rows']*cell*scale)
    page.draw_rect(rect,color=(.55,.58,.65),width=.7)
    for col in range(1,grid['columns']):
        x=origin_x+col*cell*scale;page.draw_line((x,origin_y),(x,rect.y1),color=(.82,.83,.87),width=.35)
    for row in range(1,grid['rows']):
        y=origin_y+row*cell*scale;page.draw_line((origin_x,y),(origin_x+grid['columns']*cell*scale,y),color=(.82,.83,.87),width=.35)
    selected=set(selected_ids)
    for index,obj in enumerate(project['objects'],1):
        if not HOUSE_TEMPLATES.get(obj['assetId']):continue
        sw,sh=_span(CityObject.model_validate(obj),cell)
        x0=origin_x+obj['xCell']*cell*scale;y0=origin_y+obj['zCell']*cell*scale
        box=pymupdf.Rect(x0,y0,x0+sw*cell*scale,y0+sh*cell*scale)
        active=obj['id'] in selected;color=(.42,.3,.88) if active else (.69,.72,.78);fill=(.93,.91,.99) if active else (.97,.97,.98)
        page.draw_rect(box,color=color,fill=fill,width=.8)
        page.insert_textbox(box,f"#{index}\nCell {obj['xCell']+1},{obj['zCell']+1}\nR{obj['rotationDeg']}",fontsize=max(3.4,min(5.2,cell*scale*.17)),align=1,color=(.18,.2,.3))
        # North is toward the top of the map; the front of a 0-degree V1
        # model points south after the V1 y-to-city-z conversion.
        arrows={0:(0,1),90:(-1,0),180:(0,-1),270:(1,0)}
        vx,vy=arrows[obj['rotationDeg']];cx=(box.x0+box.x1)/2;cy=(box.y0+box.y1)/2;length=min(box.width,box.height)*.19;ex=cx+vx*length;ey=cy+vy*length
        page.draw_line((cx,cy),(ex,ey),color=(.24,.2,.48),width=.75)
        back_x,back_y=ex-vx*length*.45,ey-vy*length*.45;wing=length*.28
        page.draw_line((ex,ey),(back_x-vy*wing,back_y+vx*wing),color=(.24,.2,.48),width=.65)
        page.draw_line((ex,ey),(back_x+vy*wing,back_y-vx*wing),color=(.24,.2,.48),width=.65)
    y=rect.y1+17
    page.insert_text((34,y),f'Grid: {grid["columns"]} × {grid["rows"]} cells · {cell} mm/cell · North ↑',fontsize=8)
    y+=26;page.draw_line((34,y),(34+50*72/25.4,y),color=(.12,.15,.18),width=1.2);page.draw_line((34,y-4),(34,y+4),color=(.12,.15,.18),width=.8);page.draw_line((34+50*72/25.4,y-4),(34+50*72/25.4,y+4),color=(.12,.15,.18),width=.8)
    page.insert_text((34,y+13),'50 mm calibration ruler · Print at Actual Size / 100% · Disable Fit to Page',fontsize=7)
    y+=33;page.insert_text((34,y),'PRINT INVENTORY — SELECTED OBJECTS ONLY',fontsize=9,fontname='hebo');y+=17
    first=items[:first_capacity]
    for i,entry in enumerate(first):
        col=i%2;row=i//2;column_x=34+col*((page_w-68)/2)
        refs=', '.join('#'+ref for ref in entry['modelRefs'][:5])
        if len(entry['modelRefs'])>5:refs+=f" +{len(entry['modelRefs'])-5} more"
        dims=' x '.join(str(v) for v in entry['dimensionsMm'])+' mm'
        label=f"{refs} · {entry['name']}\n{dims} · {entry['quantity']}× · {entry['pagesPerCopy']} pages/copy + {entry['guidePages']} guide pages"
        right=page_w-34 if col else column_x+(page_w-68)/2-8
        page.insert_textbox(pymupdf.Rect(column_x,y+row*24,right,y+row*24+22),label,fontsize=6.6,lineheight=1.1)
    footer_y=min(page_h-21,y+math.ceil(len(first)/2)*24+10)
    page.insert_text((34,footer_y),'Print model sheets at 100%. The map is a placement reference only; the city grid is non-printing.',fontsize=7,color=(.35,.38,.44))
    remaining=items[first_capacity:]
    for start in range(0,len(remaining),continuation_capacity):
        page=doc.new_page(width=page_w,height=page_h)
        page.insert_text((34,38),'MINI CITY BUILDER | PRINT INVENTORY CONTINUED',fontsize=13,fontname='hebo')
        page.insert_text((34,56),f"{project['name']} · Inventory continuation",fontsize=9)
        chunk=remaining[start:start+continuation_capacity]
        for i,entry in enumerate(chunk):
            col=i%2;row=i//2;column_x=34+col*((page_w-68)/2)
            refs=', '.join('#'+ref for ref in entry['modelRefs'][:5])
            if len(entry['modelRefs'])>5:refs+=f" +{len(entry['modelRefs'])-5} more"
            dims=' x '.join(str(v) for v in entry['dimensionsMm'])+' mm'
            label=f"{refs} · {entry['name']}\n{dims} · {entry['quantity']}× · {entry['pagesPerCopy']} pages/copy + {entry['guidePages']} guide pages"
            right=page_w-34 if col else column_x+(page_w-68)/2-8
            page.insert_textbox(pymupdf.Rect(column_x,80+row*24,right,102+row*24),label,fontsize=6.6,lineheight=1.1)
        page.insert_text((34,page_h-21),'Print model sheets at 100%. Keep this inventory with the reference map.',fontsize=7,color=(.35,.38,.44))
    return doc


def city_preflight(data:Path, project:dict, selected_ids:list[str]|None, paper:str):
    by_id={obj['id']:obj for obj in project['objects']}
    selected=set(selected_ids) if selected_ids is not None else set(by_id)
    missing=selected-set(by_id)
    if missing:raise HTTPException(422,'Selected object IDs are not in this city: '+', '.join(sorted(missing)))
    chosen=[obj for obj in project['objects'] if obj['id'] in selected]
    if not chosen:raise HTTPException(422,'Select at least one city object to print.')
    unknown=sorted({obj['assetId'] for obj in chosen if obj['assetId'] not in HOUSE_TEMPLATES})
    if unknown:raise HTTPException(422,'Printable templates are unavailable for: '+', '.join(unknown))
    counts=Counter((obj['assetId'],obj['assetRevision']) for obj in chosen)
    entries=[];total=1
    for (asset_id,revision),quantity in sorted(counts.items()):
        if revision!=CATALOG_VERSION:raise HTTPException(409,f'{asset_id} uses revision {revision}; current printable source is {CATALOG_VERSION}. Update or remove this object before printing.')
        pdf=_template_pdf(data,asset_id,paper)
        with pymupdf.open(pdf) as source:pages=len(source)
        guide=_guide_pdf(data,asset_id,paper)
        with pymupdf.open(guide) as source:guide_pages=len(source)
        refs=[str(index) for index,obj in enumerate(project['objects'],1) if obj['id'] in selected and obj['assetId']==asset_id and obj['assetRevision']==revision]
        template=HOUSE_TEMPLATES[asset_id]
        item={'assetId':asset_id,'assetRevision':revision,'name':template['name'],'quantity':quantity,'modelRefs':refs,'pagesPerCopy':pages,'totalPages':quantity*pages,'guidePages':guide_pages,'guideCopies':1,'dimensionsMm':[template['width'],template['depth'],template['wall_height']+template['roof_rise']],'paper':paper,'sourceBytes':pdf.stat().st_size,'guideBytes':guide.stat().st_size}
        entries.append(item);total+=item['totalPages']+guide_pages
    layout_pages=_layout_page_count(project,paper,len(entries));total+=layout_pages-1
    if total>MAX_EXPORT_PAGES:raise HTTPException(413,f'This export would contain {total} pages. The safe limit is {MAX_EXPORT_PAGES}; print a smaller selection.')
    estimated=sum(i['sourceBytes']*i['quantity']+i['guideBytes'] for i in entries)
    if estimated>MAX_EXPORT_BYTES:raise HTTPException(413,'This export exceeds the 100 MiB safe limit; print a smaller selection.')
    return {'projectId':project['id'],'paper':paper,'selectedObjectCount':len(chosen),'items':entries,'layoutPages':layout_pages,'totalPages':total,'totalSourceBytes':estimated,'maxPages':MAX_EXPORT_PAGES,'maxBytes':MAX_EXPORT_BYTES,'warnings':['The editor grid and reduced overview are non-printing. The overview is a reference map, not a printable base.']}


def export_city_pdf(data:Path, project:dict, selected_ids:list[str]|None, paper:str):
    preflight=city_preflight(data,project,selected_ids,paper)
    chosen_ids=set(selected_ids) if selected_ids is not None else {o['id'] for o in project['objects']}
    chosen=[o for o in project['objects'] if o['id'] in chosen_ids]
    doc=_layout_pdf(project,preflight['items'],paper,chosen_ids)
    try:
        for item in preflight['items']:
            source_path=_template_pdf(data,item['assetId'],paper)
            for _ in range(item['quantity']):
                with pymupdf.open(source_path) as source:
                    for page in source:
                        target=doc.new_page(width=page.rect.width,height=page.rect.height)
                        target.show_pdf_page(target.rect,source,page.number,keep_proportion=False,overlay=True)
            guide_path=_guide_pdf(data,item['assetId'],paper)
            with pymupdf.open(guide_path) as guide:
                for page in guide:
                    target=doc.new_page(width=page.rect.width,height=page.rect.height)
                    target.show_pdf_page(target.rect,guide,page.number,keep_proportion=False,overlay=True)
        raw=doc.tobytes(garbage=3,deflate=True)
    finally:doc.close()
    if len(raw)>MAX_EXPORT_BYTES:raise HTTPException(413,'Generated PDF exceeds the 100 MiB safe limit.')
    return raw,preflight
