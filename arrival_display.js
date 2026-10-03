/* Seconds are display precision; accuracy depends on the estimate's source. */
window.ArrivalDisplay={
 now(){let sec=(Math.floor(Date.now()/1000)+8*3600)%86400;return sec<14400?sec+86400:sec},
 time(seconds){if(!Number.isFinite(seconds))return '—';const s=((Math.round(seconds)%86400)+86400)%86400,h=String(Math.floor(s/3600)).padStart(2,'0'),m=String(Math.floor(s%3600/60)).padStart(2,'0');return `≈ ${h}:${m}:${String(s%60).padStart(2,'0')}`},
 countdown(seconds){if(!Number.isFinite(seconds))return 'Unavailable';if(seconds<-30)return 'Awaiting update';if(seconds<=0)return 'Due · unconfirmed';const s=Math.ceil(seconds);return `≈ ${Math.floor(s/60)}m ${String(s%60).padStart(2,'0')}s`},
 age(row,fallback){let n=Date.parse(row.observed_at||'');return Math.max(0,(Date.now()-(Number.isFinite(n)?n:fallback))/1000)}
};
