from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zipfile import ZipFile

from rxoptimizer.midi import Event, MidiFile, encode_midi, note_rows, parse_midi, validate_midi
from rxoptimizer.song_dna import (
    apply_song_dna, build_gold_ornament_database, detect_delay_pairs, detect_harmony_pairs,
)


def lead_track(channel=0,velocity=90,shift=0,third=False):
    events=[Event(0,0,"program",channel,73,None,0xC0|channel)]; order=1
    scale=(60,62,64,65,67,69,71,72,71,69,67,65)
    for index,note in enumerate(scale):
        pitch=note+(4 if third and note%12 in (0,5,7) else 3 if third else 0)
        tick=index*240+shift
        events.extend([Event(tick,order,"note_on",channel,pitch,velocity,0x90|channel),
                       Event(tick+180,order+1,"note_off",channel,pitch,0,0x80|channel)])
        order+=2
    return events


class SongDNATest(unittest.TestCase):
    def test_detects_separate_note_delay_track(self):
        midi=MidiFile(1,480,[lead_track(),lead_track(3,45,360)])
        pairs=detect_delay_pairs(midi)
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]["offset_quarters"],.75)
        self.assertAlmostEqual(pairs[0]["velocity_ratio"],.5)

    def test_detects_separate_thirds_track(self):
        midi=MidiFile(1,480,[lead_track(),lead_track(4,70,0,True)])
        pairs=detect_harmony_pairs(midi)
        self.assertTrue(pairs)
        self.assertGreaterEqual(pairs[0]["coverage"],.6)
        models=[{"scope_key":"global","direction":"up","velocity_ratio":.7,"gate_ratio":.9,"coverage":.8}]
        _,report=apply_song_dna(midi,[],models,[],delay_enabled=False,harmony_create=False,ornament_enabled=False)
        self.assertEqual(report["harmony"]["mode"],"optimized_existing")

    def test_rejects_sparse_third_matches_inside_large_unrelated_track(self):
        source=lead_track()
        target=lead_track(4,70,0,True)
        order=1000
        for index in range(300):
            tick=5000+index*20
            target.extend([Event(tick,order,"note_on",4,90+(index%5),60,0x94),
                           Event(tick+10,order+1,"note_off",4,90+(index%5),0,0x84)])
            order+=2
        midi=MidiFile(1,480,[source,target])
        self.assertEqual(detect_harmony_pairs(midi),[])

    def test_creates_delay_but_never_creates_missing_third(self):
        midi=MidiFile(1,480,[lead_track()])
        # A weighted corpus mean may be slightly off-grid; creation must still
        # land on the stable musical subdivision learned from the examples.
        delay=[{"scope_key":"global","offset_quarters":.754166,"velocity_ratio":.5,"gate_ratio":.9,"coverage":1}]
        harmony=[{"scope_key":"global","direction":"up","velocity_ratio":.75,"gate_ratio":1,"coverage":.8}]
        phrase_models=[{"scope_key":"program:73","source_program":73,"sample_count":10,"file_count":2,
            "full_ratio":1.0,"partial_ratio":0.0,"skip_ratio":0.0,"generation_decision":"FULL","generation_allowed":True}]
        result,report=apply_song_dna(midi,delay,harmony,[],ornament_enabled=False,delay_phrase_models=phrase_models)
        self.assertEqual(report["delay"]["mode"],"created")
        self.assertEqual(report["delay"]["offset_quarters"],.75)
        self.assertEqual(report["harmony"]["mode"],"not_detected")
        self.assertFalse(report["harmony"]["creation_allowed"])
        parsed=parse_midi(encode_midi(result))
        self.assertTrue(validate_midi(parsed)["valid"])
        # Only the echo layer was added; no generated third voice exists.
        self.assertEqual(len(note_rows(parsed)),24)

    def test_missing_delay_is_skipped_without_exact_phrase_evidence(self):
        midi=MidiFile(1,480,[lead_track()])
        delay=[{"scope_key":"global","offset_quarters":.75,"velocity_ratio":.5,"gate_ratio":.9,"coverage":1}]
        _,report=apply_song_dna(midi,delay,[],[],harmony_enabled=False,ornament_enabled=False,delay_phrase_models=[])
        self.assertEqual(report["delay"]["mode"],"skipped")
        self.assertEqual(report["delay"]["reason"],"insufficient_phrase_evidence")
        self.assertEqual(len(midi.tracks),1)

    def test_delay_creation_never_reuses_source_channel_when_all_channels_busy(self):
        tracks=[lead_track(channel) for channel in range(16)]
        midi=MidiFile(1,480,tracks)
        delay=[{"scope_key":"global","offset_quarters":.75,"velocity_ratio":.5,"gate_ratio":.9,"coverage":1}]
        phrase_models=[{"scope_key":"program:73","source_program":73,"sample_count":10,"file_count":2,
            "generation_decision":"FULL","generation_allowed":True}]
        _,report=apply_song_dna(midi,delay,[],[],harmony_enabled=False,ornament_enabled=False,
            primary_source=(0,0,73),delay_phrase_models=phrase_models)
        self.assertEqual(report["delay"]["mode"],"skipped")
        self.assertEqual(report["delay"]["reason"],"no_safe_channel")
        self.assertEqual(len(midi.tracks),16)

    def test_existing_third_changes_only_velocity_and_existing_volume_controls(self):
        source=lead_track()
        source.insert(1,Event(0,1,"control",0,7,100,0xB0))
        source.insert(2,Event(0,2,"control",0,11,110,0xB0))
        harmony=lead_track(4,70,0,True)
        harmony.insert(1,Event(0,1,"control",4,7,90,0xB4))
        harmony.insert(2,Event(0,2,"control",4,11,95,0xB4))
        midi=MidiFile(1,480,[source,harmony])
        before=[(row["note"],row["start"],row["duration"]) for row in note_rows(midi) if row["channel"]==4]
        models=[{"scope_key":"global","direction":"up","velocity_ratio":.7,"gate_ratio":.2,"coverage":.8}]
        result,report=apply_song_dna(midi,[],models,[],delay_enabled=False,harmony_create=True,ornament_enabled=False)
        after=[(row["note"],row["start"],row["duration"]) for row in note_rows(result) if row["channel"]==4]
        self.assertEqual(before,after)
        self.assertEqual(report["harmony"]["policy"],"velocity_volume_only")
        self.assertEqual(report["harmony"]["pitch_changed"],0)
        self.assertEqual(report["harmony"]["duration_changed"],0)
        self.assertGreater(report["harmony"]["controls_changed"],0)

    def test_ornament_database_is_explicitly_gold_only(self):
        trill=MidiFile(1,480,[lead_track()])
        nested=BytesIO()
        with ZipFile(nested,"w") as archive:archive.writestr("Gold DNA/Test.mid",encode_midi(trill))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); outer=root/"DNA.zip"
            with ZipFile(outer,"w") as archive:archive.writestr("Gold DNA.zip",nested.getvalue())
            result=build_gold_ornament_database(outer,root/"ornament.sqlite3")
            self.assertEqual(result["source"],"gold_only")
            database=sqlite3.connect(root/"ornament.sqlite3")
            self.assertEqual(database.execute("SELECT value FROM build_info WHERE key='source'").fetchone()[0],"Gold DNA only")
            database.close()


if __name__ == "__main__":
    unittest.main()