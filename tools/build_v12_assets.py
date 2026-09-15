from pathlib import Path
import json, math

ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'data.js').read_text(encoding='utf-8')
D=json.loads(raw[len('window.TRAIN_DATA='):].rstrip().rstrip(';'))

# Full public heavy-rail station sequences used for clickable station boards.
# TKL/EAL branches are represented as separate paths.
PATHS={
'TWL':[['TSW','TWH','KWH','KWF','LAK','MEF','LCK','CSW','SSP','PRE','MOK','YMT','JOR','TST','ADM','CEN']],
'ISL':[['KET','HKU','SYP','SHW','CEN','ADM','WAC','CAB','TIH','FOH','NOP','QUB','TAK','SWH','SKW','HFC','CHW']],
'KTL':[['TIK','YAT','LAT','KWT','NTK','KOB','CHH','DIH','WTS','LOF','KOT','SKM','PRE','MOK','YMT','HOM','WHA']],
'TKL':[['NOP','QUB','YAT','TIK','TKO','HAH','POA'],['NOP','QUB','YAT','TIK','TKO','LHP']],
'SIL':[['ADM','OCP','WCH','LET','SOH']],
'TML':[['TUM','SIH','TIS','LOP','YUL','KSR','TWW','MEF','NAC','AUS','ETS','HUH','HOM','TKW','SUW','KAT','DIH','HIK','TAW','CKT','STW','CIO','SHM','TSH','HEO','MOS','WKS']],
'EAL':[['ADM','EXC','HUH','MKK','KOT','TAW','SHT','FOT','UNI','TAP','TWO','FAN','SHS','LOW'],['ADM','EXC','HUH','MKK','KOT','TAW','SHT','FOT','UNI','TAP','TWO','FAN','SHS','LMC'],['TAW','SHT','RAC','UNI']],
'TCL':[['HOK','KOW','OLY','NAC','LAK','TSY','SUN','TUC']],
'AEL':[['HOK','KOW','TSY','AIR','AWE']],
'DRL':[['SUN','DIS']],
}
NAMES={
'TSW':'Tsuen Wan','TWH':'Tai Wo Hau','KWH':'Kwai Hing','KWF':'Kwai Fong','LAK':'Lai King','MEF':'Mei Foo','LCK':'Lai Chi Kok','CSW':'Cheung Sha Wan','SSP':'Sham Shui Po','PRE':'Prince Edward','MOK':'Mong Kok','YMT':'Yau Ma Tei','JOR':'Jordan','TST':'Tsim Sha Tsui','ADM':'Admiralty','CEN':'Central',
'KET':'Kennedy Town','HKU':'HKU','SYP':'Sai Ying Pun','SHW':'Sheung Wan','WAC':'Wan Chai','CAB':'Causeway Bay','TIH':'Tin Hau','FOH':'Fortress Hill','NOP':'North Point','QUB':'Quarry Bay','TAK':'Tai Koo','SWH':'Sai Wan Ho','SKW':'Shau Kei Wan','HFC':'Heng Fa Chuen','CHW':'Chai Wan',
'TIK':'Tiu Keng Leng','YAT':'Yau Tong','LAT':'Lam Tin','KWT':'Kwun Tong','NTK':'Ngau Tau Kok','KOB':'Kowloon Bay','CHH':'Choi Hung','DIH':'Diamond Hill','WTS':'Wong Tai Sin','LOF':'Lok Fu','KOT':'Kowloon Tong','SKM':'Shek Kip Mei','HOM':'Ho Man Tin','WHA':'Whampoa',
'TKO':'Tseung Kwan O','HAH':'Hang Hau','POA':'Po Lam','LHP':'LOHAS Park',
'OCP':'Ocean Park','WCH':'Wong Chuk Hang','LET':'Lei Tung','SOH':'South Horizons',
'TUM':'Tuen Mun','SIH':'Siu Hong','TIS':'Tin Shui Wai','LOP':'Long Ping','YUL':'Yuen Long','KSR':'Kam Sheung Road','TWW':'Tsuen Wan West','NAC':'Nam Cheong','AUS':'Austin','ETS':'East Tsim Sha Tsui','HUH':'Hung Hom','TKW':'To Kwa Wan','SUW':'Sung Wong Toi','KAT':'Kai Tak','HIK':'Hin Keng','TAW':'Tai Wai','CKT':'Che Kung Temple','STW':'Sha Tin Wai','CIO':'City One','SHM':'Shek Mun','TSH':'Tai Shui Hang','HEO':'Heng On','MOS':'Ma On Shan','WKS':'Wu Kai Sha',
'EXC':'Exhibition Centre','MKK':'Mong Kok East','SHT':'Sha Tin','FOT':'Fo Tan','RAC':'Racecourse','UNI':'University','TAP':'Tai Po Market','TWO':'Tai Wo','FAN':'Fanling','SHS':'Sheung Shui','LOW':'Lo Wu','LMC':'Lok Ma Chau',
'HOK':'Hong Kong','KOW':'Kowloon','OLY':'Olympic','TSY':'Tsing Yi','SUN':'Sunny Bay','TUC':'Tung Chung','AIR':'Airport','AWE':'AsiaWorld-Expo','DIS':'Disneyland Resort'
}
# Approximate station centroids in WGS84, sufficient for map overlay. Track curves remain the supplied GeoTD geometry warped between these anchors.
GEO={
'TSW':(22.3730,114.1170),'TWH':(22.3708,114.1250),'KWH':(22.3630,114.1315),'KWF':(22.3560,114.1278),'LAK':(22.3485,114.1264),'MEF':(22.3377,114.1375),'LCK':(22.3370,114.1480),'CSW':(22.3350,114.1567),'SSP':(22.3307,114.1621),'PRE':(22.3244,114.1681),'MOK':(22.3193,114.1694),'YMT':(22.3133,114.1706),'JOR':(22.3048,114.1714),'TST':(22.2975,114.1722),'ADM':(22.2794,114.1655),'CEN':(22.2819,114.1589),
'KET':(22.2815,114.1287),'HKU':(22.2830,114.1352),'SYP':(22.2860,114.1420),'SHW':(22.2865,114.1512),'WAC':(22.2775,114.1731),'CAB':(22.2804,114.1849),'TIH':(22.2820,114.1918),'FOH':(22.2882,114.1938),'NOP':(22.2914,114.2001),'QUB':(22.2885,114.2094),'TAK':(22.2844,114.2163),'SWH':(22.2824,114.2223),'SKW':(22.2790,114.2281),'HFC':(22.2769,114.2408),'CHW':(22.2649,114.2371),
'TIK':(22.3040,114.2529),'YAT':(22.2967,114.2376),'LAT':(22.3076,114.2328),'KWT':(22.3121,114.2260),'NTK':(22.3159,114.2190),'KOB':(22.3236,114.2142),'CHH':(22.3347,114.2097),'DIH':(22.3402,114.2011),'WTS':(22.3420,114.1937),'LOF':(22.3380,114.1873),'KOT':(22.3373,114.1760),'SKM':(22.3315,114.1688),'HOM':(22.3094,114.1826),'WHA':(22.3050,114.1905),
'TKO':(22.3075,114.2607),'HAH':(22.3158,114.2645),'POA':(22.3225,114.2570),'LHP':(22.2950,114.2690),
'OCP':(22.2481,114.1742),'WCH':(22.2480,114.1680),'LET':(22.2427,114.1562),'SOH':(22.2420,114.1495),
'TUM':(22.3953,113.9732),'SIH':(22.4118,113.9787),'TIS':(22.4480,114.0045),'LOP':(22.4477,114.0257),'YUL':(22.4460,114.0340),'KSR':(22.4345,114.0636),'TWW':(22.3688,114.1096),'NAC':(22.3268,114.1532),'AUS':(22.3044,114.1665),'ETS':(22.2952,114.1744),'HUH':(22.3030,114.1810),'TKW':(22.3174,114.1884),'SUW':(22.3250,114.1900),'KAT':(22.3290,114.1995),'HIK':(22.3636,114.1700),'TAW':(22.3720,114.1785),'CKT':(22.3748,114.1865),'STW':(22.3770,114.1930),'CIO':(22.3828,114.2030),'SHM':(22.3870,114.2080),'TSH':(22.4080,114.2220),'HEO':(22.4160,114.2250),'MOS':(22.4249,114.2319),'WKS':(22.4294,114.2435),
'EXC':(22.2817,114.1751),'MKK':(22.3210,114.1726),'SHT':(22.3820,114.1870),'FOT':(22.3950,114.1980),'RAC':(22.4002,114.2030),'UNI':(22.4130,114.2100),'TAP':(22.4446,114.1707),'TWO':(22.4510,114.1612),'FAN':(22.4910,114.1392),'SHS':(22.5010,114.1277),'LOW':(22.5280,114.1133),'LMC':(22.5146,114.0656),
'HOK':(22.2851,114.1582),'KOW':(22.3045,114.1615),'OLY':(22.3176,114.1600),'TSY':(22.3585,114.1078),'SUN':(22.3318,114.0289),'TUC':(22.2895,113.9413),'AIR':(22.3156,113.9369),'AWE':(22.3219,113.9407),'DIS':(22.3155,114.0452),
'THW':(22.3020,114.0500),'HTD':(22.4002,114.2030),'WCD':(22.2500,114.1660),'TKD':(22.3035,114.2620),'TWD':(22.3715,114.1145)
}
# Official-map pixel coordinates (1000 x 586 image). Anchors are calibrated to MTR's public system_map.png layout.
# These are intentionally presentation coordinates, not geospatial claims.
OFF={
'TUM':(97,198),'SIH':(95,169),'TIS':(112,82),'LOP':(111,137),'YUL':(139,164),'KSR':(168,204),'TWW':(210,215),'MEF':(363,217),'NAC':(365,282),'AUS':(481,389),'ETS':(566,409),'HUH':(600,378),'HOM':(659,340),'TKW':(712,320),'SUW':(748,286),'KAT':(748,255),'DIH':(731,220),'HIK':(694,190),'TAW':(620,169),'CKT':(668,143),'STW':(676,116),'CIO':(700,59),'SHM':(746,59),'TSH':(792,59),'HEO':(838,59),'MOS':(884,59),'WKS':(930,59),
'TSW':(209,215),'TWH':(247,215),'KWH':(285,215),'KWF':(324,215),'LAK':(363,217),'LCK':(399,219),'CSW':(440,219),'SSP':(478,219),'PRE':(515,247),'MOK':(515,277),'YMT':(515,310),'JOR':(515,344),'TST':(515,378),'ADM':(515,456),'CEN':(438,456),
'KET':(245,444),'HKU':(294,444),'SYP':(341,444),'SHW':(389,444),'WAC':(566,444),'CAB':(611,444),'TIH':(662,444),'FOH':(716,444),'NOP':(771,444),'QUB':(829,444),'TAK':(865,461),'SWH':(898,486),'SKW':(930,511),'HFC':(930,548),'CHW':(930,575),
'TIK':(850,345),'YAT':(825,345),'LAT':(825,319),'KWT':(825,289),'NTK':(825,260),'KOB':(792,220),'CHH':(760,220),'WTS':(694,220),'LOF':(655,220),'KOT':(618,220),'SKM':(577,220),'HOM':(659,340),'WHA':(693,363),
'TKO':(894,345),'HAH':(932,292),'POA':(932,250),'LHP':(894,383),
'OCP':(515,495),'WCH':(476,525),'LET':(451,552),'SOH':(421,570),
'EXC':(566,421),'MKK':(558,318),'SHT':(620,116),'FOT':(625,93),'RAC':(620,92),'UNI':(582,59),'TAP':(530,59),'TWO':(489,59),'FAN':(443,59),'SHS':(397,59),'LOW':(356,59),'LMC':(340,84),
'HOK':(439,424),'KOW':(424,383),'OLY':(400,329),'TSY':(317,259),'SUN':(222,382),'TUC':(192,445),'AIR':(145,421),'AWE':(181,391),'DIS':(260,355)
}

