from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zipfile import ZipFile

from rxoptimizer.articulation_probe import (
    articulation_promotion_queue_status,build_articulation_promotion_queue,build_single_articulation_probes,
    file_articulation_probe_status,record_file_articulation_result,
)
from rxoptimizer.database import connect
from rxoptimizer.midi import Event,MidiFile,encode_midi,note_rows,parse_midi,validate_midi


class SingleArticulationProbeTest(unittest.TestCase):
    def test_factory_observation_creates_exactly_one_special_trigger(self):
        midi=MidiFile(1,480,[[
            Event(0,0,"control",0,0,121,0xB0),Event(0,1,"control",0,32,13,0xB0),Event(0,2,"program",0,33,None,0xC0),
            Event(0,3,"note_on",0,40,70,0x90),Event(240,4,"note_off",0,40,0,0x80),
            Event(480,5,"note_on",0,96,80,0x90),Event(600,6,"note_off",0,96,0,0x80),
            Event(960,7,"note_on",0,41,72,0x90),Event(1200,8,"note_off",0,41,0,0x80)]])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);factory=root/"factory.sqlite3";db=connect(factory)
            db.execute("INSERT INTO pa800_voice_catalog(name,category,bank_msb,bank_lsb,program,is_rx,source) VALUES('Finger Bass RX','bass',121,13,33,1,'test')")
            db.execute("INSERT INTO rx_zones(profile_name,oscillator,articulation,velocity_min,velocity_max,key_min,key_max,switch_value,notes) VALUES('Finger Bass RX',1,'Radni Bass',53,113,0,95,1,'test')")
            db.execute("INSERT INTO rx_zones(profile_name,oscillator,articulation,velocity_min,velocity_max,key_min,key_max,switch_value,notes) VALUES('Finger Bass RX',2,'Noise',1,127,96,127,1,'test')")
            db.commit();db.close()
            nested=BytesIO()
            with ZipFile(nested,"w") as archive:archive.writestr("Style_Var1.mid",encode_midi(midi))
            outer=root/"DNA.zip"
            with ZipFile(outer,"w") as archive:archive.writestr("Split Factory Styles.zip",nested.getvalue())
            output=root/"probes";probe_db=root/"probe.sqlite3"
            report=build_single_articulation_probes(outer,factory,output,probe_db)
            self.assertEqual(report["files_created"],1)
            generated=parse_midi(next(output.glob("*.mid")).read_bytes())
            self.assertTrue(validate_midi(generated)["valid"])
            notes=note_rows(generated)
            self.assertEqual(len(notes),3)
            self.assertEqual(sum(row["note"]>=96 for row in notes),1)
            database=sqlite3.connect(probe_db)
            self.assertEqual(database.execute("SELECT trigger_count FROM articulation_probe_files").fetchone()[0],1)
            self.assertEqual(database.execute("SELECT best_source_class FROM articulation_evidence").fetchone()[0],"factory_raw")
            database.close()
            manifest=output/"single-articulation-manifest.json";results=output/"articulation-results.json"
            self.assertEqual(file_articulation_probe_status(manifest,results)["results"]["pending_hardware"],1)
            with self.assertRaisesRegex(ValueError,"OS"):
                record_file_articulation_result(manifest,results,1,"confirmed","noise","","","resources")
            confirmed=record_file_articulation_result(manifest,results,1,"confirmed","fret noise","heard once","2.01","Factory Resources")
            self.assertEqual(confirmed["promotion_status"],"pending_evidence_review")
            self.assertEqual(file_articulation_probe_status(manifest,results)["results"]["confirmed"],1)
            queue_path=output/"evidence-promotion-queue.json"
            queue=build_articulation_promotion_queue(manifest,results,queue_path)
            self.assertEqual(queue["ready_count"],1)
            self.assertFalse(queue["ready"][0]["automatic_runtime_promotion"])
            self.assertEqual(articulation_promotion_queue_status(queue_path)["status"],"pending_review")


if __name__=="__main__":unittest.main()