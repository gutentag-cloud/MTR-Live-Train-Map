import datetime as dt
import unittest
from unittest.mock import patch
from serve_live import TimetableMatcher,HeavyRailSource

class MatchingTests(unittest.TestCase):
    def matcher(self, index):
        m=object.__new__(TimetableMatcher)
        m.station_index=lambda line:index
        return m
    def event(self,key,when,dest='ADM'):
        return {'key':key,'sched':when,'final':dest,'remaining':{'ADM'}}
    def observation(self,station='MKK',when=1000):
        return {'line':'EAL','station':station,'direction':'DOWN','dest':'ADM','eta_sec':when,'eta':'2026-09-23 12:00:00'}
    def test_ambiguous_trip_not_corrected(self):
        m=self.matcher({'MKK':[self.event('EAL|a',990),self.event('EAL|b',1010)]})
        self.assertEqual(m.match([self.observation()]),{})
    def test_single_anchor_not_medium_confidence(self):
        m=self.matcher({'MKK':[self.event('EAL|a',990)]})
        self.assertEqual(m.match([self.observation()])['EAL|a']['confidence'],'low')
    def test_independent_stations_required(self):
        m=self.matcher({s:[self.event('EAL|a',990)] for s in ('MKK','HUH')})
        result=m.match([self.observation(s) for s in ('MKK','HUH')])
        self.assertEqual(result['EAL|a']['confidence'],'medium')
    def test_periodic_headways_do_not_identify_line_delay(self):
        events=[self.event('EAL|'+str(i),i*120) for i in range(20)]
        m=self.matcher({'MKK':events})
        obs=[self.observation(when=600+i*120) for i in range(6)]
        self.assertEqual(m.estimate_line_offsets(obs)['EAL']['confidence'],'low')
    def test_old_upstream_cannot_be_refreshed_by_fetch(self):
        source=HeavyRailSource(self.matcher({}))
        now=dt.datetime(2026,9,23,12,tzinfo=dt.timezone(dt.timedelta(hours=8)))
        payload={'status':1,'sys_time':'2026-09-23 11:55:00','data':{'EAL-MKK':{}}}
        with patch('serve_live.get_json',return_value=payload),patch('serve_live.hk_now',return_value=now):
            result=source._fetch_station('EAL','MKK')
        self.assertEqual(result[2],[])
        self.assertIn('stale',result[4])
