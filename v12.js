(()=>{
'use strict';
const D=window.TRAIN_DATA, G=window.V12_GEO, TD=window.V12_GEOTD_DETAIL||null, models=window.V11_TRAIN_MODELS||{};
if(!D||!G)return;
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let runtime=window.V11_RUNTIME||{states:[],simSec:0,stationLines:{}};
let mode='geotd';
let leafletPromise=null,geoMap=null,trackLayer=null,stationLayer=null,radarLayer=null;
let geoMarkers=new Map(), screenMarkers={schematic:new Map(),official:new Map()};
const directGeo={lines:new Map(),graphs:new Map(),segments:new Map(),loading:false,loaded:0,failed:0,osmWays:[],tceCurrent:null,tceSource:null};
let officialRaster=null,officialBuckets={},officialReady=false,schematicBuilt=false;
const polyMetricCache=new WeakMap(),geoPathCache=new Map(),screenPathCache=new Map();let quickLastSec=-1;
let quickCode=null,quickObs=[],quickError='',quickFetchAt=0,quickTimer=null;
let radarMeta=null,radarOn=false,radarPlaying=false,radarIndex=0,radarTimer=null;
const screenState={schematic:{scale:1,x:0,y:0,fit:true},official:{scale:1,x:0,y:0,fit:true}};
const MODEL_NATIVE_DEG=10;
// MTR-published train lengths (Business Overview; metres). Width is a representative
// heavy-rail envelope used only for map-scale rendering; the longitudinal size is exact by line.
const TRAIN_REAL_M={KTL:[182,3.1],TWL:[182,3.1],ISL:[182,3.1],TCL:[184,3.096],TKL:[182,3.1],SIL:[70,3.0],DRL:[91,3.0],EAL:[219,3.1],TML:[195,3.1],AEL:[184,3.096]};
const MIN_REAL_TRAIN_ZOOM=15;
const TCE_SITE=[22.29724,113.95864];
// 13 Sep 2026 00:00 HKT = 12 Sep 2026 16:00 UTC. MTR announced Hong Kong-bound
// TCL trains use the diverted track section from this date.
const TCE_HK_TRACK_ACTIVE_UTC=Date.UTC(2026,8,12,16,0,0);

// Merge the full public station catalogue into the parsed data so existing boards can name every station.
for(const [code,s] of Object.entries(G.stations||{})){
  if(!D.stations[code])D.stations[code]={x:s.geotd?.[0]??0,y:s.geotd?.[1]??0,name:s.name};
  else if(!D.stations[code].name)D.stations[code].name=s.name;
}
window.V12_STATION_LINES=G.stationLines;
window.V12_STATION_NAMES=Object.fromEntries(Object.entries(G.stations).map(([k,v])=>[k,v.name]));

function modelFor(line){return models[line]||models.TWL}
function stateId(s){return s.live?`LIVE-EAL-${s.train?.train_set_id}`:`${s.line}-${s.trip?.[0]}-${s.trip?.[2]?.[0]?.[1]}`}
function statePair(s){return s.pos?.pair||[s.a?.[0],s.b?.[0]]}
function stateFrac(s){let u=s.pos?.pairFraction;if(!Number.isFinite(u))u=s.u;return Math.max(0,Math.min(1,Number.isFinite(u)?u:.5))}
function openState(s){document.getElementById('m-'+stateId(s))?.click()}
function fmt(sec){if(sec==null||!isFinite(sec))return '—';sec=((Math.round(sec)%86400)+86400)%86400;let h=Math.floor(sec/3600),m=Math.floor(sec%3600/60),s=Math.floor(sec%60);return [h,m,s].map(v=>String(v).padStart(2,'0')).join(':')}
function fmtCountdown(x){x=Math.round(x);if(x<=0)return 'DUE';let m=Math.floor(x/60),s=x%60;return m?`${m}m ${String(s).padStart(2,'0')}s`:`${s}s`}

function polyPoint(points,u){
  if(!points?.length)return null;if(points.length===1)return {p:points[0],angle:0};
  let met=polyMetricCache.get(points);if(!met){const lens=[];let total=0;for(let i=0;i<points.length-1;i++){let dx=points[i+1][1]-points[i][1],dy=points[i+1][0]-points[i][0],l=Math.hypot(dx,dy);lens.push(l);total+=l}met={lens,total};polyMetricCache.set(points,met)}
  const {lens,total}=met;let t=Math.max(0,Math.min(1,u))*total,acc=0;
  for(let i=0;i<lens.length;i++)if(t<=acc+lens[i]||i===lens.length-1){let q=lens[i]?((t-acc)/lens[i]):0,a=points[i],b=points[i+1];return {p:[a[0]+(b[0]-a[0])*q,a[1]+(b[1]-a[1])*q],angle:Math.atan2(b[0]-a[0],b[1]-a[1])*180/Math.PI}}
  return null;
}
function geoWarpPoint(x,y){
  if(!TD?.affine||!TD?.anchors?.length)return null;
  const c=TD.affine;let lon=c[0][0]+x*c[1][0]+y*c[2][0],lat=c[0][1]+x*c[1][1]+y*c[2][1];
  let near=TD.anchors.map(a=>{let dx=x-a[1],dy=y-a[2];return [dx*dx+dy*dy,a]}).sort((a,b)=>a[0]-b[0]).slice(0,14);
  if(!near.length)return [lat,lon];if(near[0][0]<1e-14)return [near[0][1][3],near[0][1][4]];
  let sw=0,dlon=0,dlat=0,eps=.0025*.0025;for(const [d,a] of near){let w=1/(d+eps);sw+=w;dlon+=w*a[5];dlat+=w*a[6]}
  return [lat+dlat/sw,lon+dlon/sw];
}
function geoDist2(a,b){const lat=(a[0]+b[0])*.5*Math.PI/180,dx=(a[1]-b[1])*Math.cos(lat),dy=a[0]-b[0];return dx*dx+dy*dy}
function geoKey(p){return `${p[0].toFixed(5)},${p[1].toFixed(5)}`}
function routePartsFromGeoJSON(j){const out=[];for(const f of j?.features||[]){const g=f?.geometry;if(!g)continue;let cs=g.coordinates||[];if(g.type==='LineString')cs=[cs];else if(g.type!=='MultiLineString')continue;for(const part of cs){let pts=part.map(q=>[+q[1],+q[0]]).filter(q=>Number.isFinite(q[0])&&Number.isFinite(q[1]));if(pts.length>1)out.push(pts)}}return out}
function buildDirectGraph(line,parts){const nodes=new Map(),edges=new Map();function addNode(p){let k=geoKey(p);if(!nodes.has(k))nodes.set(k,p);if(!edges.has(k))edges.set(k,[]);return k}for(const part of parts)for(let i=0;i<part.length-1;i++){let a=addNode(part[i]),b=addNode(part[i+1]),w=Math.sqrt(geoDist2(part[i],part[i+1]));edges.get(a).push([b,w]);edges.get(b).push([a,w])}directGeo.graphs.set(line,{nodes,edges});directGeo.segments.clear()}
function nearestGeoNode(graph,p){let best=null,bd=Infinity;for(const [k,q] of graph.nodes){let d=geoDist2(p,q);if(d<bd){bd=d;best=k}}return best}
function heapPush(h,item){let i=h.length;h.push(item);while(i){let p=(i-1)>>1;if(h[p][0]<=item[0])break;h[i]=h[p];i=p;h[i]=item}}
function heapPop(h){if(!h.length)return null;const root=h[0],last=h.pop();if(h.length){let i=0;while(true){let l=i*2+1,r=l+1;if(l>=h.length)break;let c=r<h.length&&h[r][0]<h[l][0]?r:l;if(h[c][0]>=last[0])break;h[i]=h[c];i=c}h[i]=last}return root}
function shortestGraphPoints(graph,A,B){
  if(!graph||!A||!B)return null;const ak=nearestGeoNode(graph,A),bk=nearestGeoNode(graph,B);if(!ak||!bk)return null;
  const dist=new Map([[ak,0]]),prev=new Map(),todo=[];heapPush(todo,[0,ak]);
  while(todo.length){const [d,k]=heapPop(todo);if(d!==dist.get(k))continue;if(k===bk)break;for(const [n,w] of graph.edges.get(k)||[]){let nd=d+w;if(nd<(dist.get(n)??Infinity)){dist.set(n,nd);prev.set(n,k);heapPush(todo,[nd,n])}}}
  if(!dist.has(bk))return null;let ks=[bk];while(ks[ks.length-1]!==ak){let q=prev.get(ks[ks.length-1]);if(!q)return null;ks.push(q)}ks.reverse();return ks.map(k=>graph.nodes.get(k));
}
function directSegment(line,a,b){const key=`${line}|${a}|${b}`;if(directGeo.segments.has(key))return directGeo.segments.get(key);const graph=directGeo.graphs.get(line),A=G.stations[a],B=G.stations[b];if(!graph||!A||!B)return null;let pts=shortestGraphPoints(graph,[A.lat,A.lon],[B.lat,B.lon]);if(!pts?.length)return null;const da=Math.sqrt(geoDist2([A.lat,A.lon],pts[0])),db=Math.sqrt(geoDist2([B.lat,B.lon],pts[pts.length-1]));if(da>.01||db>.01)return null;pts=[[A.lat,A.lon],...pts,[B.lat,B.lon]];directGeo.segments.set(key,pts);directGeo.segments.set(`${line}|${b}|${a}`,[...pts].reverse());return pts}
function bakedSegment(line,a,b){const tab=G.geoRoutes?.[line]||{};let p=tab[`${a}|${b}`];if(p?.length)return p;p=tab[`${b}|${a}`];return p?.length?[...p].reverse():null}
function geoMeters(a,b){const R=6371008.8,p1=a[0]*Math.PI/180,p2=b[0]*Math.PI/180,dp=(b[0]-a[0])*Math.PI/180,dl=(b[1]-a[1])*Math.PI/180,h=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;return 2*R*Math.asin(Math.min(1,Math.sqrt(h)))}
function geoMetricM(points){let lens=[],total=0;for(let i=0;i<(points?.length||0)-1;i++){let d=geoMeters(points[i],points[i+1]);lens.push(d);total+=d}return {lens,total}}
function geoAtMeters(points,met,d){if(!points?.length)return null;if(points.length===1)return points[0];d=Math.max(0,Math.min(met.total,d));let acc=0;for(let i=0;i<met.lens.length;i++){let l=met.lens[i];if(d<=acc+l||i===met.lens.length-1){let u=l?(d-acc)/l:0,a=points[i],b=points[i+1];return [a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u]}acc+=l}return points.at(-1)}
function geoSliceMeters(points,startM,endM){if(!points?.length)return [];const met=geoMetricM(points);if(!(met.total>0))return points.slice(0,1);startM=Math.max(0,startM);endM=Math.min(met.total,endM);if(endM<startM)[startM,endM]=[endM,startM];let out=[geoAtMeters(points,met,startM)],acc=0;for(let i=0;i<met.lens.length;i++){acc+=met.lens[i];if(acc>startM+1e-6&&acc<endM-1e-6)out.push(points[i+1])}out.push(geoAtMeters(points,met,endM));return out}
function linePointDist2(p,a,b){let lat=p[0]*Math.PI/180,c=Math.cos(lat),px=p[1]*c,py=p[0],ax=a[1]*c,ay=a[0],bx=b[1]*c,by=b[0],vx=bx-ax,vy=by-ay,den=vx*vx+vy*vy,u=den?((px-ax)*vx+(py-ay)*vy)/den:0;u=Math.max(0,Math.min(1,u));let dx=px-(ax+vx*u),dy=py-(ay+vy*u);return dx*dx+dy*dy}
function nearCorridor(p,path,limit=.0032){let best=Infinity;for(let i=0;i<(path?.length||0)-1;i++){let d=linePointDist2(p,path[i],path[i+1]);if(d<best)best=d;if(best<limit*limit)return true}return false}
function buildTceCurrentFromOsm(ways){const corridor=bakedSegment('TCL','TUC','SUN')||directSegment('TCL','TUC','SUN');if(!corridor?.length)return null;const parts=[];for(const w of ways||[]){let pts=(w.points||[]).filter(q=>Number.isFinite(q?.[0])&&Number.isFinite(q?.[1]));let run=[];for(let i=0;i<pts.length-1;i++){let a=pts[i],b=pts[i+1],mid=[(a[0]+b[0])/2,(a[1]+b[1])/2];if(nearCorridor(mid,corridor)){if(!run.length)run.push(a);run.push(b)}else if(run.length>1){parts.push(run);run=[]}else run=[]}if(run.length>1)parts.push(run)}if(!parts.length)return null;const nodes=new Map(),edges=new Map();function addNode(p){let k=geoKey(p);if(!nodes.has(k))nodes.set(k,p);if(!edges.has(k))edges.set(k,[]);return k}for(const part of parts)for(let i=0;i<part.length-1;i++){let a=addNode(part[i]),b=addNode(part[i+1]),w=Math.sqrt(geoDist2(part[i],part[i+1]));edges.get(a).push([b,w]);edges.get(b).push([a,w])}let A=G.stations.TUC,B=G.stations.SUN,pts=shortestGraphPoints({nodes,edges},[A.lat,A.lon],[B.lat,B.lon]);if(!pts?.length)return null;let d0=Math.sqrt(geoDist2([A.lat,A.lon],pts[0])),d1=Math.sqrt(geoDist2([B.lat,B.lon],pts.at(-1)));if(d0>.012||d1>.012)return null;return [[A.lat,A.lon],...pts,[B.lat,B.lon]]}
function tceActive(){return Date.now()>=TCE_HK_TRACK_ACTIVE_UTC}
function orientGeoPath(path,a,b){
  if(!path?.length)return path;const A=G.stations[a],B=G.stations[b];if(!A||!B)return path;
  const ap=[A.lat,A.lon],bp=[B.lat,B.lon],forward=geoDist2(path[0],ap)+geoDist2(path.at(-1),bp),reverse=geoDist2(path[0],bp)+geoDist2(path.at(-1),ap);
  return reverse+1e-12<forward?[...path].reverse():path
}
function geoPathForState(s){const [a,b]=statePair(s);let path;if(s.line==='TCL'&&a==='TUC'&&b==='SUN'&&tceActive()&&directGeo.tceCurrent?.length)path=directGeo.tceCurrent;else path=directSegment(s.line,a,b)||bakedSegment(s.line,a,b)||(()=>{const A=G.stations[a],B=G.stations[b];return A&&B?[[A.lat,A.lon],[B.lat,B.lon]]:null})();return orientGeoPath(path,a,b)}
function directGeoPointForState(s){const pts=geoPathForState(s);if(!pts?.length)return null;return polyPoint(pts,stateFrac(s))}
function geoPointForState(s){const q=directGeoPointForState(s);return q?{p:q.p,angle:q.angle,direct:true}:null}
function trainBodyForState(s){const path=geoPathForState(s);if(!path?.length)return null;const met=geoMetricM(path);if(!(met.total>0))return null;const dims=TRAIN_REAL_M[s.line]||[182,3.1],center=stateFrac(s)*met.total,half=dims[0]/2,start=Math.max(0,center-half),end=Math.min(met.total,center+half),body=geoSliceMeters(path,start,end);return {path,body,front:geoAtMeters(path,met,end),center:geoAtMeters(path,met,center),lengthM:dims[0],widthM:dims[1],clipped:(end-start)<dims[0]*.98}}
function metersPerPixel(lat,zoom){return 156543.03392804097*Math.cos(lat*Math.PI/180)/Math.pow(2,zoom)}
async function loadDirectGeoRoutes(){if(directGeo.loading)return;directGeo.loading=true;const lines=Object.keys(D.lines||{}).filter(x=>x!=='LRL');await Promise.all(lines.map(async line=>{try{let r=await fetch('/api/geo/mtr-route?line='+encodeURIComponent(line),{cache:'force-cache'}),j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||'route unavailable');let parts=routePartsFromGeoJSON(j.geojson);if(!parts.length)throw new Error('empty route');directGeo.lines.set(line,{parts,source:j.source,sourceUrl:j.source_url});buildDirectGraph(line,parts);directGeo.loaded++}catch(e){directGeo.failed++}}));directGeo.loading=false;if(geoMap){drawGeoTDTracks();updateGeoTrains(runtime.states||[])}let m=$('#mapResolution');if(m&&mode==='geo')m.textContent=`Real map · direct geographic tracks ${directGeo.loaded}/${lines.length} · physical-size trains at z${MIN_REAL_TRAIN_ZOOM}+`}
async function loadCurrentRailways(){try{let r=await fetch('/api/geo/railways',{cache:'force-cache'}),j=await r.json();if(!r.ok||!j.ok)throw new Error('OSM railway topology unavailable');directGeo.osmWays=(j.ways||[]).filter(w=>w.railway!=='light_rail'&&(w.points||[]).length>1);let tce=buildTceCurrentFromOsm(directGeo.osmWays);if(tce){directGeo.tceCurrent=tce;directGeo.tceSource=j.source||'OpenStreetMap';geoPathCache.clear()}if(geoMap){drawGeoTDTracks();drawGeoStations();updateGeoTrains(runtime.states||[])}}catch(e){/* Public line geometry remains the deterministic fallback. */}}

// ---------- instant startup / lazy real map ----------
function loadLeaflet(){
  if(window.L)return Promise.resolve(window.L);if(leafletPromise)return leafletPromise;
  leafletPromise=new Promise((resolve,reject)=>{
    if(!document.querySelector('link[data-v12-leaflet]')){let l=document.createElement('link');l.rel='stylesheet';l.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';l.dataset.v12Leaflet='1';document.head.appendChild(l)}
    let s=document.createElement('script');s.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';s.async=true;s.onload=()=>resolve(window.L);s.onerror=()=>reject(new Error('Leaflet CDN unavailable'));document.head.appendChild(s)
  });return leafletPromise;
}
async function initGeo(){
  if(geoMap){setTimeout(()=>geoMap.invalidateSize(),30);return}
  const box=$('#geoMap');box.innerHTML='<div class="v12-loading"><b>Opening real map…</b><span>Train data is already running; only the base-map library/tiles are loading.</span></div>';
  try{await loadLeaflet()}catch(e){box.innerHTML='<div class="v12-loading error"><b>Real map library unavailable.</b><span>GeoTD, schematic and train data remain available. Retry when online.</span><button id="retryGeo">Retry</button></div>';$('#retryGeo')?.addEventListener('click',()=>{leafletPromise=null;initGeo()});return}
  box.innerHTML='';
  geoMap=L.map('geoMap',{zoomControl:true,preferCanvas:true,minZoom:9,maxZoom:20,zoomSnap:.25}).setView([22.34,114.16],11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'© OpenStreetMap contributors',updateWhenIdle:true,keepBuffer:3}).addTo(geoMap);
  geoMap.createPane('trainPane');geoMap.getPane('trainPane').style.zIndex=640;
  geoMap.createPane('trainHitPane');geoMap.getPane('trainHitPane').style.zIndex=645;
  trackLayer=L.layerGroup().addTo(geoMap);stationLayer=L.layerGroup().addTo(geoMap);
  geoMap.on('zoomend',()=>updateGeoTrains(runtime.states||[]));
  drawGeoTDTracks();drawGeoStations();updateGeoTrains(runtime.states||[]);loadDirectGeoRoutes();loadCurrentRailways();
  setTimeout(()=>geoMap.invalidateSize(),40);
}
function tceSection(path){if(!path?.length)return null;let idx=[];for(let i=0;i<path.length;i++)if(path[i][1]>=113.94&&path[i][1]<=113.978)idx.push(i);if(!idx.length)return null;let a=Math.max(0,idx[0]-1),b=Math.min(path.length-1,idx.at(-1)+1);return path.slice(a,b+1)}
function drawGeoTDTracks(){
  trackLayer.clearLayers();let any=false;
  // Fine neutral underlay = currently mapped physical heavy-rail rails. This is deliberately
  // separate from line-route geometry so newly mapped civil works (e.g. TCE) are visible.
  for(const w of directGeo.osmWays||[]){let pts=w.points||[];if(pts.length>1)L.polyline(pts,{color:'#7b8790',weight:.8,opacity:.28,interactive:false,smoothFactor:0}).addTo(trackLayer)}
  // Direct line-route geometry is the coloured operational alignment. No GeoTD warp is permitted here.
  for(const [line,obj] of directGeo.lines){const col=D.lines[line]?.color||'#82909e';for(const part of obj.parts){if(!part?.length)continue;any=true;L.polyline(part,{color:'#061017',weight:5.2,opacity:.66,lineCap:'round',lineJoin:'round',interactive:false,smoothFactor:0}).addTo(trackLayer);L.polyline(part,{color:col,weight:2.8,opacity:.98,lineCap:'round',lineJoin:'round',interactive:false,smoothFactor:0,className:'v13-direct-track'}).addTo(trackLayer)}}
  // From 13 Sep 2026 Hong Kong-bound TCL uses the first diverted TCE track section.
  if(tceActive()&&directGeo.tceCurrent){let sec=tceSection(directGeo.tceCurrent);if(sec?.length>1){const col=D.lines.TCL?.color||'#f7943e';L.polyline(sec,{color:'#061017',weight:5.6,opacity:.78,interactive:false,smoothFactor:0}).addTo(trackLayer);L.polyline(sec,{color:col,weight:3.1,opacity:1,interactive:false,smoothFactor:0}).addTo(trackLayer)}}
  if(any)return;
  // Honest offline fallback: use baked WGS84 rail polylines first, then station chords only if absent.
  let drew=false;for(const [line,tab] of Object.entries(G.geoRoutes||{})){const col=D.lines[line]?.color||'#82909e';for(const pts of Object.values(tab||{})){if(pts?.length>1){drew=true;L.polyline(pts,{color:col,weight:2.4,opacity:.78,interactive:false,smoothFactor:0}).addTo(trackLayer)}}}if(drew)return;
  for(const [line,paths] of Object.entries(G.paths||{})){const col=D.lines[line]?.color||'#82909e';for(const codes of paths){let pts=codes.map(c=>G.stations[c]).filter(s=>Number.isFinite(s?.lat)&&Number.isFinite(s?.lon)).map(s=>[s.lat,s.lon]);if(pts.length>1)L.polyline(pts,{color:col,weight:2.5,opacity:.72,dashArray:'5 5',interactive:false}).addTo(trackLayer)}}
}
function drawGeoStations(){
  stationLayer.clearLayers();
  for(const [code,s] of Object.entries(G.stations||{})){if(!Number.isFinite(s.lat)||!Number.isFinite(s.lon))continue;const colors=(s.lines||[]).map(l=>D.lines[l]?.color).filter(Boolean);const col=colors[0]||'#fff';const m=L.circleMarker([s.lat,s.lon],{radius:4.3,weight:2,color:'#071017',fillColor:'#fff',fillOpacity:.98,pane:'markerPane'}).addTo(stationLayer);m.bindTooltip(s.name,{direction:'top',className:'v12-station-label',opacity:.97});m.on('click',()=>openStationQuick(code));if(colors.length>1)L.circleMarker([s.lat,s.lon],{radius:6.1,weight:1.5,color:col,fill:false,interactive:false}).addTo(stationLayer)}
  // Construction reference only: TCE is not treated as an open passenger station or ETA stop.
  if(tceActive()){let m=L.circleMarker(TCE_SITE,{radius:3.7,weight:1.5,color:D.lines.TCL?.color||'#f7943e',fillColor:'#fff',fillOpacity:.88,dashArray:'2 2'}).addTo(stationLayer);m.bindTooltip('Tung Chung East · under construction · HK-bound diverted track active from 13 Sep 2026',{direction:'top',className:'v12-station-label',opacity:.97})}
}
function updateGeoTrains(states){
  if(!geoMap)return;const keep=new Set,zoom=geoMap.getZoom();
  for(const s of states||[]){const body=trainBodyForState(s);if(!body)continue;const id=stateId(s);keep.add(id);let obj=geoMarkers.get(id),col=D.lines[s.line]?.color||'#f4f7f8',mpp=metersPerPixel(body.center[0],zoom),widthPx=body.widthM/mpp,physical=zoom>=MIN_REAL_TRAIN_ZOOM&&widthPx>=.55,overview=!physical;
    if(!obj){
      const outer=L.polyline(body.body,{pane:'trainPane',color:'#071017',weight:Math.max(.1,widthPx),opacity:physical?.98:0,lineCap:'butt',lineJoin:'round',smoothFactor:0,interactive:true});
      const inner=L.polyline(body.body,{pane:'trainPane',color:col,weight:Math.max(.1,widthPx*.56),opacity:physical?1:0,lineCap:'butt',lineJoin:'round',smoothFactor:0,interactive:true});
      const nose=L.circle(body.front,{pane:'trainPane',radius:body.widthM*.52,color:'#071017',weight:0,fillColor:col,fillOpacity:physical?1:0,interactive:true});
      const hit=L.polyline(body.body,{pane:'trainHitPane',color:'#000',weight:16,opacity:physical?.001:0,interactive:physical,smoothFactor:0});
      // Overview marker stays exactly on the same route centreline.  It is deliberately
      // screen-sized so trains remain discoverable before the physical-length body is visible.
      const dot=L.circleMarker(body.center,{pane:'trainPane',radius:4.6,color:'#061017',weight:1.8,fillColor:col,fillOpacity:overview?.98:0,opacity:overview?1:0,interactive:overview});
      const group=L.layerGroup([outer,inner,nose,hit,dot]).addTo(geoMap);obj={group,outer,inner,nose,hit,dot,state:s,tipSec:null};
      const click=()=>openState(obj.state);for(const l of [outer,inner,nose,hit,dot])l.on('click',click);geoMarkers.set(id,obj)
    }
    obj.state=s;obj.outer.setLatLngs(body.body);obj.inner.setLatLngs(body.body);obj.hit.setLatLngs(body.body);obj.nose.setLatLng(body.front);obj.dot.setLatLng(body.center);
    obj.outer.setStyle({weight:Math.max(.1,widthPx),opacity:physical?.98:0});obj.inner.setStyle({color:col,weight:Math.max(.1,widthPx*.56),opacity:physical?1:0});obj.nose.setStyle({fillColor:col,fillOpacity:physical?1:0});obj.hit.setStyle({opacity:physical?.001:0,weight:16});obj.dot.setStyle({fillColor:col,fillOpacity:overview?.98:0,opacity:overview?1:0});
    for(const l of [obj.outer,obj.inner,obj.nose,obj.hit])l.options.interactive=physical;obj.dot.options.interactive=overview;
    const tipSec=Math.floor(runtime.simSec||0);if(obj.tipSec!==tipSec){obj.tipSec=tipSec;const tip=`${esc(s.line)} ${s.live?esc(s.train?.td||s.train?.train_set_id):esc(s.trip?.[0])} · ${Math.round(s.speedKph||0)} km/h · ${body.lengthM} m train`;for(const l of [obj.hit,obj.outer,obj.inner,obj.nose,obj.dot]){l.unbindTooltip?.();l.bindTooltip?.(tip,{direction:'top'})}}
  }
  for(const [id,obj] of [...geoMarkers])if(!keep.has(id)){geoMap.removeLayer(obj.group);geoMarkers.delete(id)}
}
// ---------- station ETA quick board ----------
function servingLines(code){return G.stationLines?.[code]||runtime.stationLines?.[code]||[]}
async function fetchQuick(){
  if(!quickCode)return;const code=quickCode,lines=servingLines(code);if(!lines.length){quickError='No supported live lines at this station';quickObs=[];renderQuick();return}
  try{let u='/api/station-board?station='+encodeURIComponent(code)+'&lines='+encodeURIComponent(lines.join(','));let r=await fetch(u,{cache:'no-store'}),j=await r.json();if(code!==quickCode)return;if(!r.ok||!j.ok)throw new Error(j.error||`HTTP ${r.status}`);quickObs=j.observations||[];quickFetchAt=Date.now();quickError='';}
  catch(e){if(code===quickCode)quickError=String(e?.message||e)}renderQuick();
}
function setActiveGeoTDStation(code){
  $$('.v12-geotd-hotspot').forEach(x=>x.classList.toggle('active',x.dataset.station===code));
}
function openStationQuick(code){
  quickCode=code;quickObs=[];quickError='Loading official ETA…';
  setActiveGeoTDStation(code);
  $('#stationQuick').classList.remove('hidden');
  // Open the full Board at the same time. It combines direct MTR ETA with the
  // app's ETA-corrected timetable/WTT fallback, so a station click is useful
  // even when a direct station request is temporarily unavailable.
  (window.V12_OPEN_STATION||window.V11_OPEN_STATION)?.(code);
  renderQuick();fetchQuick();clearInterval(quickTimer);quickTimer=setInterval(fetchQuick,8000)
}
function closeQuick(){quickCode=null;setActiveGeoTDStation(null);clearInterval(quickTimer);quickTimer=null;$('#stationQuick')?.classList.add('hidden')}
function renderQuick(){
  const box=$('#stationQuick');if(!box||!quickCode)return;const st=G.stations[quickCode]||D.stations[quickCode],now=runtime.simSec||0;
  const etaOf=o=>o.estimated_eta_sec??o.eta_sec;
  const rows=(quickObs||[]).filter(o=>etaOf(o)>=now-30).sort((a,b)=>etaOf(a)-etaOf(b)).slice(0,10);
  let h=`<button class="sq-close" title="Close">×</button><h3>${esc(st?.name||quickCode)}</h3><div class="sq-sub">Estimated station times · HKT · MTR live ETA window + WTT seconds</div>`;
  if(quickError)h+=`<div class="sq-note">${esc(quickError)}${window.V12_OPEN_STATION?' · The full board remains available with ETA-corrected/WTT fallback.':''}</div>`;
  if(!rows.length&&!quickError)h+='<div class="sq-note">No direct arrivals returned in the current API window.</div>';
  for(const o of rows){const col=D.lines[o.line]?.color||'#889',dest=(G.stations[o.dest]?.name||D.stations[o.dest]?.name||o.dest||'—'),eta=etaOf(o),d=eta-now,src=o.estimated?'EST':'API';h+=`<div class="sq-row" title="${esc(o.estimate_source||'MTR Next Train API')}"><i style="background:${col}"></i><div><b>${esc(o.line)} · ${esc(dest)}</b><span>${esc(o.direction||'')} ${o.platform?`· platform ${esc(o.platform)}`:''} · ${src}</span></div><time>${fmt(eta)}<small>${fmtCountdown(d)}</small></time></div>`}
  h+=`<button class="sq-full">Open full station board</button><div class="sq-note">Seconds are <b>estimated</b>, not claimed as one-second MTR ground truth. The live MTR ETA fixes the arrival window; WTT timing seconds and the current live line-delay model refine the second phase.</div>`;box.innerHTML=h;
  box.querySelector('.sq-close')?.addEventListener('click',closeQuick);box.querySelector('.sq-full')?.addEventListener('click',()=>{(window.V12_OPEN_STATION||window.V11_OPEN_STATION)?.(quickCode);closeQuick()});
}


function buildGeoTDHotspots(){const box=$('#geotdStationHotspots');if(!box)return;box.innerHTML='';for(const [code,s] of Object.entries(G.stations||{})){if(!s.geotd)continue;let b=document.createElement('button');b.className='v12-geotd-hotspot';b.dataset.station=code;b.style.left=(s.geotd[0]*100)+'%';b.style.top=(s.geotd[1]*100)+'%';b.title=`${s.name} · click for ETA`;b.setAttribute('aria-label',`${s.name} station ETA`);b.onpointerdown=e=>e.stopPropagation();b.onclick=e=>{e.preventDefault();e.stopPropagation();openStationQuick(code)};box.appendChild(b)}}

// ---------- HKO radar: fully lazy; never delays map startup ----------
async function ensureRadarMeta(force=false){
  if(radarMeta&&!force)return radarMeta;$('#radarStatus').textContent='HKO radar loading…';
  try{const r=await fetch('/api/weather/radar',{cache:'no-store'}),j=await r.json();radarMeta=j||{frames:[]};if(j.frames?.length){radarIndex=j.frames.length-1;$('#radarStatus').textContent=`HKO · ${j.frames[radarIndex].time||'latest'}`}else $('#radarStatus').textContent='HKO radar unavailable'}catch(e){radarMeta={frames:[]};$('#radarStatus').textContent='HKO radar unavailable'}return radarMeta;
}
async function showRadarFrame(){if(!geoMap||!radarOn)return;await ensureRadarMeta();if(!radarMeta.frames?.length)return;const f=radarMeta.frames[Math.max(0,Math.min(radarMeta.frames.length-1,radarIndex))];if(radarLayer)geoMap.removeLayer(radarLayer);radarLayer=L.imageOverlay('/api/weather/radar-image?u='+encodeURIComponent(f.url),f.bounds,{opacity:(+$('#radarOpacity').value||55)/100,interactive:false,zIndex:250}).addTo(geoMap);$('#radarStatus').textContent=`HKO · ${f.time||`frame ${radarIndex+1}/${radarMeta.frames.length}`}`}
$('#radarToggle')?.addEventListener('click',async()=>{radarOn=!radarOn;$('#radarToggle').textContent=radarOn?'Radar on':'Radar off';if(!radarOn&&radarLayer){geoMap?.removeLayer(radarLayer);radarLayer=null}else if(radarOn)showRadarFrame()});
$('#radarPlay')?.addEventListener('click',()=>{radarPlaying=!radarPlaying;$('#radarPlay').textContent=radarPlaying?'❚❚':'▶';clearInterval(radarTimer);if(radarPlaying)radarTimer=setInterval(async()=>{await ensureRadarMeta();if(!radarMeta?.frames?.length)return;radarIndex=(radarIndex+1)%radarMeta.frames.length;showRadarFrame()},850)});
$('#radarOpacity')?.addEventListener('input',()=>radarLayer?.setOpacity((+$('#radarOpacity').value||55)/100));

// ---------- schematic / official-map shared geometry ----------
function stationOfficial(code){const q=G.stations?.[code]?.official;return q?[q[0]*1000,q[1]*586]:null}
const graphByLine={};
for(const [line,paths] of Object.entries(G.paths||{})){const g={};for(const path of paths)for(let i=0;i<path.length-1;i++){let a=path[i],b=path[i+1];(g[a]??=[]).push(b);(g[b]??=[]).push(a)}graphByLine[line]=g}
function shortestStationPath(line,a,b){if(a===b)return [a];const g=graphByLine[line];if(!g?.[a]||!g?.[b])return null;let q=[a],prev={[a]:null};for(let k=0;k<q.length;k++){let x=q[k];for(const y of g[x]||[])if(!(y in prev)){prev[y]=x;q.push(y);if(y===b){let p=[b];while(p.at(-1)!==a)p.push(prev[p.at(-1)]);return p.reverse()}}}return null}
function warpGeoTD(x,y){const p=geoWarpPoint(x,y);if(!p)return [500,293]; // fallback only for missing schematic station anchors
  const anchors=[];for(const s of Object.values(G.stations)){if(s.geotd&&s.official)anchors.push([s.geotd[0],s.geotd[1],s.official[0]*1000,s.official[1]*586])}let near=anchors.map(a=>{let dx=x-a[0],dy=y-a[1];return [dx*dx+dy*dy,a]}).sort((a,b)=>a[0]-b[0]).slice(0,12);if(!near.length)return [500,293];if(near[0][0]<1e-10)return [near[0][1][2],near[0][1][3]];let sw=0,X=0,Y=0;for(const [d,a] of near){let w=1/Math.pow(Math.max(d,1e-8),.85);sw+=w;X+=w*a[2];Y+=w*a[3]}return [X/sw,Y/sw]}
function screenPathForState(s){const [a,b]=statePair(s),key=`${s.line}|${a}|${b}`;if(screenPathCache.has(key))return screenPathCache.get(key);let codes=shortestStationPath(s.line,a,b),pts=codes?.map(stationOfficial).filter(Boolean);if(!(pts?.length>=2)&&s.pos&&Number.isFinite(s.pos.x)&&Number.isFinite(s.pos.y)){let p=warpGeoTD(s.pos.x,s.pos.y);pts=[p,[p[0]+1,p[1]]]}let out=pts?.length?pts:null;screenPathCache.set(key,out);return out}
function rawScreenPointForState(s){let path=screenPathForState(s);if(!path)return null;if(path.length===2&&Math.abs(path[1][0]-path[0][0])<=1&&Math.abs(path[1][1]-path[0][1])<.1)return {p:path[0],angle:0};let q=polyPoint(path.map(p=>[p[1],p[0]]),stateFrac(s));return q?{p:[q.p[1],q.p[0]],angle:q.angle}:null}
function rgb(hex){hex=hex.replace('#','');return [parseInt(hex.slice(0,2),16),parseInt(hex.slice(2,4),16),parseInt(hex.slice(4,6),16)]}
function buildOfficialRaster(img){
  try{const c=document.createElement('canvas');c.width=1000;c.height=586;const x=c.getContext('2d',{willReadFrequently:true});x.drawImage(img,0,0,1000,586);officialRaster=x.getImageData(0,0,1000,586);officialBuckets={};const targets=Object.fromEntries(Object.keys(D.lines).filter(l=>l!=='LRL').map(l=>[l,rgb(D.lines[l].color)]));
    for(const line of Object.keys(targets))officialBuckets[line]=new Map();
    for(let y=0;y<586;y+=2)for(let xx=0;xx<1000;xx+=2){let i=(y*1000+xx)*4,R=officialRaster.data[i],GG=officialRaster.data[i+1],B=officialRaster.data[i+2];let best=null,bd=1e9;for(const [line,t] of Object.entries(targets)){let d=(R-t[0])**2+(GG-t[1])**2+(B-t[2])**2;if(d<bd){bd=d;best=line}}if(bd<95*95){let key=(xx>>5)+','+(y>>5),m=officialBuckets[best];if(!m.has(key))m.set(key,[]);m.get(key).push([xx,y])}}officialReady=true;buildScreenStations('official',true);updateScreenTrains('official',runtime.states||[]);
  }catch(e){officialReady=false}
}
function snapOfficial(p,line,radius=96){
  if(!officialReady||!officialBuckets[line])return p;
  const m=officialBuckets[line],bx=p[0]>>5,by=p[1]>>5;
  let best=null,bd=Infinity;
  // Search locally first, then expand only if the rough schematic seed is materially displaced.
  // Returning only a sampled pixel from the official line guarantees the dot visually lies on that route.
  const localR=Math.ceil(radius/32);
  for(let ring=0;ring<=Math.max(localR,32)&&!best;ring++){
    let x0=bx-ring,x1=bx+ring,y0=by-ring,y1=by+ring;
    for(let yy=y0;yy<=y1;yy++)for(let xx=x0;xx<=x1;xx++){
      if(ring&&xx>x0&&xx<x1&&yy>y0&&yy<y1)continue;
      for(const q of m.get(xx+','+yy)||[]){let d=(q[0]-p[0])**2+(q[1]-p[1])**2;if(d<bd){bd=d;best=q}}
    }
    if(best&&ring>=localR)break;
  }
  return best||p;
}
function screenPointForState(s,kind){let q=rawScreenPointForState(s);if(!q)return null;if(kind==='official')q={...q,p:snapOfficial(q.p,s.line)};return q}
function buildCleanSchematic(){if(schematicBuilt)return;const svg=$('#schematicSvg');if(!svg)return;svg.innerHTML='';const NS='http://www.w3.org/2000/svg';for(const [line,paths] of Object.entries(G.paths||{})){for(const codes of paths){let pts=codes.map(stationOfficial).filter(Boolean);if(pts.length<2)continue;let e=document.createElementNS(NS,'polyline');e.setAttribute('points',pts.map(p=>p.join(',')).join(' '));e.setAttribute('fill','none');e.setAttribute('stroke','#061017');e.setAttribute('stroke-width','9');e.setAttribute('stroke-linecap','round');e.setAttribute('stroke-linejoin','round');e.setAttribute('opacity','.72');svg.appendChild(e);let f=e.cloneNode();f.setAttribute('stroke',D.lines[line]?.color||'#fff');f.setAttribute('stroke-width','5');f.setAttribute('opacity','.98');svg.appendChild(f)}}for(const [code,st] of Object.entries(G.stations)){let p=stationOfficial(code);if(!p)continue;let c=document.createElementNS(NS,'circle');c.setAttribute('cx',p[0]);c.setAttribute('cy',p[1]);c.setAttribute('r',(st.lines?.length||0)>1?'5.5':'3.2');c.setAttribute('fill','#f8fbfc');c.setAttribute('stroke','#081117');c.setAttribute('stroke-width','2');svg.appendChild(c)}schematicBuilt=true}
function fitWorld(kind){const vp=$(`#${kind}Viewport`),w=$(`#${kind}World`);if(!vp||!w)return;const st=screenState[kind],base=Math.min(vp.clientWidth/1000,vp.clientHeight/586);st.scale=base;st.x=(vp.clientWidth-1000*base)/2;st.y=(vp.clientHeight-586*base)/2;st.fit=true;applyWorld(kind)}
function applyWorld(kind){const w=$(`#${kind}World`),st=screenState[kind];if(w)w.style.transform=`translate(${st.x}px,${st.y}px) scale(${st.scale})`}
function zoomWorld(kind,f,cx,cy){const vp=$(`#${kind}Viewport`),st=screenState[kind];if(!vp)return;cx??=vp.clientWidth/2;cy??=vp.clientHeight/2;let old=st.scale;st.scale=Math.max(.18,Math.min(40,st.scale*f));st.x=cx-(cx-st.x)*(st.scale/old);st.y=cy-(cy-st.y)*(st.scale/old);st.fit=false;applyWorld(kind)}
function bindPanZoom(kind){const vp=$(`#${kind}Viewport`);if(!vp)return;let drag=null;vp.addEventListener('wheel',e=>{e.preventDefault();let r=vp.getBoundingClientRect();zoomWorld(kind,e.deltaY<0?1.18:.85,e.clientX-r.left,e.clientY-r.top)},{passive:false});vp.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,mx:screenState[kind].x,my:screenState[kind].y};vp.setPointerCapture(e.pointerId);vp.classList.add('dragging')});vp.addEventListener('pointermove',e=>{if(!drag)return;screenState[kind].x=drag.mx+e.clientX-drag.x;screenState[kind].y=drag.my+e.clientY-drag.y;screenState[kind].fit=false;applyWorld(kind)});vp.addEventListener('pointerup',()=>{drag=null;vp.classList.remove('dragging')});}
function buildScreenStations(kind,force=false){const box=$(`#${kind}Stations`);if(!box)return;if(!force&&box.children.length)return;box.innerHTML='';for(const [code,s] of Object.entries(G.stations)){if(kind==='official'&&!(s.lines||[]).some(l=>l!=='LRL'))continue;let p=stationOfficial(code);if(!p)continue;if(kind==='official'&&officialReady){let candidates=(s.lines||[]).filter(l=>l!=='LRL').map(l=>snapOfficial(p,l,75));if(candidates.length)candidates.sort((a,b)=>(a[0]-p[0])**2+(a[1]-p[1])**2-((b[0]-p[0])**2+(b[1]-p[1])**2)),p=candidates[0]}let b=document.createElement('button');b.className='v12-station-hotspot';b.style.left=(p[0]/10)+'%';b.style.top=(p[1]/5.86)+'%';b.title=`${s.name} · click for live ETA`;b.setAttribute('aria-label',`${s.name} station ETA`);b.onclick=e=>{e.stopPropagation();openStationQuick(code)};box.appendChild(b)}}
function updateScreenTrains(kind,states){const box=$(`#${kind}Markers`);if(!box)return;const map=screenMarkers[kind],keep=new Set;for(const s of states||[]){if(kind==='official'&&s.line==='LRL')continue;const q=screenPointForState(s,kind);if(!q)continue;const id=stateId(s);keep.add(id);let b=map.get(id);if(!b){b=document.createElement('button');b.className=`v12-train-dot ${s.live?'live':''}`;b.onclick=e=>{e.stopPropagation();openState(b._state)};box.appendChild(b);map.set(id,b)}b._state=s;b.style.left=(q.p[0]/10)+'%';b.style.top=(q.p[1]/5.86)+'%';b.style.setProperty('--train-color',D.lines[s.line]?.color||'#fff');b.classList.toggle('live',!!s.live);if(b._tipSec!==Math.floor(runtime.simSec||0)){b._tipSec=Math.floor(runtime.simSec||0);b.title=`${s.line} ${s.live?s.train?.td||s.train?.train_set_id:s.trip?.[0]} · ${Math.round(s.speedKph||0)} km/h`}}for(const [id,b] of [...map])if(!keep.has(id)){b.remove();map.delete(id)}}
function initScreenWorld(kind){if(kind==='schematic')buildCleanSchematic();buildScreenStations(kind);fitWorld(kind);updateScreenTrains(kind,runtime.states||[])}

