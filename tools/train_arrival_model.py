"""Backfill telemetry archive, derive observed-arrival labels, validate a learned baseline.
No model is deployed automatically. ETA predictions never serve as ground truth.
"""
import csv, datetime as dt, json, math, sqlite3, statistics, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from training_store import TrainingStore
ROOT=Path(__file__).resolve().parents[1]

def build_rows(samples):
    by_train=defaultdict(list)
    for ts,t in samples:by_train[t['train_set_id']].append((ts,t))
    rows=[]
    for train,items in by_train.items():
        items.sort(key=lambda x:x[0]);pending=[];previous=None
        for ts,t in items:
            if previous is not None and ts-previous>30:pending=[]
            previous=ts
            if t.get('vehicle_in_station') and (t.get('speed_kph') or 0)<3:
                station=t.get('current_station')
                for start,p in pending:
                    remaining=ts-start
                    if p.get('next_station')!=station or not 0<remaining<=900:continue
                    before=p.get('distance_prev_m') or 0;after=p.get('distance_next_m') or 0
                    if before<0 or after<=0 or before+after<=0:continue
                    rows.append({'observed_epoch':start,'arrival_epoch':ts,'run':f'{train}:{ts}',
                        'from_station':p.get('current_station'),'to_station':station,
                        'fraction':before/(before+after),'remaining_m':after,'speed_kph':p.get('speed_kph') or 0,
                        'target_remaining_s':remaining,'label_source':'first stopped telemetry sample; up to 30s sampling gap'})
                pending=[]
            elif t.get('current_station') and t.get('next_station') and t['current_station']!=t['next_station']:
                pending.append((ts,t));pending=[x for x in pending if ts-x[0]<=900]
    return rows

def train(rows):
    runs=sorted({r['run'] for r in rows},key=lambda key:float(key.rsplit(':',1)[1]));cut=max(1,int(len(runs)*.8));train_runs=set(runs[:cut]);buckets=defaultdict(list)
    key=lambda r:f"{r['from_station']}|{r['to_station']}|{min(9,int(r['fraction']*10))}"
    for r in rows:
        if r['run'] in train_runs:buckets[key(r)].append(r['target_remaining_s'])
    model={k:{'seconds':statistics.median(v),'samples':len(v)} for k,v in buckets.items() if len(v)>=5}
    errors=[];baseline=[]
    for r in rows:
        if r['run'] in train_runs:continue
        cell=model.get(key(r))
        if not cell:continue
        errors.append(abs(cell['seconds']-r['target_remaining_s']))
        baseline.append(abs(min(900,r['remaining_m']/max(1,r['speed_kph']/3.6))-r['target_remaining_s']))
    days=len({dt.datetime.fromtimestamp(r['observed_epoch'],dt.timezone(dt.timedelta(hours=8))).date() for r in rows})
    mae=statistics.mean(errors) if errors else None;base=statistics.mean(baseline) if baseline else None
    report={'labeled_rows':len(rows),'journeys':len(runs),'days':days,'test_rows':len(errors),
        'test_mae_seconds':mae,'constant_speed_baseline_mae_seconds':base,
        'eligible_for_review':bool(days>=3 and len(errors)>=100 and mae<base*.9),
        'deployed':False,'split':'chronological 80/20 by complete journey; no journey in both partitions',
        'target':'time to first stopped telemetry sample, not exact doors-open time',
        'scope':'East Rail only; sampled telemetry labels, not GPS',
        'model':'median remaining time by directed station pair and progress decile'}
    return {'report':report,'cells':model}

def main():
    archive=TrainingStore(ROOT)
    history=ROOT/'runtime/history.sqlite3'
    if history.exists():
        with sqlite3.connect(history) as db:
            for payload, in db.execute("SELECT payload FROM snapshots WHERE kind='eal' ORDER BY ts"):
                data=json.loads(payload)
                if data.get('ok') and not data.get('stale'):archive.record('eal',data)
    with sqlite3.connect(archive.path) as db:
        rows=build_rows((ts,json.loads(payload)) for ts,payload in db.execute("SELECT observed,payload FROM samples WHERE kind='eal' ORDER BY observed"))
    output=ROOT/'runtime/training';output.mkdir(parents=True,exist_ok=True)
    if rows:
        with (output/'arrival_labels.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    model=train(rows);(output/'arrival_model.json').write_text(json.dumps(model,indent=2));print(json.dumps(model['report'],indent=2))
if __name__=='__main__':main()
