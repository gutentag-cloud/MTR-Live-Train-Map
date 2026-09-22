const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const ctx={window:{}};vm.runInNewContext(fs.readFileSync('live_position.js','utf8'),ctx);const p=ctx.window.LivePosition;
assert.equal(p.ageSeconds('2026-09-22 12:00:00',Date.parse('2026-09-22T04:00:10Z')),10);
assert.equal(p.ageSeconds('invalid'),Infinity);
assert.equal(p.ageSeconds('2026-09-22T04:01:00Z',Date.parse('2026-09-22T04:00:00Z')),Infinity);
const t={distance_prev_m:100,distance_next_m:900,speed_kph:72};
assert.equal(p.fraction(t,2),.14);assert.equal(p.fraction(t,90),.16);
assert.equal(p.fraction({...t,vehicle_in_station:true},2),.1);
assert.equal(p.fraction({...t,zero_velocity:true},2),.1);
assert.equal(p.fraction({...t,distance_next_m:1},3),1);
assert.equal(p.fraction({...t,distance_prev_m:-1},2),null);
console.log('Position timestamps, stopped trains, latency cap and segment bounds passed');
// A line-wide offset must never silently shift a WTT-only arrival.
const app=fs.readFileSync('app.js','utf8');const start=app.indexOf('function delayPrediction('),end=app.indexOf('\n',start);
const forecast={correctionFor:()=>null,fitDelayHistory:()=>{throw Error('Unmatched trip must not use history')},tripDelayHistory:()=>[]};
vm.createContext(forecast);vm.runInContext(app.slice(start,end),forecast);
assert.equal(forecast.delayPrediction(['test','EAL',[]],600).delaySec,0);
assert.equal(forecast.delayPrediction(['test','EAL',[]],600).source,'WTT only');
console.log('Unmatched arrival forecasts remain unshifted');
