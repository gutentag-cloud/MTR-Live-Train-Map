import json,sqlite3,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from training_store import TrainingStore
from tools.train_arrival_model import build_rows,train

class TrainingTests(unittest.TestCase):
    def test_archive_dedup_and_whitelist(self):
        with tempfile.TemporaryDirectory() as root,patch.dict('os.environ',{},clear=True):
            archive=TrainingStore(root)
            payload={'trains':[{'train_set_id':'T1','updated_at':'2026-09-22 12:00:00','secret':'never'}]}
            archive.record('eal',payload);archive.record('eal',payload)
            self.assertEqual(archive.status()['sources'][0]['rows'],1)
            with sqlite3.connect(archive.path) as db:
                raw=db.execute('select payload from samples').fetchone()[0]
                self.assertNotIn('secret',json.loads(raw))
    def test_labels_require_continuity_and_correct_station(self):
        move={'train_set_id':'T1','current_station':'MKK','next_station':'HUH','distance_prev_m':100,'distance_next_m':1000,'speed_kph':60}
        stop={**move,'current_station':'HUH','vehicle_in_station':True,'speed_kph':0}
        rows=build_rows([(100,move),(120,stop)])
        self.assertEqual(rows[0]['target_remaining_s'],20)
        self.assertEqual(build_rows([(100,move),(131,stop)]),[])
        self.assertEqual(build_rows([(100,move),(120,{**stop,'current_station':'ADM'})]),[])
    def test_empty_training_never_deploys(self):
        report=train([])['report']
        self.assertFalse(report['eligible_for_review']);self.assertFalse(report['deployed'])
        self.assertIsNone(report['test_mae_seconds'])