# add names from parsed data when available
for c,st in D.get('stations',{}).items():
    if st.get('name') and c not in NAMES: NAMES[c]=st['name']

# Create station -> lines map from full paths.
station_lines={}
for line,paths in PATHS.items():
    for path in paths:
        for c in path: station_lines.setdefault(c,[]).append(line)
for c in station_lines: station_lines[c]=list(dict.fromkeys(station_lines[c]))

# Missing GeoTD station x/y values: infer from nearest same-line known neighbors in sequence.
# This is only used for a station hotspot on GeoTD-derived schematics, never for WTT motion.
def geotd_xy(code):
    st=D['stations'].get(code)
    if st and math.isfinite(st.get('x',float('nan'))): return (st['x'],st['y'])
    # interpolate between nearest parsed station nodes in a full line path
    for line,paths in PATHS.items():
        for path in paths:
            if code not in path: continue
            i=path.index(code); L=None;R=None
            for j in range(i-1,-1,-1):
                s=D['stations'].get(path[j]);
                if s and 'x' in s: L=(j,s);break
            for j in range(i+1,len(path)):
                s=D['stations'].get(path[j]);
                if s and 'x' in s: R=(j,s);break
            if L and R:
                u=(i-L[0])/(R[0]-L[0]);return (L[1]['x']+(R[1]['x']-L[1]['x'])*u,L[1]['y']+(R[1]['y']-L[1]['y'])*u)
            if L:return (L[1]['x'],L[1]['y'])
            if R:return (R[1]['x'],R[1]['y'])
    return None

