"""Offline East Rail arrival experiment. No model is activated automatically."""
import csv
import datetime as dt
import json
import math
from contextlib import closing
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training_store import TrainingStore
ROOT = Path(__file__).resolve().parents[1]
HKT = dt.timezone(dt.timedelta(hours=8))
STATIONS = set('ADM EXC HUH MKK KOT TAW SHT FOT RAC UNI TAP TWO FAN SHS LOW LMC'.split())


def station(value):
    value = {'ADM_S': 'ADM', 'NHUH': 'HUH', 'HTD': 'RAC'}.get(value, value)
    return value if value in STATIONS else None


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def build_rows(samples):
    by_train = defaultdict(list)
    for ts, t in samples:
        if t.get('train_set_id') and number(ts) is not None:
            by_train[t['train_set_id']].append((ts, t))
    rows = []
    for train, items in by_train.items():
        pending, previous, edge = [], None, None
        for ts, t in sorted(items, key=lambda x: x[0]):
            if previous is not None and (ts <= previous or ts - previous > 30):
                pending, edge = [], None
            previous = ts
            a, b = station(t.get('current_station')), station(t.get('next_station'))
            before, after, speed = (number(t.get(k)) for k in ('distance_prev_m', 'distance_next_m', 'speed_kph'))
            if None in (before, after, speed) or min(before, after, speed) < 0 or speed > 140:
                pending, edge = [], None
                continue
            if t.get('vehicle_in_station') is True and speed < 3:
                # SSP distances can still describe the arriving segment. Once both
                # reset to zero, current_station names the station occupied.
                arrived = b if after <= 30 < before else a if before <= 30 and (after > 30 or before == after == 0) else None
                for start, p in pending:
                    remaining = ts - start
                    if arrived != p['to_station'] or not 0 < remaining <= 900:
                        continue
                    rows.append({**p, 'observed_epoch': start, 'arrival_epoch': ts,
                                 'run': f'{train}:{ts}', 'target_remaining_s': remaining,
                                 'label_source': 'first stopped telemetry sample; sampling gap <=30s'})
                pending, edge = [], None
                continue
            if not a or not b or a == b or not 100 <= before + after <= 15000 or after <= 0:
                pending, edge = [], None
                continue
            if edge != (a, b):
                pending = []  # Never label across an unobserved stop or reversal.
            edge = (a, b)
            p = {'from_station': a, 'to_station': b, 'fraction': before / (before + after),
                 'remaining_m': after, 'speed_kph': speed}
            pending.append((ts, p))
            pending = [x for x in pending if ts - x[0] <= 900]
    return rows


def day(ts):
    return dt.datetime.fromtimestamp(ts, HKT).date().isoformat()


def split_rows(rows):
    dates = sorted({day(r['arrival_epoch']) for r in rows})
    if len(dates) < 3:
        return rows, [], []
    # Entire dates are held out. Purge trips whose observations cross a boundary.
    validation, test = dates[-2:]
    parts = ([], [], [])
    crossing = {r['run'] for r in rows if day(r['observed_epoch']) != day(r['arrival_epoch'])}
    for r in rows:
        arrival_day = day(r['arrival_epoch'])
        if r['run'] in crossing:
            continue
        parts[2 if arrival_day == test else 1 if arrival_day == validation else 0].append(r)
    return parts


def cell_key(r, kind):
    key = f"{r['from_station']}|{r['to_station']}|{min(9, int(r['fraction'] * 10))}"
    return key + (f"|{min(4, int(r['speed_kph'] / 25))}" if kind == 'progress_speed' else '')


def fit(rows, kind):
    buckets = defaultdict(lambda: defaultdict(list))
    for r in rows:
        buckets[cell_key(r, kind)][r['run']].append(r['target_remaining_s'])
    # Each arrival group contributes once per cell, regardless of polling rate.
    return {k: {'seconds': statistics.median(statistics.median(v) for v in runs.values()),
                'journeys': len(runs)} for k, runs in buckets.items() if len(runs) >= 5}


def baseline(r):
    return min(900, r['remaining_m'] / max(1, r['speed_kph'] / 3.6))


def prediction(r, cells, kind, fallback):
    cell = cells.get(cell_key(r, kind))
    coarse = fallback.get(cell_key(r, 'progress'))
    return (cell or coarse or {}).get('seconds', baseline(r)), cell is not None


def percentile(values, q):
    return sorted(values)[min(len(values)-1, math.ceil(len(values)*q)-1)] if values else None


