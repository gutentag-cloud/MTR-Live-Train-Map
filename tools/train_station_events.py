"""Fit travel/dwell durations in seconds from observed station events, offline."""
import sys,json,sqlite3,statistics,csv,datetime as dt
from pathlib import Path
from contextlib import closing
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from station_events import telemetry_intervals,countdown_intervals,day
ROOT=Path(__file__).resolve().parents[1]

def train(rows):
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
    pending=sum(day(r['arrival_epoch'])>=today for r in rows)
    rows=[r for r in rows if day(r['arrival_epoch'])<today]
    dates=sorted({day(r['arrival_epoch']) for r in rows})
    training=[r for r in rows if len(dates)>1 and day(r['arrival_epoch'])<dates[-1] and day(r['observed_epoch'])==day(r['arrival_epoch'])]
    test=[r for r in rows if len(dates)>1 and day(r['arrival_epoch'])==dates[-1] and day(r['observed_epoch'])==dates[-1]]
    key=lambda r:f"{r['kind']}|{r['from_station']}|{r['to_station']}"
    buckets=defaultdict(list)
    for r in training:buckets[key(r)].append(r['seconds'])
    cells={k:{'seconds':statistics.median(v),'events':len(v)} for k,v in buckets.items() if len(v)>=5}
    metrics={}
    for kind in ('travel','dwell'):
        subset=[r for r in test if r['kind']==kind];supported=[r for r in subset if key(r) in cells]
        errors=[abs(cells[key(r)]['seconds']-r['seconds']) for r in supported]
        metrics[kind]={'test_events':len(subset),'supported_events':len(errors),'coverage':len(errors)/len(subset) if subset else 0,
            'mae_seconds':statistics.mean(errors) if errors else None,'p90_error_seconds':sorted(errors)[min(len(errors)-1,int(len(errors)*.9))] if errors else None}
    return {'cells':cells,'report':{'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'dates':dates,'events':len(rows),
        'excluded_in_progress_events':pending,'training_events':len(training),'test_date':dates[-1] if dates else None,'test':metrics,'deployed':False,
        'target':'travel: first moving sample after departure → first stopped sample at next station; dwell: first stopped → first moving',
        'limitations':'Telemetry transitions have up to 30s observation gaps. Error metrics cover supported segments only; coverage is reported. No exact one-second accuracy claim.'}}

def main():
    with closing(sqlite3.connect(ROOT/'runtime/training.sqlite3')) as db:
        rows=telemetry_intervals((ts,json.loads(p)) for ts,p in db.execute("select observed,payload from samples where kind='eal'"))
        # Only explicit countdowns qualify. Old archives omitted ttnt; never synthesize
        # a 1/0 state from the API's ETA timestamp to inflate training coverage.
        eta=[(ts,json.loads(p)) for ts,p in db.execute("select observed,payload from samples not indexed where kind='eta' and payload like '%\"ttnt\"%'")]
    countdown=countdown_intervals(eta);model=train(rows)
    model['report']['explicit_countdown_rows']=len(eta);model['report']['one_to_zero_events']=len(countdown)
    model['report']['one_to_zero_median_seconds']=statistics.median(r['seconds'] for r in countdown) if countdown else None
    model['report']['countdown_note']='Countdown disappearance is not a departure. Cross-station identity cannot be established from sequence numbers.'
    folder=ROOT/'runtime/training';folder.mkdir(parents=True,exist_ok=True)
    for name,values in [('station_intervals',rows),('countdown_intervals',countdown)]:
        fields=sorted({k for r in values for k in r})
        with (folder/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(values)
    (folder/'station_event_model.json').write_text(json.dumps(model,indent=2))
    (ROOT/'station_event_report.json').write_text(json.dumps(model['report'],indent=2))
    print(json.dumps(model['report'],indent=2))
if __name__=='__main__':main()
