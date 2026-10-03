from contextlib import closing
import json,sqlite3,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from training_store import TrainingStore
from tools.train_arrival_model import build_rows,train,split_rows,fit,evaluate,historical_backtests

class TrainingTests(unittest.TestCase):
    def test_archive_dedup_and_whitelist(self):
        with tempfile.TemporaryDirectory() as root,patch.dict('os.environ',{},clear=True):
            archive=TrainingStore(root)
            payload={'trains':[{'train_set_id':'T1','updated_at':'2026-09-22 12:00:00','secret':'never'}]}
            archive.record('eal',payload);archive.record('eal',payload)
            self.assertEqual(archive.status()['sources'][0]['rows'],1)
            with closing(sqlite3.connect(archive.path)) as db, db:
                raw=db.execute('select payload from samples').fetchone()[0]
                self.assertNotIn('secret',json.loads(raw))
    def test_labels_require_continuity_and_correct_station(self):
        move={'train_set_id':'T1','current_station':'MKK','next_station':'HUH','distance_prev_m':100,'distance_next_m':1000,'speed_kph':60}
        stop={**move,'current_station':'HUH','vehicle_in_station':True,'speed_kph':0,'distance_prev_m':0,'distance_next_m':0}
        rows=build_rows([(100,move),(120,stop)])
        self.assertEqual(rows[0]['target_remaining_s'],20)
        self.assertEqual(build_rows([(100,move),(131,stop)]),[])
        self.assertEqual(build_rows([(100,move),(120,{**stop,'current_station':'ADM'})]),[])
    def test_empty_training_never_deploys(self):
        report=train([])['report']
        self.assertFalse(report['eligible_for_review']);self.assertFalse(report['deployed'])
        self.assertIsNone(report['test_mae_seconds'])

    def test_arriving_pair_can_still_name_previous_station(self):
        move={'train_set_id':'T1','current_station':'MKK','next_station':'NHUH','distance_prev_m':2000,'distance_next_m':100,'speed_kph':30}
        stop={**move,'vehicle_in_station':True,'speed_kph':0,'distance_prev_m':2100,'distance_next_m':0}
        rows=build_rows([(100,move),(110,stop)])
        self.assertEqual(rows[0]['to_station'],'HUH')
        self.assertEqual(rows[0]['target_remaining_s'],10)

    def test_unobserved_stop_or_reversal_breaks_labels(self):
        move={'train_set_id':'T1','current_station':'MKK','next_station':'HUH','distance_prev_m':100,'distance_next_m':1000,'speed_kph':50}
        other={**move,'current_station':'HUH','next_station':'EXC'}
        stop={**move,'current_station':'HUH','vehicle_in_station':True,'speed_kph':0,'distance_prev_m':0,'distance_next_m':0}
        self.assertEqual(build_rows([(100,move),(110,other),(120,stop)]),[])

    def test_day_split_keeps_test_out_and_purges_crossing_group(self):
        def row(day,run,start=None):
            import datetime as dt
            ts=dt.datetime.fromisoformat(f'2026-09-{day:02d}T00:00:10+08:00').timestamp()
            return {'run':run,'arrival_epoch':ts,'observed_epoch':ts-5 if start is None else ts-start}
        rows=[row(21,'train'),row(22,'validate'),row(23,'test'),row(23,'cross',20),row(23,'cross',2)]
        parts=split_rows(rows)
        self.assertEqual([[r['run'] for r in part] for part in parts],[['train'],['validate'],['test']])

    def test_repeated_frames_do_not_count_as_independent_journeys(self):
        r={'run':'one','from_station':'MKK','to_station':'HUH','fraction':.5,'target_remaining_s':20}
        self.assertEqual(fit([r]*100,'progress'),{})
        cells=fit([{**r,'run':str(i)} for i in range(5)],'progress')
        self.assertEqual(cells['MKK|HUH|5']['journeys'],5)

    def test_unsupported_rows_are_included_in_evaluation(self):
        r={'run':'one','from_station':'MKK','to_station':'HUH','fraction':.5,'remaining_m':100,'speed_kph':36,'target_remaining_s':20}
        result=evaluate([r],{},'progress',{})
        self.assertEqual(result['rows'],1)
        self.assertEqual(result['coverage'],0)
        self.assertEqual(result['mae_seconds'],10)

    def test_explicit_countdown_survives_archive(self):
        with tempfile.TemporaryDirectory() as root,patch.dict('os.environ',{},clear=True):
            archive=TrainingStore(root)
            archive.record('eta',{'observations':[{'line':'EAL','station':'MKK','direction':'DOWN','seq':'1','ttnt':'0','upstream_time':'2026-10-02 12:00:00','observed_at':'2026-10-02T04:00:01+00:00','secret':'never'}]})
            with closing(sqlite3.connect(archive.path)) as db:
                record=json.loads(db.execute('select payload from samples').fetchone()[0])
            self.assertEqual(record['ttnt'],'0')
            self.assertEqual(record['upstream_time'],'2026-10-02 12:00:00')
            self.assertNotIn('secret',record)

    def test_one_second_metric_uses_actual_error(self):
        row={'run':'one','from_station':'MKK','to_station':'HUH','fraction':.5,'remaining_m':100,'speed_kph':36,'target_remaining_s':10}
        result=evaluate([row,{**row,'run':'two','target_remaining_s':20}],{},'progress',{})
        self.assertEqual(result['within_one_second_fraction'],.5)
        self.assertEqual(result['within_five_seconds_fraction'],.5)

    def test_backtests_never_train_on_future_dates(self):
        import datetime as dt
        rows=[]
        for d in range(21,25):
            ts=dt.datetime.fromisoformat(f'2026-09-{d:02d}T12:00:00+08:00').timestamp()
            for i in range(5):rows.append({'run':f'{d}:{i}','arrival_epoch':ts,'observed_epoch':ts-20,'from_station':'MKK','to_station':'HUH','fraction':.5,'speed_kph':36,'remaining_m':100,'target_remaining_s':20})
        original=historical_backtests(rows)
        self.assertEqual(original['folds'][0]['training_dates'],['2026-09-21'])
        self.assertEqual(original['folds'][0]['validation_dates'],['2026-09-22'])
        for r in rows[-5:]:r['target_remaining_s']=800
        changed=historical_backtests(rows)
        self.assertEqual(original['folds'][0],changed['folds'][0])
        self.assertNotEqual(original['folds'][-1]['mae_seconds'],changed['folds'][-1]['mae_seconds'])

    def test_ongoing_date_is_excluded(self):
        import datetime as dt
        ts=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).timestamp()
        result=train([{'arrival_epoch':ts,'observed_epoch':ts-10,'run':'today'}])['report']
        self.assertEqual(result['excluded_in_progress_rows'],1)
        self.assertEqual(result['labeled_rows'],0)