# Transform one GeoTD route into geodetic coords while preserving its local curve shape between anchored endpoints.
def route_to_geo(code_a,code_b,pts):
    if code_a not in GEO or code_b not in GEO or not pts:return []
    stA=D['stations'].get(code_a); stB=D['stations'].get(code_b)
    if not stA or not stB:return [[GEO[code_a][0],GEO[code_a][1]],[GEO[code_b][0],GEO[code_b][1]]]
    ax,ay=stA['x'],stA['y']; bx,by=stB['x'],stB['y']; dx,dy=bx-ax,by-ay; L2=dx*dx+dy*dy
    ga,gb=GEO[code_a],GEO[code_b]; lat0=(ga[0]+gb[0])/2; c=math.cos(math.radians(lat0)); gx0=ga[1]*c; gy0=ga[0]; gx1=gb[1]*c; gy1=gb[0]; gdx,gdy=gx1-gx0,gy1-gy0; gl=math.hypot(gdx,gdy)
    if L2<1e-12 or gl<1e-12:return [[ga[0],ga[1]],[gb[0],gb[1]]]
    L=math.sqrt(L2); ux,uy=dx/L,dy/L; gux,guy=gdx/gl,gdy/gl; scale=gl/L
    out=[]
    for x,y in pts:
        rx,ry=x-ax,y-ay; along=rx*ux+ry*uy; cross=-rx*uy+ry*ux
        X=gx0+gux*along*scale-guy*cross*scale
        Y=gy0+guy*along*scale+gux*cross*scale
        out.append([round(Y,7),round(X/c,7)])
    out[0]=[ga[0],ga[1]];out[-1]=[gb[0],gb[1]]
    return out

