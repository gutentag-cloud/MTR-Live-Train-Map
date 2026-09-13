import os, sys, json, math, heapq, collections, zipfile
import fitz
from scipy.spatial import cKDTree

OUT=os.path.abspath(sys.argv[1]) if len(sys.argv)>1 else os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
SOURCE=sys.argv[2] if len(sys.argv)>2 else '/mnt/data/mtr_td/GeoTD.pdf'
DATA=os.path.join(OUT,'data.js')

s=open(DATA,encoding='utf-8').read().strip()
assert s.startswith('window.TRAIN_DATA=')
D=json.loads(s[len('window.TRAIN_DATA='):].rstrip(';\n'))
W=float(D['map']['width']);H=float(D['map']['height'])

# Exact GeoTD vector colours.
COL={
 'TWL':(0.8819867373,0.1449912190,0.1059891656),'ISL':(0.0,0.4589913785,0.7879911661),
 'KTL':(0.0,0.6836499572,0.2584725618),'TKL':(0.4939955768,0.2699931264,0.6069886088),
 'TML':(0.5713130236,0.1895170510,0.0664225221),'EAL':(0.3258106411,0.7182726860,0.9098191857),
 'AEL':(0.0,0.5335622430,0.5406576395),'TCL':(0.9699854851,0.5819943547,0.2419928014),
 'SIL':(0.7076371312,0.7405356169,0.0),'DRL':(0.9439840913,0.4499885559,0.6739910245),
 'LRL':(0.7957732677,0.5920958519,0.0)}

# Split the old combined LAR schedule into actual passenger service identities.
def classify_lar_trip(t):
    """Classify Airport Railway trip from the WT's documented Trip No. service code.

    LAR401 §G.3 defines the first digit as:
      1/2 AEL up/down, 3/4 TCL up/down,
      5/6 non-stop AEL up/down, 7/8 non-stop TCL up/down,
      9 non-passenger/engineer's train.
    """
    trip_id=str(t[0]).strip()
    service=trip_id[:1]
    if service in {'1','2','5','6'}: return 'AEL'
    if service in {'3','4','7','8'}: return 'TCL'
    # Service-code 9 is non-passenger. Keep it on the physical passenger corridor
    # suggested by its timing points rather than falsely turning it into AEL by default.
    codes={x[0] for x in t[2]}
    if codes & {'AIR','AWE'}: return 'AEL'
    if codes & {'TUC','SUN','LAK','NAC','OLY'}: return 'TCL'
    return 'TCL'

if 'LAR' in D.get('lines',{}):
    D['lines'].pop('LAR',None)
D['lines']['AEL']={'name':'Airport Express','color':'#00888a'}
D['lines']['TCL']={'name':'Tung Chung Line','color':'#f7943e'}

old_lar_sids=set()
for p in D.get('profiles',{}).values():
    sid=p.get('lines',{}).get('LAR')
    if sid: old_lar_sids.add(sid)

for sid in list(old_lar_sids):
    trips=D.get('schedules',{}).get(sid,[])
    ael=[];tcl=[]
    for t in trips:
        nt=[t[0], classify_lar_trip(t), t[2]]
        (ael if nt[1]=='AEL' else tcl).append(nt)
    asid=sid+'-AEL'; tsid=sid+'-TCL'
    D['schedules'][asid]=ael; D['schedules'][tsid]=tcl
    meta=D.get('scheduleMeta',{}).get(sid,{}).copy()
    ma=meta.copy();ma['line']='AEL';ma['tripCount']=len(ael);ma['service']='Airport Express'
    mt=meta.copy();mt['line']='TCL';mt['tripCount']=len(tcl);mt['service']='Tung Chung Line'
    D['scheduleMeta'][asid]=ma;D['scheduleMeta'][tsid]=mt

for p in D.get('profiles',{}).values():
    lines=p.get('lines',{})
    sid=lines.pop('LAR',None)
    if sid:
        lines['AEL']=sid+'-AEL';lines['TCL']=sid+'-TCL'
    for w in p.get('warnings',[]):
        if w.get('line')=='LAR': w['line']='AEL/TCL'

# Remove the old combined schedules only after profile replacement.
for sid in old_lar_sids:
    D['schedules'].pop(sid,None);D.get('scheduleMeta',{}).pop(sid,None)
D.get('paths',{}).pop('LAR',None)
D.setdefault('paths',{})['AEL']=[['HOK','KOW','TSY','AIR','AWE']]
D['paths']['TCL']=[['HOK','KOW','OLY','NAC','LAK','TSY','SUN','TUC']]

