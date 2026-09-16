const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const c=vm.createContext({window:{},Date,Math});vm.runInContext(fs.readFileSync('arrival_display.js','utf8'),c);const a=c.window.ArrivalDisplay;
assert.equal(a.time(47467),'≈ 13:11');assert.equal(a.time(47467,true),'≈ 13:11:07');assert.equal(a.time(90007),'≈ 01:00');assert.equal(a.countdown(-60),'Awaiting update');assert.equal(a.countdown(10),'Due soon');assert.equal(a.countdown(165),'~3 min');assert.equal(a.countdown(165,true),'≈ 2m 45s');console.log('Arrival presentation checks passed.');
