from pathlib import Path
import tempfile
import unittest

from rxoptimizer.database import analyze_and_store,connect,seed_pa800_catalog,seed_rx_zones
from rxoptimizer.database_layout import RAW_TABLES,connect_raw,migrate_split_layout,semantic_digest
from tests.test_mvp import fixture


class DatabaseLayoutTest(unittest.TestCase):
    def test_split_layout_preserves_raw_semantics_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);factory=root/"factory.sqlite3";gold=root/"gold.sqlite3"
            for path,source in ((factory,"factory"),(gold,"gold")):
                db=connect(path)
                if source=="factory":seed_rx_zones(db);seed_pa800_catalog(db)
                cursor=db.execute("INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES(?,?,?,?,?)",
                    (source+".mid",source,1,480,1));analyze_and_store(db,cursor.lastrowid,fixture(),source);db.close()
            expected=(semantic_digest(factory),semantic_digest(gold))
            layout=migrate_split_layout(factory,gold,root/"data")
            factory_raw=root/layout["factory_raw"];gold_raw=root/layout["gold_raw"]
            self.assertEqual((semantic_digest(factory_raw),semantic_digest(gold_raw)),expected)
            db=connect_raw(factory_raw)
            with self.assertRaises(Exception):db.execute("UPDATE midi_files SET filename='mutated'")
            db.close()
            self.assertTrue((root/"data"/"database-layout.json").exists())
            self.assertEqual(layout["counts"]["factory"]["midi_files"],1)


if __name__=="__main__":unittest.main()