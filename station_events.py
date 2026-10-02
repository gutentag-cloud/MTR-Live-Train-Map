"""Observed station intervals. Feed countdowns never count as measured departures."""
from collections import defaultdict
from tools.train_arrival_model import station, number, day

def occupied(t):
    speed=number(t.get('speed_kph'))
    if t.get('vehicle_in_station') is not True or speed is None or not 0<=speed<3:return None
    a,b=station(t.get('current_station')),station(t.get('next_station'))
    before,after=number(t.get('distance_prev_m')),number(t.get('distance_next_m'))
    if before is None or after is None or min(before,after)<0:return None
    if after<=30<before:return b
    if before<=30 and (after>30 or before==after==0):return a
    return None

def telemetry_intervals(samples):
    groups=defaultdict(list)
    for ts,t in samples:
        if t.get('train_set_id'):groups[t['train_set_id']].append((ts,t))
    result=[]
    for train,rows in groups.items():
        previous=None;previous_t=None;visit=None;departure=None
        for ts,t in sorted(rows,key=lambda x:x[0]):
            if previous is not None and (ts<=previous or ts-previous>30):visit=departure=None;previous_t=None
            at=occupied(t);a=station(t.get('current_station'));b=station(t.get('next_station'))
            speed=number(t.get('speed_kph'))
            if at:
                if visit is None or visit['station']!=at:
                    if departure and departure['to_station']==at and 0<ts-departure['observed_epoch']<=900:
                        result.append({**departure,'arrival_epoch':ts,'seconds':ts-departure['observed_epoch'],
                            'arrival_lower':previous,'run':f'{train}:{ts}','kind':'travel'})
                    departure=None
                    visit={'station':at,'arrival':ts,'arrival_lower':previous,'last':ts,'known_arrival':bool(previous_t and (number(previous_t.get('speed_kph')) or 0)>=3 and station(previous_t.get('next_station'))==at)}
                else:visit['last']=ts
            elif t.get('vehicle_in_station') is False and speed is not None and speed>=3 and a and b and a!=b:
                if visit and visit['station']==a:
                    if visit['known_arrival'] and ts-visit['arrival']<=600:
                        result.append({'kind':'dwell','from_station':a,'to_station':a,'observed_epoch':visit['arrival'],
                            'arrival_epoch':ts,'seconds':ts-visit['arrival'],'run':f'{train}:dwell:{ts}',
                            'departure_lower':visit['last'],'arrival_lower':visit['arrival_lower']})
                    departure={'from_station':a,'to_station':b,'observed_epoch':ts,'departure_lower':visit['last']}
                elif departure and (a,b)!=(departure['from_station'],departure['to_station']):departure=None
                visit=None
            elif not at:
                # Unusable data cannot bridge an event transition.
                if speed is None or not a or not b:visit=departure=None
            previous=ts;previous_t=t
    return result

def countdown_intervals(samples):
    """Track explicit first-train 1→0 transitions only, without assuming a train ID.
    Sequence position is not identity: reset on gaps, backwards changes or ETA jumps.
    """
    active={};out=[]
    for ts,t in sorted(samples,key=lambda x:x[0]):
        if str(t.get('seq'))!='1':continue
        minute=number(t.get('ttnt'));eta=number(t.get('eta_sec'))
        key=tuple(t.get(k) for k in ('line','station','direction','platform','dest'))
        old=active.get(key)
        if minute not in (0,1) or eta is None:
            active.pop(key,None);continue
        if old and (not 0<ts-old['last']<=30 or abs(eta-old['eta'])>45 or minute>old['minute']):old=None
        if old and old['minute']==1 and minute==0:
            out.append({'kind':'countdown_1_to_0','line':key[0],'station':key[1],'direction':key[2],
                'observed_epoch':old['one'],'arrival_epoch':ts,'seconds':ts-old['one'],
                'transition_lower':old['last'],'source':'explicit API countdown; association inferred, not measured arrival'})
        active[key]={'last':ts,'eta':eta,'minute':minute,'one':old['one'] if old else ts}
    return out
