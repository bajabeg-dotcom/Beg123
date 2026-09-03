from pathlib import Path
import hashlib
import tempfile
import unittest

from rxoptimizer.database import analyze_and_store, connect, seed_pa800_catalog, seed_rx_zones
from rxoptimizer.dna_databases import build_all, dna_status
from rxoptimizer.midi import Event, MidiFile


def small_midi(program=33):
    return MidiFile(1,480,[[
        Event(0,0,"meta",data1=3,raw=b"BASS CV1"),
        Event(0,1,"meta",data1=1,raw=b"Finger Bass RX"),
        Event(0,2,"program",8,program,None,0xC8),
        Event(0,3,"note_on",8,40,80,0x98),Event(240,4,"note_off",8,40,0,0x88),
    ]])


class DNADatabaseTest(unittest.TestCase):
    def test_builds_all_derived_databases_idempotently(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); factory=root/"factory.sqlite3"; gold=root/"gold.sqlite3"
            for path,source in ((factory,"factory"),(gold,"gold")):
                database=connect(path)
                if source=="factory": seed_rx_zones(database); seed_pa800_catalog(database)
                cursor=database.execute("INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES(?,?,?,?,?)",
                    ("Demo_Var1.mid",hashlib.sha256(source.encode()).hexdigest(),1,480,1))
                analyze_and_store(database,cursor.lastrowid,small_midi(),source); database.close()
            first=build_all(factory,gold,root); second=build_all(factory,gold,root)
            self.assertEqual(first["rhythm"]["tracks"],1)
            self.assertEqual(second["performance"]["tracks"],1)
            status=dna_status(root)
            self.assertEqual(len(status),20)
            external={"hardware_test_dna.sqlite3","rx_noise_probe.sqlite3","articulation_probe.sqlite3","rhythm_validation.sqlite3","rhythm_calibration.sqlite3","rhythm_consensus.sqlite3","strumming_dna.sqlite3","delay_dna.sqlite3","harmony_dna.sqlite3","ornament_dna.sqlite3","sound_intelligence_dna.sqlite3","evidence_registry.sqlite3","musical_intelligence_dna.sqlite3"}
            built={name:item for name,item in status.items() if name not in external}
            self.assertTrue(all(item["exists"] and item["integrity"]=="ok" for item in built.values()))
            self.assertFalse(status["hardware_test_dna.sqlite3"]["exists"])
            self.assertFalse(status["strumming_dna.sqlite3"]["exists"])

    def test_build_all_refuses_empty_corpus(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);factory=root/"factory.sqlite3";gold=root/"gold.sqlite3"
            connect(factory).close();connect(gold).close()
            with self.assertRaisesRegex(ValueError,"Factory corpus je prazan"):
                build_all(factory,gold,root)


if __name__=="__main__": unittest.main()