"""v13.3 network overlays for the standalone preview build.

All requests are read-only and cached. No EAL credential ever enters this module.
Sources:
- HKO public georeferenced radar KML
- ArcGIS public MTR station layer (legacy coordinates, supplemented by local anchors)
- OpenStreetMap/Overpass railway geometry
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = "HKTrainDisplay-v13.3/1.0 (+local visualization)"
HKO_KML_CANDIDATES = [
    "https://www.hko.gov.hk/wxinfo/radars/radar_256_kml/Radar_256.kml",
    "https://www.weather.gov.hk/wxinfo/radars/radar_256_kml/Radar_256.kml",
]
ARCGIS_STATIONS = (
    "https://services.arcgis.com/2ycVue24EK6qzjat/ArcGIS/rest/services/"
    "MTR_Stations/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=json"
)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OFFICIAL_SYSTEM_MAP = "https://www.mtr.com.hk/en/customer/images/jp/system_map.png"
OFFICIAL_LIGHT_RAIL_MAP = "https://www.mtr.com.hk/archive/en/services/LR_routemap.pdf"
OFFICIAL_LIGHT_RAIL_SYSTEM_MAP = "https://www.mtr.com.hk/en/customer/jp/images/lr/lr_system_map.png"

# High-confidence anchor set used when public geodata is unavailable or lacks newer stations.
# Coordinates are only fallback anchors; online ArcGIS/OSM data is preferred where available.
SEED = {
    "HOK": (22.2851,114.1582), "CEN": (22.2819,114.1589), "ADM": (22.2794,114.1655),
    "WAC": (22.2775,114.1731), "CAB": (22.2804,114.1849), "NOP": (22.2914,114.2001),
    "QUB": (22.2885,114.2094), "CHW": (22.2649,114.2371), "KET": (22.2815,114.1287),
    "HKU": (22.2830,114.1352), "SYP": (22.2860,114.1420), "TST": (22.2975,114.1722),
    "PRE": (22.3244,114.1681), "MOK": (22.3193,114.1694), "YMT": (22.3133,114.1706),
    "KOT": (22.3373,114.1760), "DIH": (22.3402,114.2011), "KWT": (22.3121,114.2260),
    "TIK": (22.3040,114.2529), "TKO": (22.3075,114.2607), "POA": (22.3225,114.2570),
    "LHP": (22.2950,114.2690), "HUH": (22.3030,114.1810), "EXC": (22.2817,114.1751),
    "TAW": (22.3720,114.1785), "SHT": (22.3820,114.1870), "FOT": (22.3950,114.1980),
    "UNI": (22.4130,114.2100), "TAP": (22.4446,114.1707), "SHS": (22.5010,114.1277),
    "LOW": (22.5280,114.1133), "LMC": (22.5146,114.0656), "TUM": (22.3953,113.9732),
    "YUL": (22.4460,114.0340), "KSR": (22.4345,114.0636), "TWW": (22.3688,114.1096),
    "WKS": (22.4294,114.2435), "MOS": (22.4249,114.2319), "TSY": (22.3585,114.1078),
    "SUN": (22.3318,114.0289), "TUC": (22.2895,113.9413), "AIR": (22.3156,113.9369),
    "AWE": (22.3219,113.9407), "DIS": (22.3155,114.0452), "TSW": (22.3730,114.1170),
    "MEF": (22.3377,114.1375), "LAK": (22.3485,114.1264), "NAC": (22.3268,114.1532),
    "OLY": (22.3176,114.1600), "KOW": (22.3045,114.1615), "OCP": (22.2481,114.1742),
    "WCH": (22.2480,114.1680), "LET": (22.2427,114.1562), "SOH": (22.2420,114.1495),
    "HIK": (22.3636,114.1700), "KAT": (22.3290,114.1995), "SUW": (22.3250,114.1900),
    "TKW": (22.3174,114.1884), "HOM": (22.3094,114.1826), "AUS": (22.3044,114.1665),
    "ETS": (22.2952,114.1744),
}


def _norm_name(s: str) -> str:
    s=(s or "").lower().replace("mtr","").replace("station","")
    return "".join(c for c in s if c.isalnum())


def _read_train_data():
    p=ROOT/"data.js"
    txt=p.read_text(encoding="utf-8")
    pre="window.TRAIN_DATA="
    if not txt.startswith(pre): return {}
    return json.loads(txt[len(pre):].rstrip().rstrip(";"))


class V12Backend:
    def __init__(self):
        self.lock=threading.Lock()
        self.cache={}
        self.train_data=_read_train_data()

    def _cache_get(self,key,max_age):
        with self.lock:
            e=self.cache.get(key)
            if e and time.time()-e[0] <= max_age:return e[1]
        return None

    def _cache_set(self,key,val):
        with self.lock:self.cache[key]=(time.time(),val)
        return val

    @staticmethod
    def _request(url,timeout=10,data=None,headers=None):
        h={"User-Agent":UA,"Accept":"*/*"}
        if headers:h.update(headers)
        req=urllib.request.Request(url,data=data,headers=h)
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return r.read(), r.headers.get("Content-Type","application/octet-stream")


    def public_asset(self, which):
        if which == "official-system":
            url=OFFICIAL_SYSTEM_MAP; key="asset-official-system"; age=3600
        elif which == "light-rail-map":
            url=OFFICIAL_LIGHT_RAIL_MAP; key="asset-light-rail-map"; age=3600
        elif which == "light-rail-system":
            url=OFFICIAL_LIGHT_RAIL_SYSTEM_MAP; key="asset-light-rail-system"; age=3600
        else:
            raise ValueError("unknown public asset")
        cached=self._cache_get(key,age)
        if cached:return cached
        body,ctype=self._request(url,timeout=12)
        return self._cache_set(key,(body,ctype))

    def geo_stations(self):
        cached=self._cache_get("geo-stations",3600)
        if cached:return cached
        stations={k:{"lat":v[0],"lon":v[1],"source":"fallback-anchor"} for k,v in SEED.items()}
        errors=[]
        try:
            raw,_=self._request(ARCGIS_STATIONS,timeout=8)
            j=json.loads(raw)
            feats=j.get("features",[])
            # Build lookup from our names and codes.
            td=self.train_data.get("stations",{})
            byname={_norm_name(v.get("name")):k for k,v in td.items() if v.get("name")}
            for f in feats:
                a=f.get("attributes") or f.get("properties") or {}
                g=f.get("geometry") or {}
                name=""
                for key,val in a.items():
                    if "name" in key.lower() and isinstance(val,str) and val.strip():
                        name=val.strip(); break
                code=None
                for key,val in a.items():
                    if "code" in key.lower() and isinstance(val,str) and 2<=len(val.strip())<=5:
                        code=val.strip().upper(); break
                if not code and name: code=byname.get(_norm_name(name))
                x=g.get("x"); y=g.get("y")
                if x is None and isinstance(g.get("coordinates"),list):
                    x,y=g["coordinates"][:2]
                if code and x is not None and y is not None and -180<=float(x)<=180 and -90<=float(y)<=90:
                    stations[code]={"lat":float(y),"lon":float(x),"source":"ArcGIS MTR station layer"}
        except Exception as e:
            errors.append(type(e).__name__)
        return self._cache_set("geo-stations",{
            "ok":bool(stations),"stations":stations,"source":"public geodata + fallback anchors",
            "errors":errors,"fetched_at":time.time()
        })

    def railways(self):
        cached=self._cache_get("railways",3600)
        if cached:return cached
        q='[out:json][timeout:18];way["railway"~"^(rail|subway|light_rail)$"](22.14,113.80,22.60,114.50);out geom;'
        errors=[]; lines=[]
        try:
            data=urllib.parse.urlencode({"data":q}).encode()
            raw,_=self._request(OVERPASS_URL,timeout=22,data=data,headers={"Content-Type":"application/x-www-form-urlencoded"})
            j=json.loads(raw)
            for e in j.get("elements",[]):
                geom=e.get("geometry") or []
                if len(geom)<2: continue
                # Downsample only extremely long ways; keep shape otherwise.
                step=max(1,len(geom)//220)
                sampled=geom[::step]
                pts=[[p["lat"],p["lon"]] for p in sampled]
                if sampled and (sampled[-1].get("lat"),sampled[-1].get("lon")) != (geom[-1].get("lat"),geom[-1].get("lon")):
                    pts.append([geom[-1]["lat"],geom[-1]["lon"]])
                tags=e.get("tags") or {}
                lines.append({"points":pts,"railway":tags.get("railway"),"name":tags.get("name"),"operator":tags.get("operator")})
        except Exception as e:
            errors.append(type(e).__name__)
        return self._cache_set("railways",{
            "ok":bool(lines),"ways":lines,"source":"OpenStreetMap via Overpass","errors":errors,"fetched_at":time.time()
        })


    def mtr_route(self, line):
        line=(line or "").strip().lower()
        if not re.fullmatch(r"[a-z]{3}",line):
            raise ValueError("invalid MTR line code")
        key=f"mtr-route-{line}"
        cached=self._cache_get(key,86400)
        if cached:return cached
        code=line.upper()
        urls=[
            f"https://hkbus.github.io/route-waypoints/{line}.json",
            f"https://waypoints.hkbuseta.com/waypoints/{code}.json",
            f"https://raw.githubusercontent.com/hkbus/route-waypoints/main/mtr/{line}.json",
        ]
        errors=[]
        for url in urls:
            try:
                raw,_=self._request(url,timeout=6)
                j=json.loads(raw)
                feats=j.get("features") or []
                if not feats:raise ValueError("empty route data")
                out={"ok":True,"line":line.upper(),"geojson":j,"source":"HK Bus WayPoints Crawling / public MTR route geometry","source_url":url,"fetched_at":time.time()}
                return self._cache_set(key,out)
            except Exception as e:
                errors.append(type(e).__name__)
        return {"ok":False,"line":line.upper(),"geojson":None,"errors":errors,"fetched_at":time.time()}

    @staticmethod
    def _normalise_hko_url(url):
        u=urllib.parse.urlparse(url)
        host=(u.hostname or "").lower()
        allowed=(host=="hko.gov.hk" or host.endswith(".hko.gov.hk") or host=="weather.gov.hk" or host.endswith(".weather.gov.hk"))
        if not allowed:return url
        if u.scheme=="http":
            return urllib.parse.urlunparse(("https",u.netloc,u.path,u.params,u.query,u.fragment))
        return url

    @classmethod
    def _safe_hko_url(cls,url):
        url=cls._normalise_hko_url(url)
        u=urllib.parse.urlparse(url)
        host=(u.hostname or "").lower()
        return u.scheme=="https" and (host=="hko.gov.hk" or host.endswith(".hko.gov.hk") or host=="weather.gov.hk" or host.endswith(".weather.gov.hk"))

    def _radar_frames_from_kml(self,url,depth=0,seen=None):
        if seen is None:seen=set()
        if depth>2 or url in seen or not self._safe_hko_url(url):return []
        seen.add(url)
        raw,_=self._request(url,timeout=8)
        root=ET.fromstring(raw)
        # namespace-agnostic helpers
        def local(el):return el.tag.rsplit('}',1)[-1]
        def child_text(el,name):
            for x in el.iter():
                if local(x)==name and x.text:return x.text.strip()
            return None
        frames=[]
        for el in root.iter():
            if local(el)!="GroundOverlay":continue
            href=None; box={}
            for x in el.iter():
                n=local(x)
                if n=="href" and x.text and href is None:href=x.text.strip()
                elif n in {"north","south","east","west"} and x.text:
                    try:box[n]=float(x.text.strip())
                    except Exception:pass
            if href and len(box)==4:
                href=self._normalise_hko_url(urllib.parse.urljoin(url,href))
                if self._safe_hko_url(href):
                    when=child_text(el,"when") or child_text(el,"begin") or child_text(el,"name")
                    frames.append({"url":href,"bounds":[[box["south"],box["west"]],[box["north"],box["east"]]],"time":when})
        # Master KML often points at frame KMLs.
        if not frames:
            links=[]
            for el in root.iter():
                if local(el)=="NetworkLink":
                    h=child_text(el,"href")
                    if h:links.append(self._normalise_hko_url(urllib.parse.urljoin(url,h)))
            for link in links[-18:]:
                try:frames.extend(self._radar_frames_from_kml(link,depth+1,seen))
                except Exception:continue
        return frames

    def radar(self):
        cached=self._cache_get("radar",120)
        if cached:return cached
        errors=[]; frames=[]
        for u in HKO_KML_CANDIDATES:
            try:
                frames=self._radar_frames_from_kml(u)
                if frames:break
            except Exception as e:errors.append(f"{type(e).__name__}")
        # dedupe while preserving sequence
        uniq=[]; seen=set()
        for f in frames:
            k=(f["url"],tuple(map(tuple,f["bounds"])))
            if k not in seen:seen.add(k);uniq.append(f)
        frames=uniq[-16:]
        return self._cache_set("radar",{
            "ok":bool(frames),"frames":frames,"source":"Hong Kong Observatory 256 km radar KML",
            "update_frequency_sec":360,"errors":errors,"fetched_at":time.time()
        })

    def radar_image(self,url):
        if not self._safe_hko_url(url):raise ValueError("invalid HKO image host")
        raw,ctype=self._request(url,timeout=10)
        if not ctype.startswith("image/"):
            # Some HKO responses omit a useful type; infer conservatively.
            path=urllib.parse.urlparse(url).path.lower()
            ctype="image/png" if path.endswith('.png') else "image/gif" if path.endswith('.gif') else "image/jpeg"
        return raw,ctype
