from pathlib import Path
import sqlite3
import tempfile
import unittest

from rxoptimizer.database import connect
from rxoptimizer.midi import Event, MidiFile, encode_midi, note_rows, parse_midi, validate_midi
from rxoptimizer.rx_noise_probe import generate_probe_pack, probe_status, record_probe_result


class RXNoiseProbeTest(unittest.TestCase):
    def test_generates_isolated_hardware_probe_and_records_confirmation(self):
        source=MidiFile(1,480,[[
            Event(0,0,"program",0,0,None,0xC0),Event(0,1,"note_on",0,60,80,0x90),
            Event(240,2,"note_off",0,60,0,0x80)]])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);factory=root/"factory.sqlite3";database=connect(factory)
            database.execute("INSERT INTO pa800_voice_catalog(name,category,bank_msb,bank_lsb,program,is_rx,source) VALUES('Probe RX','guitar',121,14,28,1,'test')")
            database.execute("INSERT INTO rx_zones(profile_name,oscillator,articulation,velocity_min,velocity_max,key_min,key_max,switch_value,notes) VALUES('Probe RX',1,'RX Noise',1,127,96,127,1,'test')")
            database.commit();database.close()
            output=root/"probes";probe_db=root/"probe.sqlite3"
            report=generate_probe_pack([("song.mid",encode_midi(source))],factory,output,probe_db)
            self.assertEqual(report["files_created"],1)
            self.assertEqual(report["steps_per_file"],128)
            generated=next(output.glob("*.mid"));midi=parse_midi(generated.read_bytes())
            self.assertTrue(generated.name.endswith(".mid"))
            self.assertTrue(validate_midi(midi)["valid"])
            self.assertEqual(len(note_rows(midi)),129)
            db=sqlite3.connect(probe_db)
            file_id=db.execute("SELECT id FROM probe_files").fetchone()[0]
            self.assertEqual(db.execute("SELECT COUNT(*) FROM probe_steps").fetchone()[0],128)
            db.close()
            row=record_probe_result(probe_db,file_id,"partial",confirmed_notes=[{"note":96,"velocity":42}],
                rejected_notes=[{"note":97,"velocity":84}],comments="Pa800 test")
            self.assertEqual(row["result_status"],"partial")
            self.assertEqual(probe_status(probe_db)["results"]["partial"],1)
            repeated=generate_probe_pack([("song.mid",encode_midi(source))],factory,output,probe_db)
            self.assertEqual(repeated["files_created"],0)
            self.assertEqual(repeated["files_reused"],1)
            self.assertTrue((output/"RX_NOISE_TEST_GUIDE.md").is_file())
            self.assertTrue((output/"RX_NOISE_CONFIRMATION.csv").is_file())

    def test_probe_may_inherit_but_not_worsen_source_note_off_error(self):
        source=MidiFile(1,480,[[Event(0,0,"note_off",0,60,0,0x80)]])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);factory=root/"factory.sqlite3";database=connect(factory)
            database.execute("INSERT INTO pa800_voice_catalog(name,category,bank_msb,bank_lsb,program,is_rx,source) VALUES('Probe RX','guitar',121,14,28,1,'test')")
            database.execute("INSERT INTO rx_zones(profile_name,oscillator,articulation,velocity_min,velocity_max,key_min,key_max,switch_value,notes) VALUES('Probe RX',1,'RX Noise',1,127,96,127,1,'test')")
            database.commit();database.close()
            report=generate_probe_pack([("imperfect.mid",encode_midi(source))],factory,root/"probes",root/"probe.sqlite3")
            self.assertEqual(report["files_created"],1)


if __name__ == "__main__":
    unittest.main()