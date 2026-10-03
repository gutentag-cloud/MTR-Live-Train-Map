const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const c=vm.createContext({window:{},Date,Math});vm.runInContext(fs.readFileSync('arrival_display.js','utf8'),c);const a=c.window.ArrivalDisplay;
assert.equal(a.time(47467),'≈ 13:11:07');assert.equal(a.time(47467,true),'≈ 13:11:07');assert.equal(a.time(90007),'≈ 01:00:07');assert.equal(a.time(NaN),'—');
assert.equal(a.countdown(-60),'Awaiting update');assert.equal(a.countdown(0),'Due · unconfirmed');assert.equal(a.countdown(10),'≈ 0m 10s');assert.equal(a.countdown(165),'≈ 2m 45s');assert.equal(a.countdown(165,true),'≈ 2m 45s');assert.equal(a.countdown(60),'≈ 1m 00s');assert.equal(a.countdown(59),'≈ 0m 59s');assert.equal(a.countdown(.1),'≈ 0m 01s');assert.equal(a.countdown(undefined),'Unavailable');
console.log('Second display, countdown transitions, midnight and invalid estimates passed.');

// Live station countdown follows real time even when simulation is paused or accelerated.
let callback,wallTime=1000,draws=0;
const tickContext=vm.createContext({window:{addEventListener:(type,fn)=>callback=fn},Date:{now:()=>wallTime},runtime:{},mode:'geotd',quickCode:'MKK',quickLastSec:-1,renderQuick:()=>draws++});
const handler=fs.readFileSync('v12.js','utf8').match(/window\.addEventListener\('mtr:v11-state',e=>\{[^\n]*\}\);/)[0];vm.runInContext(handler,tickContext);
callback({detail:{simSec:100}});assert.equal(draws,1);
callback({detail:{simSec:1000}});assert.equal(draws,1);
wallTime=2000;callback({detail:{simSec:1000}});assert.equal(draws,2);
console.log('Live station countdown remains independent of simulation pause and speed.');
