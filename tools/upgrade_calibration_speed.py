import json, re, math, collections, zipfile, os, sys, fitz
DEFAULT_OUT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
DEFAULT_ZIP='/mnt/data/Timetables, Traffic Notices, Track Diagrams-20260908T153610Z-1-001.zip'
ZIP=os.path.abspath(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_ZIP
OUT=os.path.abspath(sys.argv[2]) if len(sys.argv)>2 else DEFAULT_OUT
data_path=os.path.join(OUT,'data.js')
s=open(data_path,encoding='utf-8').read().strip()
assert s.startswith('window.TRAIN_DATA=')
payload=json.loads(s[len('window.TRAIN_DATA='):].rstrip(';\n'))
with zipfile.ZipFile(ZIP) as z:
    geo_bytes=z.read('Timetables, Traffic Notices, Track Diagrams/TD/GeoTD.pdf')
    url_bytes=z.read('Timetables, Traffic Notices, Track Diagrams/TD/Official/TD_URL.pdf')
geo=fitz.open(stream=geo_bytes,filetype='pdf'); pg=geo[0]; W,H=pg.rect.width,pg.rect.height
# Text-code anchor locations (labels are NOT the final train coordinates).
labels=collections.defaultdict(list)
for b in pg.get_text('dict')['blocks']:
    for ln in b.get('lines',[]):
        for sp in ln['spans']:
            t=sp['text'].strip(); size=sp['size']; x0,y0,x1,y1=sp['bbox']
            if 110<=size<=130 and re.fullmatch(r'[A-Z][A-Z0-9]{1,5}',t): labels[t].append(((x0+x1)/2,(y0+y1)/2))
            elif 75<=size<=85 and re.fullmatch(r'\d{3}',t): labels[t].append(((x0+x1)/2,(y0+y1)/2))
# Exact line colours used by the vector track diagram.
COL={
 'TWL':(0.8819867373,0.1449912190,0.1059891656),'ISL':(0.0,0.4589913785,0.7879911661),
 'KTL':(0.0,0.6836499572,0.2584725618),'TKL':(0.4939955768,0.2699931264,0.6069886088),
 'TML':(0.5713130236,0.1895170510,0.0664225221),'EAL':(0.3258106411,0.7182726860,0.9098191857),
 'AEL':(0.0,0.5335622430,0.5406576395),'TCL':(0.9699854851,0.5819943547,0.2419928014),
 'SIL':(0.7076371312,0.7405356169,0.0),'DRL':(0.9439840913,0.4499885559,0.6739910245),
 'LRL':(0.7957732677,0.5920958519,0.0)}
def color_name(fill):
    if fill is None:return None
    best=min(COL,key=lambda k:sum((fill[i]-COL[k][i])**2 for i in range(3)))
    d=math.sqrt(sum((fill[i]-COL[best][i])**2 for i in range(3)))
    return best if d<0.055 else None
circles=[]
for d in pg.get_drawings():
    r=d['rect']; fill=d.get('fill'); cname=color_name(fill)
    if not cname or not d['items'] or d['items'][0][0]!='c': continue
    # Heavy-rail route nodes are ~30 units diameter; LRL nodes are ~16.9.
    if cname=='LRL': ok=12<=r.width<=22 and 12<=r.height<=22
    else: ok=20<=r.width<=40 and 20<=r.height<=40
    if ok: circles.append(((r.x0+r.x1)/2,(r.y0+r.y1)/2,cname))
# Infer which line colours are valid for each timing point from actual schedules.
usage=collections.defaultdict(set)
for trips in payload['schedules'].values():
    for tr in trips:
        line=tr[1]
        for st,_ in tr[2]: usage[st].add(line)
for line,paths in payload.get('paths',{}).items():
    for p in paths:
        for st in p: usage[st].add(line)
def allowed(line): return {'AEL','TCL'} if line=='LAR' else {line}
calibrated={}; residuals=[]
for st,old in payload['stations'].items():
    labs=labels.get(st,[])
    if not labs: continue
    if st.isdigit():
        cand=[]
        for lp in labs:
            for x,y,c in circles:
                if c=='LRL': cand.append((math.hypot(x-lp[0],y-lp[1]),x,y))
        if cand:
            md=min(q[0] for q in cand)
            pts=[q for q in cand if q[0]<=min(520,md+110)]
            if pts:
                x=sum(q[1] for q in pts)/len(pts); y=sum(q[2] for q in pts)/len(pts)
                calibrated[st]=(x,y); residuals.append(md)
        continue
    aset=set()
    for line in usage.get(st,[]): aset |= allowed(line)
    if not aset: aset=set(COL)-{'LRL'}
    picked=[]; mind=1e9
    # Treat each serving line independently so interchange platforms are averaged together.
    for cwant in aset:
        cand=[]
        for lp in labs:
            for x,y,c in circles:
                if c==cwant: cand.append((math.hypot(x-lp[0],y-lp[1]),x,y))
        if not cand: continue
        md=min(q[0] for q in cand); mind=min(mind,md)
        if md>850: continue
        picked += [q for q in cand if q[0]<=min(700,md+180)]
    if picked:
        x=sum(q[1] for q in picked)/len(picked); y=sum(q[2] for q in picked)/len(picked)
        calibrated[st]=(x,y); residuals.append(mind)
for st,(x,y) in calibrated.items():
    payload['stations'][st]['x']=round(x/W,8); payload['stations'][st]['y']=round(y/H,8)
# Geographic scale printed in GeoTD: 2942.5 PDF units = 1 km.
# (The diagram itself prints this conversion beside the dual scale bar.)
units_per_km=2942.5
# Operational/rolling-stock ceilings used by the simulator; restriction data can lower these.
line_caps={'TWL':80,'ISL':80,'KTL':80,'TKL':80,'SIL':80,'DRL':80,'LRL':80,'TML':130,'EAL':120,'LAR':135}
# Extract a usable fixed-speed profile from TD-URL page 76 (SIL LET-WCH-OCP section).
url=fitz.open(stream=url_bytes,filetype='pdf'); p76=url[75]
words=p76.get_text('words')
def xs(code): return [w[0] for w in words if w[4]==code and 150<w[1]<560]
anchors={k:sorted(xs(k))[len(xs(k))//2] for k in ('LET','WCH','OCP') if xs(k)}
rows=[]
for row_name,(ya,yb) in {'A':(65,100),'B':(650,700)}.items():
    pts=[]
    for w in words:
        if ya<=w[1]<=yb and re.fullmatch(r'[4-9]\d',w[4]):
            v=int(w[4])
            if 40<=v<=99: pts.append((w[0],v))
    rows.append((row_name,pts))
restr=[]
if set(anchors)=={'LET','WCH','OCP'}:
    xl,xw,xo=anchors['LET'],anchors['WCH'],anchors['OCP']
    for rn,pts in rows:
        for x,v in pts:
            if xl-65<=x<=xw+25:
                f=max(0,min(1,(x-xl)/(xw-xl))); restr.append({'pair':['LET','WCH'],'fraction':round(f,4),'limit':v,'row':rn})
            elif xw-25<x<=xo+65:
                f=max(0,min(1,(x-xw)/(xo-xw))); restr.append({'pair':['WCH','OCP'],'fraction':round(f,4),'limit':v,'row':rn})
payload['speedModel']={
 'distanceScalePdfUnitsPerKm':units_per_km,
 'lineMaxKph':line_caps,
 'accelerationMps2':{'default':1.0,'LRL':1.1,'LAR':0.85,'EAL':0.9,'TML':0.9},
 'decelerationMps2':{'default':1.0,'LRL':1.1,'LAR':0.9,'EAL':0.95,'TML':0.95},
 'fixedRestrictions':{'SIL':restr},
 'restrictionSource':'TD/Official/TD_URL.pdf page 76 (maximum allowable speed values spatially matched to LET-WCH-OCP); other lines currently use the line/rolling-stock ceiling unless a fixed restriction has been mapped.',
 'calibration':{'method':'GeoTD vector route-node centres matched by line colour; station-code text is used only as an anchor','stationsSnapped':len(calibrated),'medianLabelToTrackPdfUnits':round(sorted(residuals)[len(residuals)//2],1) if residuals else None}
}
payload['map']['calibration']='vector route-node centres, not station label text centres'
with open(data_path,'w',encoding='utf-8') as f:
    f.write('window.TRAIN_DATA='); json.dump(payload,f,separators=(',',':'),ensure_ascii=False); f.write(';\n')
print(json.dumps({'stationsSnapped':len(calibrated),'totalStations':len(payload['stations']),'medianResidual':payload['speedModel']['calibration']['medianLabelToTrackPdfUnits'],'silRestrictions':len(restr)},indent=2))
