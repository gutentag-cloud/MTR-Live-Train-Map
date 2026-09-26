(()=>{
const $=s=>document.querySelector(s),G=window.V12_GEO;
const nav=document.createElement('nav');nav.className='phone-nav';nav.setAttribute('aria-label','Phone navigation');nav.innerHTML='<button data-view="map" aria-pressed="true">Map</button><button data-view="board" aria-pressed="false">Arrivals</button><button data-view="plan">Journey</button><button data-view="data">Data</button>';document.body.append(nav);
function view(which){document.body.dataset.phoneView=which;nav.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===which)))}
document.addEventListener('station-board-open',()=>view('board'));
nav.onclick=e=>{const v=e.target.dataset.view;if(v==='plan')$('#journeyBtn').click();else if(v==='data')openData();else if(v){view(v);if(v==='board')$('#boardTab').click()}};
const toolbar=$('.explore-bar');const doorButton=document.createElement('button');doorButton.textContent='Best door';doorButton.onclick=openDoor;toolbar.append(doorButton);
const dataButton=document.createElement('button');dataButton.textContent='Prediction data';dataButton.onclick=openData;toolbar.append(dataButton);
function dialog(id,title){let d=document.createElement('dialog');d.id=id;d.className='passenger-dialog';d.innerHTML=`<form method="dialog"><h2>${title}</h2><button aria-label="Close ${title}">×</button></form><div class="passenger-content"></div>`;document.body.append(d);return d}
const door=dialog('doorAdvisor','Best door'),data=dialog('dataPanel','Prediction data');
const options=Object.entries(G.stations).sort((a,b)=>a[1].name.localeCompare(b[1].name)).map(([c,s])=>`<option value="${c}">${s.name}</option>`).join('');
door.querySelector('.passenger-content').innerHTML=`<p>Plan for the shortest walk to your chosen exit.</p><label>Starting station<select id="doorFrom">${options}</select></label><label>Destination station<select id="doorTo">${options}</select></label><label>Exit letter / number<input id="doorExit" value="F" maxlength="12" placeholder="e.g. F"></label><button id="doorCheck">Check boarding guidance</button><div id="doorResult" aria-live="polite"></div>`;
$('#doorFrom').value='MKK';$('#doorTo').value='ADM';
function openDoor(){door.showModal();doorResult()}
function doorResult(){const from=$('#doorFrom').value,to=$('#doorTo').value,exit=$('#doorExit').value.trim().toUpperCase(),r=$('#doorResult');r.replaceChildren();let p=document.createElement('p');p.textContent=`${G.stations[from].name} → ${G.stations[to].name} · Exit ${exit||'not selected'}`;r.append(p);let note=document.createElement('p');note.textContent=from===to?'Select a different destination for a train journey.':!exit?'Enter your destination exit.':'Car and door mapping is not verified in this app. In MTR Mobile, select this journey, open Suggested Route → Fast Exit, then choose this exit. An arrival platform is also needed at stations with multiple possible platforms.';r.append(note);let a=document.createElement('a');a.href='https://www.mtr.com.hk/mtrmobile/en/transport/fast-exit/';a.target='_blank';a.rel='noopener';a.textContent='MTR Fast Exit instructions ↗';r.append(a)}
$('#doorCheck').onclick=doorResult;for(const id of ['doorFrom','doorTo','doorExit'])$('#'+id).addEventListener('change',doorResult);
async function openData(){
 data.showModal();const box=data.querySelector('.passenger-content');box.replaceChildren();
 const statusBox=document.createElement('section'),reportBox=document.createElement('section');box.append(reportBox,statusBox);
 statusBox.textContent='Checking collector…';reportBox.textContent='Loading historical evaluation…';
 const paragraph=(parent,text)=>{const p=document.createElement('p');p.textContent=text;parent.append(p)};
 await Promise.allSettled([
  (async()=>{try{
   const response=await apiFetch('/api/training/status',{signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error('Unavailable');const status=await response.json();statusBox.replaceChildren();
   paragraph(statusBox,'Collector observations');
   for(const source of status.sources||[])paragraph(statusBox,`${source.kind==='eal'?'East Rail telemetry':'Official ETA'}: ${source.rows.toLocaleString()} rows. Last record: ${new Date(source.newest*1000).toLocaleString('en-GB',{timeZone:'Asia/Hong_Kong'})} HKT.`);
   paragraph(statusBox,'Collection runs while the API server is awake. Continuous collection requires persistent storage and an always-on service.');
  }catch{statusBox.textContent='Collector status unavailable. The historical evaluation above is independent of the live API.'}})(),
  (async()=>{try{
   const response=await fetch('training_report.json',{signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error('Unavailable');const r=await response.json();reportBox.replaceChildren();
   const seconds=n=>Number.isFinite(n)?n.toFixed(1)+' s':'not evaluated';
   paragraph(reportBox,`Historical model · ${r.deployed?'active':'not deployed'}`);
   paragraph(reportBox,`${r.labeled_rows.toLocaleString()} labeled observations, ${r.journeys.toLocaleString()} arrival groups across ${r.days} dates. ${r.dates?.join(', ')||''}`);
   paragraph(reportBox,`Training: ${r.training_dates?.join(', ')||'see report'}. Validation: ${r.validation_dates?.join(', ')||'see report'}. Test: ${r.test_dates?.join(', ')||'see report'}.`);
   paragraph(reportBox,`Held-out mean error: ${seconds(r.test_mae_seconds)}. Learned progress-only baseline: ${seconds(r.test?.progress_baseline_mae_seconds)}. Distance/speed baseline: ${seconds(r.constant_speed_baseline_mae_seconds)}.`);
   paragraph(reportBox,`90th-percentile error: ${seconds(r.test?.p90_error_seconds)}. Model support: ${((r.test?.coverage||0)*100).toFixed(1)}%. Error includes unsupported rows using fallback estimates.`);
   if(r.test?.segments){const table=document.createElement('table');table.className='evaluation-table';const caption=document.createElement('caption');caption.textContent='Your direction: Mong Kok East → Admiralty';table.append(caption);for(const name of ['MKK → HUH','HUH → EXC','EXC → ADM']){const metric=r.test.segments[name];if(!metric)continue;const row=table.insertRow();row.insertCell().textContent=name;row.insertCell().textContent=seconds(metric.mae_seconds)+' mean error'}reportBox.append(table)}
   paragraph(reportBox,'Target: time to the first stopped telemetry sample. These are not GPS-position errors or independently measured doors-open times.');
   if(r.review_blockers?.length)paragraph(reportBox,'Not ready for live use: '+r.review_blockers.join('; ')+'.');
  }catch{reportBox.textContent='Historical evaluation could not be loaded.'}})()
 ]);
}
})();