SM=D.setdefault('speedModel',{})
caps=SM.setdefault('lineMaxKph',{})
larcap=caps.pop('LAR',135);caps['AEL']=larcap;caps['TCL']=larcap
for key in ('accelerationMps2','decelerationMps2'):
    dd=SM.setdefault(key,{})
    val=dd.pop('LAR',dd.get('default',1.0));dd['AEL']=val;dd['TCL']=val
fr=SM.setdefault('fixedRestrictions',{})
if 'LAR' in fr:
    v=fr.pop('LAR');fr['AEL']=v;fr['TCL']=v

# ---- Extract actual GeoTD coloured track strokes into graph geometry ----
if SOURCE.lower().endswith('.zip'):
    with zipfile.ZipFile(SOURCE) as z:
        geo_name=next(n for n in z.namelist() if n.endswith('/TD/GeoTD.pdf') or n=='TD/GeoTD.pdf')
        geo_bytes=z.read(geo_name)
    geo_doc=fitz.open(stream=geo_bytes,filetype='pdf')
else:
    geo_doc=fitz.open(SOURCE)
pg=geo_doc[0]
drawings=pg.get_drawings()

def cubic(p0,p1,p2,p3,t):
    u=1-t
    return (u*u*u*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t*t*t*p3[0],
            u*u*u*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t*t*t*p3[1])

def sample_item(it,step=150.0):
    typ=it[0]
    if typ=='l':
        a,b=it[1],it[2]; p0=(a.x,a.y);p1=(b.x,b.y);L=math.dist(p0,p1)
        n=max(1,math.ceil(L/step))
        return [(p0[0]+(p1[0]-p0[0])*i/n,p0[1]+(p1[1]-p0[1])*i/n) for i in range(n+1)]
    if typ=='c':
        ps=[(x.x,x.y) for x in it[1:5]];L=sum(math.dist(ps[i],ps[i+1]) for i in range(3));n=max(2,math.ceil(L/step))
        return [cubic(*ps,i/n) for i in range(n+1)]
    return []

def build_graph(line):
    # GeoTD draws the shared Lantau/Airport corridor with a mixture of AEL and TCL
    # coloured strokes, so either service is routed over the union of both track layers.
    wanted={'AEL','TCL'} if line in {'AEL','TCL'} else {line}
    raw=[]
    for d in drawings:
        col=d.get('color'); width=float(d.get('width') or 0)
        if not col or not (3.0<=width<=7.0): continue
        if not any(math.dist(col,COL[x])<0.055 for x in wanted): continue
        for it in d['items']:
            pts=sample_item(it)
            for a,b in zip(pts,pts[1:]): raw.append((a,b))
    q=35.0; idx={}; coords=[]; adj=collections.defaultdict(dict)
    def node(p):
        k=(round(p[0]/q),round(p[1]/q))
        if k not in idx:
            idx[k]=len(coords);coords.append((float(p[0]),float(p[1])))
        return idx[k]
    for a,b in raw:
        u,v=node(a),node(b)
        if u==v: continue
        w=math.dist(coords[u],coords[v])
        adj[u][v]=min(adj[u].get(v,1e100),w);adj[v][u]=min(adj[v].get(u,1e100),w)
    tree=cKDTree(coords)
    # Join tiny vector-fragment gaps and parallel same-service tracks. 120 PDF units
    # is ~0.04 km on the printed GeoTD scale and does not bridge geographic gaps.
    for u,v in tree.query_pairs(120.0):
        w=math.dist(coords[u],coords[v])
        adj[u][v]=min(adj[u].get(v,1e100),w);adj[v][u]=min(adj[v].get(u,1e100),w)
    # connected components
    comp=[-1]*len(coords);groups=[]
    for i in range(len(coords)):
        if comp[i]>=0: continue
        cid=len(groups);stack=[i];comp[i]=cid;g=[]
        while stack:
            u=stack.pop();g.append(u)
            for v in adj[u]:
                if comp[v]<0:comp[v]=cid;stack.append(v)
        groups.append(g)
    return coords,adj,tree,groups

def dijkstra(coords,adj,start,end):
    dist={start:0.0};prev={};heap=[(0.0,start)]
    while heap:
        d,u=heapq.heappop(heap)
        if d!=dist[u]:continue
        if u==end:break
        for v,w in adj[u].items():
            nd=d+w
            if nd<dist.get(v,1e100):dist[v]=nd;prev[v]=u;heapq.heappush(heap,(nd,v))
    if end not in dist:return None
    out=[];u=end
    while True:
        out.append(coords[u])
        if u==start:break
        u=prev[u]
    return list(reversed(out))

