import unittest
from io import BytesIO
from pathlib import Path
import hashlib
import tempfile
from zipfile import ZipFile

from rxoptimizer.database import analyze_and_store,connect
from rxoptimizer.midi import Event,MidiFile
from rxoptimizer.midi import encode_midi
from rxoptimizer.rhythm_calibration import (
    build_rhythm_calibration_database,calibrate_repeated_patterns,evaluate_bar_against_profile,rhythm_calibration_status,
)
from rxoptimizer.rhythm_context import extract_rhythm_note_context
from rxoptimizer.rhythm_validation import build_rhythm_validation_database


def repeated_bars(offsets=(0,4,3)):
    events=[];order=0
    for bar,offset in enumerate(offsets):
        base=bar*1920
        for tick,note,velocity in ((0,60,80),(480,64,92)):
            start=base+tick+offset
            events.extend((Event(start,order,"note_on",0,note,velocity,0x90),Event(start+120,order+1,"note_off",0,note,0,0x80)))
            order+=2
    return MidiFile(1,480,[events])


class RhythmCalibrationTest(unittest.TestCase):
    def test_calibration_uses_repeated_pattern_phases_without_grid_target(self):
        observations=extract_rhythm_note_context(repeated_bars(),"d"*64)
        profiles=calibrate_repeated_patterns(observations)
        self.assertEqual(len(profiles),1)
        profile=profiles[0]
        self.assertEqual(profile["bar_count"],3)
        self.assertEqual(profile["repair_capability"],"NONE_ANALYZE_ONLY")
        self.assertEqual(profile["status"],"ROBUST_VARIATION_PROFILE")
        self.assertEqual(profile["alignment"],"ONSET_CLUSTER")
        first_bar=[row for row in observations if row["bar"]==0]
        result=evaluate_bar_against_profile(first_bar,profile)
        self.assertEqual(result["status"],"OBSERVED")
        self.assertFalse(result["repair_allowed"])

    def test_different_relative_ioi_is_not_same_topology(self):
        first=extract_rhythm_note_context(repeated_bars((0,0,0)),"f"*64)
        changed_midi=repeated_bars((0,0,0))
        for event in changed_midi.tracks[0]:
            if event.data1==64:event.tick+=120
        changed=extract_rhythm_note_context(changed_midi,"g"*64)
        self.assertNotEqual(
            calibrate_repeated_patterns(first)[0]["topology_sha256"],
            calibrate_repeated_patterns(changed)[0]["topology_sha256"],
        )

    def test_insufficient_repetition_produces_no_profile(self):
        observations=extract_rhythm_note_context(repeated_bars((0,4)),"e"*64)
        self.assertEqual(calibrate_repeated_patterns(observations),[])

    def test_database_builder_is_analyze_only_and_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);factory=root/"factory.sqlite3";gold=root/"gold.sqlite3";midi=repeated_bars()
            encoded=encode_midi(midi);digest=hashlib.sha256(encoded).hexdigest()
            for path,corpus in ((factory,"factory"),(gold,"gold")):
                db=connect(path);source_digest=digest if corpus=="factory" else hashlib.sha256((corpus+"x").encode()).hexdigest()
                cursor=db.execute("INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES(?,?,?,?,?)",
                    (corpus+".mid",source_digest,1,480,1));analyze_and_store(db,cursor.lastrowid,midi,corpus);db.close()
            archive=root/"DNA.zip"
            def nested(name):
                stream=BytesIO()
                with ZipFile(stream,"w") as zipped:zipped.writestr(name,encoded)
                return stream.getvalue()
            with ZipFile(archive,"w") as outer:
                outer.writestr("Split Factory Styles.zip",nested("factory.mid"));outer.writestr("Gold DNA.zip",nested("gold.mid"))
            validation=root/"validation.sqlite3";build_rhythm_validation_database(archive,factory,gold,validation)
            output=root/"calibration.sqlite3";summary=build_rhythm_calibration_database(archive,validation,output)
            self.assertFalse(summary["repair_capability"])
            self.assertEqual(summary["calibration_profiles"],1)
            self.assertEqual(summary["robust_variation_profile"],1)
            self.assertEqual(rhythm_calibration_status(output)["integrity"],"ok")


if __name__=="__main__":unittest.main()