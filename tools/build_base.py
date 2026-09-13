import os, re, math, json, zipfile, subprocess, statistics, collections, shutil, sys, fitz

DEFAULT_ZIP='/mnt/data/Timetables, Traffic Notices, Track Diagrams-20260908T153610Z-1-001.zip'
ZIP=os.path.abspath(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_ZIP
OUT=os.path.abspath(sys.argv[2]) if len(sys.argv)>2 else '/mnt/data/MTR_Live_Train_Display'
WORK=os.path.join(os.path.dirname(OUT),'.mtr_train_build')
os.makedirs(WORK,exist_ok=True)
os.makedirs(OUT,exist_ok=True)
os.makedirs(os.path.join(OUT,'assets'),exist_ok=True)

# Schedule assignments. These are the best available regular working timetables in the archive,
# with the WT & other info.docx note taking precedence where it explicitly states latest-in-use.
profiles={
 'weekday': {
  'label':'Monday–Thursday',
  'KTL':'KTL/Weekday (Monday - Thursday)/KTL151.pdf',
  'ISL':'ISL/Weekday (Monday - Thursday)/ISL838.pdf',
  'TWL':'TWL/Weekday (Monday - Thursday)/TWL321.pdf',
  'TKL':'TKL/Weekday (Monday - Friday)/TKL161.pdf',
  'LRL':'LRL/Weekday (Monday - Friday)/LRL135 (1 Rev 0).pdf',
  'TML':'TML/Weekday (Monday - Friday)/TML1090.pdf',
  'LAR':'LAR (TCL, AEL)/Weekday (Monday - Friday)/LAR401.pdf',
  'SIL':'SIL/Weekday (Monday - Friday)/SIL903.pdf',
  'EAL':'EAL/Weekday (Monday - Thursday)/EAL5240A.pdf',
  'DRL':'DRL/DRLN138.pdf',
 },
 'friday': {
  'label':'Friday',
  'KTL':'KTL/Friday/KTL135.pdf',
  'ISL':'ISL/Friday/ISL145.pdf',
  'TWL':'TWL/Friday/TWL215.pdf',
  'TKL':'TKL/Weekday (Monday - Friday)/TKL161.pdf',
  'LRL':'LRL/Weekday (Monday - Friday)/LRL135 (1 Rev 0).pdf',
  'TML':'TML/Weekday (Monday - Friday)/TML1090.pdf',
  'LAR':'LAR (TCL, AEL)/Weekday (Monday - Friday)/LAR401.pdf',
  'SIL':'SIL/Weekday (Monday - Friday)/SIL903.pdf',
  'EAL':'EAL/Weekday (Monday - Thursday)/EAL5240A.pdf',
  'DRL':'DRL/DRLN138.pdf',
 },
 'saturday': {
  'label':'Saturday',
  'KTL':'KTL/Saturday/KTL076 (version 4).pdf',
  'ISL':'ISL/Saturday/ISL146.pdf',
  'TWL':'TWL/Saturday/TWL166.pdf',
  'TKL':'TKL/Saturday/TKL116.pdf',
  'LRL':'LRL/Saturday/LRL626 (1 Rev 0).pdf',
  'TML':'TML/Saturday/TML6090A.pdf',
  'LAR':'LAR (TCL, AEL)/Weekend (Saturday, Sunday, and PH)/LAR347.pdf',
  'SIL':'SIL/Saturday/SIL833.pdf',
  'EAL':'EAL/Saturday, Sunday, and PH/EAL6240P.pdf',
  'DRL':'DRL/DRLN138.pdf',
 },
 'sunday': {
  'label':'Sunday / public holiday',
  'KTL':'KTL/Sunday and PH/KTL008.pdf',
  'ISL':'ISL/Sunday and PH/ISL127.pdf',
  'TWL':'TWL/Sunday and PH/TWL658.pdf',
  'TKL':'TKL/Sunday and PH/TKL117.pdf',
  'LRL':'LRL/Sunday/LRL731 (1 Rev 0).pdf',
  'TML':'TML/Sunday and PH/TML7090.pdf',
  'LAR':'LAR (TCL, AEL)/Weekend (Saturday, Sunday, and PH)/LAR347.pdf',
  'SIL':'SIL/Sunday and PH/SIL853.pdf',
  'EAL':'EAL/Saturday, Sunday, and PH/EAL6240P.pdf',
  'DRL':'DRL/DRLN138.pdf',
 },
}

prefix='Timetables, Traffic Notices, Track Diagrams/Timetables/'
all_paths=sorted({p for prof in profiles.values() for k,p in prof.items() if k!='label'})

# Explicit warnings based on WT & other info.docx (last updated 2026-06-03).
warning_by_line={
 'KTL':'Archive note says the latest Saturday KTL106 and Sunday KTL107 files are missing; weekend profiles use the newest attached regular fallback.',
 'ISL':'Archive note says weekday ISL151, Saturday ISL176 and Sunday ISL157 are missing; affected profiles use attached fallbacks.',
 'TWL':'Archive note says TWL10103 / 50103 / 60103 / 70102 are missing; all regular profiles use attached fallbacks.',
 'TKL':'Archive note says TKL181 / 126 / 127 are missing; regular profiles use attached fallbacks.',
 'LAR':'Archive note says AnT10105 / AnT70104 are missing; regular profiles use attached LAR fallbacks.',
 'EAL':'Friday uses the attached Monday–Thursday working timetable as a fallback because no regular Friday EAL file is present.',
}

# Extract selected PDFs and cover metadata.
meta={}
with zipfile.ZipFile(ZIP) as z:
    names=set(z.namelist())
    for rel in all_paths:
        full=prefix+rel
        if full not in names:
            raise FileNotFoundError(full)
        safe=re.sub(r'[^A-Za-z0-9._-]+','_',rel)
        pdf=os.path.join(WORK,safe)
        if not os.path.exists(pdf):
            with open(pdf,'wb') as f: f.write(z.read(full))
        txt=pdf[:-4]+'.txt'
        if not os.path.exists(txt):
            subprocess.run(['pdftotext','-layout',pdf,txt],check=True)
        doc=fitz.open(pdf)
        cover='\n'.join(doc[i].get_text() for i in range(min(2,len(doc))))
        pages=len(doc); doc.close()
        m=re.search(r'Effective(?:\s*(?:Date)?\s*[:\-])?\s*(?:from\s+)?(\d{1,2}\s+[A-Za-z]+\s+\d{4})',cover,re.I)
        eff=m.group(1) if m else None
        sid=os.path.splitext(os.path.basename(rel))[0]
        meta[rel]={'id':sid,'file':rel,'effective':eff,'pages':pages,'txt':txt}

# Extract official geographic track diagram and render a browser-sized map.
with zipfile.ZipFile(ZIP) as z:
    geo_bytes=z.read('Timetables, Traffic Notices, Track Diagrams/TD/GeoTD.pdf')
geo_pdf=os.path.join(WORK,'GeoTD.pdf')
with open(geo_pdf,'wb') as f:f.write(geo_bytes)
doc=fitz.open(geo_pdf); page=doc[0]; W,H=page.rect.width,page.rect.height
# Adaptive high-resolution GeoTD renders. All use identical full-page bounds so normalized station/train coordinates remain unchanged.
for target_w,name in [(3200,'geotd-map-3200.png'),(6000,'geotd-map-6000.png'),(12000,'geotd-map.png')]:
    scale=target_w/W
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
    pix.save(os.path.join(OUT,'assets',name))
# Keep the original vector source alongside the 12K canonical raster.
shutil.copy2(geo_pdf,os.path.join(OUT,'assets','GeoTD.pdf'))

# Station code positions from the diagram: heavy-rail codes use 120pt labels; light-rail numeric stop codes use 80pt labels.
raw=collections.defaultdict(list); name_spans=[]
for b in page.get_text('dict')['blocks']:
    if 'lines' not in b: continue
    for ln in b['lines']:
        for sp in ln['spans']:
            t=sp['text'].strip(); size=sp['size']
            x0,y0,x1,y1=sp['bbox']; cx=(x0+x1)/2; cy=(y0+y1)/2
            if 110 <= size <= 130 and re.fullmatch(r'[A-Z][A-Z0-9]{1,5}',t): raw[t].append((cx,cy))
            if 75 <= size <= 85 and re.fullmatch(r'\d{3}',t): raw[t].append((cx,cy))
            if 75 <= size <= 85 and re.search(r'[A-Za-z]',t): name_spans.append((t,cx,cy))
doc.close()

coords={}
for k,pts in raw.items():
    if len(pts)==1: chosen=pts
    else:
        clusters=[]
        for p in pts:
            for c in clusters:
                ax=sum(q[0] for q in c)/len(c); ay=sum(q[1] for q in c)/len(c)
                if math.hypot(p[0]-ax,p[1]-ay)<2500:
                    c.append(p); break
            else: clusters.append([p])
        chosen=max(clusters,key=len)
    x=sum(p[0] for p in chosen)/len(chosen); y=sum(p[1] for p in chosen)/len(chosen)
    coords[k]={'x':x/W,'y':y/H}

# Closest 80pt English label gives a robust display name for heavy rail station codes.
station_names={}
for code,c in coords.items():
    if code.isdigit():
        station_names[code]=code
        continue
    x,y=c['x']*W,c['y']*H
    candidates=sorted(name_spans,key=lambda q:math.hypot(q[1]-x,q[2]-y))
    name=code
    for t,cx,cy in candidates[:12]:
        dist=math.hypot(cx-x,cy-y)
        if dist>900: break
        if t.upper()==code or re.fullmatch(r'[A-Z0-9()]+',t): continue
        if len(t)>42: continue
        name=t; break
    station_names[code]=name

aliases={'NHUH':'HUH','CIOT':'CIO','KATS':'KAT','EXT':'ETS','ADM5':'ADM','ADM6':'ADM','SOH1':'SOH','SOH2':'SOH'}
def norm_station(s):
    s=s.strip().upper(); s=re.sub(r'\([^)]*\)','',s).strip(); s=s.replace(' ',''); s=re.sub(r'[^A-Z0-9]','',s)
    s=aliases.get(s,s)
    if s in coords:return s
    m=re.match(r'^([A-Z]{2,5})\d+$',s)
    if m and m.group(1) in coords:return m.group(1)
    if len(s)>2 and s[-1] in 'ST' and s[:-1] in coords:return s[:-1]
    return None

time_re=re.compile(r'(?<!\d)([0-2]?\d)[: ](\d{2})(?:[: ](\d{2}))?(?!\d)')
event_re=re.compile(r'^\s*(.*?)\s+(dep/arr|arr/dep|dep|arr|pass|pas)\b',re.I)
lrl_re=re.compile(r'^\s*\((\d{3})(?:/\d+)?\)')

def header_tokens(line,label_regex):
    m=re.search(label_regex,line,re.I)
    if not m:return [],[]
    tail=line[m.end():]; out=[]
    for mm in re.finditer(r'\b[A-Z]{0,3}\d{2,6}[A-Z]?\*?\b',tail,re.I):
        out.append((mm.group(0).rstrip('*'),m.end()+mm.start()+len(mm.group(0))/2))
    return [x[0] for x in out],[x[1] for x in out]

def append_motion_segments(trips, trip_id, linecode, points):
    # Prevent a vehicle/run identifier from being rendered as continuously moving across long layovers
    # or across distinct trips that share a timetable column. Thresholds reflect each WT's timing-point density.
    gap_limit={'DRL':15*60,'LRL':40*60,'TML':70*60,'EAL':45*60}.get(linecode,30*60)
    seg=[]
    for item in points:
        if seg and item[1]-seg[-1][1] > gap_limit:
            if len(seg)>=2 and seg[-1][1]>seg[0][1]:
                trips.append([trip_id,linecode,[[st,sec] for st,sec in seg]])
            seg=[]
        seg.append(item)
    if len(seg)>=2 and seg[-1][1]>seg[0][1]:
        trips.append([trip_id,linecode,[[st,sec] for st,sec in seg]])

def parse_schedule(txt_path,linecode):
    lines=open(txt_path,encoding='utf-8',errors='ignore').read().splitlines(); trips=[]
    ids=[]; centers=[]; cur=[]; kind=None; last_station=None; pending_lrl=None
    def finalize():
        nonlocal cur
        for tr in cur:
            if not tr or len(tr['p'])<2: continue
            out=[]; prev=None; add=0
            for st,rawsec in tr['p']:
                sec=rawsec+add
                if prev is not None and sec<prev:
                    if prev>=20*3600 and sec<5*3600: add+=86400; sec+=86400
                    else: continue
                if not out or (st,sec)!=out[-1]:out.append((st,sec))
                prev=sec
            if len(out)>=2 and out[-1][1]>out[0][1]:
                append_motion_segments(trips,tr['id'],linecode,out)
        cur=[None]*len(ids)
    def set_header(newids,newcenters,newkind):
        nonlocal ids,centers,cur,kind,last_station,pending_lrl
        finalize(); ids=newids; centers=newcenters; cur=[{'id':x,'p':[]} if x else None for x in ids]; kind=newkind; last_station=None; pending_lrl=None
    for i,line in enumerate(lines):
        low=line.lower()
        if re.search(r'\btrain\s*no\.?',line,re.I):
            nxt='\n'.join(lines[i+1:i+3])
            if re.search(r'\btrip\s*no\.?',nxt,re.I) or kind in ('trip','journey'): continue
            a,b=header_tokens(line,r'\btrain\s*no\.?')
            if len(a)>=2: set_header(a,b,'train'); continue
        if re.search(r'\b(?:next\s+)?trip\s*no\.?',line,re.I):
            a,b=header_tokens(line,r'\b(?:next\s+)?trip\s*no\.?')
            if len(a)>=1:
                if 'next' in low and centers:
                    assigned=[None]*len(centers)
                    for tid,cc in zip(a,b): assigned[min(range(len(centers)),key=lambda j:abs(centers[j]-cc))]=tid
                    set_header(assigned,centers,'trip')
                elif len(a)>=2:set_header(a,b,'trip')
                continue
        if re.search(r'\bjourney\s*no\.?',line,re.I):
            a,b=header_tokens(line,r'\bjourney\s*no\.?')
            if len(a)>=2:set_header(a,b,'journey'); continue
        if not centers:continue
        em=event_re.match(line); station=None
        if em:
            pending_lrl=None
            rawst=em.group(1).strip()
            if rawst:
                rawst=rawst.split()[0]
                if rawst.lower() not in ('train','notes','next'):last_station=rawst
            station=norm_station(last_station or '')
        else:
            lm=lrl_re.match(line)
            if lm:
                last_station=lm.group(1); station=norm_station(last_station); pending_lrl=station
            elif kind=='journey' and pending_lrl and time_re.search(line):
                # LRL weekend PDFs often put the stop code on one physical text line
                # and its timetable cells on the immediately following line.
                station=pending_lrl; pending_lrl=None
            else:
                # Keep a pending LRL stop only across blank/separator lines.
                if line.strip() and pending_lrl: pending_lrl=None
                continue
        if not station:continue
        times=[]
        for tm in time_re.finditer(line):
            hh=int(tm.group(1)); mm=int(tm.group(2)); ss=int(tm.group(3) or 0)
            if mm<60 and ss<60:times.append(((tm.start()+tm.end())/2,hh*3600+mm*60+ss))
        if not times:continue
        pending_lrl=None
        spacing=statistics.median(abs(centers[k+1]-centers[k]) for k in range(len(centers)-1)) if len(centers)>1 else 12
        assigned={}
        for cc,sec in times:
            j=min(range(len(centers)),key=lambda k:abs(centers[k]-cc)); d=abs(centers[j]-cc)
            if d>spacing*0.70:continue
            if j not in assigned or d<assigned[j][0]:assigned[j]=(d,sec)
        for j,(_,sec) in assigned.items():
            if j<len(cur) and cur[j]:cur[j]['p'].append((station,sec))
    finalize(); return trips


def parse_lar_schedule(txt_path,linecode='LAR'):
    """Parse combined AEL/TCL Airport Railway WTs.

    LAR pages use one `Trip no.` header for a set of physical columns, then print
    the AEL timing rows and an AEL `Next Trip No.` line, followed by TCL timing
    rows for the *same original columns* and a second `Next Trip No.` line.
    Therefore `Next Trip No.` must never replace the active current-trip header.
    """
    lines=open(txt_path,encoding='utf-8',errors='ignore').read().splitlines(); trips=[]
    ids=[]; centers=[]; cur=[]; last_station=None
    def finalize():
        nonlocal cur
        for tr in cur:
            if not tr or len(tr['p'])<2: continue
            out=[]; prev=None; add=0
            for st,rawsec in tr['p']:
                sec=rawsec+add
                if prev is not None and sec<prev:
                    if prev>=20*3600 and sec<5*3600:
                        add+=86400; sec+=86400
                    else:
                        continue
                if not out or (st,sec)!=out[-1]: out.append((st,sec))
                prev=sec
            if len(out)>=2 and out[-1][1]>out[0][1]:
                append_motion_segments(trips,tr['id'],linecode,out)
        cur=[None]*len(ids)
    def set_header(newids,newcenters):
        nonlocal ids,centers,cur,last_station
        finalize(); ids=newids; centers=newcenters
        cur=[{'id':x,'p':[]} if x else None for x in ids]
        last_station=None
    for line in lines:
        low=line.lower()
        # Current Trip no. starts a new physical timetable block. Do NOT consume
        # the intervening `Next Trip No.` rows; those refer to future workings.
        if re.search(r'\btrip\s*no\.?',line,re.I) and not re.search(r'\bnext\s+trip\s*no\.?',line,re.I):
            a,b=header_tokens(line,r'\btrip\s*no\.?')
            if len(a)>=1: set_header(a,b)
            continue
        if re.search(r'\bnext\s+trip\s*no\.?',line,re.I):
            continue
        if not centers: continue
        em=event_re.match(line)
        if not em: continue
        rawst=em.group(1).strip()
        if rawst:
            rawst=rawst.split()[0]
            if rawst.lower() not in ('train','notes','next'): last_station=rawst
        station=norm_station(last_station or '')
        if not station: continue
        times=[]
        for tm in time_re.finditer(line):
            hh=int(tm.group(1)); mm=int(tm.group(2)); ss=int(tm.group(3) or 0)
            if mm<60 and ss<60: times.append(((tm.start()+tm.end())/2,hh*3600+mm*60+ss))
        if not times: continue
        spacing=statistics.median(abs(centers[k+1]-centers[k]) for k in range(len(centers)-1)) if len(centers)>1 else 12
        assigned={}
        for cc,sec in times:
            j=min(range(len(centers)),key=lambda k:abs(centers[k]-cc)); d=abs(centers[j]-cc)
            if d>spacing*0.70: continue
            if j not in assigned or d<assigned[j][0]: assigned[j]=(d,sec)
        for j,(_,sec) in assigned.items():
            if j<len(cur) and cur[j]: cur[j]['p'].append((station,sec))
    finalize(); return trips


def parse_lrl_schedule(txt_path,linecode='LRL'):
    """Parse Light Rail WTs, whose Journey No. footer follows each timing block."""
    lines=open(txt_path,encoding='utf-8',errors='ignore').read().splitlines(); trips=[]
    block=[]; pending_station=None
    def extract_times(line):
        vals=[]
        for tm in time_re.finditer(line):
            hh=int(tm.group(1)); mm=int(tm.group(2)); ss=int(tm.group(3) or 0)
            if mm<60 and ss<60: vals.append(((tm.start()+tm.end())/2,hh*3600+mm*60+ss))
        return vals
    def emit(ids,centers,rows):
        if not ids or not rows:return
        cur=[{'id':x,'p':[]} for x in ids]
        spacing=statistics.median(abs(centers[k+1]-centers[k]) for k in range(len(centers)-1)) if len(centers)>1 else 12
        for station,times in rows:
            if not station:continue
            assigned={}
            for cc,sec in times:
                j=min(range(len(centers)),key=lambda k:abs(centers[k]-cc)); d=abs(centers[j]-cc)
                if d>spacing*0.72:continue
                if j not in assigned or d<assigned[j][0]:assigned[j]=(d,sec)
            for j,(_,sec) in assigned.items(): cur[j]['p'].append((station,sec))
        for tr in cur:
            if len(tr['p'])<2:continue
            out=[]; prev=None; add=0
            for st,rawsec in tr['p']:
                sec=rawsec+add
                if prev is not None and sec<prev:
                    # Some WTs reset to 00:xx after 23:xx; explicit 24/25-hour cells need no adjustment.
                    if rawsec<5*3600 and (prev%86400)>=20*3600:
                        add+=86400; sec=rawsec+add
                    else:continue
                if not out or (st,sec)!=out[-1]:out.append((st,sec))
                prev=sec
            if len(out)>=2 and out[-1][1]>out[0][1]:
                append_motion_segments(trips,tr['id'],linecode,out)
    for line in lines:
        # A Journey No. line closes the timing block immediately above it.
        if re.search(r'\bjourney\s*no\.?',line,re.I):
            ids,centers=header_tokens(line,r'\bjourney\s*no\.?')
            if ids and block: emit(ids,centers,block)
            block=[]; pending_station=None
            continue
        lm=lrl_re.match(line)
        if lm:
            pending_station=norm_station(lm.group(1))
            vals=extract_times(line)
            if vals:
                if pending_station:block.append((pending_station,vals))
                pending_station=None
            continue
        if pending_station:
            vals=extract_times(line)
            if vals:
                block.append((pending_station,vals)); pending_station=None
                continue
            if line.strip(): pending_station=None
    return trips

# Parse each unique regular timetable once.
schedules={}; schedule_meta={}
for rel,m in meta.items():
    line=rel.split('/')[0]
    line='LAR' if line.startswith('LAR') else line
    trips=parse_lrl_schedule(m['txt'],line) if line=='LRL' else (parse_lar_schedule(m['txt'],line) if line=='LAR' else parse_schedule(m['txt'],line))
    sid=m['id']
    schedules[sid]=trips
    schedule_meta[sid]={k:m[k] for k in ('file','effective','pages')}
    schedule_meta[sid]['line']=line
    schedule_meta[sid]['tripCount']=len(trips)

# Build profile map schedule IDs.
profile_out={}
for key,prof in profiles.items():
    profile_out[key]={'label':prof['label'],'lines':{},'warnings':[]}
    for line,rel in prof.items():
        if line=='label':continue
        sid=meta[rel]['id']; profile_out[key]['lines'][line]=sid
        if line in warning_by_line:profile_out[key]['warnings'].append({'line':line,'text':warning_by_line[line]})

# Canonical passenger-station graphs used so trains follow real route shape between timing points.
paths={
 'TWL':[['TSW','TWH','KWH','KWF','LAK','MEF','LCK','CSW','SSP','PRE','MOK','YMT','JOR','TST','ADM','CEN']],
 'ISL':[['KET','HKU','SYP','SHW','CEN','ADM','WAC','CAB','TIH','FOH','NOP','QUB','TAK','SWH','SKW','HFC','CHW']],
 'KTL':[['WHA','HOM','YMT','MOK','PRE','SKM','KOT','LOF','WTS','DIH','CHH','KOB','NTK','KWT','LAT','YAT','TIK']],
 'TKL':[['NOP','QUB','YAT','TIK','TKO','HAH','POA'],['TKO','LHP']],
 'SIL':[['ADM','OCP','WCH','LET','SOH']],
 'EAL':[['ADM','EXC','HUH','MKK','KOT','TAW','SHT','FOT','UNI','TAP','TWO','FAN','SHS','LOW'],['SHT','RAC','UNI'],['SHS','LMC']],
 'TML':[['WKS','MOS','HEO','TSH','SHM','CIO','STW','CKT','TAW','HIK','DIH','KAT','SUW','TKW','HOM','HUH','ETS','AUS','NAC','MEF','TWW','KSR','YUL','LOP','TIS','SIH','TUM']],
 'LAR':[['HOK','KOW','TSY','AIR','AWE'],['HOK','KOW','OLY','NAC','LAK','TSY','SUN','TUC']],
 'DRL':[['SUN','DIS']],
}
# Keep only map-resolvable station nodes.
paths={k:[[s for s in p if s in coords] for p in vv] for k,vv in paths.items()}

line_info={
 'TWL':{'name':'Tsuen Wan Line','color':'#d71920'},
 'ISL':{'name':'Island Line','color':'#0079c2'},
 'KTL':{'name':'Kwun Tong Line','color':'#00a651'},
 'TKL':{'name':'Tseung Kwan O Line','color':'#7b4397'},
 'TML':{'name':'Tuen Ma Line','color':'#9a3820'},
 'EAL':{'name':'East Rail Line','color':'#5eb6e4'},
 'LAR':{'name':'Tung Chung / Airport Express','color':'#f7943e'},
 'SIL':{'name':'South Island Line','color':'#b5bd00'},
 'DRL':{'name':'Disneyland Resort Line','color':'#e86a9f'},
 'LRL':{'name':'Light Rail','color':'#d6a400'},
}

# A complete timetable file catalog for provenance/audit.
catalog=[]
with zipfile.ZipFile(ZIP) as z:
    for n in z.namelist():
        if '/Timetables/' in n and n.lower().endswith('.pdf'):
            catalog.append(n.split('/Timetables/',1)[1])

payload={
 'generated':'2026-09-08',
 'mode':'timetable_simulation',
 'map':{'width':W,'height':H,'source':'TD/GeoTD.pdf','label':'Hong Kong Local Heavy Railways and Light Rail Geographic Track Diagram'},
 'lines':line_info,
 'stations':{k:{'x':round(v['x'],8),'y':round(v['y'],8),'name':station_names.get(k,k)} for k,v in coords.items()},
 'paths':paths,
 'profiles':profile_out,
 'scheduleMeta':schedule_meta,
 'schedules':schedules,
 'catalogCount':len(catalog),
}

with open(os.path.join(OUT,'data.js'),'w',encoding='utf-8') as f:
    f.write('window.TRAIN_DATA='); json.dump(payload,f,separators=(',',':'),ensure_ascii=False); f.write(';\n')
with open(os.path.join(OUT,'source_catalog.json'),'w',encoding='utf-8') as f: json.dump({'timetables':catalog},f,indent=2,ensure_ascii=False)

# Website.
html='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hong Kong Timetable Train Display</title><link rel="stylesheet" href="styles.css"></head>
<body><div id="app">
<header class="topbar">
  <div class="brand"><div class="pulse"></div><div><strong>HK Train Display</strong><span>Timetable-simulated operations</span></div></div>
  <div class="clockblock"><span id="clock">--:--:--</span><small>Hong Kong time</small></div>
  <div class="controls">
    <label>Schedule<select id="profile"></select></label>
    <button id="nowBtn" class="primary">Now</button><button id="playBtn">Pause</button>
    <label>Speed<select id="speed"><option value="1">1×</option><option value="10">10×</option><option value="60">60×</option><option value="300">300×</option></select></label>
  </div>
</header>
<main class="layout">
  <section class="map-panel">
    <div class="statusrow"><div><span class="badge">SCHEDULE SIMULATION</span><span id="profileStatus"></span></div><div class="map-actions"><button id="zoomOut">−</button><button id="resetMap">Reset</button><button id="zoomIn">+</button></div></div>
    <div id="mapViewport" class="map-viewport" tabindex="0" aria-label="Interactive train map. Drag to pan and use wheel or zoom buttons to zoom.">
      <div id="mapWorld" class="map-world"><img src="assets/geotd-map.png" alt="Hong Kong geographic railway track diagram"><div id="markers" class="markers"></div></div>
    </div>
    <div class="timeline"><input id="timeRange" type="range" min="14400" max="100800" step="30"><div><span>04:00</span><strong id="simTime">--:--:--</strong><span>28:00</span></div></div>
    <div id="legend" class="legend"></div>
  </section>
  <aside class="sidebar">
    <div class="summary"><div><b id="activeCount">0</b><span>active trains</span></div><div><b id="sourceCount">0</b><span>source trips</span></div></div>
    <div id="warningBox" class="warning"></div>
    <div class="filterHead"><strong>Lines</strong><button id="allLines">All</button></div><div id="lineFilters" class="lineFilters"></div>
    <label class="search"><span>Find train</span><input id="search" placeholder="Trip / train no."></label>
    <div id="trainList" class="trainList"></div>
  </aside>
</main>
<div id="detail" class="detail hidden"><button id="closeDetail">×</button><div id="detailBody"></div></div>
</div><script src="data.js"></script><script src="app.js"></script></body></html>'''
open(os.path.join(OUT,'index.html'),'w',encoding='utf-8').write(html)

css='''*{box-sizing:border-box}html,body{margin:0;background:#0b0e13;color:#eef2f7;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;height:100%}button,select,input{font:inherit}.topbar{min-height:72px;display:flex;align-items:center;gap:22px;padding:12px 18px;border-bottom:1px solid #262c35;background:#11151c}.brand{display:flex;align-items:center;gap:10px;min-width:220px}.brand strong{display:block;font-size:16px}.brand span,.clockblock small{display:block;color:#8d98a8;font-size:11px;margin-top:2px}.pulse{width:10px;height:10px;border-radius:50%;background:#39d98a;box-shadow:0 0 0 5px #39d98a1d}.clockblock{margin-left:auto;text-align:right}.clockblock #clock{font:700 20px ui-monospace,SFMono-Regular,Menlo,monospace}.controls{display:flex;align-items:end;gap:8px}.controls label{font-size:10px;color:#8994a4}.controls select{display:block;margin-top:3px;background:#171c24;border:1px solid #303845;color:#eef2f7;border-radius:7px;padding:7px 28px 7px 9px}.controls button,.map-actions button,.filterHead button{border:1px solid #303845;background:#171c24;color:#dbe2ea;border-radius:7px;padding:8px 11px;cursor:pointer}.controls .primary{background:#1c5cff;border-color:#1c5cff;color:white}.layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;height:calc(100vh - 72px)}.map-panel{min-width:0;display:flex;flex-direction:column;position:relative;background:#0f1319}.statusrow{min-height:42px;display:flex;align-items:center;justify-content:space-between;padding:7px 12px;border-bottom:1px solid #222933;font-size:12px;color:#9ca7b6}.badge{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.06em;color:#f7c654;border:1px solid #8a6b20;background:#342b14;padding:4px 7px;border-radius:999px;margin-right:9px}.map-actions{display:flex;gap:5px}.map-actions button{padding:4px 9px}.map-viewport{position:relative;flex:1;overflow:hidden;cursor:grab;background:#d9dde0;min-height:300px}.map-viewport.dragging{cursor:grabbing}.map-world{position:absolute;left:0;top:0;transform-origin:0 0;width:100%;will-change:transform}.map-world img{display:block;width:100%;height:auto;user-select:none;pointer-events:none}.markers{position:absolute;inset:0;pointer-events:none}.train-marker{appearance:none;padding:0;position:absolute;width:11px;height:11px;margin:-5.5px 0 0 -5.5px;border-radius:50%;border:2px solid #10141a;box-shadow:0 0 0 1px rgba(255,255,255,.8),0 1px 5px #0008;pointer-events:auto;cursor:pointer;transition:left .8s linear,top .8s linear}.train-marker.selected{width:16px;height:16px;margin:-8px 0 0 -8px;border-width:3px;z-index:5}.timeline{padding:8px 14px;background:#11161d;border-top:1px solid #252c35}.timeline input{width:100%;accent-color:#4a83ff}.timeline div{display:flex;justify-content:space-between;color:#778394;font-size:10px}.timeline strong{color:#f0f4f8;font:700 13px ui-monospace,monospace}.legend{display:flex;gap:5px;overflow-x:auto;padding:7px 10px;border-top:1px solid #222933;background:#0e1218}.legend span{white-space:nowrap;border:1px solid #303744;border-radius:999px;padding:3px 7px;font-size:10px;color:#bac3cf}.legend i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}.sidebar{border-left:1px solid #262c35;background:#11151b;overflow:auto}.summary{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #262c35}.summary div{padding:14px}.summary div+div{border-left:1px solid #262c35}.summary b{display:block;font-size:24px}.summary span{font-size:10px;color:#8c97a6}.warning{display:none;margin:10px;padding:9px 10px;border-radius:8px;border:1px solid #594d25;background:#2b2616;color:#e6cd7d;font-size:11px;line-height:1.4}.warning.show{display:block}.filterHead{display:flex;justify-content:space-between;align-items:center;padding:10px 12px 4px}.filterHead button{padding:3px 8px;font-size:10px}.lineFilters{display:flex;flex-wrap:wrap;gap:5px;padding:5px 10px 9px;border-bottom:1px solid #262c35}.lineFilters label{display:flex;align-items:center;gap:5px;font-size:10px;padding:4px 6px;border:1px solid #303744;border-radius:999px;cursor:pointer}.lineFilters input{accent-color:#4a83ff}.search{display:block;padding:10px 12px;border-bottom:1px solid #262c35;font-size:10px;color:#8e99a7}.search input{display:block;width:100%;margin-top:5px;background:#0d1117;border:1px solid #303845;color:white;border-radius:7px;padding:8px}.trainList{padding:6px}.trainRow{display:grid;grid-template-columns:8px 1fr auto;gap:8px;align-items:center;padding:8px;border-radius:7px;cursor:pointer}.trainRow:hover{background:#1a2029}.trainRow i{width:8px;height:26px;border-radius:4px}.trainRow b{display:block;font-size:12px}.trainRow span{display:block;color:#8f99a7;font-size:10px;margin-top:2px}.trainRow time{font:600 11px ui-monospace,monospace;color:#c8d0da}.empty{padding:30px 12px;text-align:center;color:#687484;font-size:12px}.detail{position:fixed;right:350px;top:88px;width:310px;background:#171c24;border:1px solid #36404e;border-radius:12px;box-shadow:0 18px 60px #0008;padding:14px;z-index:20}.detail.hidden{display:none}.detail>button{position:absolute;right:8px;top:7px;background:none;border:0;color:#9aa5b4;font-size:20px;cursor:pointer}.detail h2{font-size:16px;margin:0 26px 3px 0}.detail .sub{font-size:11px;color:#8d98a7;margin-bottom:12px}.detail dl{display:grid;grid-template-columns:90px 1fr;gap:7px;font-size:11px}.detail dt{color:#7f8a99}.detail dd{margin:0}.progressbar{height:5px;background:#303744;border-radius:9px;overflow:hidden;margin:12px 0}.progressbar i{display:block;height:100%;background:#5d8fff}.source{font-size:10px;color:#758191;line-height:1.4;border-top:1px solid #2b323c;padding-top:10px;margin-top:10px}@media(max-width:900px){.layout{grid-template-columns:1fr;height:auto}.map-panel{height:70vh}.sidebar{border-left:0;border-top:1px solid #262c35;max-height:none}.topbar{flex-wrap:wrap}.clockblock{margin-left:auto}.controls{width:100%;overflow-x:auto}.detail{right:12px;left:12px;top:120px;width:auto}.brand{min-width:auto}}'''
open(os.path.join(OUT,'styles.css'),'w',encoding='utf-8').write(css)

js=r'''(()=>{const D=window.TRAIN_DATA,$=s=>document.querySelector(s);const profileSel=$('#profile'),clock=$('#clock'),simTimeEl=$('#simTime'),range=$('#timeRange'),markers=$('#markers'),list=$('#trainList'),warning=$('#warningBox'),detail=$('#detail'),detailBody=$('#detailBody');let profileKey='weekday',simSec=0,playing=true,speed=1,lastTs=performance.now(),lastRender=0,enabled=new Set(Object.keys(D.lines)),selected=null,currentTrips=[];let mapScale=1,mapX=0,mapY=0,drag=null;const world=$('#mapWorld'),viewport=$('#mapViewport');
function fmt(sec){sec=((Math.floor(sec)%86400)+86400)%86400;let h=Math.floor(sec/3600),m=Math.floor(sec%3600/60),s=Math.floor(sec%60);return [h,m,s].map(x=>String(x).padStart(2,'0')).join(':')}
function hkNow(){const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Hong_Kong',hour:'2-digit',minute:'2-digit',second:'2-digit',weekday:'short',hour12:false}).formatToParts(new Date());let o={};parts.forEach(p=>o[p.type]=p.value);return {sec:+o.hour*3600+ +o.minute*60+ +o.second,weekday:o.weekday}}
function autoProfile(){let w=hkNow().weekday;return w==='Fri'?'friday':w==='Sat'?'saturday':w==='Sun'?'sunday':'weekday'}
function loadProfileTrips(){let p=D.profiles[profileKey],out=[];for(const [line,sid] of Object.entries(p.lines)){for(const t of D.schedules[sid]||[])out.push(t)}currentTrips=out}
function sourceTrips(){return currentTrips.length}
function buildGraph(line){let g={};for(const path of D.paths[line]||[]){for(let i=0;i<path.length-1;i++){let a=path[i],b=path[i+1];(g[a]??=[]).push(b);(g[b]??=[]).push(a)}}return g}const graphs={};for(const l of Object.keys(D.lines))graphs[l]=buildGraph(l);const pathCache=new Map();
function route(line,a,b){let key=line+'|'+a+'|'+b;if(pathCache.has(key))return pathCache.get(key);if(a===b)return [a];let g=graphs[line]||{},q=[[a]],seen=new Set([a]);while(q.length){let p=q.shift(),x=p[p.length-1];for(const n of g[x]||[]){if(seen.has(n))continue;let np=p.concat(n);if(n===b){pathCache.set(key,np);return np}seen.add(n);q.push(np)}}let direct=[a,b];pathCache.set(key,direct);return direct}
function interpPath(line,a,b,t){let codes=route(line,a,b).filter(c=>D.stations[c]);if(codes.length<2)codes=[a,b].filter(c=>D.stations[c]);if(codes.length<2)return null;let pts=codes.map(c=>D.stations[c]),lens=[],total=0;for(let i=0;i<pts.length-1;i++){let dx=(pts[i+1].x-pts[i].x),dy=(pts[i+1].y-pts[i].y),d=Math.hypot(dx,dy);lens.push(d);total+=d}let target=Math.max(0,Math.min(1,t))*total,acc=0;for(let i=0;i<lens.length;i++){if(target<=acc+lens[i]||i===lens.length-1){let u=lens[i]?((target-acc)/lens[i]):0;return{x:pts[i].x+(pts[i+1].x-pts[i].x)*u,y:pts[i].y+(pts[i+1].y-pts[i].y)*u}}acc+=lens[i]}return pts[pts.length-1]}
function stateAt(t,sec){let p=t[2];if(sec<p[0][1]||sec>p[p.length-1][1])return null;let i=0;while(i<p.length-2&&sec>p[i+1][1])i++;let a=p[i],b=p[i+1],den=b[1]-a[1],u=den?Math.max(0,Math.min(1,(sec-a[1])/den)):0,pos=interpPath(t[1],a[0],b[0],u);if(!pos)return null;return{trip:t,line:t[1],a,b,u,pos,overall:(sec-p[0][1])/(p[p.length-1][1]-p[0][1])}}
function active(){let out=[];for(const t of currentTrips){if(!enabled.has(t[1]))continue;let s=stateAt(t,simSec);if(s)out.push(s)}return out}
function renderMarkers(a){let keep=new Set;for(const s of a){let id=s.line+'-'+s.trip[0]+'-'+s.trip[2][0][1];keep.add(id);let el=document.getElementById('m-'+id);if(!el){el=document.createElement('button');el.className='train-marker';el.id='m-'+id;el.title=s.line+' '+s.trip[0];el.style.background=D.lines[s.line].color;el.addEventListener('click',e=>{e.stopPropagation();selectTrip(s.trip)});markers.appendChild(el)}el.style.left=(s.pos.x*100)+'%';el.style.top=(s.pos.y*100)+'%';el.classList.toggle('selected',selected===s.trip)}for(const el of [...markers.children]){let id=el.id.slice(2);if(!keep.has(id))el.remove()}}
function renderList(a){let q=$('#search').value.trim().toLowerCase();let items=a.filter(s=>!q||s.trip[0].toLowerCase().includes(q)||D.lines[s.line].name.toLowerCase().includes(q)).sort((x,y)=>x.b[1]-y.b[1]).slice(0,180);list.innerHTML=items.length?'':'<div class="empty">No active trains match this view.</div>';for(const s of items){let r=document.createElement('div');r.className='trainRow';r.innerHTML=`<i style="background:${D.lines[s.line].color}"></i><div><b>${s.line} ${s.trip[0]}</b><span>${D.stations[s.a[0]]?.name||s.a[0]} → ${D.stations[s.b[0]]?.name||s.b[0]}</span></div><time>${fmt(s.b[1])}</time>`;r.onclick=()=>selectTrip(s.trip);list.appendChild(r)}}
function selectTrip(t){selected=t;let s=stateAt(t,simSec);if(!s){detail.classList.add('hidden');return}let sid=D.profiles[profileKey].lines[t[1]],m=D.scheduleMeta[sid],p=t[2];detailBody.innerHTML=`<h2>${D.lines[t[1]].name} · ${t[0]}</h2><div class="sub">Scheduled train / trip</div><dl><dt>From</dt><dd>${D.stations[p[0][0]]?.name||p[0][0]} · ${fmt(p[0][1])}</dd><dt>To</dt><dd>${D.stations[p[p.length-1][0]]?.name||p[p.length-1][0]} · ${fmt(p[p.length-1][1])}</dd><dt>Now between</dt><dd>${D.stations[s.a[0]]?.name||s.a[0]} → ${D.stations[s.b[0]]?.name||s.b[0]}</dd><dt>Next timing</dt><dd>${fmt(s.b[1])}</dd></dl><div class="progressbar"><i style="width:${Math.max(0,Math.min(100,s.overall*100))}%"></i></div><div class="source">Source: ${m.file}<br>Effective: ${m.effective||'not extracted'} · ${m.tripCount} parsed trips<br>Position is interpolated from the timetable and track diagram; it is not GPS/ATS telemetry.</div>`;detail.classList.remove('hidden');render()}
function render(){clock.textContent=fmt(hkNow().sec);simTimeEl.textContent=fmt(simSec)+(simSec>=86400?' +1d':'');range.value=Math.max(+range.min,Math.min(+range.max,simSec));let a=active();$('#activeCount').textContent=a.length;$('#sourceCount').textContent=sourceTrips().toLocaleString();renderMarkers(a);renderList(a);if(selected){let s=stateAt(selected,simSec);if(!s)detail.classList.add('hidden')} }
function setProfile(k){profileKey=k;profileSel.value=k;loadProfileTrips();selected=null;detail.classList.add('hidden');let p=D.profiles[k];$('#profileStatus').textContent=p.label+' · '+Object.keys(p.lines).length+' lines';warning.innerHTML=p.warnings.length?'<strong>Coverage notes</strong><br>'+p.warnings.map(x=>x.line+': '+x.text).join('<br>'):'';warning.classList.toggle('show',!!p.warnings.length);buildFilters();render()}
function buildFilters(){let lines=Object.keys(D.profiles[profileKey].lines);enabled=new Set(lines);let box=$('#lineFilters');box.innerHTML='';for(const l of lines){let lab=document.createElement('label');lab.innerHTML=`<input type="checkbox" checked value="${l}"><span style="color:${D.lines[l].color}">●</span>${l}`;lab.querySelector('input').onchange=e=>{e.target.checked?enabled.add(l):enabled.delete(l);render()};box.appendChild(lab)}let leg=$('#legend');leg.innerHTML=lines.map(l=>`<span><i style="background:${D.lines[l].color}"></i>${D.lines[l].name}</span>`).join('')}
for(const [k,p] of Object.entries(D.profiles)){let o=document.createElement('option');o.value=k;o.textContent=p.label;profileSel.appendChild(o)}profileSel.onchange=e=>setProfile(e.target.value);$('#nowBtn').onclick=()=>{simSec=hkNow().sec;setProfile(autoProfile());render()};$('#playBtn').onclick=e=>{playing=!playing;e.currentTarget.textContent=playing?'Pause':'Play'};$('#speed').onchange=e=>speed=+e.target.value;range.oninput=e=>{simSec=+e.target.value;playing=false;$('#playBtn').textContent='Play';render()};$('#search').oninput=render;$('#allLines').onclick=()=>{enabled=new Set(Object.keys(D.profiles[profileKey].lines));document.querySelectorAll('#lineFilters input').forEach(x=>x.checked=true);render()};$('#closeDetail').onclick=()=>{selected=null;detail.classList.add('hidden');render()};
function applyMap(){world.style.transform=`translate(${mapX}px,${mapY}px) scale(${mapScale})`}function zoom(f,cx=viewport.clientWidth/2,cy=viewport.clientHeight/2){let old=mapScale;mapScale=Math.max(.7,Math.min(6,mapScale*f));mapX=cx-(cx-mapX)*(mapScale/old);mapY=cy-(cy-mapY)*(mapScale/old);applyMap()}$('#zoomIn').onclick=()=>zoom(1.25);$('#zoomOut').onclick=()=>zoom(.8);$('#resetMap').onclick=()=>{mapScale=1;mapX=0;mapY=0;applyMap()};viewport.addEventListener('wheel',e=>{e.preventDefault();let r=viewport.getBoundingClientRect();zoom(e.deltaY<0?1.15:.87,e.clientX-r.left,e.clientY-r.top)},{passive:false});viewport.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,mx:mapX,my:mapY};viewport.setPointerCapture(e.pointerId);viewport.classList.add('dragging')});viewport.addEventListener('pointermove',e=>{if(!drag)return;mapX=drag.mx+e.clientX-drag.x;mapY=drag.my+e.clientY-drag.y;applyMap()});viewport.addEventListener('pointerup',()=>{drag=null;viewport.classList.remove('dragging')});
profileKey=autoProfile();simSec=hkNow().sec;setProfile(profileKey);applyMap();function tick(ts){let dt=(ts-lastTs)/1000;lastTs=ts;if(playing){simSec+=dt*speed;if(simSec>100800)simSec=14400}if(ts-lastRender>=500){render();lastRender=ts}requestAnimationFrame(tick)}requestAnimationFrame(tick);})();'''
open(os.path.join(OUT,'app.js'),'w',encoding='utf-8').write(js)

# Coverage/report/readme.
rows=[]
for pk,p in profile_out.items():
    for line,sid in p['lines'].items():
        m=schedule_meta[sid]; rows.append((p['label'],line,sid,m['effective'] or '',m['tripCount'],m['file']))
coverage=['# Data coverage and provenance','',
'**Display mode:** timetable simulation, not GPS/ATS telemetry. Positions are interpolated between scheduled timing points and projected over the supplied `GeoTD.pdf` geographic track diagram.','',
'## Important archive gaps','',
'The attached `WT & other info.docx` is dated **3 June 2026** and explicitly says several latest working timetables are missing. The site surfaces these as coverage warnings rather than silently treating older PDFs as current.','']
for line,text in warning_by_line.items():coverage.append(f'- **{line}:** {text}')
coverage+=['','## Regular profiles included','','| Profile | Line | Timetable | Effective | Parsed trips | Source PDF |','|---|---|---|---|---:|---|']
for r in rows:coverage.append('| '+' | '.join(str(x).replace('|','/') for x in r)+' |')
coverage+=['','## Scope','','- Four regular day profiles: Monday–Thursday, Friday, Saturday, Sunday/public holiday.','- 10 operating groups are represented: KTL, ISL, TWL, TKL, LRL, TML, LAR (TCL/AEL), SIL, EAL, DRL.','- Special-event, race-day, overnight and engineering/special timetables remain in the source catalog but are intentionally not auto-activated.','- `source_catalog.json` lists every timetable PDF found in the uploaded archive.','',
'## Interpretation','','A train is shown as active from its first parsed scheduled timing point to its final timing point. Between timing points, position is linearly interpolated by distance along a station graph built from the supplied geographic track diagram. Some working timetables only print selected timing points, so intermediate motion is reconstructed along the route geometry.']
open(os.path.join(OUT,'DATA_COVERAGE.md'),'w',encoding='utf-8').write('\n'.join(coverage))

readme='''# HK Train Display\n\nInteractive static website generated from the supplied timetable archive and geographic track diagram.\n\n## Run\n\nThe site is self-contained. Open `index.html` directly in a modern browser. For the most consistent browser behaviour you can also run:\n\n```bash\npython3 -m http.server 8080\n```\n\nthen open `http://localhost:8080`.\n\n## Features\n\n- Live Hong Kong clock and timetable-based train animation\n- Geographic track-diagram map with pan/zoom\n- Monday–Thursday, Friday, Saturday and Sunday/PH regular profiles\n- Line filters, train search, active-train list and trip detail panel\n- Time scrubber and accelerated playback\n- Source timetable/effective-date provenance and missing-current-file warnings\n- No backend or build step required\n\n## Accuracy\n\nThis is **not a real-time GPS/ATS feed**. It reconstructs scheduled positions from working timetables. See `DATA_COVERAGE.md` for source gaps and interpretation details.\n'''
open(os.path.join(OUT,'README.md'),'w',encoding='utf-8').write(readme)

# Small launch helper for users who prefer a local HTTP server.
serve='''#!/usr/bin/env python3\nimport http.server, socketserver, webbrowser, threading\nPORT=8080\nthreading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()\nwith socketserver.TCPServer(("127.0.0.1",PORT),http.server.SimpleHTTPRequestHandler) as httpd:\n    print(f"HK Train Display running at http://localhost:{PORT}")\n    httpd.serve_forever()\n'''
open(os.path.join(OUT,'serve.py'),'w',encoding='utf-8').write(serve)

print('OUT',OUT)
print('schedules',len(schedules),'catalog',len(catalog),'data.js MB',os.path.getsize(os.path.join(OUT,'data.js'))/1e6)
for sid,m in sorted(schedule_meta.items()): print(sid,m['line'],m['effective'],m['tripCount'])