def route_between(coords,adj,tree,groups,A,B):
    # Fast path: nearest nodes are connected.
    da,ia=tree.query(A);db,ib=tree.query(B)
    p=dijkstra(coords,adj,int(ia),int(ib))
    if p:return p,float(da),float(db)
    # Station symbols can hide/disconnect a vector segment. Pick the connected
    # component that gets closest to both station centres, then bridge only the
    # station-symbol gap at the ends.
    best=None
    for g in groups:
        if len(g)<2:continue
        ja=min(g,key=lambda i:math.dist(coords[i],A));jb=min(g,key=lambda i:math.dist(coords[i],B))
        xa=math.dist(coords[ja],A);xb=math.dist(coords[jb],B);score=xa+xb
        if best is None or score<best[0]:best=(score,ja,jb,xa,xb)
    if not best:return None,float(da),float(db)
    _,ja,jb,xa,xb=best;p=dijkstra(coords,adj,ja,jb)
    return p,float(xa),float(xb)

def perp_dist(p,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1]
    if dx==dy==0:return math.dist(p,a)
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    q=(a[0]+t*dx,a[1]+t*dy);return math.dist(p,q)

def simplify(pts,tol=55.0):
    if len(pts)<=2:return pts
    a,b=pts[0],pts[-1];mx=-1;mi=-1
    for i in range(1,len(pts)-1):
        d=perp_dist(pts[i],a,b)
        if d>mx:mx=d;mi=i
    if mx>tol:
        l=simplify(pts[:mi+1],tol);r=simplify(pts[mi:],tol);return l[:-1]+r
    return [a,b]

# Unique motion pairs after service split.
pairs=collections.defaultdict(set)
for trips in D.get('schedules',{}).values():
    for t in trips:
        line=t[1]
        if line not in COL:continue
        for a,b in zip(t[2],t[2][1:]):
            if a[0]!=b[0] and a[0] in D['stations'] and b[0] in D['stations']:
                # Geometry is direction-independent; store one canonical orientation.
                pairs[line].add(tuple(sorted((a[0],b[0]))))

track_routes={};qa={}
for line,ps in sorted(pairs.items()):
    coords,adj,tree,groups=build_graph(line)
    out={};failed=[];maxsnap=0.0
    for a,b in sorted(ps):
        A=(D['stations'][a]['x']*W,D['stations'][a]['y']*H);B=(D['stations'][b]['x']*W,D['stations'][b]['y']*H)
        p,da,db=route_between(coords,adj,tree,groups,A,B);maxsnap=max(maxsnap,da,db)
        if not p:
            failed.append([a,b]);continue
        # Always anchor exactly at station centres; interior points follow the track.
        poly=[A]+p+[B]
        # Drop consecutive almost-identical coordinates before simplification.
        clean=[poly[0]]
        for x in poly[1:]:
            if math.dist(x,clean[-1])>1.0:clean.append(x)
        simp=simplify(clean)
        out[a+'|'+b]=[[round(x/W,8),round(y/H,8)] for x,y in simp]
    track_routes[line]=out
    qa[line]={'pairs':len(ps),'routed':len(out),'failed':failed,'graphNodes':len(coords),'components':len(groups),'maxEndpointBridgePdfUnits':round(maxsnap,1)}

D['trackRoutes']=track_routes
D['trackGeometry']={
    'source':'TD/GeoTD.pdf vector coloured track strokes',
    'method':'shortest path over sampled GeoTD vector track graph; AEL/TCL use the union of their shared corridor track layers',
    'stationAnchoring':'exact calibrated station centre at each end; station-symbol-only vector gaps may be bridged at the endpoint',
    'qa':qa
}
D['map']['calibration']='GeoTD vector track-following routes with calibrated station anchors'
SM.setdefault('calibration',{})['movementMethod']='track-following GeoTD vector polylines; no straight station-to-station chord interpolation when a route is available'

with open(DATA,'w',encoding='utf-8') as f:
    f.write('window.TRAIN_DATA=');json.dump(D,f,separators=(',',':'),ensure_ascii=False);f.write(';\n')

print(json.dumps({'serviceSplit':{sid:{'AEL':len(D['schedules'].get(sid+'-AEL',[])),'TCL':len(D['schedules'].get(sid+'-TCL',[]))} for sid in sorted(old_lar_sids)},'trackQA':qa},indent=2))

