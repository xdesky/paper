from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
import json
import html
import re
import mimetypes
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, field_validator
from .personalization import normalize_name
from .design_options import DesignOptions,OPTIONS,apply_design
from .template_catalog import BY_ID, TEMPLATES, CATALOG_VERSION, public_template

ROOT = Path(__file__).resolve().parents[1]
Preset = Literal[tuple(['cube_100', 'cube_200', 'cube_300', 'house_frame', *BY_ID])]
PRESETS = {'cube_100': 'Cube 100 mm', 'cube_200': 'Cube 200 mm', 'cube_300': 'Cube 300 mm', 'house_frame': 'Khung nhà 120 × 90 × 180 mm'}


class CreateProject(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    preset: Preset = 'cube_100'
    paper: Literal['US Letter', 'A4'] = 'US Letter'
    design: DesignOptions = Field(default_factory=DesignOptions)
    personal_name: str = Field(default='', max_length=24)
    _name = field_validator('personal_name',mode='before')(normalize_name)


class EditProject(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    preset: Preset | None = None
    paper: Literal['US Letter', 'A4'] | None = None
    design: DesignOptions | None = None
    personal_name: str | None = Field(default=None,max_length=24)
    _name = field_validator('personal_name',mode='before')(normalize_name)


class NamePreview(BaseModel):
    design: DesignOptions = Field(default_factory=DesignOptions)
    model_config = ConfigDict(extra='forbid')
    personal_name: str = Field(default='',max_length=24)
    _name = field_validator('personal_name',mode='before')(normalize_name)


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(data_dir=None, seed=False):
    data = Path(data_dir or os.getenv('PPM_DATA_DIR', str(ROOT / '.data'))).resolve()
    data.mkdir(parents=True, exist_ok=True)
    db_path = data / 'studio.sqlite3'
    pool = ThreadPoolExecutor(max_workers=1)
    timeout = int(os.getenv('PPM_JOB_TIMEOUT', '180'))

    @contextmanager
    def connection():
        db = sqlite3.connect(db_path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, preset TEXT NOT NULL, revision INTEGER NOT NULL, result_revision INTEGER, status TEXT NOT NULL, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, revision INTEGER, status TEXT NOT NULL, stage TEXT, error TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS revisions(project_id TEXT, revision INTEGER, snapshot TEXT, created_at TEXT, PRIMARY KEY(project_id,revision));
        ''')
        if 'paper' not in {row['name'] for row in db.execute('PRAGMA table_info(projects)')}:
            db.execute("ALTER TABLE projects ADD COLUMN paper TEXT NOT NULL DEFAULT 'US Letter'")
        if 'personal_name' not in {row['name'] for row in db.execute('PRAGMA table_info(projects)')}:
            db.execute("ALTER TABLE projects ADD COLUMN personal_name TEXT NOT NULL DEFAULT ''")

        if 'design' not in {row['name'] for row in db.execute('PRAGMA table_info(projects)')}:
            db.execute("ALTER TABLE projects ADD COLUMN design TEXT NOT NULL DEFAULT '{}'")

    def serialize_project(row):
        p=dict(row);p['design']=DesignOptions(**json.loads(p['design'])).model_dump();return p

    def project(pid):
        with connection() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
        if not row:
            raise HTTPException(404, 'Project not found')
        return serialize_project(row)

    def create(body):
        pid = uuid.uuid4().hex
        with connection() as db:
            db.execute('INSERT INTO projects (id,name,preset,revision,result_revision,status,created_at,updated_at,paper,personal_name,design) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (pid, body.name, body.preset, 1, None, 'DRAFT', now(), now(), body.paper,body.personal_name,body.design.model_dump_json()))
        return project(pid)

    def update_job(jid, status, stage, error=None):
        with connection() as db:
            db.execute('UPDATE jobs SET status=?,stage=?,error=?,updated_at=? WHERE id=?', (status, stage, error, now(), jid))

    def run_job(jid, snapshot):
        pid, rev = snapshot['project_id'], snapshot['revision']
        folder = data / pid / str(rev)
        out = folder / 'artifacts'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'request.json').write_text(json.dumps(snapshot))
        update_job(jid, 'RUNNING', 'Validate Input')
        try:
            env = {**os.environ, 'MPLCONFIGDIR': str(data / '.mpl-cache'), 'PYTHONHASHSEED': '0'}
            with (folder / 'worker.log').open('w') as log:
                subprocess.run([sys.executable, '-m', 'backend.worker', str(folder / 'request.json'), str(out), str(folder / 'progress.json')], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=True)
            report = json.loads((out / 'validation_report.json').read_text())
            if report['overall_status'] != 'PASS':
                raise RuntimeError('QA failed')
            with connection() as db:
                db.execute("UPDATE projects SET result_revision=?,status='READY',updated_at=? WHERE id=? AND revision=?", (rev, now(), pid, rev))
            update_job(jid, 'SUCCEEDED', 'Complete')
        except Exception as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                message = f'Generation exceeded {timeout}s timeout.'
            else:
                lines = (folder / 'worker.log').read_text(errors='replace').splitlines()
                message = '\n'.join(lines[-8:])[-2500:] or str(exc)
            with connection() as db:
                db.execute("UPDATE projects SET status='FAILED',updated_at=? WHERE id=? AND revision=?", (now(), pid, rev))
            update_job(jid, 'FAILED', 'Failed', message)

    def enqueue(pid):
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Project not found')
            active = db.execute("SELECT * FROM jobs WHERE project_id=? AND status IN ('QUEUED','RUNNING')", (pid,)).fetchone()
            if active:
                return dict(active)
            if db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0] >= 8:
                raise HTTPException(429, 'Generation queue is full')
            rev = row['revision']
            if db.execute('SELECT 1 FROM revisions WHERE project_id=? AND revision=?', (pid, rev)).fetchone():
                rev += 1
            snapshot = {'project_id': pid, 'revision': rev, 'preset': row['preset'], 'paper': row['paper'], 'personal_name':row['personal_name'], 'design':json.loads(row['design']), 'scale': 1.0, 'engine_version': '1.2.0'}
            if row['preset'] in BY_ID:
                snapshot.update(engine_version='gingerbread-4.0.0', template={**apply_design(BY_ID[row['preset']],json.loads(row['design'])),**({'personal_name':row['personal_name']} if row['personal_name'] else {})}, template_version=CATALOG_VERSION)
            jid = uuid.uuid4().hex
            db.execute('INSERT INTO revisions VALUES(?,?,?,?)', (pid, rev, json.dumps(snapshot), now()))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)', (jid, pid, rev, 'QUEUED', 'Queued', None, now(), now()))
            db.execute("UPDATE projects SET revision=?,status='GENERATING',updated_at=? WHERE id=?", (rev, now(), pid))
        pool.submit(run_job, jid, snapshot)
        return {'id': jid, 'project_id': pid, 'revision': rev, 'status': 'QUEUED', 'stage': 'Queued', 'error': None}

    @asynccontextmanager
    async def lifespan(app):
        # A terminated server cannot certify unfinished subprocess output.
        with connection() as db:
            db.execute("UPDATE jobs SET status='FAILED',stage='Interrupted',error='Server restarted before completion' WHERE status IN ('QUEUED','RUNNING')")
            db.execute("UPDATE projects SET status='FAILED' WHERE status='GENERATING'")
            count = db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
        if seed and count == 0:
            samples = [create(CreateProject(name=name, preset=preset)) for preset, name in PRESETS.items()]
            enqueue(samples[0]['id'])
        yield
        pool.shutdown(wait=True)

    app = FastAPI(title='Print Play Magic Studio', version='0.1.0', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=os.getenv('PPM_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','), allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Content-Type'])

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'engine': '1.2.0', 'phase': 'A'}

    @app.get('/api/presets')
    def presets():
        return {**PRESETS, **{t['id']: t['name'] for t in TEMPLATES}}

    @app.get('/api/design-options')
    def design_options():
        return {key:[dict(id=id,label=label) for id,label in values] for key,values in OPTIONS.items()}

    @app.get('/api/templates')
    def templates():
        from .gingerbread import model
        result=[]
        for t in TEMPLATES:
            panels,seams,units,pages,_=model(t)
            from .roof_cap import metadata
            cap=metadata(t)
            result.append({**public_template(t),'sheet_count':len(pages)+2+cap['sheet_count']+int(bool(t.get('chimney'))),'roof_cap':cap,'house_sheet_count':len(pages),'house_cut_pieces':len(units),'accessory_cut_pieces':5+cap['cut_pieces']+int(bool(t.get('chimney'))),'cut_pieces':len(units)+5+cap['cut_pieces']+int(bool(t.get('chimney'))),'face_count':len(panels),'fold_hinges':sum(s['hinge'] for s in seams),'glue_seams':sum(not s['hinge'] for s in seams)})
        return result

    @app.get('/api/templates/{template_id}/preview.svg')
    def template_preview(template_id: str):
        if template_id not in BY_ID:
            raise HTTPException(404, 'Template not found')
        from .gingerbread import preview_svg
        return Response(preview_svg(BY_ID[template_id]), media_type='image/svg+xml', headers={'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff'})

    @app.post('/api/templates/{template_id}/personalize-preview')
    def personalized_preview(template_id: str, body: NamePreview):
        if template_id not in BY_ID:raise HTTPException(404,'Template not found')
        from .gingerbread import preview_svg
        return Response(preview_svg({**apply_design(BY_ID[template_id],body.design.model_dump()),'personal_name':body.personal_name}),media_type='image/svg+xml',headers={'Cache-Control':'no-store'})

    @app.get('/api/projects')
    def projects():
        with connection() as db:
            return [serialize_project(r) for r in db.execute('SELECT * FROM projects ORDER BY created_at')]

    @app.post('/api/projects', status_code=201)
    def new_project(body: CreateProject):
        return create(body)

    @app.get('/api/projects/{pid}')
    def get_project(pid: str):
        result = project(pid)
        with connection() as db:
            row = db.execute('SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 1', (pid,)).fetchone()
        result['latest_job'] = dict(row) if row else None
        return result

    @app.patch('/api/projects/{pid}')
    def edit_project(pid: str, body: EditProject):
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Project not found')
            if row['status'] == 'GENERATING':
                raise HTTPException(409, 'Wait for current generation')
            design=body.design.model_dump_json() if body.design is not None else row['design']
            design_changed=DesignOptions(**json.loads(design))!=DesignOptions(**json.loads(row['design']))
            changed = design_changed or (body.preset is not None and body.preset != row['preset']) or (body.paper is not None and body.paper != row['paper']) or (body.personal_name is not None and body.personal_name != row['personal_name'])
            db.execute('UPDATE projects SET name=?,preset=?,paper=?,personal_name=?,design=?,revision=?,status=?,updated_at=? WHERE id=?', (body.name or row['name'], body.preset or row['preset'], body.paper or row['paper'], body.personal_name if body.personal_name is not None else row['personal_name'], design, row['revision'] + int(changed), 'STALE' if changed else row['status'], now(), pid))
        return project(pid)

    @app.post('/api/projects/{pid}/duplicate', status_code=201)
    def duplicate(pid: str):
        p = project(pid)
        return create(CreateProject(name=(p['name'][:90] + ' (bản sao)'), preset=p['preset'], paper=p['paper'],personal_name=p['personal_name'],design=p['design']))

    @app.delete('/api/projects/{pid}', status_code=204)
    def delete(pid: str):
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Project not found')
            if row['status']=='GENERATING':
                raise HTTPException(409, 'Wait for current generation')
            db.execute('DELETE FROM projects WHERE id=?', (pid,))
            db.execute('DELETE FROM jobs WHERE project_id=?', (pid,))
        # Immutable artifact history is retained on disk; no route serves deleted projects.

    @app.post('/api/projects/{pid}/generate', status_code=202)
    def generate(pid: str):
        return enqueue(pid)

    @app.get('/api/jobs/{jid}')
    def job(jid: str):
        with connection() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
        if not row:
            raise HTTPException(404, 'Job not found')
        result = dict(row)
        if result['status'] == 'RUNNING':
            progress = data / result['project_id'] / str(result['revision']) / 'progress.json'
            if progress.exists():
                result['stage'] = json.loads(progress.read_text())['stage']
                with connection() as db:
                    db.execute("UPDATE jobs SET stage=? WHERE id=? AND status='RUNNING'", (result['stage'], jid))
        return result

    def artifact_root(pid):
        p = project(pid)
        if p['status'] != 'READY' or p['result_revision'] != p['revision']:
            raise HTTPException(409, 'Artifacts unavailable: generate current revision and pass QA first')
        return data / pid / str(p['revision']) / 'artifacts'

    def read_artifact(pid, name):
        return json.loads((artifact_root(pid) / name).read_text())

    @app.get('/api/projects/{pid}/geometry')
    def geometry(pid: str):
        return read_artifact(pid, 'model_spec.json')

    @app.get('/api/projects/{pid}/validation')
    def validation(pid: str):
        return read_artifact(pid, 'validation_report.json')

    @app.get('/api/projects/{pid}/pages')
    def pages(pid: str, style: Literal['color','coloring'] = 'color'):
        root = artifact_root(pid)
        folder='coloring_svg_pages' if style=='coloring' else 'svg_pages'
        if not (root/folder).exists():raise HTTPException(409,'Bấm Generate để tạo bản tự tô cho dự án này.')
        return [{'number': i+1, 'url': f'/api/projects/{pid}/artifacts/{folder}/{p.name}'} for i, p in enumerate(sorted((root / folder).glob('*.svg')))]

    @app.get('/api/projects/{pid}/artifacts')
    def artifacts(pid: str):
        root = artifact_root(pid)
        return [{'name': p.relative_to(root).as_posix(), 'url': f'/api/projects/{pid}/artifacts/{p.relative_to(root).as_posix()}'} for p in sorted(root.rglob('*')) if p.is_file()]

    @app.get('/api/projects/{pid}/print')
    def print_project(pid: str, style: Literal['color','coloring'] = 'color'):
        root = artifact_root(pid)
        folder='coloring_svg_pages' if style=='coloring' else 'svg_pages'
        if not (root/folder).exists():raise HTTPException(409,'Bấm Generate để tạo bản tự tô cho dự án này.')
        title = html.escape(project(pid)['name']) + (' — Bản tự tô' if style=='coloring' else ' — Bản màu')
        sheets = ''.join('<section class="sheet">'+re.sub(r'<\?xml[^>]*\?>', '', p.read_text())+'</section>' for p in sorted((root/folder).glob('*.svg')))
        document = '''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Print — '''+title+'''</title>
<style>@page{size:215.9mm 279.4mm;margin:0}*{box-sizing:border-box}body{margin:0;background:#e8ece7;font:14px system-ui}header{padding:16px;text-align:center;background:white}button{padding:10px 20px;cursor:pointer}.sheet{width:215.9mm;height:279.4mm;margin:12px auto;background:white;break-after:page;overflow:hidden}.sheet:last-child{break-after:auto}.sheet svg{display:block;width:215.9mm;height:279.4mm}@media print{header{display:none}body{background:white}.sheet{margin:0}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style>
<header><strong>'''+title+'''</strong><p>US Letter · Scale 100% · Không Fit to Page · Tắt headers/footers của trình duyệt. Đo vạch 40 mm trước khi cắt.</p><button onclick="window.print()">Print / In ngay</button></header>'''+sheets+'''<script>window.addEventListener('load',()=>{document.fonts.ready.then(()=>window.print())});</script></html>'''
        if project(pid)['paper'] == 'A4':
            document = document.replace('215.9mm','210mm').replace('279.4mm','297mm').replace('US Letter ·','A4 ·')
        return Response(document,media_type='text/html',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.get('/api/projects/{pid}/artifacts/{filename:path}')
    def artifact(pid: str, filename: str, download: bool = False):
        root = artifact_root(pid).resolve()
        target = (root / filename).resolve()
        if not target.is_relative_to(root) or not target.is_file() or target.is_symlink():
            raise HTTPException(404, 'Artifact not found')
        media = {'.svg': 'image/svg+xml', '.obj': 'text/plain'}.get(target.suffix) or mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        return FileResponse(target, media_type=media, filename=target.name if download else None, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    dist = ROOT / 'frontend/dist'
    if dist.exists():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app


app = create_app()
