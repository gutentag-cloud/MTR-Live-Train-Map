window.LivePosition={
 ageSeconds(stamp,now=Date.now()){if(!stamp)return Infinity;const text=String(stamp).trim().replace(' ','T');const ms=Date.parse(/(?:Z|[+-]\d\d:\d\d)$/.test(text)?text:text+'+08:00');return Number.isFinite(ms)&&ms<=now+5000?Math.max(0,(now-ms)/1000):Infinity},
 fraction(train,age){const before=Number(train.distance_prev_m),after=Number(train.distance_next_m),sum=before+after;if(!(sum>0)||before<0||after<0)return null;const advance=train.vehicle_in_station||train.zero_velocity?0:Math.min(3,Math.max(0,age))*Math.max(0,Math.min(140,Number(train.speed_kph)||0))/3.6;return Math.max(0,Math.min(1,(before+advance)/sum))}
};