// ---------- mode switch ----------
function ensureOfficialImage(){const img=$('#officialWorld .official-map-img');if(!img)return;if(!img.dataset.bound){img.dataset.bound='1';img.addEventListener('load',()=>buildOfficialRaster(img));img.addEventListener('error',()=>{officialReady=false;if(img.getAttribute('src')==='/api/map/official-system'){img.src='https://www.mtr.com.hk/en/customer/images/jp/system_map.png'}})}if(!img.getAttribute('src')&&img.dataset.src)img.src=img.dataset.src}

async function setMode(next){
  mode=next;$$('.map-mode-switch button').forEach(b=>b.classList.toggle('active',b.dataset.mapMode===next));
  $('#mapWorld')?.classList.toggle('hidden',next!=='geotd');$('#geoMap')?.classList.toggle('hidden',next!=='geo');$('#schematicPane')?.classList.toggle('hidden',next!=='schematic');$('#officialMapPane')?.classList.toggle('hidden',next!=='official');$('#radarControl')?.classList.toggle('hidden',next!=='geo');
  for(const id of ['zoomOut','resetMap','zoomIn'])$('#'+id)?.classList.toggle('hidden',next!=='geotd');
  if(next==='geo'){await initGeo();updateGeoTrains(runtime.states||[])}else if(next==='schematic'){initScreenWorld('schematic');updateScreenTrains('schematic',runtime.states||[])}else if(next==='official'){ensureOfficialImage();initScreenWorld('official');updateScreenTrains('official',runtime.states||[])}
  const r=next==='geotd'?($('#mapImage')?.dataset.res?`GeoTD ${$('#mapImage').dataset.res}`:'GeoTD'):next==='geo'?`Real map · native WGS84/OSM tracks${directGeo.loaded?' · '+directGeo.loaded+' line routes':''} · real-size trains z${MIN_REAL_TRAIN_ZOOM}+`:next==='schematic'?'Calibrated vector schematic':'Official MTR map · heavy rail live overlay';$('#mapResolution').textContent=r;
}
$$('.map-mode-switch button').forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.mapMode)));

