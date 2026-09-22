/* Route planning from the bundled station topology. Costs are stops/transfers, not minutes. */
(function(root){
 function plan(paths,from,to,preference='transfers',includeExpress=false){
  const graph=new Map();
  for(const [line,branches] of Object.entries(paths)){
   if(line==='LRL'||(!includeExpress&&line==='AEL'))continue;
   for(const branch of branches)for(let i=1;i<branch.length;i++)for(const [a,b] of [[branch[i-1],branch[i]],[branch[i],branch[i-1]]]){
    if(!graph.has(a))graph.set(a,[]);graph.get(a).push({to:b,line});
   }
  }
  if(!graph.has(from)||!graph.has(to))return null;
  if(from===to)return {legs:[],stops:0,transfers:0};
  const compare=(a,b)=>preference==='stops'?a.stops-b.stops||a.transfers-b.transfers:a.transfers-b.transfers||a.stops-b.stops;
  const queue=[{station:from,line:'',stops:0,transfers:0,edges:[]}],best=new Map();
  while(queue.length){queue.sort(compare);const current=queue.shift(),key=current.station+'|'+current.line;
   if(best.has(key)&&compare(best.get(key),current)<=0)continue;best.set(key,current);
   if(current.station===to){const legs=[];for(const e of current.edges){const last=legs.at(-1);if(last?.line===e.line){last.to=e.to;last.stations.push(e.to)}else legs.push({line:e.line,from:e.from,to:e.to,stations:[e.from,e.to]})}return {legs,stops:current.stops,transfers:current.transfers}}
   for(const e of graph.get(current.station)||[])queue.push({station:e.to,line:e.line,stops:current.stops+1,transfers:current.transfers+(current.line&&current.line!==e.line?1:0),edges:[...current.edges,{...e,from:current.station}]});
  }
  return null;
 }
 root.JourneyPlanner={plan};
})(typeof window==='undefined'?globalThis:window);
