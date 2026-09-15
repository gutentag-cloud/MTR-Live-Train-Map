"""Offline regression: one fresh stop must not refresh another stop's timestamp."""
import datetime as dt
import sys
from pathlib import Path
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve_live

class FreshnessTest(unittest.TestCase):
    def test_stop_observation_times_survive_partial_refresh(self):
        source = serve_live.LightRailSource()
        old = time.time() - 45
        source.station_cache['002'] = {'rows': [{'station_id': '002'}], 'system_time': '', 'ts': old}
        with patch.object(serve_live, 'LRT_STATIONS', ['001', '002']), patch.object(source, '_fetch_station', side_effect=lambda sta: (sta, [{'station_id':sta}], '', None) if sta == '001' else (sta, [], None, 'offline')):
            source.refresh()
        rows = {r['station_id']: r for r in source.get()['arrivals']}
        cached = dt.datetime.fromisoformat(rows['002']['observed_at']).timestamp()
        fresh = dt.datetime.fromisoformat(rows['001']['observed_at']).timestamp()
        self.assertAlmostEqual(cached, old, places=4)
        self.assertGreater(fresh - cached, 40)
        self.assertEqual(source.get()['cached_station_count'], 1)

if __name__ == '__main__':
    unittest.main()
