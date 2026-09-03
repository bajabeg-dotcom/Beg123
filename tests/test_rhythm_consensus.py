import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from rxoptimizer.midi import Event,MidiFile
from rxoptimizer.rhythm_calibration import SCHEMA as CALIBRATION_SCHEMA,calibrate_repeated_patterns
from rxoptimizer.rhythm_consensus import analyze_against_consensus,build_rhythm_consensus_database,load_factory_consensus
from rxoptimizer.rhythm_context import extract_rhythm_note_context


def pattern(offset):
    events=[];order=0
    for bar in range(3):
        base=bar*1920+offset
        for tick,note in ((0,60),(480,64)):
            events.extend((Event(base+tick,order,"note_on",0,note,80+tick//40,0x90),Event(base+tick+120,order+1,"note_off",0,note,0,0x80)))
            order+=2
    return MidiFile(1,480,[events])


class RhythmConsensusTest(unittest.TestCase):
    def test_cross_file_consensus_and_anomaly_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);calibration=root/"calibration.sqlite3";db=sqlite3.connect(calibration);db.executescript(CALIBRATION_SCHEMA)
            for index,offset in enumerate((0,3,5)):
                observations=extract_rhythm_note_context(pattern(offset),str(index+1)*64);profile=calibrate_repeated_patterns(observations)[0]
                db.execute("""INSERT INTO repeated_pattern_calibration(corpus,source_sha256,filename,track_index,channel,
                  role,section,meter_num,meter_den,topology_sha256,bar_count,event_count,minimum_bars,status,profile_json)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  ("factory",str(index+1)*64,f"style{index}.mid",0,0,"bass","variation",4,4,profile["topology_sha256"],
                   profile["bar_count"],profile["event_count"],3,profile["status"],json.dumps(profile)))
            db.commit();db.close();output=root/"consensus.sqlite3"
            summary=build_rhythm_consensus_database(calibration,output)
            self.assertEqual(summary["FACTORY_CONSENSUS"],1)
            profiles=load_factory_consensus(output);self.assertEqual(profiles[0]["distinct_files"],3)
            check=sqlite3.connect(output)
            self.assertEqual(check.execute("SELECT COUNT(*) FROM negative_rules").fetchone()[0],12)
            check.close()
            distorted=extract_rhythm_note_context(pattern(100),"d"*64)
            result=analyze_against_consensus(distorted,profiles,"bass","variation")
            self.assertTrue(all(not row["repair_allowed"] for row in result))
            self.assertTrue(all("LOCAL_REPEAT_SUPPORTS_ORIGINAL" in row["negative_rules"] for row in result))

    def test_insufficient_files_never_become_consensus(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);calibration=root/"calibration.sqlite3";db=sqlite3.connect(calibration);db.executescript(CALIBRATION_SCHEMA)
            observations=extract_rhythm_note_context(pattern(0),"a"*64);profile=calibrate_repeated_patterns(observations)[0]
            db.execute("""INSERT INTO repeated_pattern_calibration(corpus,source_sha256,filename,track_index,channel,
              role,section,meter_num,meter_den,topology_sha256,bar_count,event_count,minimum_bars,status,profile_json)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",("factory","a"*64,"one.mid",0,0,"bass","variation",4,4,
              profile["topology_sha256"],3,profile["event_count"],3,profile["status"],json.dumps(profile)))
            db.commit();db.close();output=root/"consensus.sqlite3";summary=build_rhythm_consensus_database(calibration,output)
            self.assertEqual(summary["INSUFFICIENT_CROSS_FILE_EVIDENCE"],1)
            self.assertEqual(load_factory_consensus(output),[])


if __name__=="__main__":unittest.main()