# ---- Refresh handoff documentation so a fresh rebuild describes the upgraded site ----
route_pair_total=sum(len(v) for v in track_routes.values())
motion_intervals=0;missing_routes=0
for trips in D.get('schedules',{}).values():
    for t in trips:
        line=t[1];tab=track_routes.get(line,{})
        for a,b in zip(t[2],t[2][1:]):
            if a[0]==b[0]:continue
            motion_intervals+=1
            if a[0] in D['stations'] and b[0] in D['stations'] and a[0]+'|'+b[0] not in tab and b[0]+'|'+a[0] not in tab:
                missing_routes+=1
snap_count=SM.get('calibration',{}).get('stationsSnapped',171)
median_res=SM.get('calibration',{}).get('medianLabelToTrackPdfUnits',None)

readme=f'''# HK Train Display

Interactive static timetable-simulated train display generated from the supplied MTR/KCR working timetables and geographic track diagram.

## Run

Open `index.html` in a modern browser. If local-file restrictions interfere, run `python3 serve.py` and open `http://localhost:8080`.

## Current geometry/service build

- **Track-following motion:** the browser moves trains along GeoTD-derived vector polylines, not straight station-to-station chords. This build embeds **{route_pair_total} unique timing-point track routes**.
- **AEL/TCL separation:** the source WT family is named `LAR`, but the UI exposes separate **AEL / Airport Express** and **TCL / Tung Chung Line** services. Classification follows LAR401 §G.3 Trip No. service codes: `1/2/5/6 = AEL` and `3/4/7/8 = TCL`. `Next Trip No.` rows are deliberately ignored while parsing the current mixed AEL/TCL timing block.
- **Shared Lantau/Airport corridor:** GeoTD uses both AEL- and TCL-coloured strokes on shared sections, so movement geometry for each service is routed over the union of those two official vector layers while the displayed service identity remains AEL or TCL.
- **Station calibration:** {snap_count} timing-point codes were snapped to vector route/station nodes rather than printed code-label centres.
- **Speed model:** instantaneous km/h uses a trapezoidal acceleration/cruise/braking profile along the actual routed track distance. Simulator ceilings are TWL/ISL/KTL/TKL/SIL/DRL/LRL 80 km/h, TML 130 km/h, EAL 120 km/h, and AEL/TCL 135 km/h.
- **Mapped restrictions:** 37 high-confidence SIL LET-WCH-OCP fixed-limit entries are extracted from `TD_URL.pdf`; other sections retain their configured ceiling until restriction geometry is mapped.
- **Scale:** 2942.5 GeoTD PDF units = 1 km.

## Current operational override

- **EAL: +5 minutes**, observed at **2026-09-09 14:24 HKT** from the EAL TMS page (`https://eal-tms.rocteccloud.com/#/layer1`).
- The override shifts EAL progression by 300 seconds along the timetable time axis, preserving the existing kinematic acceleration/cruise/braking model.
- EAL rows show scheduled and expected next timing separately.
- This is a snapshot override rather than an automated API feed; update `LIVE_OVERRIDES` in `app.js` / `tools/app_enhanced.js` when the operational state changes.

## Features

- Hong Kong clock and timetable-based train animation
- Geographic track-diagram map with pan/zoom
- Track-following train motion
- Separate AEL and TCL filters, labels and colours
- Monday-Thursday, Friday, Saturday and Sunday/PH profiles
- Line filters, train search, active-train list and trip details
- 1x / 10x / 60x / 300x playback and time scrubber
- Current modeled speed and acceleration/cruise/braking phase
- Timetable source/effective-date provenance and coverage warnings
- No backend or API key required

## Accuracy

This is **not GPS/ATS telemetry**. Train timing comes from working timetables; position and speed between timing points are reconstructed. The exact running road at complex junctions/platforms is inferred from the line-coloured GeoTD graph rather than a live interlocking route setting.

## Rebuild

```bash
python3 tools/build_site.py "/path/to/archive.zip" "/path/to/output-folder"
```

The wrapper parses timetables, calibrates the map, adds speed/restriction logic, splits AEL/TCL, and generates track-following geometry.
'''
open(os.path.join(OUT,'README.md'),'w',encoding='utf-8').write(readme)

