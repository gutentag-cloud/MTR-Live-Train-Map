const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx=vm.createContext({window:{},console,Intl,Date,Math,Map,Set,document:{querySelector:()=>null}});
for(const f of ['light_rail_schedule.js','light_rail_data.js'])vm.runInContext(fs.readFileSync(f,'utf8'),ctx);
const source=fs.readFileSync('light_rail.js','utf8');
vm.runInContext(source.slice(0,source.indexOf("$('#lrRefresh').onclick"))+';window.test={metric,pathAt,spark,stateAt,observationAge,hkNow};})();',ctx);
const {metric,pathAt,spark,stateAt}=ctx.window.test,L=ctx.window.LR_DATA;
let count=0;
for(const pair of Object.keys(L.trackRoutes)){
 const [a,b]=pair.split('|'),m=metric(a,b);assert(m.tot>0);
 for(const f of [0,.2,.5,.9,1]){let p=pathAt(a,b,f);assert(Number.isFinite(p.angle));assert(p.x>=0&&p.x<=1&&p.y>=0&&p.y<=1);count++}
 const start=pathAt(a,b,0),end=pathAt(a,b,1);assert(Math.hypot(start.x-m.pts[0].x,start.y-m.pts[0].y)<1e-8);assert(Math.hypot(end.x-m.pts.at(-1).x,end.y-m.pts.at(-1).y)<1e-8);
}
assert.equal(metric('missing','station'),null);
assert(spark([2,5,1]).includes('<svg'));assert(!spark([2,5,1]).includes('NaN'));
L.trackRoutes['test|angle']=[[0,0],[1,1]];
assert(Math.abs(pathAt('test','angle',.5).angle-Math.atan2(4314,3163)*180/Math.PI)<1e-9);
console.log(`Passed: ${count} route samples, endpoint alignment, aspect-correct tangent, missing geometry, delay chart.`);

assert(ctx.window.test.observationAge({observed_at:new Date(Date.now()-120000).toISOString()})>=120);
assert(ctx.window.test.observationAge({observed_at:new Date(Date.now()+120000).toISOString()})===0);
console.log('Passed: per-stop freshness and future timestamp bounds.');
