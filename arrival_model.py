"""Conservative timetable/live-delay fusion; no synthetic second-phase substitution."""
def refine_arrivals(rows, matcher, offsets):
    result=[]
    used=set()
    previous={}
    for original in sorted(rows, key=lambda r:r.get('eta_sec', float('inf'))):
        row=dict(original)
        for field in ('estimated_eta_sec','scheduled_sec','estimate_delay_sec','estimate_source','estimate_confidence','matched_trip_key'):
            row.pop(field, None)
        row['estimated']=False
        raw=row.get('eta_sec')
        row['raw_eta_sec']=raw
        row['estimate_source']='Official MTR estimate; second-level accuracy is not established'
        if raw is None:
            result.append(row); continue
        info=offsets.get(row.get('line')) or {}
        delay=info.get('delay_sec')
        candidates=[]
        if delay is not None and info.get('confidence') in ('medium','high'):
            for event in matcher.station_index(row['line']).get(row.get('station'),[]):
                if not row.get('dest') or event['final']!=row['dest'] or event['key'] in used:
                    continue
                scheduled=matcher._nearest_sched(event['sched'],raw)
                predicted=scheduled+delay
                error=abs(predicted-raw)
                if error<=30:
                    candidates.append((error,event,scheduled,predicted))
        candidates.sort(key=lambda c:c[0])
        # Ambiguous trip matches cannot justify selecting a particular second.
        if candidates and (len(candidates)==1 or candidates[1][0]-candidates[0][0]>=15):
            _,event,scheduled,predicted=candidates[0]
            group=(row.get('line'),row.get('direction'),row.get('platform'))
            if predicted>=previous.get(group,float('-inf')):
                row.update(estimated=True,estimated_eta_sec=round(predicted),scheduled_sec=scheduled,
                           estimate_delay_sec=delay,matched_trip_key=event['key'],
                           estimate_confidence='model estimate',
                           estimate_source='Matched timetable + live line delay; within 30 seconds of official ETA')
                used.add(event['key'])
        previous[(row.get('line'),row.get('direction'),row.get('platform'))]=row.get('estimated_eta_sec',raw)
        result.append(row)
    return result
