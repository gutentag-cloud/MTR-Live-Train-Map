"""Regenerate optimized map assets and the Light Rail-only timetable bundle."""
from pathlib import Path
import json
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
for name in ('geotd-map-3200', 'geotd-map-6000', 'light-rail-map'):
    Image.open(ROOT / 'assets' / f'{name}.png').convert('RGB').save(
        ROOT / 'assets' / f'{name}.webp', lossless=True, method=6)
preview = Image.open(ROOT / 'assets/geotd-map-3200.png')
preview.thumbnail((1600, 1600))
preview.save(ROOT / 'assets/geotd-map-preview.webp', quality=85, method=6)
data = json.loads((ROOT / 'data.js').read_text().split('=', 1)[1].rstrip(';\n'))
ids = {p['lines']['LRL'] for p in data['profiles'].values()}
lite = {k: data[k] for k in ('profiles', 'map', 'speedModel')}
lite['schedules'] = {k: data['schedules'][k] for k in ids}
lite['trackRoutes'] = {'LRL': data['trackRoutes']['LRL']}
(ROOT / 'light_rail_schedule.js').write_text('window.TRAIN_DATA=' + json.dumps(lite, separators=(',', ':')) + ';\n')
