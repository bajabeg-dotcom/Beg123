from pathlib import Path
import sqlite3
import tempfile
import unittest
from zipfile import ZipFile

from rxoptimizer.evidence import build_evidence_inventory
from rxoptimizer.evidence_registry import build_evidence_registry
from rxoptimizer.database import connect,seed_pa800_catalog,seed_rx_zones


class EvidenceInventoryTest(unittest.TestCase):
    def test_separates_factory_reference_and_user_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            uploads = root / "prism-uploads"
            uploads.mkdir()
            factory = root / "factory.zip"
            gold = root / "gold.zip"
            with ZipFile(factory, "w") as archive:
                archive.writestr("Factory/A.mid", b"factory")
            with ZipFile(gold, "w") as archive:
                archive.writestr("Gold/B.mid", b"reference")
            with ZipFile(uploads / "DNA.zip", "w") as archive:
                archive.writestr("Split Factory Styles.zip", factory.read_bytes())
                archive.writestr("Gold DNA.zip", gold.read_bytes())
            (uploads / "Oscilatori.txt").write_text("user claim", encoding="utf-8")
            result = build_evidence_inventory(root)
            self.assertEqual(result["summary"]["factory_midi"], 1)
            self.assertEqual(result["summary"]["reference_midi"], 1)
            observation = next(row for row in result["source_records"] if row["classification"] == "user_observation")
            self.assertEqual(observation["evidence_status"], "UNVERIFIED")
            self.assertTrue(result["rules"]["factory_raw_read_only"])

    def test_registry_keeps_unknowns_tasks_and_slap_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);uploads=root/"prism-uploads";uploads.mkdir(parents=True)
            reference=root/"reference"/"pa800";reference.mkdir(parents=True)
            factory_zip=root/"factory.zip";gold_zip=root/"gold.zip"
            with ZipFile(factory_zip,"w") as archive:archive.writestr("Factory/A.mid",b"factory")
            with ZipFile(gold_zip,"w") as archive:archive.writestr("Gold/B.mid",b"reference")
            with ZipFile(uploads/"DNA.zip","w") as archive:
                archive.writestr("Split Factory Styles.zip",factory_zip.read_bytes())
                archive.writestr("Gold DNA.zip",gold_zip.read_bytes())
            (uploads/"Oscilatori.txt").write_text("user observation",encoding="utf-8")
            (reference/"README.md").write_text("official links only",encoding="utf-8")
            inventory=root/"analysis"/"evidence_inventory.json"
            build_evidence_inventory(root,inventory)
            factory_db=root/"factory.sqlite3"
            with connect(factory_db) as database:
                seed_pa800_catalog(database);seed_rx_zones(database)
            registry=root/"evidence_registry.sqlite3"
            result=build_evidence_registry(inventory,factory_db,registry)
            self.assertEqual(result["integrity"],"ok")
            self.assertEqual(result["conflicts"],2)
            database=sqlite3.connect(registry);database.row_factory=sqlite3.Row
            self.assertEqual(database.execute("SELECT COUNT(*) FROM subjects WHERE subject_type='RX_SOUND'").fetchone()[0],21)
            self.assertEqual(database.execute("SELECT COUNT(*) FROM claims WHERE status='UNKNOWN'").fetchone()[0],21)
            self.assertEqual(database.execute("SELECT COUNT(*) FROM verification_tasks WHERE status='OPEN'").fetchone()[0],70)
            slap=database.execute("SELECT status FROM claims WHERE claim_key='zone:SlapFing Bass RX:2:switch_value'").fetchone()
            self.assertEqual(slap["status"],"CONFLICTED")
            database.close()


if __name__ == "__main__":
    unittest.main()