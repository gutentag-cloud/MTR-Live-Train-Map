window.APP_CONFIG = {
  API_BASE:
    location.hostname === "gutentag-cloud.github.io"
      ? "https://mtr-live-train-map-api.onrender.com"
      : ""
};

// GitHub Pages is static-only, so same-origin /api calls would return GitHub's HTML
// 404 page there. Route them to the Render backend declared in render.yaml while
// keeping same-origin behaviour when serve_live.py hosts the page locally.
// No upstream credential is embedded here or ever served to the browser.
window.API = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "";
// Share simultaneous GETs, while retaining a separate cancellation signal per caller.
const apiPending=new Map();
window.apiFetch=function(url,opts={}){
 const share=(!opts.method||opts.method==='GET')&&!opts.body&&!opts.headers;
 const key=window.API+url;
 let work=share?apiPending.get(key):null;
 if(!work){
  work=fetch(key,{cache:'no-store',...opts,signal:share?AbortSignal.timeout(15000):opts.signal}).then(r=>{
   if(!r.ok)throw new Error(`HTTP ${r.status}${r.status>=502?' — live service warming up or unavailable':''}`);
   return r;
  });
  if(share){apiPending.set(key,work);work.finally(()=>{if(apiPending.get(key)===work)apiPending.delete(key)}).catch(()=>{})}
 }
 return new Promise((resolve,reject)=>{
  const abort=()=>reject(opts.signal.reason||new DOMException('Aborted','AbortError'));
  if(opts.signal?.aborted){abort();return}
  opts.signal?.addEventListener('abort',abort,{once:true});
  work.then(r=>resolve(r.clone()),reject).finally(()=>opts.signal?.removeEventListener('abort',abort));
 });
};