geo_routes={}
for line,routes in D.get('trackRoutes',{}).items():
    if line=='LRL':continue
    out={}
    for key,pts in routes.items():
        a,b=key.split('|')
        q=route_to_geo(a,b,pts)
        if len(q)>=2:out[key]=q
    geo_routes[line]=out

stations={}
for c,lines in station_lines.items():
    e={'name':NAMES.get(c,c),'lines':lines}
    if c in GEO:e.update({'lat':GEO[c][0],'lon':GEO[c][1]})
    if c in OFF:e.update({'official':[OFF[c][0]/1000,OFF[c][1]/586]})
    xy=geotd_xy(c)
    if xy:e['geotd']=[round(xy[0],8),round(xy[1],8)]
    stations[c]=e

payload={'version':12,'officialImage':'https://www.mtr.com.hk/en/customer/images/jp/system_map.png','officialSource':'https://www.mtr.com.hk/en/customer/services/system_map.html','officialSize':[1000,586],'paths':PATHS,'stations':stations,'stationLines':station_lines,'geoRoutes':geo_routes}
(ROOT/'v12_geo_data.js').write_text('window.V12_GEO='+json.dumps(payload,separators=(',',':'))+';\n',encoding='utf-8')

# Generate a vector schematic using the same official-coordinate calibration. This guarantees overlay alignment.
colors={k:v.get('color','#888') for k,v in D['lines'].items()}
W,H=1000,586
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="v12 calibrated railway schematic">', '<rect width="1000" height="586" fill="#071116"/>']
# areas for visual orientation
parts += ['<path d="M210 416 L950 416 L980 586 L300 586 Z" fill="#0c1a22" opacity=".8"/>','<path d="M40 20 L650 20 L650 210 L40 210 Z" fill="#0b171e" opacity=".65"/>']
# draw lines along full paths
for line,paths in PATHS.items():
    col=colors.get(line,'#889')
    for path in paths:
        pts=[OFF[c] for c in path if c in OFF]
        if len(pts)<2:continue
        d='M'+' L'.join(f'{x},{y}' for x,y in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="#020609" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>')
        parts.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
# stations
for c,e in stations.items():
    if c not in OFF:continue
    x,y=OFF[c]; parts.append(f'<circle cx="{x}" cy="{y}" r="4.2" fill="#f5f8fa" stroke="#071116" stroke-width="1.6" data-code="{c}"/>')
    # label only terminals/interchanges / every full public station at small size
    anchor='end' if x>760 else 'start'; tx=x-6 if anchor=='end' else x+6; ty=y-6
    parts.append(f'<text x="{tx}" y="{ty}" text-anchor="{anchor}" fill="#d8e1e8" font-family="system-ui,sans-serif" font-size="7.2" paint-order="stroke" stroke="#071116" stroke-width="2.4">{NAMES.get(c,c)}</text>')
parts.append('</svg>')
(ROOT/'assets'/'mtr-v12-schematic.svg').write_text('\n'.join(parts),encoding='utf-8')
print('wrote v12_geo_data.js', (ROOT/'v12_geo_data.js').stat().st_size)
print('wrote schematic', (ROOT/'assets'/'mtr-v12-schematic.svg').stat().st_size)
