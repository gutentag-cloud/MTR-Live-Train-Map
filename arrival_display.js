/* Shared presentation: time formatting must not imply accuracy the source lacks. */
window.ArrivalDisplay={
 now(){let sec=(Math.floor(Date.now()/1000)+8*3600)%86400;return sec<14400?sec+86400:sec},
 time(seconds,refined=false){const s=((Math.round(seconds)%86400)+86400)%86400,h=String(Math.floor(s/3600)).padStart(2,'0'),m=String(Math.floor(s%3600/60)).padStart(2,'0');return refined?`≈ ${h}:${m}:${String(s%60).padStart(2,'0')}`:`≈ ${h}:${m}`},
 countdown(seconds,refined=false){if(seconds<-30)return 'Awaiting update';if(seconds<=30)return 'Due soon';if(refined)return `≈ ${Math.floor(seconds/60)}m ${String(Math.floor(seconds%60)).padStart(2,'0')}s`;return `~${Math.max(1,Math.round(seconds/60))} min`},
 age(row,fallback){let n=Date.parse(row.observed_at||'');return Math.max(0,(Date.now()-(Number.isFinite(n)?n:fallback))/1000)}
};
