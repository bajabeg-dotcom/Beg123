from io import BytesIO
from pathlib import Path
import hashlib
import tempfile
import unittest
from zipfile import ZipFile

from rxoptimizer.database import analyze_and_store,connect
from rxoptimizer.midi import encode_midi
from rxoptimizer.rhythm_validation import (
    build_rhythm_validation_database,classify_metrics,note_pair_diagnostics,robust_statistics,rhythm_validation_status,
)
from tests.test_mvp import fixture


class RhythmValidationTest(unittest.TestCase):
    def test_note_pair_diagnostics_records_edges_without_calling_them_errors(self):
        from rxoptimizer.midi import Event,MidiFile
        midi=MidiFile(1,480,[[Event(0,0,"note_off",0,60,0,0x80),Event(960,1,"note_on",0,62,80,0x90)]])
        result=note_pair_diagnostics(midi)
        self.assertEqual((result["unmatched_note_on"],result["unmatched_note_off"]),(1,1))
        self.assertEqual(result["tracks"][0]["boundary_observation"],"EDGE_CONCENTRATED")
        self.assertEqual(result["interpretation"],"OBSERVATION_ONLY_NOT_AUTOMATIC_ERROR")

    def test_robust_classifier_requires_multiple_extreme_metrics_for_outlier(self):
        rows=[{"velocity_mean":70+i%3,"velocity_std":5,"duration_quarters":.5,
               "density_per_quarter":2,"note_count_log":3} for i in range(30)]
        stats=robust_statistics(rows)
        one={**rows[0],"velocity_mean":127}
        classification,_,_=classify_metrics(one,stats,30)
        self.assertEqual(classification,"RARE")
        two={**one,"density_per_quarter":50}
        classification,_,_=classify_metrics(two,stats,30)
        self.assertEqual(classification,"OUTLIER")

    def test_builder_records_archive_duplicates_and_never_repairs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);factory=root/"factory.sqlite3";gold=root/"gold.sqlite3"
            encoded=encode_midi(fixture());digest=hashlib.sha256(encoded).hexdigest()
            for path,corpus in ((factory,"factory"),(gold,"gold")):
                db=connect(path);cursor=db.execute("INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES(?,?,?,?,?)",
                    (corpus+".mid",digest if corpus=="factory" else hashlib.sha256((corpus+"x").encode()).hexdigest(),1,480,1))
                analyze_and_store(db,cursor.lastrowid,fixture(),corpus);db.close()
            archive=root/"DNA.zip"
            def nested(names):
                stream=BytesIO()
                with ZipFile(stream,"w") as zipped:
                    for name in names:zipped.writestr(name,encoded)
                return stream.getvalue()
            with ZipFile(archive,"w") as outer:
                outer.writestr("Split Factory Styles.zip",nested(["factory.mid","copy.mid"]))
                outer.writestr("Gold DNA.zip",nested(["gold.mid"]))
            output=root/"rhythm_validation.sqlite3"
            summary=build_rhythm_validation_database(archive,factory,gold,output)
            self.assertTrue(summary["analyze_only"])
            self.assertEqual(summary["track_total"],2)
            self.assertEqual(summary["eligible_for_validated_dna"],1)
            status=rhythm_validation_status(output)
            self.assertEqual(status["integrity"],"ok")
            db=connect(output)
            ranks=[row[0] for row in db.execute("SELECT duplicate_rank FROM corpus_members WHERE corpus='factory' ORDER BY id")]
            self.assertEqual(ranks,[1,2])
            self.assertEqual(db.execute("SELECT value FROM build_info WHERE key='repair_capability'").fetchone()[0],"NONE_ANALYZE_ONLY")
            self.assertTrue(all(row[0] in ("VALID","MISSING_ARCHIVE_MEMBER") for row in db.execute("SELECT DISTINCT source_validation_status FROM track_quality")))
            db.close()


if __name__=="__main__":unittest.main()