def evaluate(rows, cells, kind, fallback, interval=None):
    errors, base_errors, coarse_errors, covered, intervals = [], [], [], 0, 0
    by_run, by_segment = defaultdict(list), defaultdict(list)
    for r in rows:
        pred, supported = prediction(r, cells, kind, fallback)
        error = abs(pred - r['target_remaining_s'])
        errors.append(error); covered += supported
        base_errors.append(abs(baseline(r) - r['target_remaining_s']))
        coarse = fallback.get(cell_key(r, 'progress'), {}).get('seconds', baseline(r))
        coarse_errors.append(abs(coarse - r['target_remaining_s']))
        by_run[r['run']].append(error)
        by_segment[f"{r['from_station']} → {r['to_station']}"].append(error)
        intervals += interval is not None and error <= interval
    mean = lambda xs: statistics.mean(xs) if xs else None
    return {'rows': len(rows), 'journeys': len(by_run), 'mae_seconds': mean(errors),
            'journey_mae_seconds': mean([mean(v) for v in by_run.values()]),
            'p90_error_seconds': percentile(errors, .9),
            'coverage': covered / len(rows) if rows else 0,
            'constant_speed_mae_seconds': mean(base_errors), 'progress_baseline_mae_seconds': mean(coarse_errors),
            'interval_coverage': intervals / len(rows) if rows and interval is not None else None,
            'segments': {k: {'rows': len(v), 'mae_seconds': mean(v), 'p90_error_seconds': percentile(v, .9)} for k, v in sorted(by_segment.items())}}


def train(rows):
    training, validation, test = split_rows(rows)
    coarse = fit(training, 'progress')
    candidates = {kind: fit(training, kind) for kind in ('progress', 'progress_speed')}
    scores = {kind: evaluate(validation, cells, kind, coarse) for kind, cells in candidates.items()}
    kind = min(scores, key=lambda k: scores[k]['journey_mae_seconds'] if scores[k]['journey_mae_seconds'] is not None else math.inf)
    cells = candidates[kind]
    interval = scores[kind]['p90_error_seconds']
    metrics = evaluate(test, cells, kind, coarse, interval)
    dates = sorted({day(r['arrival_epoch']) for r in rows})
    reasons = []
    if len(dates) < 5: reasons.append('Fewer than five dates of labeled data')
    if scores[kind]['journeys'] < 100: reasons.append('Fewer than 100 validation arrival groups')
    if metrics['journeys'] < 100: reasons.append('Fewer than 100 held-out arrival groups')
    if metrics['coverage'] < .9: reasons.append('Less than 90% model support on held-out rows')
    if metrics['mae_seconds'] is None or metrics['mae_seconds'] >= metrics['constant_speed_mae_seconds'] * .9:
        reasons.append('Does not improve held-out constant-speed error by at least 10%')
    if metrics['interval_coverage'] is None or metrics['interval_coverage'] < .85:
        reasons.append('Validation-derived uncertainty interval covers less than 85% of test rows')
    report = {'schema_version': 2, 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'labeled_rows': len(rows), 'journeys': len({r['run'] for r in rows}), 'days': len(dates),
              'dates': dates, 'training_dates': sorted({day(r['arrival_epoch']) for r in training}),
              'validation_dates': sorted({day(r['arrival_epoch']) for r in validation}),
              'test_dates': sorted({day(r['arrival_epoch']) for r in test}),
              'test_rows': len(test), 'test_mae_seconds': metrics['mae_seconds'],
              'constant_speed_baseline_mae_seconds': metrics['constant_speed_mae_seconds'],
              'validation_candidates': scores, 'test': metrics, 'interval_half_width_seconds': interval,
              'eligible_for_review': not reasons, 'review_blockers': reasons, 'deployed': False,
              'split': 'Whole dates: latest test, preceding validation, earlier training; cross-midnight groups purged',
              'target': 'time to first stopped telemetry sample, not exact doors-open time',
              'scope': 'East Rail only; errors include unsupported rows using explicit fallback',
              'model': kind, 'weighting': 'One contribution per arrival group per training cell'}
    return {'report': report, 'cells': cells, 'fallback_cells': coarse}


def main():
    archive = TrainingStore(ROOT)
    history = ROOT / 'runtime/history.sqlite3'
    if history.exists():
        with closing(sqlite3.connect(history)) as db, db:
            for payload, in db.execute("SELECT payload FROM snapshots WHERE kind='eal' ORDER BY ts"):
                data = json.loads(payload)
                if data.get('ok') and not data.get('stale'): archive.record('eal', data)
    with closing(sqlite3.connect(archive.path)) as db, db:
        rows = build_rows((ts, json.loads(payload)) for ts, payload in db.execute("SELECT observed,payload FROM samples WHERE kind='eal' ORDER BY observed"))
    output = ROOT / 'runtime/training'; output.mkdir(parents=True, exist_ok=True)
    fields = ['from_station','to_station','fraction','remaining_m','speed_kph','observed_epoch','arrival_epoch','run','target_remaining_s','label_source']
    with (output / 'arrival_labels.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    model = train(rows)
    (output / 'arrival_model.json').write_text(json.dumps(model, indent=2))
    (ROOT / 'training_report.json').write_text(json.dumps(model['report'], indent=2))
    print(json.dumps({k:v for k,v in model['report'].items() if k not in ('test','validation_candidates')}, indent=2))

if __name__ == '__main__': main()
