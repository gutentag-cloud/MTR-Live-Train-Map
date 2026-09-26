"""History pruning must return disk space, not just free pages inside the file."""
from contextlib import closing
import sys,tempfile,time,unittest,sqlite3
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import serve_live

class HistoryVacuumTest(unittest.TestCase):
    def test_file_shrinks_after_old_rows_are_pruned(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'TRAINING_DB_PATH':str(Path(root)/'t.sqlite3')}):
            store=serve_live.HistoryStore(Path(root),retention_hours=1)
            with closing(sqlite3.connect(store.path)) as db, db:
                self.assertEqual(db.execute('PRAGMA auto_vacuum').fetchone()[0],2)
                old=time.time()-7200
                db.executemany('INSERT INTO snapshots VALUES(?,?,?)',[(old,'rail','x'*4000) for _ in range(2000)])
            grown=store.path.stat().st_size
            store._last_vacuum=0
            store.record('rail',{'trains':[]},min_interval=0)
            self.assertEqual(store.status()['rows'],1)
            self.assertLess(store.path.stat().st_size,grown/4)

    def test_existing_file_without_auto_vacuum_is_converted(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ',{'TRAINING_DB_PATH':str(Path(root)/'t.sqlite3')}):
            path=Path(root)/'runtime'/'history.sqlite3';path.parent.mkdir()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE snapshots (ts REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)')
                db.execute("INSERT INTO snapshots VALUES(1,'rail','{}')")
            serve_live.HistoryStore(Path(root))
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute('PRAGMA auto_vacuum').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0],1)

if __name__=='__main__':unittest.main()
