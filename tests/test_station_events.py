import unittest
from station_events import telemetry_intervals,countdown_intervals,occupied
class StationEventTests(unittest.TestCase):
    def point(self,a,b,stopped=False):
        return {'train_set_id':'test','current_station':a,'next_station':b,'vehicle_in_station':stopped,'speed_kph':0 if stopped else 40,'distance_prev_m':0 if stopped else 100,'distance_next_m':0 if stopped else 1000}
    def test_departure_to_next_arrival(self):
        points=[(0,self.point('MKK','HUH',True)),(10,self.point('MKK','HUH')),(30,self.point('MKK','HUH')),(50,self.point('HUH','EXC',True)),(60,self.point('HUH','EXC',True)),(70,self.point('HUH','EXC'))]
        rows=telemetry_intervals(points)
        self.assertEqual([(r['kind'],r['seconds']) for r in rows],[('travel',40),('dwell',20)])
        self.assertEqual(rows[0]['departure_lower'],0)
    def test_gap_cannot_be_travel_label(self):
        rows=telemetry_intervals([(0,self.point('MKK','HUH',True)),(10,self.point('MKK','HUH')),(100,self.point('HUH','EXC',True))])
        self.assertEqual(rows,[])
    def row(self,minute,eta=100):return {'line':'EAL','station':'MKK','direction':'DOWN','platform':'1','dest':'ADM','seq':'1','ttnt':minute,'eta_sec':eta}
    def test_explicit_countdown_transition(self):
        rows=countdown_intervals([(0,self.row('1')),(10,self.row('1')),(20,self.row('0'))])
        self.assertEqual(rows[0]['seconds'],20)
    def test_no_countdown_from_eta_timestamp_or_disappearance(self):
        self.assertEqual(countdown_intervals([(0,self.row(None)),(20,self.row(None))]),[])
        self.assertEqual(countdown_intervals([(0,self.row('0'))]),[])
    def test_new_train_and_gaps_break_countdown(self):
        self.assertEqual(countdown_intervals([(0,self.row('1')),(10,self.row('0',300))]),[])
        self.assertEqual(countdown_intervals([(0,self.row('1')),(50,self.row('0'))]),[])

    def test_invalid_speed_is_not_a_stop(self):
        for speed in (None, -1, float("nan")):
            point=self.point("MKK","HUH",True);point["speed_kph"]=speed
            self.assertIsNone(occupied(point))

    def test_invalid_previous_sample_cannot_establish_arrival(self):
        bad=self.point('MKK','HUH');bad['speed_kph']=None
        rows=telemetry_intervals([(0,bad),(10,self.point('HUH','EXC',True)),(20,self.point('HUH','EXC'))])
        self.assertEqual(rows,[])

    def test_moving_train_in_station_can_precede_observed_stop(self):
        moving=self.point('MKK','HUH');moving['vehicle_in_station']=True
        rows=telemetry_intervals([(0,moving),(10,self.point('HUH','EXC',True)),(20,self.point('HUH','EXC'))])
        self.assertEqual([(r['kind'],r['seconds']) for r in rows],[('dwell',10)])
