"""Compact, deduplicated observation archive. Never stores credentials or headers."""
import datetime as dt
import json
import os
import sqlite3
import threading
from pathlib import Path

class TrainingStore:
    def __init__(self, root):
        self.path=Path(os.environ.get('TRAINING_DB_PATH',str(Path(root)/'runtime'/'training.sqlite3')))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock()
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS samples(kind TEXT, entity TEXT, observed REAL, payload TEXT, PRIMARY KEY(kind,entity,observed))')
    def record(self,kind,payload):
        rows=[]
        if kind=='eal':
            for t in payload.get('trains',[]):
                if not t.get('train_set_id'):continue
                stamp=t.get('updated_at')
                try:
                    date=dt.datetime.fromisoformat(stamp.replace('Z','+00:00'))
                    if date.tzinfo is None:date=date.replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
                    ts=date.timestamp()
                except (ValueError,TypeError,AttributeError):continue
                safe={k:t.get(k) for k in ['train_set_id','current_station','next_station','speed_kph','distance_prev_m','distance_next_m','vehicle_in_station','zero_velocity','updated_at']}
                rows.append((kind,str(t.get('train_set_id')),ts,json.dumps(safe,separators=(',',':'))))
        elif kind=='eta':
            for t in payload.get('observations',[]):
                try:ts=dt.datetime.fromisoformat(t['observed_at']).timestamp()
                except (KeyError,ValueError,TypeError):continue
                safe={k:t.get(k) for k in ['line','station','dest','direction','platform','seq','eta_sec','observed_at']}
                entity='|'.join(str(safe.get(k,'')) for k in ['line','station','direction','seq'])
                rows.append((kind,entity,ts,json.dumps(safe,separators=(',',':'))))
        if rows:
            with self.lock,sqlite3.connect(self.path) as db:db.executemany('INSERT OR IGNORE INTO samples VALUES(?,?,?,?)',rows)
    def status(self):
        with self.lock,sqlite3.connect(self.path) as db:
            rows=db.execute('SELECT kind,COUNT(*),MIN(observed),MAX(observed) FROM samples GROUP BY kind').fetchall()
        return {'sources':[dict(zip(['kind','rows','oldest','newest'],r)) for r in rows],
                'retention':'No automatic deletion; export and back up the configured database',
                'storage':'Requires a persistent TRAINING_DB_PATH volume in hosted deployments',
                'labels':'EAL telemetry can supply observed arrival labels; ETA rows are predictions, not measured arrivals'}
