import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from arrival_model import refine_arrivals
class Matcher:
    def __init__(self,events): self.events=events
    def station_index(self,line): return {'STA':self.events}
    def _nearest_sched(self,sched,eta): return sched
class ArrivalTests(unittest.TestCase):
    def event(self,key,sec,final='DEST'):return {'key':key,'sched':sec,'final':final}
    def row(self,sec=36007):return {'line':'KTL','station':'STA','dest':'DEST','direction':'UP','platform':'1','eta_sec':sec}
    def refine(self,events,offset=None,rows=None):return refine_arrivals(rows or [self.row()],Matcher(events),offset or {})
    def test_no_delay_keeps_official(self):
        self.assertFalse(self.refine([self.event('a',36020)])[0]['estimated'])
    def test_real_model_time_not_modulo_phase(self):
        r=self.refine([self.event('a',35985)],{'KTL':{'delay_sec':30,'confidence':'high'}})[0]
        self.assertEqual(r['estimated_eta_sec'],36015)
    def test_ambiguous_match_rejected(self):
        r=self.refine([self.event('a',36000),self.event('b',36010)],{'KTL':{'delay_sec':0,'confidence':'high'}})[0]
        self.assertFalse(r['estimated'])
    def test_wrong_destination_rejected(self):
        self.assertFalse(self.refine([self.event('a',36000,'OTHER')],{'KTL':{'delay_sec':0,'confidence':'high'}})[0]['estimated'])
    def test_distant_model_not_folded_to_minute(self):
        self.assertFalse(self.refine([self.event('a',35007)],{'KTL':{'delay_sec':0,'confidence':'high'}})[0]['estimated'])
    def test_does_not_mutate_cache(self):
        r=self.row();self.refine([],rows=[r]);self.assertNotIn('raw_eta_sec',r)
    def test_trip_not_reused(self):
        r=self.refine([self.event('a',36000)],{'KTL':{'delay_sec':0,'confidence':'high'}},[self.row(),self.row(36010)])
        self.assertEqual(sum(x['estimated'] for x in r),1)
if __name__=='__main__':unittest.main()
