from pathlib import Path
import sqlite3
import tempfile
import unittest

from rxoptimizer.database import analyze_and_store, connect, seed_pa800_catalog, seed_rx_zones
from rxoptimizer.midi import Event, MidiFile, encode_midi, note_rows, parse_midi, validate_midi
from rxoptimizer.optimizer import optimize


def fixture() -> MidiFile:
    return MidiFile(1, 480, [[
        Event(0, 0, "control", 0, 0, 0, 0xB0),
        Event(0, 1, "control", 0, 32, 0, 0xB0),
        Event(0, 2, "program", 0, 33, None, 0xC0),
        Event(0, 3, "note_on", 0, 40, 70, 0x90),
        Event(240, 4, "note_off", 0, 40, 0, 0x80),
        Event(240, 5, "meta", data1=0x2F, raw=b""),
    ]])


class MVPTest(unittest.TestCase):
    def test_midi_round_trip(self):
        parsed = parse_midi(encode_midi(fixture()))
        self.assertEqual(parsed.division, 480)
        self.assertEqual(note_rows(parsed)[0]["duration"], 240)
        self.assertTrue(validate_midi(parsed)["valid"])

    def test_parser_rejects_truncated_track_payload(self):
        encoded=encode_midi(fixture())
        with self.assertRaises(Exception):
            parse_midi(encoded[:-2])

    def test_database_seed_and_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            database = connect(Path(folder) / "test.sqlite3")
            seed_rx_zones(database)
            cursor = database.execute(
                "INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES('x.mid','hash',1,480,1)"
            )
            analyze_and_store(database, cursor.lastrowid, fixture(), "factory")
            self.assertGreater(database.execute("SELECT COUNT(*) FROM rx_zones").fetchone()[0], 0)
            self.assertEqual(database.execute("SELECT COUNT(*) FROM instrument_profiles").fetchone()[0], 1)
            self.assertEqual(database.execute("SELECT COUNT(*) FROM performance_features").fetchone()[0], 1)
            database.close()

    def test_optimizer_maps_program(self):
        mapping = [{
            "source_bank_msb": 0, "source_bank_lsb": 0, "source_program": 33, "role": "melodic",
            "rx_name": "Finger Bass RX", "target_bank_msb": 121, "target_bank_lsb": 13, "target_program": 33,
        }]
        result, report = optimize(fixture(), [], mapping)
        self.assertEqual(report["program_changes_mapped"], 1)
        self.assertEqual([e for e in result.tracks[0] if e.kind == "program"][0].data1, 33)
        parse_midi(encode_midi(result))

    def test_strength_zero_preserves_performance(self):
        before = fixture()
        stats = [{"role": "melodic", "note_count": 10, "velocity_mean": 110,
                  "velocity_std": 4, "duration_mean": 90, "duration_quarters": .1875, "density_per_quarter": 2}]
        result, report = optimize(before, stats, [], strength=0)
        note = note_rows(result)[0]
        self.assertEqual(note["velocity"], 70)
        self.assertEqual(note["duration"], 240)
        self.assertEqual(report["strength"], 0)

    def test_factory_profile_uses_embedded_name_and_role(self):
        midi = MidiFile(1, 192, [[
            Event(0, 0, "meta", data1=3, raw=b"BASS CV1"),
            Event(0, 1, "meta", data1=1, raw=b"Acous. Bass Pro1"),
            Event(0, 2, "control", 8, 0, 121, 0xB8),
            Event(0, 3, "control", 8, 32, 6, 0xB8),
            Event(0, 4, "program", 8, 33, None, 0xC8),
            Event(0, 5, "note_on", 8, 40, 80, 0x98),
            Event(96, 6, "note_off", 8, 40, 0, 0x88),
        ]])
        with tempfile.TemporaryDirectory() as folder:
            database = connect(Path(folder) / "test.sqlite3")
            cursor = database.execute(
                "INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES('bass.mid','bass',1,192,1)"
            )
            analyze_and_store(database, cursor.lastrowid, midi, "factory")
            profile = database.execute("SELECT * FROM instrument_profiles").fetchone()
            self.assertEqual(profile["name"], "Acous. Bass Pro1")
            self.assertEqual(profile["role"], "bass")
            database.close()

    def test_pa800_catalog_seeds_conservative_defaults_with_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            database = connect(Path(folder) / "test.sqlite3")
            seed_pa800_catalog(database)
            self.assertEqual(database.execute("SELECT COUNT(*) FROM pa800_voice_catalog").fetchone()[0], 21)
            rows = database.execute("SELECT * FROM gm_rx_mappings WHERE is_default=1").fetchall()
            self.assertEqual(len(rows), 7)
            finger = next(row for row in rows if row["source_program"] == 33)
            self.assertEqual((finger["target_bank_msb"], finger["target_bank_lsb"], finger["target_program"]), (121,13,33))
            self.assertGreater(finger["confidence"], .9)
            self.assertIn("Pa800", finger["provenance"])
            database.close()

    def test_gm_bass_role_maps_and_stays_in_rx_work_zone(self):
        mapping = [{
            "source_bank_msb":0,"source_bank_lsb":0,"source_program":33,"role":"bass",
            "rx_name":"Finger Bass RX","target_bank_msb":121,"target_bank_lsb":13,"target_program":33,
        }]
        stats = [{"role":"bass","note_count":10,"velocity_mean":127,
                  "velocity_std":1,"duration_mean":240,"duration_quarters":.5,"density_per_quarter":2}]
        result, report = optimize(fixture(), stats, mapping, strength=1)
        self.assertEqual(report["program_changes_mapped"], 1)
        self.assertEqual(note_rows(result)[0]["velocity"], 113)
        self.assertEqual(report["rx_velocity_notes_protected"], 1)

    def test_strict_evidence_gate_preserves_rx_velocity_without_admitted_claim(self):
        mapping=[{"source_bank_msb":0,"source_bank_lsb":0,"source_program":33,"role":"bass",
            "rx_name":"Finger Bass RX","target_bank_msb":121,"target_bank_lsb":13,"target_program":33}]
        stats=[{"role":"bass","note_count":10,"velocity_mean":127,"velocity_std":1,
                "duration_mean":240,"duration_quarters":.5,"density_per_quarter":2}]
        rules={"Finger Bass RX":[{"velocity_min":53,"velocity_max":113,"key_min":0,"key_max":95,
            "switch_value":94,"runtime_transform_allowed":False,"malformed":False}],
            "__gate__":{"Finger Bass RX":{"transform_existing_allowed":False,"conflicted":False}},
            "__report__":{"mode":"strict","policy_version":"1","fail_closed":False}}
        result,report=optimize(fixture(),stats,mapping,strength=1,rx_rules=rules,rx_mapping_mode="catalog_review")
        self.assertEqual(note_rows(result)[0]["velocity"],70)
        self.assertGreater(report["rx_evidence_gate"]["fail_closed_velocity_preserved"],0)

    def test_admitted_evidence_zone_can_clamp_without_crossing(self):
        mapping=[{"source_bank_msb":0,"source_bank_lsb":0,"source_program":33,"role":"bass",
            "rx_name":"Finger Bass RX","target_bank_msb":121,"target_bank_lsb":13,"target_program":33}]
        stats=[{"role":"bass","note_count":10,"velocity_mean":127,"velocity_std":1,
                "duration_mean":240,"duration_quarters":.5,"density_per_quarter":2}]
        rules={"Finger Bass RX":[{"velocity_min":53,"velocity_max":113,"key_min":0,"key_max":95,
            "switch_value":94,"runtime_transform_allowed":True,"malformed":False}],
            "__gate__":{"Finger Bass RX":{"transform_existing_allowed":True,"conflicted":False}},
            "__report__":{"mode":"strict","policy_version":"1","fail_closed":False}}
        result,report=optimize(fixture(),stats,mapping,strength=1,rx_rules=rules,rx_mapping_mode="catalog_review")
        self.assertEqual(note_rows(result)[0]["velocity"],113)
        self.assertGreater(report["rx_evidence_gate"]["evidence_zone_clamps"],0)

    def test_strict_evidence_mode_blocks_unconfirmed_sound_mapping(self):
        mapping=[{"source_bank_msb":0,"source_bank_lsb":0,"source_program":33,"role":"bass",
            "rx_name":"Finger Bass RX","target_bank_msb":121,"target_bank_lsb":13,"target_program":33}]
        rules={"__gate__":{},"__policy__":{"sounds":{}},
            "__report__":{"mode":"strict","policy_version":"1","fail_closed":False}}
        result,report=optimize(fixture(),[],mapping,rx_rules=rules)
        self.assertEqual(report["program_changes_mapped"],0)
        self.assertEqual(report["rx_mapping_mode"],"strict")
        self.assertEqual(len(report["rx_mapping_evidence_rejections"]),1)
        self.assertEqual(report["unverified_mappings_applied"],0)
        self.assertTrue(report["release_eligible"])

    def test_drum_gold_normalization_preserves_hit_intent(self):
        midi = fixture()
        for event in midi.tracks[0]:
            if event.channel is not None: event.channel=9; event.status=(event.status & 0xF0) | 9
        stats = [{"role":"drums","note_count":10,"velocity_mean":127,
                  "velocity_std":1,"duration_mean":240,"duration_quarters":.5,"density_per_quarter":2}]
        result, report = optimize(midi, stats, [], strength=1)
        self.assertEqual(note_rows(result)[0]["velocity"], 82)
        self.assertEqual(report["rx_velocity_notes_protected"], 1)

    def test_gm_clean_guitar_role_uses_rx_mapping(self):
        midi=fixture()
        program=next(event for event in midi.tracks[0] if event.kind=="program")
        program.data1=27
        mapping=[{"source_bank_msb":0,"source_bank_lsb":0,"source_program":27,"role":"guitar",
            "rx_name":"Clean Guitar RX1","target_bank_msb":121,"target_bank_lsb":14,"target_program":28}]
        result,report=optimize(midi,[],mapping)
        self.assertEqual(report["program_changes_mapped"],1)
        self.assertEqual(next(event for event in result.tracks[0] if event.kind=="program").data1,28)

    def test_connect_migrates_legacy_mapping_table(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"legacy.sqlite3"
            legacy=sqlite3.connect(path)
            legacy.execute("""CREATE TABLE gm_rx_mappings(id INTEGER PRIMARY KEY,
                source_bank_msb INTEGER NOT NULL DEFAULT 0,source_bank_lsb INTEGER NOT NULL DEFAULT 0,
                source_program INTEGER NOT NULL,role TEXT NOT NULL,rx_name TEXT NOT NULL,
                target_bank_msb INTEGER NOT NULL,target_bank_lsb INTEGER NOT NULL,target_program INTEGER NOT NULL,
                UNIQUE(source_bank_msb,source_bank_lsb,source_program,role))""")
            legacy.commit(); legacy.close()
            database=connect(path)
            columns={row[1] for row in database.execute("PRAGMA table_info(gm_rx_mappings)")}
            self.assertTrue({"confidence","provenance","is_default"}.issubset(columns))
            database.close()

    def test_duration_target_is_ppq_independent_and_eot_is_last(self):
        stats=[{"role":"melodic","note_count":10,"velocity_mean":70,"velocity_std":1,
                "duration_mean":192,"duration_quarters":.5,"density_per_quarter":2}]
        result,_=optimize(fixture(),stats,[],strength=1)
        self.assertEqual(note_rows(result)[0]["duration"],240)
        parsed=parse_midi(encode_midi(result))
        eot=next(e for e in parsed.tracks[0] if e.kind=="meta" and e.data1==0x2F)
        self.assertGreaterEqual(eot.tick,note_rows(parsed)[0]["off_event"].tick)

    def test_sysex_is_quarantined_by_default(self):
        midi=fixture(); midi.tracks[0].insert(0,Event(0,-1,"sysex",status=0xF0,raw=b"\x42\x30"))
        result,report=optimize(midi,[],[])
        self.assertEqual(report["sysex_quarantined"],1)
        self.assertFalse(any(e.kind=="sysex" for e in result.tracks[0]))

    def test_drums_never_fall_back_to_melodic_mapping(self):
        midi=fixture()
        for event in midi.tracks[0]:
            if event.channel is not None:
                event.channel=9; event.status=(event.status & 0xF0)|9
        melodic=[{"source_bank_msb":0,"source_bank_lsb":0,"source_program":33,"role":"melodic",
                  "rx_name":"Wrong melodic","target_bank_msb":121,"target_bank_lsb":13,"target_program":33}]
        result,report=optimize(midi,[],melodic)
        self.assertEqual(report["program_changes_mapped"],0)
        self.assertEqual(next(e for e in result.tracks[0] if e.kind=="program").data1,33)

    def test_factory_bank_requires_explicit_recommended_source_tuple(self):
        midi=fixture()
        for event in midi.tracks[0]:
            if event.kind=="control" and event.data1==0: event.data2=121
        default={"source_bank_msb":121,"source_bank_lsb":0,"source_program":33,"role":"bass",
                 "rx_name":"Finger Bass RX","target_bank_msb":121,"target_bank_lsb":13,
                 "target_program":33,"is_default":1}
        result,report=optimize(midi,[],[default])
        self.assertEqual(report["program_changes_mapped"],1)

    def test_slap_bass_preserves_velocity_side_of_switch_87(self):
        mapping={"source_bank_msb":0,"source_bank_lsb":0,"source_program":37,"role":"bass",
                 "rx_name":"SlapPick Bass RX","target_bank_msb":121,"target_bank_lsb":5,
                 "target_program":36,"is_default":1}
        stats=[{"role":"bass","note_count":10,"velocity_mean":127,"velocity_std":1,
                "duration_mean":240,"duration_quarters":.5,"density_per_quarter":2}]
        low=fixture()
        next(e for e in low.tracks[0] if e.kind=="program").data1=37
        next(e for e in low.tracks[0] if e.kind=="note_on").data2=72
        low_result,_=optimize(low,stats,[mapping],strength=1)
        self.assertLessEqual(note_rows(low_result)[0]["velocity"],86)
        high=fixture()
        next(e for e in high.tracks[0] if e.kind=="program").data1=37
        next(e for e in high.tracks[0] if e.kind=="note_on").data2=100
        high_result,_=optimize(high,stats,[mapping],strength=1)
        self.assertGreaterEqual(note_rows(high_result)[0]["velocity"],87)

    def test_program_segments_map_independently(self):
        midi=MidiFile(1,480,[[
            Event(0,0,"program",0,33,None,0xC0),Event(0,1,"note_on",0,40,70,0x90),
            Event(200,2,"note_off",0,40,0,0x80),Event(480,3,"program",0,27,None,0xC0),
            Event(480,4,"note_on",0,64,70,0x90),Event(680,5,"note_off",0,64,0,0x80)]])
        mappings=[
            {"source_bank_msb":0,"source_bank_lsb":0,"source_program":33,"role":"bass","rx_name":"Finger Bass RX","target_bank_msb":121,"target_bank_lsb":13,"target_program":33},
            {"source_bank_msb":0,"source_bank_lsb":0,"source_program":27,"role":"guitar","rx_name":"Clean Guitar RX1","target_bank_msb":121,"target_bank_lsb":14,"target_program":28},]
        result,report=optimize(midi,[],mappings)
        self.assertEqual(report["program_changes_mapped"],2)
        self.assertEqual([e.data1 for e in result.tracks[0] if e.kind=="program"],[33,28])

    def test_database_extracts_bank_program_segments_by_note_on_order(self):
        midi=MidiFile(1,480,[[
            Event(0,0,"program",0,33,None,0xC0),
            Event(0,1,"note_on",0,40,70,0x90),Event(240,2,"note_off",0,40,0,0x80),
            Event(480,3,"control",0,0,121,0xB0),Event(480,4,"control",0,32,14,0xB0),
            # This note starts before the Program Change at the same tick.
            Event(480,5,"note_on",0,41,72,0x90),Event(480,6,"program",0,27,None,0xC0),
            Event(480,7,"note_on",0,64,90,0x90),Event(600,8,"note_off",0,41,0,0x80),
            Event(650,9,"note_off",0,64,0,0x80),
            # Bank Select without another PC must not activate a new Sound.
            Event(700,10,"control",0,32,99,0xB0),Event(720,11,"note_on",0,67,92,0x90),
            Event(900,12,"note_off",0,67,0,0x80),Event(960,13,"program",0,27,None,0xC0),
        ]])
        with tempfile.TemporaryDirectory() as folder:
            database=connect(Path(folder)/"segments.sqlite3")
            cursor=database.execute("INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES('multi.mid','multi',1,480,1)")
            analyze_and_store(database,cursor.lastrowid,midi,"factory")
            segments=database.execute("SELECT * FROM instrument_segments ORDER BY segment_index").fetchall()
            self.assertEqual([(row["bank_msb"],row["bank_lsb"],row["program"],row["note_count"]) for row in segments],
                             [(0,0,33,2),(121,14,27,2)])
            self.assertEqual([row["role"] for row in segments],["bass","guitar"])
            legacy=database.execute("SELECT * FROM track_stats").fetchone()
            self.assertEqual(legacy["program"],33)  # equal-count tie keeps earliest segment
            self.assertEqual(sum(row["note_count"] for row in segments),legacy["note_count"])
            database.close()

    def test_duration_is_clamped_before_repeated_note(self):
        midi=MidiFile(1,480,[[
            Event(0,0,"program",0,0,None,0xC0),Event(0,1,"note_on",0,60,70,0x90),
            Event(80,2,"note_off",0,60,0,0x80),Event(100,3,"note_on",0,60,75,0x90),
            Event(180,4,"note_off",0,60,0,0x80)]])
        stats=[{"role":"melodic","note_count":10,"velocity_mean":80,"velocity_std":4,
                "duration_mean":480,"duration_quarters":1.0,"density_per_quarter":2}]
        result,report=optimize(midi,stats,[],strength=1)
        notes=note_rows(result)
        self.assertGreaterEqual(report["overlap_clamps"],1)
        self.assertLess(notes[0]["off_event"].tick,notes[1]["start"])


if __name__ == "__main__":
    unittest.main()