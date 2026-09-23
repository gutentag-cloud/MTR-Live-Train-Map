#!/usr/bin/env python3
"""Serve HK Train Display v12 preview with telemetry, ETA fusion, weather/geodata overlays, WTT fallback and local replay history.

Live hierarchy:
  * EAL: RocTec TMS telemetry (HAR-discovered API key, server-side only)
  * Heavy rail: official MTR Next Train API, matched to supplied WTT trips
  * Light Rail: official MTR Light Rail Next Train API, exposed for the dedicated map

No upstream credential is served to the browser.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import functools
import gzip
import http.server
import json
import os
from pathlib import Path
import statistics
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

from v12_backend import V12Backend
from arrival_model import refine_arrivals
from training_store import TrainingStore

ROOT = Path(__file__).resolve().parent
EAL_DEFAULT_URL = "https://uonfjf884h.execute-api.ap-east-1.amazonaws.com/prod/api/TableViewer/getAllTrainStatusesValueV3"
MTR_API = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"
LRT_API = "https://rt.data.gov.hk/v1/transport/mtr/lrt/getSchedule"

# Live-feed performance controls.  The official feeds update every ~10 s, so the
# server refreshes at that cadence but fetches independent station endpoints in
# parallel.  Short per-request timeouts prevent one bad station from blocking a
# whole-network refresh.
HTTP_TIMEOUT_SEC = 2.5
HEAVY_WORKERS = 18
LRT_WORKERS = 12
STATION_CACHE_SEC = 120


# Strategic timing points. A full-network all-station poll would be unnecessarily
# aggressive; these give multiple anchors per corridor while staying polite.
HEAVY_STATIONS = {
    "TML": ["TUM","SIH","TIS","YUL","KSR","TWW","MEF","HUH","TAW","MOS","WKS"],
    "TWL": ["TSW","LCK","MEF","PRE","ADM","CEN"],
    "ISL": ["KET","NOP","TIH","CAB","ADM","CEN"],
    "KTL": ["WHA","HOM","KOT","DIH","KWT","TIK"],
    "TKL": ["NOP","YAT","TIK","TKO","LHP","POA"],
    "SIL": ["ADM","OCP","WCH","LET","SOH"],
    "TCL": ["HOK","KOW","OLY","NAC","LAK","TSY","SUN","TUC"],
    "AEL": ["HOK","KOW","TSY","AIR","AWE"],
    "DRL": ["SUN","DIS"],
}

# Two high-yield anchors per line are fetched first.  This makes a usable ETA
# solution available quickly while the rest of the network continues loading.

# Full public station catalogue for on-demand boards. The network-wide matcher still
# polls the smaller HEAVY_STATIONS anchor set above so startup remains fast.
BOARD_STATIONS = {
    "TWL": ["TSW","TWH","KWH","KWF","LAK","MEF","LCK","CSW","SSP","PRE","MOK","YMT","JOR","TST","ADM","CEN"],
    "ISL": ["KET","HKU","SYP","SHW","CEN","ADM","WAC","CAB","TIH","FOH","NOP","QUB","TAK","SWH","SKW","HFC","CHW"],
    "KTL": ["TIK","YAT","LAT","KWT","NTK","KOB","CHH","DIH","WTS","LOF","KOT","SKM","PRE","MOK","YMT","HOM","WHA"],
    "TKL": ["NOP","QUB","YAT","TIK","TKO","HAH","POA","LHP"],
    "SIL": ["ADM","OCP","WCH","LET","SOH"],
    "TML": ["TUM","SIH","TIS","LOP","YUL","KSR","TWW","MEF","NAC","AUS","ETS","HUH","HOM","TKW","SUW","KAT","DIH","HIK","TAW","CKT","STW","CIO","SHM","TSH","HEO","MOS","WKS"],
    "EAL": ["ADM","EXC","HUH","MKK","KOT","TAW","SHT","FOT","RAC","UNI","TAP","TWO","FAN","SHS","LOW","LMC"],
    "TCL": ["HOK","KOW","OLY","NAC","LAK","TSY","SUN","TUC"],
    "AEL": ["HOK","KOW","TSY","AIR","AWE"],
    "DRL": ["SUN","DIS"],
}

HEAVY_BOOTSTRAP = {
    "TML": ["HUH", "TAW"],
    "TWL": ["MEF", "ADM"],
    "ISL": ["ADM", "CAB"],
    "KTL": ["KOT", "DIH"],
    "TKL": ["TIK", "TKO"],
    "SIL": ["ADM", "WCH"],
    "TCL": ["TSY", "NAC"],
    "AEL": ["TSY", "AIR"],
    "DRL": ["SUN", "DIS"],
}

# Spread across the LRT network, including key junctions / termini. The dedicated
# map calls the same public API and labels its markers as arrival-inferred.
LRT_STATIONS = [
    "001","040","070","100","140","160","200","230","250","280","295",
    "310","340","370","400","430","450","480","500","530","550","570",
    "590","600","920",
]


def hk_now():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))


def sec_of_day(x: dt.datetime) -> int:
    return x.hour * 3600 + x.minute * 60 + x.second


def parse_hk_timestamp(text: str | None):
    if not text or text == "-":
        return None
    try:
        return dt.datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
    except Exception:
        return None


def get_json(url, headers=None, timeout=6):
    req = urllib.request.Request(url, headers=headers or {"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_from_har(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data.get("log", {}).get("entries", []):
        req = entry.get("request", {})
        url = req.get("url", "")
        if "getAllTrainStatusesValueV3" not in url:
            continue
        headers = {h.get("name", "").lower(): h.get("value", "") for h in req.get("headers", [])}
        key = headers.get("xapikey") or headers.get("x-api-key")
        if key:
            return url, key
    raise RuntimeError("Could not find the EAL TMS train-status request/API key in the HAR.")


def as_float(v, default=0.0):
    try: return float(v)
    except (TypeError, ValueError): return default


def as_bool(v):
    return str(v).strip() == "1" or v is True


def active_cab(row):
    for cab in ("C01", "C10"):
        if as_bool(row.get(f"#{cab} OBCU active")): return cab
    for cab in ("C01", "C10"):
        if as_bool(row.get(f"#{cab} Cab Active")): return cab
    return "C01"


def normalize_eal(payload):
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    trains, newest = [], None
    for row in rows:
        cab = active_cab(row)
        updated = row.get("updated_display_time")
        if updated and (newest is None or updated > newest): newest = updated
        trains.append({
            "train_set_id": row.get("train_set_id"), "td": row.get("td"),
            "destination": row.get("destination"), "current_station": row.get("current_station"),
            "next_station": row.get("next_station"), "updated_at": updated,
            "speed_kph": as_float(row.get(f"{cab} Current Speed (KMH)")),
            "distance_prev_m": as_float(row.get(f"{cab} Distance to previous SSP (M)")),
            "distance_next_m": as_float(row.get(f"{cab} Distance to next SSP (M)")),
            "powering": as_bool(row.get(f"#{cab} Powering")), "braking": as_bool(row.get(f"#{cab} Braking")),
            "forward": as_bool(row.get(f"#{cab} Forward")), "reverse": as_bool(row.get(f"#{cab} Reverse")),
            "ato_mode": as_bool(row.get(f"#{cab} ATO mode")),
            "vehicle_in_station": as_bool(row.get(f"#{cab} OBCU Vehicle in Station")),
            "zero_velocity": as_bool(row.get(f"#{cab} Zero Velocity Relay")),
            "has_fault": bool(row.get("has_fault")), "alarm_count": int(row.get("alarm_count") or 0),
            "active_cab": cab,
        })
    return {"ok": payload.get("status") == 0 if isinstance(payload, dict) else False,
            "source":"EAL TMS","upstream_updated_at":newest,"fetched_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "train_count":len(trains),"trains":trains}


class CachedSource:
    def __init__(self):
        self.lock = threading.Lock(); self.data = None; self.updated = 0.0
    def set(self, data):
        with self.lock: self.data = data; self.updated = time.time()
    def get(self):
        with self.lock:
            if self.data is None: return {"ok":False,"loading":True}
            return dict(self.data)


class HistoryStore:
    """Small persistent rolling store for sanitized live snapshots.

    The file contains only normalized API output used by this app. It never stores
    the EAL upstream credential or HAR headers. Rows older than retention_hours are
    pruned opportunistically.
    """
    def __init__(self, root: Path, retention_hours=24):
        self.path=root/"runtime"/"history.sqlite3"
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.training=TrainingStore(root)
        self.retention_hours=retention_hours
        self.lock=threading.Lock()
        self._last={}
        self._last_vacuum=time.time()
        with sqlite3.connect(self.path) as db:
            # Pruned rows only free pages inside the file; without auto_vacuum a 24 h window
            # of ~80 MB grew to a ~480 MB file. Converting an existing file needs one VACUUM.
            if db.execute("PRAGMA auto_vacuum").fetchone()[0]!=2:
                db.execute("PRAGMA auto_vacuum=INCREMENTAL")
                db.isolation_level=None
                db.execute("VACUUM")
            db.execute("CREATE TABLE IF NOT EXISTS snapshots (ts REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_kind_ts ON snapshots(kind,ts)")
    VACUUM_INTERVAL=600
    def record(self, kind, payload, min_interval=8):
        now=time.time()
        if now-self._last.get(kind,0)<min_interval:return
        if kind=="eal":self.training.record(kind,payload)
        safe=dict(payload)
        safe.pop("error",None)
        with self.lock, sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO snapshots(ts,kind,payload) VALUES(?,?,?)",(now,kind,json.dumps(safe,separators=(",",":"),ensure_ascii=False)))
            db.execute("DELETE FROM snapshots WHERE ts<?",(now-self.retention_hours*3600,))
            if now-self._last_vacuum>=self.VACUUM_INTERVAL:
                db.commit()
                db.execute("PRAGMA incremental_vacuum").fetchall()  # steps once per freed page
                self._last_vacuum=now
        self._last[kind]=now
    def query(self, minutes=30, kinds=None, limit=5000, since=0.0):
        minutes=max(1,min(24*60,int(minutes)))
        start=max(float(since or 0.0), time.time()-minutes*60)
        kinds=[x for x in (kinds or ["eal","rail","lrt"]) if x in {"eal","rail","lrt"}]
        if not kinds:return []
        qs=','.join('?' for _ in kinds)
        args=[start,*kinds,limit]
        with self.lock, sqlite3.connect(self.path) as db:
            rows=db.execute(f"SELECT ts,kind,payload FROM snapshots WHERE ts>=? AND kind IN ({qs}) ORDER BY ts ASC LIMIT ?",args).fetchall()
        out=[]
        for ts,kind,payload in rows:
            try: data=json.loads(payload)
            except Exception: continue
            out.append({"ts":ts,"kind":kind,"data":data})
        return out
    def status(self):
        with self.lock, sqlite3.connect(self.path) as db:
            row=db.execute("SELECT COUNT(*),MIN(ts),MAX(ts) FROM snapshots").fetchone()
        return {"rows":row[0] or 0,"oldest":row[1],"newest":row[2],"retention_hours":self.retention_hours}

class EalSource(CachedSource):
    """Background-polled EAL source so browser requests never wait on RocTec."""
    def __init__(self, url, key, history=None):
        super().__init__(); self.url=url; self.key=key; self.history=history

    def refresh(self):
        headers={"Accept":"application/json, text/plain, */*","Origin":"https://eal-tms.rocteccloud.com",
                 "Referer":"https://eal-tms.rocteccloud.com/","User-Agent":"Mozilla/5.0","xapikey":self.key}
        try:
            out=normalize_eal(get_json(self.url, headers=headers, timeout=HTTP_TIMEOUT_SEC))
            if out.get("ok"):
                self.set(out)
                if self.history:self.history.record("eal",out,min_interval=8)
            return out
        except Exception as exc:
            old=self.get()
            if old.get("ok"):
                old["stale"]=True
                old["error"]=f"upstream unavailable; cached ({type(exc).__name__})"
                # Do not rewrite fetched_at: the browser can age the last real sample correctly.
                self.set(old); return old
            out={"ok":False,"error":f"EAL TMS unavailable ({type(exc).__name__})","trains":[]}
            self.set(out); return out

    def loop(self):
        while True:
            started=time.time(); self.refresh()
            time.sleep(max(.5,2-(time.time()-started)))


class TimetableMatcher:
    def __init__(self, root: Path):
        raw=(root/"data.js").read_text(encoding="utf-8").strip()
        if raw.startswith("window.TRAIN_DATA="): raw=raw[len("window.TRAIN_DATA="):]
        raw=raw.rstrip(";")
        self.d=json.loads(raw)
        self._index_cache={}

    def profile_key(self):
        # Railway service day rolls over at 04:00, matching the browser/WTT model.
        now=hk_now()
        if now.hour<4:now-=dt.timedelta(days=1)
        w=now.weekday() # Mon=0
        return "friday" if w==4 else "saturday" if w==5 else "sunday" if w==6 else "weekday"

    @staticmethod
    def trip_key(t): return f"{t[1]}|{t[0]}|{t[2][0][1]}"

    def trips(self, line):
        p=self.d["profiles"][self.profile_key()]
        sid=p["lines"].get(line)
        return self.d["schedules"].get(sid,[]) if sid else []

    def station_index(self, line):
        """Index WTT timing events once per profile/line instead of rescanning every trip.

        This changes ETA matching from hundreds of millions of Python-level timing-point
        comparisons per sweep to a small station-local search.
        """
        profile=self.profile_key(); ck=(profile,line)
        if ck in self._index_cache:return self._index_cache[ck]
        idx={}
        for t in self.trips(line):
            pts=t[2]; final=pts[-1][0] if pts else ""
            key=self.trip_key(t)
            for i,(code,sched) in enumerate(pts):
                idx.setdefault(code,[]).append({"trip":t,"key":key,"sched":sched,"idx":i,
                    "final":final,"remaining":set(x[0] for x in pts[i:])})
        self._index_cache[ck]=idx
        return idx

    @staticmethod
    def _nearest_sched(sched, eta):
        ss=sched
        while ss < eta-43200:ss+=86400
        while ss > eta+43200:ss-=86400
        return ss

    def estimate_line_offsets(self, observations):
        by_line={}
        for o in observations: by_line.setdefault(o["line"],[]).append(o)
        out={}
        for line,obs in by_line.items():
            idx=self.station_index(line)
            choices=[]
            for o in obs:
                events=idx.get(o["station"],[])
                dest=o.get("dest") or ""
                preferred=[e for e in events if not dest or dest in e["remaining"]]
                if preferred:events=preferred
                deltas=[]
                for e in events:
                    ss=self._nearest_sched(e["sched"],o["eta_sec"])
                    d=o["eta_sec"]-ss
                    if -1200<=d<=1500:deltas.append(d)
                if deltas:choices.append(deltas)
            if not choices:continue
            candidates=[]
            for delay in range(-600,901,15):
                residuals=[min(abs(d-delay) for d in opts) for opts in choices]
                residuals.sort(); keep=residuals[:max(3,int(len(residuals)*.8))]
                cost=sum(keep)/len(keep)
                candidates.append((cost,abs(delay),delay))
            candidates.sort(); cost,_,delay=candidates[0]
            out[line]={"delay_sec":delay,"mean_residual_sec":round(cost,1),"samples":len(choices),
                       "confidence":"high" if cost<=25 and len(choices)>=6 else "medium" if cost<=60 else "low"}
        return out

    def match(self, observations, line_offsets=None):
        samples={}; by_group={}
        for o in observations:by_group.setdefault((o["line"],o["station"],o["direction"]),[]).append(o)
        for (line,sta,direction),obs in by_group.items():
            events=self.station_index(line).get(sta,[])
            used=set()
            for o in sorted(obs,key=lambda x:x["eta_sec"]):
                best=None; dest=o.get("dest") or ""
                for e in events:
                    key=e["key"]
                    if key in used:continue
                    ss=self._nearest_sched(e["sched"],o["eta_sec"]); delta=o["eta_sec"]-ss
                    if abs(delta)>1200:continue
                    if dest and e["final"]!=dest:continue
                    score=abs(delta)
                    if best is None or score<best[0]:best=(score,key,delta,e)
                if best:
                    _,key,delta,e=best; used.add(key)
                    samples.setdefault(key,[]).append({"delay":delta,"station":sta,"eta":o["eta"],
                        "dest":dest,"direction":direction,"platform":o.get("platform"),"ttnt":o.get("ttnt")})
        corr={}
        for key,arr in samples.items():
            vals=[x["delay"] for x in arr]; med=int(round(statistics.median(vals)))
            spread=max(vals)-min(vals) if len(vals)>1 else 0
            line=key.split("|",1)[0]; base=(line_offsets or {}).get(line,{}).get("delay_sec")
            agrees=base is None or abs(med-base)<=90
            conf="high" if len(vals)>=2 and spread<=75 and agrees else "medium" if len(vals)>=1 and agrees else "low"
            corr[key]={"delay_sec":med,"samples":len(vals),"spread_sec":spread,"confidence":conf,
                       "agrees_with_line":agrees,"anchors":arr[:6]}
        return corr


class HeavyRailSource(CachedSource):
    def __init__(self, matcher, history=None):
        super().__init__(); self.matcher=matcher; self.history=history
        self.station_cache={}; self.board_cache={}; self.board_lock=threading.Lock(); self.cycle=0

    def _fetch_station(self,line,sta):
        url=MTR_API+"?"+urllib.parse.urlencode({"line":line,"sta":sta,"lang":"en"})
        try:
            j=get_json(url,timeout=HTTP_TIMEOUT_SEC)
            if j.get("status")!=1:
                return line,sta,[],None,f"status={j.get('status')}"
            obs=[]; block=(j.get("data") or {}).get(f"{line}-{sta}",{})
            for direction in ("UP","DOWN"):
                for row in block.get(direction,[]) or []:
                    if row.get("valid") not in (None,"Y"):continue
                    when=parse_hk_timestamp(row.get("time"))
                    if not when:continue
                    eta=sec_of_day(when); now_dt=hk_now(); now=sec_of_day(now_dt)
                    if now_dt.hour < 4: eta+=86400
                    elif eta < now-6*3600:eta+=86400
                    obs.append({"line":line,"station":sta,"direction":direction,"dest":row.get("dest"),
                        "platform":row.get("plat"),"seq":row.get("seq"),"ttnt":row.get("ttnt"),
                        "eta":row.get("time"),"eta_sec":eta,"observed_at":dt.datetime.now(dt.timezone.utc).isoformat(),"upstream_time":block.get("curr_time") or j.get("sys_time")})
            return line,sta,obs,j.get("sys_time") or j.get("curr_time"),None
        except Exception as exc:
            return line,sta,[],None,type(exc).__name__

    def _refresh_board_background(self, lines, station):
        if not lines:return
        def work():
            with ThreadPoolExecutor(max_workers=min(6,len(lines)),thread_name_prefix="mtr-board-bg") as pool:
                futs=[pool.submit(self._fetch_station,line,station) for line in lines]
                for fut in as_completed(futs):
                    line,sta,obs,sys_time,err=fut.result()
                    if err is None:
                        ts=time.time()
                        with self.board_lock:self.board_cache[(line,sta)]={"ts":ts,"observations":obs,"sys_time":sys_time}
                        self.station_cache[(line,sta)]={"observations":obs,"sys_time":sys_time,"ts":ts}
        threading.Thread(target=work,daemon=True,name=f"mtr-board-{station}").start()

    def station_board(self, lines, station, max_age=8):
        """Fetch one selected station on demand for a live, second-resolution estimated board.

        Uses the official MTR Next Train API directly and reuses a short local cache so
        opening the board does not wait for the network-wide ETA fusion cycle. Successful
        responses are also inserted into station_cache and therefore improve the main ETA
        matcher on its next publish.
        """
        now=time.time(); lines=[x for x in dict.fromkeys(lines or []) if x and x != "LRL"]
        valid=[]
        for line in lines:
            if station in BOARD_STATIONS.get(line,[]):
                valid.append(line); continue
            try:
                if station in self.matcher.station_index(line): valid.append(line)
            except Exception:
                continue
        if not valid:
            return {"ok":False,"station":station,"observations":[],"error":"No WTT service for the requested line/station"}
        out=[]; errors=[]; fetched=[]; cached=[]
        todo=[]; refresh_later=[]
        with self.board_lock:
            for line in valid:
                ent=self.board_cache.get((line,station))
                if ent and now-ent["ts"] <= max_age:
                    out.extend(ent["observations"]); cached.append(line); continue
                sent=self.station_cache.get((line,station))
                if sent and now-sent["ts"] <= 30:
                    out.extend(sent["observations"]); cached.append(line); refresh_later.append(line); continue
                todo.append(line)
        # A recent network-worker sample is returned immediately; refresh happens after the response.
        if out and refresh_later:self._refresh_board_background(refresh_later,station)
        if todo and not out:
            with ThreadPoolExecutor(max_workers=min(6,len(todo)),thread_name_prefix="mtr-board") as pool:
                futs=[pool.submit(self._fetch_station,line,station) for line in todo]
                for fut in as_completed(futs):
                    line,sta,obs,sys_time,err=fut.result()
                    if err is None:
                        ts=time.time()
                        with self.board_lock:self.board_cache[(line,sta)]={"ts":ts,"observations":obs,"sys_time":sys_time}
                        self.station_cache[(line,sta)]={"observations":obs,"sys_time":sys_time,"ts":ts}
                        out.extend(obs); fetched.append(line)
                    else: errors.append(f"{line}-{sta}:{err}")
        elif todo:
            self._refresh_board_background(todo,station)
        # If a direct board fetch fails, use a still-valid station cache rather than blanking the board.
        if not out:
            for line in valid:
                ent=self.station_cache.get((line,station))
                if ent and now-ent["ts"] <= STATION_CACHE_SEC:
                    out.extend(ent["observations"]); cached.append(line)
        live=self.get() or {}
        try:
            age=time.time()-dt.datetime.fromisoformat(live.get("fetched_at") or "").timestamp()
        except (ValueError, TypeError):
            age=float("inf")
        offsets=(live.get("line_offsets") or {}) if 0<=age<=60 else {}
        out=refine_arrivals(out,self.matcher,offsets)
        out.sort(key=lambda x:x.get("estimated_eta_sec",x.get("eta_sec",10**9)))
        return {"ok":bool(out),"station":station,"lines":valid,"observations":out,
                "fetched_lines":fetched,"cached_lines":list(dict.fromkeys(cached)),"errors":errors[:10],
                "fetched_at":dt.datetime.now(dt.timezone.utc).isoformat(),"server_epoch":time.time(),
                "precision":"official estimate; seconds shown only for constrained model matches","source":"MTR official Next Train API + WTT phase model",
                "accuracy_note":"Official times are estimates. Model seconds require an unambiguous timetable match and fresh live delay within 30 seconds of the official time; no measured accuracy improvement is claimed."}

    def _run_batch(self,targets,fresh_keys,errors,completed,total,started,phase,on_progress=None):
        if not targets:return completed
        with ThreadPoolExecutor(max_workers=min(HEAVY_WORKERS,len(targets)),thread_name_prefix="mtr-eta") as pool:
            futs=[pool.submit(self._fetch_station,line,sta) for line,sta in targets]
            for fut in as_completed(futs):
                line,sta,obs,sys_time,err=fut.result(); completed+=1; key=(line,sta)
                if err is None:
                    self.station_cache[key]={"observations":obs,"sys_time":sys_time,"ts":time.time()}
                    fresh_keys.add(key)
                else:
                    errors.append(f"{line}-{sta}:{err}")
                if on_progress:on_progress(completed)
        return completed

    def _publish(self,fresh_keys,errors,phase,completed,total,started,partial):
        now=time.time(); observations=[]; cached_used=0; station_ages={}
        for key,entry in list(self.station_cache.items()):
            age=now-entry["ts"]
            if age>30:continue
            observations.extend(entry["observations"]); station_ages[f"{key[0]}-{key[1]}"]=round(age,1)
            if key not in fresh_keys:cached_used+=1
        if self.history:self.history.training.record("eta",{"observations":observations})
        line_offsets=self.matcher.estimate_line_offsets(observations) if observations else {}
        corrections_full=self.matcher.match(observations,line_offsets) if observations else {}
        corrections={k:{f:v for f,v in e.items() if f!="anchors"} for k,e in corrections_full.items()}
        by_line={}
        for k,v in corrections.items():
            if v.get("confidence") in ("high","medium"):
                line=k.split("|",1)[0]; by_line[line]=by_line.get(line,0)+1
        fresh_ts=[self.station_cache[k]["ts"] for k in fresh_keys if k in self.station_cache]
        fetched_epoch=max(fresh_ts) if fresh_ts else max((x["ts"] for x in self.station_cache.values()),default=0)
        fetched_at=dt.datetime.fromtimestamp(fetched_epoch,dt.timezone.utc).isoformat() if fetched_epoch else None
        out={"ok":bool(observations),"source":"MTR official Next Train API","fetched_at":fetched_at,
             "profile":self.matcher.profile_key(),"observation_count":len(observations),"corrections":corrections,
             "line_offsets":line_offsets,"matched_by_line":by_line,"errors":errors[:20],"api_update_frequency_sec":10,
             "partial":bool(partial),"phase":phase,"cycle":self.cycle,"completed_requests":completed,
             "total_requests":total,"fresh_station_count":len(fresh_keys),"cached_station_count":cached_used,
             "failed_request_count":len(errors),"cycle_elapsed_ms":round((time.time()-started)*1000),
             "worker_count":HEAVY_WORKERS,"request_timeout_sec":HTTP_TIMEOUT_SEC}
        if observations and not fresh_keys:
            out["stale"]=True
            out["error"]="All current ETA requests failed; using station cache until it ages out"
        if not observations:
            out["error"]=f"No usable ETA observations yet ({len(errors)} request failures in {phase})"
        if observations:self.set(out)
        elif self.get().get("ok"):
            old=self.get(); old["stale"]=True; old["error"]="No usable MTR ETA observations in current sweep; retaining last good snapshot"; self.set(old)
        else:self.set(out)
        return out

    def refresh(self):
        self.cycle+=1; started=time.time(); fresh_keys=set(); errors=[]
        previous=self.get(); previous_recent=False
        if previous.get("ok") and previous.get("fetched_at"):
            try:
                age=time.time()-dt.datetime.fromisoformat(previous["fetched_at"]).timestamp()
                previous_recent=age<30
            except Exception:pass
        all_targets=[(line,sta) for line,stations in HEAVY_STATIONS.items() for sta in stations]
        bootstrap=[]
        for line,stations in HEAVY_BOOTSTRAP.items():bootstrap.extend((line,sta) for sta in stations)
        # Deduplicate while preserving order.
        bootstrap=list(dict.fromkeys(bootstrap)); bootset=set(bootstrap)
        remainder=[x for x in all_targets if x not in bootset]
        total=len(all_targets); completed=0
        # Publish a diagnostic state immediately instead of an opaque "warming up".
        if self.data is None:
            self.set({"ok":False,"loading":True,"phase":"bootstrap","cycle":self.cycle,
                "completed_requests":0,"total_requests":total,"fresh_station_count":0,
                "corrections":{},"line_offsets":{},"matched_by_line":{},
                "started_at":dt.datetime.now(dt.timezone.utc).isoformat()})
        fast_published=False
        def bootstrap_progress(done):
            nonlocal fast_published
            if previous_recent or fast_published:return
            covered={line for line,_ in fresh_keys}
            # Publish as soon as several lines have useful anchors; unmatched lines remain WTT.
            if len(covered)>=5 or done>=10:
                self._publish(fresh_keys,errors,"bootstrap-fast",done,total,started,partial=True)
                fast_published=True
        completed=self._run_batch(bootstrap,fresh_keys,errors,completed,total,started,"bootstrap",bootstrap_progress)
        # Fast-start only when there is no recent complete snapshot.  During normal 10 s
        # refreshes we keep the previous full solution visible to avoid ETA/WTT flicker.
        if not previous_recent:
            self._publish(fresh_keys,errors,"bootstrap-complete",completed,total,started,partial=True)
        # Continue with the remaining station anchors; on cold start the browser can already use bootstrap ETA.
        completed=self._run_batch(remainder,fresh_keys,errors,completed,total,started,"full")
        out=self._publish(fresh_keys,errors,"complete",completed,total,started,partial=False)
        if out.get("ok") and self.history:self.history.record("rail",out,min_interval=8)

    def loop(self):
        while True:
            started=time.time()
            try:self.refresh()
            except Exception as exc:
                old=self.get()
                if old.get("ok"):
                    old["stale"]=True; old["error"]=f"rail refresh failed; retaining last good ETA snapshot ({type(exc).__name__})"
                    old["refresh_failed_at"]=dt.datetime.now(dt.timezone.utc).isoformat(); self.set(old)
                else:self.set({"ok":False,"error":f"rail refresh failed: {type(exc).__name__}","corrections":{},"line_offsets":{}})
            time.sleep(max(1,10-(time.time()-started)))


class LightRailSource(CachedSource):
    def __init__(self, history=None):
        super().__init__(); self.history=history; self.station_cache={}

    def _fetch_station(self,sta):
        url=LRT_API+"?"+urllib.parse.urlencode({"station_id":int(sta),"with_special":1})
        try:
            j=get_json(url,timeout=HTTP_TIMEOUT_SEC)
            if j.get("status")!=1:return sta,[],None,f"status={j.get('status')}"
            rows=[]
            for plat in j.get("platform_list",[]) or []:
                pid=plat.get("platform_id")
                for row in plat.get("route_list",[]) or []:
                    rows.append({"station_id":sta,"platform_id":pid,"route_no":row.get("route_no"),
                        "destination":row.get("dest_en"),"time_text":row.get("time_en"),
                        "arrival_departure":row.get("arrival_departure"),"train_length":row.get("train_length"),
                        "stop":row.get("stop"),"special":row.get("special"),
                        "additional":row.get("additionalInfo1") or ""})
            return sta,rows,j.get("system_time"),None
        except Exception as exc:return sta,[],None,type(exc).__name__

    def refresh(self):
        errors=[]; fresh=set(); started=time.time()
        with ThreadPoolExecutor(max_workers=min(LRT_WORKERS,len(LRT_STATIONS)),thread_name_prefix="mtr-lrt") as pool:
            futs=[pool.submit(self._fetch_station,sta) for sta in LRT_STATIONS]
            for fut in as_completed(futs):
                sta,rows,system_time,err=fut.result()
                if err is None:
                    self.station_cache[sta]={"rows":rows,"system_time":system_time,"ts":time.time()}; fresh.add(sta)
                else:errors.append(f"{sta}:{err}")
        now=time.time(); stops=[]; times=[]; cached=0
        for sta,e in self.station_cache.items():
            if now-e["ts"]>STATION_CACHE_SEC:continue
            # Preserve each stop's own observation time. A fresh stop must not
            # make older cached arrivals elsewhere look freshly observed.
            observed_at=dt.datetime.fromtimestamp(e["ts"],dt.timezone.utc).isoformat()
            stops.extend({**row, "observed_at":observed_at} for row in e["rows"])
            times.append(e.get("system_time") or "")
            if sta not in fresh:cached+=1
        fresh_ts=[self.station_cache[k]["ts"] for k in fresh if k in self.station_cache]
        fetched=max(fresh_ts) if fresh_ts else max((e["ts"] for e in self.station_cache.values()),default=0)
        out={"ok":bool(stops),"source":"MTR official Light Rail Next Train API",
             "upstream_updated_at":max(times) if times else None,
             "fetched_at":dt.datetime.fromtimestamp(fetched,dt.timezone.utc).isoformat() if fetched else None,
             "station_count":len(set(x["station_id"] for x in stops)),"arrival_count":len(stops),
             "arrivals":stops,"polled_stations":LRT_STATIONS,"errors":errors[:20],"api_update_frequency_sec":10,
             "fresh_station_count":len(fresh),"cached_station_count":cached,
             "cycle_elapsed_ms":round((time.time()-started)*1000),"worker_count":LRT_WORKERS}
        if stops and not fresh:
            out["stale"]=True; out["error"]="All current LRT requests failed; using cached arrivals until they age out"
        if stops:
            self.set(out)
            if self.history:self.history.record("lrt",out,min_interval=10)
        else:
            old=self.get()
            if old.get("ok"):
                old["stale"]=True; old["error"]="No fresh LRT observations; retaining last good snapshot"; self.set(old)
            else:self.set(out)

    def loop(self):
        while True:
            started=time.time()
            try:self.refresh()
            except Exception as exc:
                old=self.get()
                if old.get("ok"):
                    old["stale"]=True; old["error"]=f"LRT refresh failed; retaining cache ({type(exc).__name__})"; self.set(old)
                else:self.set({"ok":False,"error":f"LRT refresh failed: {type(exc).__name__}","arrivals":[]})
            time.sleep(max(2,12-(time.time()-started)))


class Handler(http.server.SimpleHTTPRequestHandler):
    eal=None; heavy=None; lrt=None; history=None; v11=None; api_only=False
    def _json(self,data,status=200,cache="no-store"):
        body=json.dumps(data,separators=(",",":"),ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Cache-Control",cache)
        if len(body)>256 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            body=gzip.compress(body); self.send_header("Content-Encoding","gzip")
        self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def _bytes(self,body,content_type="application/octet-stream",status=200,cache="public, max-age=120"):
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Cache-Control",cache)
        self.send_header("Content-Length",str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def end_headers(self):
        # Avoid stale JS/CSS/HTML when users replace one build with another on the same localhost URL.
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control","no-store, max-age=0")
        super().end_headers()
    def send_head(self):
        resolved=Path(self.translate_path(self.path)).resolve()
        try:parts=resolved.relative_to(ROOT.resolve()).parts
        except ValueError:
            self.send_error(404); return None
        if any(p.startswith('.') or p in ('runtime','__pycache__') for p in parts) or resolved.suffix.lower() in ('.har','.sqlite','.sqlite3','.db'):
            self.send_error(404); return None
        return super().send_head()
    def do_GET(self):
        path=self.path.split("?",1)[0]
        if self.api_only and not path.startswith("/api/"):
            self._json({"ok":False,"error":"API-only deployment; static frontend is served by GitHub Pages"},404); return
        if path=="/api/health":
            r=self.heavy.get(); l=self.lrt.get(); e=self.eal.get()
            self._json({"ok":True,"version":"13.3","rail":{"ok":bool(r.get("ok")),"loading":bool(r.get("loading")),"phase":r.get("phase"),"completed":r.get("completed_requests"),"total":r.get("total_requests"),"fresh_stations":r.get("fresh_station_count"),"cached_stations":r.get("cached_station_count"),"failures":r.get("failed_request_count"),"elapsed_ms":r.get("cycle_elapsed_ms"),"fetched_at":r.get("fetched_at"),"errors":r.get("errors",[])[:5]},"lrt":{"ok":bool(l.get("ok")),"fresh_stations":l.get("fresh_station_count"),"cached_stations":l.get("cached_station_count"),"elapsed_ms":l.get("cycle_elapsed_ms"),"fetched_at":l.get("fetched_at"),"errors":l.get("errors",[])[:5]},"eal":{"ok":bool(e.get("ok")),"loading":bool(e.get("loading")),"stale":bool(e.get("stale")),"fetched_at":e.get("fetched_at"),"error":e.get("error")}}); return
        if path=="/api/eal": self._json(self.eal.get()); return
        if path=="/api/rail-live": self._json(self.heavy.get()); return
        if path=="/api/lrt-live": self._json(self.lrt.get()); return
        if path=="/api/station-board":
            q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            station=(q.get("station") or [""])[0].strip().upper()
            lines=[x.strip().upper() for x in (q.get("lines") or [""])[0].split(",") if x.strip()]
            if not station or not lines:
                self._json({"ok":False,"error":"station and lines are required","observations":[]},400); return
            board=self.heavy.station_board(lines,station)
            board["server_epoch"]=time.time()
            board["display_precision"]="second-resolution estimate"
            board.setdefault("accuracy_note","Displayed seconds are an estimate fused from the MTR ETA window and WTT/live-delay phase; they are not claimed as one-second ground truth.")
            self._json(board); return
        if path=="/api/map/official-system":
            try:
                body,ctype=self.v11.public_asset("official-system"); self._bytes(body,ctype,cache="public, max-age=86400")
            except Exception as exc:self._json({"ok":False,"error":type(exc).__name__},502)
            return
        if path=="/api/map/light-rail":
            try:
                body,ctype=self.v11.public_asset("light-rail-map"); self._bytes(body,ctype,cache="public, max-age=86400")
            except Exception as exc:self._json({"ok":False,"error":type(exc).__name__},502)
            return
        if path=="/api/map/light-rail-system":
            try:
                body,ctype=self.v11.public_asset("light-rail-system"); self._bytes(body,ctype,cache="public, max-age=86400")
            except Exception as exc:self._json({"ok":False,"error":type(exc).__name__},502)
            return
        if path=="/api/weather/radar":
            try:self._json(self.v11.radar())
            except Exception as exc:self._json({"ok":False,"frames":[],"error":type(exc).__name__},502)
            return
        if path=="/api/weather/radar-image":
            q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query); url=(q.get("u") or [""])[0]
            try:
                body,ctype=self.v11.radar_image(url); self._bytes(body,ctype,cache="public, max-age=300")
            except Exception as exc:self._json({"ok":False,"error":type(exc).__name__},502)
            return
        if path=="/api/geo/stations":
            try:self._json(self.v11.geo_stations(),cache="public, max-age=600")
            except Exception as exc:self._json({"ok":False,"stations":{},"error":type(exc).__name__},502)
            return
        if path=="/api/geo/railways":
            try:self._json(self.v11.railways(),cache="public, max-age=600")
            except Exception as exc:self._json({"ok":False,"ways":[],"error":type(exc).__name__},502)
            return
        if path=="/api/geo/mtr-route":
            q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query); line=(q.get("line") or [""])[0]
            try:
                out=self.v11.mtr_route(line); self._json(out,200 if out.get("ok") else 502,cache="public, max-age=600")
            except ValueError as exc:self._json({"ok":False,"error":str(exc)},400)
            except Exception as exc:self._json({"ok":False,"error":type(exc).__name__},502)
            return
        if path=="/api/history":
            q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            def _int(name,default,cap):
                try:return max(0,min(cap,int((q.get(name) or [default])[0])))
                except (TypeError,ValueError):return default
            mins=_int("minutes",30,24*60) or 30
            kinds=(q.get("kinds") or ["eal,rail,lrt"])[0].split(",")
            limit=max(1,_int("limit",600,2000))
            since=_int("since",0,10**12)
            self._json({"ok":True,"snapshots":self.history.query(mins,kinds,limit,since),"status":self.history.status()}); return
        if path=="/api/training/status": self._json({"ok":True,**self.history.training.status()}); return
        if path=="/api/history/status": self._json({"ok":True,**self.history.status()}); return
        super().do_GET()
    def log_message(self,fmt,*args):
        if self.path.startswith("/api/"): super().log_message(fmt,*args)


def find_har(arg):
    if arg:return Path(arg).expanduser().resolve()
    env=os.environ.get("EAL_TMS_HAR")
    if env:return Path(env).expanduser().resolve()
    for p in [ROOT/"eal-tms.rocteccloud.com.har",ROOT.parent/"eal-tms.rocteccloud.com.har"]:
        if p.exists():return p
    return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--har"); ap.add_argument("--port",type=int,default=int(os.environ.get("PORT","8080"))); ap.add_argument("--no-browser",action="store_true"); ap.add_argument("--api-only",action="store_true",help="404 non-/api paths so the deployment serves no static assets"); args=ap.parse_args()
    eal_url=os.environ.get("EAL_TMS_URL",EAL_DEFAULT_URL); key=os.environ.get("EAL_TMS_API_KEY"); har=find_har(args.har)
    if not key and har and har.exists():
        eal_url,key=discover_from_har(har); print(f"EAL TMS configuration loaded from HAR: {har.name} (credential remains server-side)")
    elif key: print("EAL TMS configuration loaded from environment (credential remains server-side)")
    else: print("EAL TMS HAR/key not found: EAL will fall back to official ETA-corrected timetable mode")

    history=HistoryStore(ROOT)
    v12=V12Backend()
    eal=EalSource(eal_url,key,history) if key else None
    matcher=TimetableMatcher(ROOT); heavy=HeavyRailSource(matcher,history); lrt=LightRailSource(history)
    Handler.eal=eal or type("OfflineEAL",(),{"get":lambda self:{"ok":False,"error":"EAL TMS credential not configured","trains":[]}})()
    Handler.heavy=heavy; Handler.lrt=lrt; Handler.history=history; Handler.v11=v12; Handler.api_only=args.api_only
    if eal: threading.Thread(target=eal.loop,daemon=True).start()
    threading.Thread(target=heavy.loop,daemon=True).start(); threading.Thread(target=lrt.loop,daemon=True).start()

    handler=functools.partial(Handler,directory=str(ROOT)); httpd=http.server.ThreadingHTTPServer(("0.0.0.0",args.port),handler)
    address=f"http://localhost:{args.port}"; print(f"HK Train Display v13.3 map/ETA/LRT refinement: {address}")
    print(f"Fast live workers started: heavy rail {HEAVY_WORKERS} concurrent requests, LRT {LRT_WORKERS}; ETA bootstrap publishes before the full sweep finishes.")
    if not args.no_browser: threading.Timer(.7,lambda:webbrowser.open(address)).start()
    try:httpd.serve_forever()
    except KeyboardInterrupt:pass
    finally:httpd.server_close()

if __name__=="__main__":main()
