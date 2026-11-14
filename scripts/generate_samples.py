"""Generate reviewable samples with the production adapter (not copied fixtures)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.worker import generate
for preset in ('cube_100', 'cube_200', 'cube_300', 'house_frame'):
    out = Path('output/samples') / preset
    if out.exists():
        raise SystemExit(f'{out} already exists: choose a fresh output location to preserve snapshots')
    generate({'project_id': 'sample-' + preset, 'revision': 1, 'preset': preset, 'paper': 'US Letter', 'scale': 1.0, 'engine_version': '1.2.0'}, out, print)