// controls for local screen worlds
bindPanZoom('schematic');bindPanZoom('official');
$('#schIn')?.addEventListener('click',()=>zoomWorld('schematic',1.25));$('#schOut')?.addEventListener('click',()=>zoomWorld('schematic',.8));$('#schReset')?.addEventListener('click',()=>fitWorld('schematic'));
$('#offIn')?.addEventListener('click',()=>zoomWorld('official',1.25));$('#offOut')?.addEventListener('click',()=>zoomWorld('official',.8));$('#offReset')?.addEventListener('click',()=>fitWorld('official'));
window.addEventListener('resize',()=>{for(const k of ['schematic','official'])if(screenState[k].fit)fitWorld(k);geoMap?.invalidateSize()});

// Fleet gallery
function buildFleet(){const box=$('#fleetGrid');if(!box)return;box.innerHTML=Object.entries(models).map(([line,m])=>`<div class="fleet-card"><img src="${m.src}" alt="${esc(m.label)}"><b style="color:${D.lines[line]?.color||'#fff'}">${esc(line)} · ${esc(m.label)}</b><span>${esc(m.kind||'representative vector model')}</span></div>`).join('')}
$('#fleetBtn')?.addEventListener('click',()=>{$('#fleetModal').classList.remove('hidden');buildFleet()});$('#fleetClose')?.addEventListener('click',()=>$('#fleetModal').classList.add('hidden'));$('#fleetModal')?.addEventListener('click',e=>{if(e.target.id==='fleetModal')$('#fleetModal').classList.add('hidden')});

window.addEventListener('mtr:v11-state',e=>{runtime=e.detail||runtime;if(mode==='geo')updateGeoTrains(runtime.states||[]);if(mode==='schematic')updateScreenTrains('schematic',runtime.states||[]);if(mode==='official')updateScreenTrains('official',runtime.states||[]);if(quickCode){let sec=Math.floor(runtime.simSec||0);if(sec!==quickLastSec){quickLastSec=sec;renderQuick()}}});
buildGeoTDHotspots();setMode('geotd');
// Warm the real-map library only after the operational display is already interactive.
if('requestIdleCallback' in window)requestIdleCallback(()=>loadLeaflet().catch(()=>{}),{timeout:2500});else setTimeout(()=>loadLeaflet().catch(()=>{}),1500);
})();
