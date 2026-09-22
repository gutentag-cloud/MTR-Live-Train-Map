const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const src=fs.readFileSync('app.js','utf8');const code=src.slice(src.indexOf("let boardRequestId="),src.indexOf('\nfunction boardEvents()'));
const calls=[];let rendered=0;const ctx=vm.createContext({location:{protocol:'http:'},boardStation:'ADM',boardLine:'',activeSideTab:'board',stationBoard:{observations:[]},stationServingLines:()=>['EAL','ISL'],Date,AbortSignal,encodeURIComponent,renderBoard:()=>rendered++,apiFetch:(u)=>new Promise((resolve,reject)=>calls.push({u,resolve,reject}))});vm.runInContext(code,ctx);
(async()=>{
 const a=vm.runInContext('pollStationBoard(true)',ctx);await vm.runInContext('pollStationBoard(true)',ctx);assert.equal(calls.length,1,'duplicate fetch suppressed');
 ctx.boardLine='ISL';const b=vm.runInContext('pollStationBoard(true)',ctx);assert.equal(calls.length,2);
 calls[1].resolve({json:async()=>({ok:true,observations:[{line:'ISL'}]})});await b;
 calls[0].resolve({json:async()=>({ok:true,observations:[{line:'EAL'}]})});await a;assert.equal(ctx.stationBoard.observations[0].line,'ISL');
 ctx.boardLine='EAL';const old=vm.runInContext('pollStationBoard(true)',ctx);ctx.boardLine='ISL';const newer=vm.runInContext('pollStationBoard(true)',ctx);calls[3].resolve({json:async()=>({ok:true,observations:[{line:'ISL'}]})});await newer;calls[2].reject(new Error('old error'));await old;assert.equal(ctx.stationBoard.error,null);assert.equal(rendered,2);
 console.log('Board requests: duplicate suppression, out-of-order success and stale failure passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