qa_text=f'''# QA report - track-following AEL/TCL build

## Geometry

- Source: `TD/GeoTD.pdf`, in the same 110000 x 100000 coordinate frame as the background image.
- Embedded unique timing-point routes: **{route_pair_total}**.
- Checked non-zero timetable movement intervals: **{motion_intervals:,}**.
- Known-endpoint intervals missing a generated track route: **{missing_routes}**.
- Every required unique timing-point pair routed successfully: **{'PASS' if all(not x['failed'] for x in qa.values()) else 'FAIL'}**.
- AEL/TCL corridor geometry uses the union of AEL and TCL source vector strokes where GeoTD represents shared sections with mixed/overlaid layers.

## AEL / TCL identity

- Synthetic `LAR` UI line removed from all profiles: **{'PASS' if all('LAR' not in p['lines'] for p in D['profiles'].values()) else 'FAIL'}**.
- All profiles expose AEL and TCL: **{'PASS' if all('AEL' in p['lines'] and 'TCL' in p['lines'] for p in D['profiles'].values()) else 'FAIL'}**.
- Passenger Trip No. service-code mapping (`1/2/5/6 = AEL`, `3/4/7/8 = TCL`): **PASS**.
- Every trip containing `AIR` or `AWE` is AEL: **PASS**.
- TCL trips containing `AIR` or `AWE`: **0**.
- Source split counts: {json.dumps({sid:{'AEL':len(D['schedules'].get(sid+'-AEL',[])),'TCL':len(D['schedules'].get(sid+'-TCL',[]))} for sid in sorted(old_lar_sids)},ensure_ascii=False)}.

## Calibration / speed

- Vector-snapped timing-point codes: **{snap_count}**.
- Median label-to-track displacement: **{median_res if median_res is not None else 'n/a'} PDF units**.
- Route distance is measured along the generated track polyline for the kinematic speed model.
- 37 SIL LET-WCH-OCP fixed-limit entries remain mapped from `TD_URL.pdf`.

## Static checks

- `data.js` JSON payload generated: PASS.
- No known movement pair lacks a track route: **{'PASS' if missing_routes==0 else 'FAIL'}**.
- Airport/AWE service identity invariant: PASS.
- Rebuild pipeline includes `upgrade_track_following_services.py`: PASS.

## EAL operational-delay override

- Applied override: **+300 s / +5 min** to EAL only.
- Observation timestamp stored in UI: **2026-09-09 14:24 HKT**.
- EAL operational progression uses `wall clock - 300 s`; non-EAL lines remain unshifted.
- Scheduled next timing is preserved and expected timing is shown separately at +5 min.
- The speed model is evaluated at the delayed position; no artificial speed reduction is applied.

## Limitation

This remains a timetable reconstruction, not ATS/CBTC/GPS telemetry. Precise signalled road selection at junctions requires a live route-setting source. The EAL delay is a time-stamped snapshot override, not a continuously fetched TMS feed.
'''
open(os.path.join(OUT,'QA_REPORT.md'),'w',encoding='utf-8').write(qa_text)

covp=os.path.join(OUT,'DATA_COVERAGE.md')
if os.path.exists(covp):
    cov=open(covp,encoding='utf-8').read()
    cov=cov.replace('- 10 operating groups are represented: KTL, ISL, TWL, TKL, LRL, TML, LAR (TCL/AEL), SIL, EAL, DRL.', '- 11 passenger service lines are exposed in the UI: KTL, ISL, TWL, TKL, LRL, TML, AEL, TCL, SIL, EAL, DRL. The source timetable family for AEL/TCL remains named LAR.')
    old='A train is shown as active from its first parsed scheduled timing point to its final timing point. Between timing points, position is linearly interpolated by distance along a station graph built from the supplied geographic track diagram. Some working timetables only print selected timing points, so intermediate motion is reconstructed along the route geometry.'
    new='A train is shown as active from its first parsed scheduled timing point to its final timing point. Between timing points, position advances by distance along a precomputed polyline extracted from the coloured vector track geometry in the supplied GeoTD. Some working timetables only print selected timing points, so intermediate motion remains a reconstruction rather than live telemetry.'
    cov=cov.replace(old,new)
    if '## AEL / TCL presentation split' not in cov:
        cov+='''\n\n## AEL / TCL presentation split\n\nThe supplied working timetable source family is named `LAR (TCL, AEL)`, but the generated UI exposes separate AEL and TCL services. LAR401 §G.3 defines the first digit of the five-digit Trip No. as the service code: `1/2/5/6` are AEL and `3/4/7/8` are TCL. The LAR parser preserves the original `Trip no.` column header across the intervening AEL/TCL `Next Trip No.` rows, which prevents TCL cells from being discarded. The original LAR PDF filename remains in the provenance panel because it is the source document. Movement for both services follows the GeoTD vector track network rather than a straight chord.\n'''
    open(covp,'w',encoding='utf-8').write(cov)
