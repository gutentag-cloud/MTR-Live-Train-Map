(()=>{
'use strict';
const $=s=>document.querySelector(s),G=window.V12_GEO,D=window.TRAIN_DATA;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const name=c=>G.stations[c]?.name||c;
let currentStation=null;
const dialog=document.createElement('dialog');dialog.id='journeyDialog';
dialog.innerHTML=`<form method="dialog" class="journey-heading"><div><small>PLAN YOUR NEXT RIDE</small><h2>Across Hong Kong</h2></div><button aria-label="Close journey planner">×</button></form><form id="journeyForm"><div class="journey-inputs"><label>From<select id="journeyFrom"></select></label><button type="button" id="swapJourney" aria-label="Swap origin and destination">⇄</button><label>To<select id="journeyTo"></select></label></div><div class="journey-options"><label>Prefer<select id="journeyPreference"><option value="transfers">Fewer changes</option><option value="stops">Fewer stops</option></select></label><label><input type="checkbox" id="journeyExpress">Include Airport Express</label><button class="primary" type="submit">Find route</button></div></form><div id="journeyResult" aria-live="polite"><p>Choose two stations to see where to ride and change.</p></div><p class="journey-disclaimer">Uses the bundled network map. Stop counts exclude your starting station. This planner does not check disruptions, fares, walking connections or operating hours.</p>`;
document.body.append(dialog);
const stations=Object.entries(G.stations).filter(([c])=>Object.values(G.paths).some(branches=>branches.some(p=>p.includes(c)))).sort((a,b)=>a[1].name.localeCompare(b[1].name));
const options=stations.map(([c,s])=>`<option value="${esc(c)}">${esc(s.name)}</option>`).join('');
$('#journeyFrom').innerHTML=options;$('#journeyTo').innerHTML=options;$('#journeyFrom').value='ADM';$('#journeyTo').value='TUC';
$('#journeyBtn').onclick=()=>{if(currentStation&&stations.some(([c])=>c===currentStation))$('#journeyFrom').value=currentStation;renderJourney();dialog.showModal()};
$('#swapJourney').onclick=()=>{const from=$('#journeyFrom').value;$('#journeyFrom').value=$('#journeyTo').value;$('#journeyTo').value=from;renderJourney()};
for(const id of ['journeyFrom','journeyTo','journeyPreference','journeyExpress'])$('#'+id).addEventListener('change',renderJourney);
$('#journeyForm').onsubmit=e=>{e.preventDefault();renderJourney()};
function openStation(code){window.dispatchEvent(new CustomEvent('mtr:open-station',{detail:code}))}
function renderJourney(){
 const from=$('#journeyFrom').value,to=$('#journeyTo').value,result=JourneyPlanner.plan(G.paths,from,to,$('#journeyPreference').value,$('#journeyExpress').checked),box=$('#journeyResult');
 if(!result){box.innerHTML='<p>No connected route is available with these options.</p>';return}
 if(!result.stops){box.innerHTML='<p>You have selected the same station. No train journey is needed.</p>';return}
 box.innerHTML=`<div class="journey-summary"><strong>${result.stops} ${result.stops===1?'stop':'stops'}</strong><span>${result.transfers?result.transfers+' change'+(result.transfers>1?'s':''):'Direct · no changes'}</span></div><ol class="journey-legs">${result.legs.map((l,i)=>`<li style="--route-color:${D.lines[l.line]?.color||'#999'}"><small>${i?'Change at '+esc(name(l.from)):'Start at '+esc(name(l.from))}</small><h3>${esc(D.lines[l.line]?.name||l.line)}</h3><p>Ride to <b>${esc(name(l.to))}</b> · ${l.stations.length-1} ${l.stations.length===2?'stop':'stops'}</p><details><summary>Show stops</summary><div class="journey-stops">${l.stations.map(c=>`<button type="button" data-station="${esc(c)}">${esc(name(c))}</button>`).join('')}</div></details><button type="button" class="journey-arrivals" data-station="${esc(l.from)}">Check arrivals at ${esc(name(l.from))} ↗</button></li>`).join('')}</ol>`;
 box.querySelectorAll('[data-station]').forEach(b=>b.onclick=()=>{dialog.close();openStation(b.dataset.station)});
}
$('#cleanMap').onchange=e=>{document.body.classList.toggle('hide-trains',!e.target.checked)};
window.addEventListener('mtr:station-selected',e=>{currentStation=e.detail;$('#shareStation').disabled=false;$('#shareStation').title='Copy a link to '+name(currentStation)});
$('#shareStation').onclick=async()=>{
 if(!currentStation)return;const url=new URL(location.href);url.searchParams.set('station',currentStation);url.hash='';
 try{await navigator.clipboard.writeText(url.href);$('#finderStatus').textContent='Station link copied for '+name(currentStation)+'.'}catch{
  const status=$('#finderStatus');status.textContent='Copy this station link: ';const input=document.createElement('input');input.readOnly=true;input.value=url.href;input.setAttribute('aria-label','Station share link');status.append(input);input.select();
 }
};
const initial=new URL(location.href).searchParams.get('station');if(initial&&G.stations[initial])openStation(initial);
})();
