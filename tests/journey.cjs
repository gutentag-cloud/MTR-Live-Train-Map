const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');const ctx=vm.createContext({window:{}});for(const f of ['v12_geo_data.js','journey.js'])vm.runInContext(fs.readFileSync(f,'utf8'),ctx);const plan=ctx.window.JourneyPlanner.plan,paths=ctx.window.V12_GEO.paths;
let r=plan(paths,'ADM','CEN');assert.equal(r.stops,1);assert.equal(r.transfers,0);
r=plan(paths,'KWT','TUC');assert(r&&r.transfers>0);assert.equal(r.legs[0].from,'KWT');assert.equal(r.legs.at(-1).to,'TUC');for(let i=1;i<r.legs.length;i++)assert.equal(r.legs[i-1].to,r.legs[i].from);
assert.equal(plan(paths,'ADM','ADM').stops,0);assert.equal(plan(paths,'NOPE','ADM'),null);assert.equal(plan(paths,'HOK','AIR'),null);assert(plan(paths,'HOK','AIR','transfers',true));
const small={one:[['A','B','C','D','E']],two:[['A','X']],three:[['X','E']]};assert.equal(plan(small,'A','E','transfers').stops,4);assert.equal(plan(small,'A','E','stops').stops,2);console.log('Journey planner: direct, transfer, preferences, Airport Express, missing station, same station passed.');

assert.equal(plan(paths,'NOPE','NOPE'),null);assert.equal(plan(paths,'AIR','AIR'),null);assert.equal(plan(paths,'AIR','AIR','transfers',true).stops,0);
