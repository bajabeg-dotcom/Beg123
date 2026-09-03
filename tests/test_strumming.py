from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from rxoptimizer.midi import Event, MidiFile, encode_midi, note_rows, parse_midi
from rxoptimizer.optimizer import optimize
from rxoptimizer.strumming import (
    CHORD_VELOCITIES, STRING_COMMANDS, STRUM_COMMANDS, build_strumming_database,
)


def guitar_mode_fixture():
    return MidiFile(1,480,[[
        Event(0,0,"program",12,27,None,0xCC),
        Event(0,1,"note_on",12,24,80,0x9C),Event(60,2,"note_off",12,24,0,0x8C),
        Event(240,3,"note_on",12,24,82,0x9C),Event(300,4,"note_off",12,24,0,0x8C),
        Event(480,5,"note_on",12,26,76,0x9C),Event(540,6,"note_off",12,26,0,0x8C),
        Event(720,7,"note_on",12,42,70,0x9C),Event(780,8,"note_off",12,42,0,0x8C),
        Event(960,9,"note_on",12,0,10,0x9C),Event(1020,10,"note_off",12,0,0,0x8C),
    ]])


class StrummingDNATest(unittest.TestCase):
    def test_official_command_and_chord_maps_are_complete(self):
        self.assertEqual(len(STRUM_COMMANDS),12)
        self.assertEqual(len(STRING_COMMANDS),12)
        self.assertEqual(len(CHORD_VELOCITIES),24)
        self.assertEqual(STRUM_COMMANDS[24],"full_down")
        self.assertEqual(STRING_COMMANDS[42],"mute_all")
        self.assertEqual(CHORD_VELOCITIES[10],"minor_7")

    def test_optimizer_protects_chord_velocity_and_humanizes_commands(self):
        model={"scope_key":"global","alternation_ratio":1.0,
               "velocity_by_16th":{"0":92,"2":84,"4":88,"6":72},"timing_by_16th":{}}
        result,report=optimize(guitar_mode_fixture(),[],[],strength=1,strumming_models=[model],
            strumming_strength=1,strumming_humanize=.5,strumming_variation=True)
        rows=note_rows(result)
        chord=next(row for row in rows if row["note"]==0)
        self.assertEqual(chord["velocity"],10)
        self.assertEqual(report["guitar_chord_type_events_protected"],1)
        self.assertEqual(len(report["guitar_mode_tracks"]),1)
        self.assertGreater(report["strum_velocity_events_changed"],0)
        self.assertTrue(all(row["note"] in set(STRUM_COMMANDS)|set(STRING_COMMANDS)|{0} for row in rows))
        parse_midi(encode_midi(result))

    def test_archive_builder_materializes_factory_strumming(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); nested=BytesIO()
            with ZipFile(nested,"w") as archive:
                archive.writestr("Styles/Demo/Demo_Var1.mid",encode_midi(guitar_mode_fixture()))
            outer=root/"DNA.zip"
            with ZipFile(outer,"w") as archive: archive.writestr("Split Factory Styles.zip",nested.getvalue())
            result=build_strumming_database(outer,root/"strumming.sqlite3")
            self.assertEqual(result["tracks"],1)
            self.assertEqual(result["commands"],24)
            self.assertEqual(result["chord_types"],24)

    def test_strict_gate_preserves_potential_rx_noise_event_exactly(self):
        midi=guitar_mode_fixture()
        midi.tracks[0].extend([Event(1100,20,"note_on",12,96,101,0x9C),Event(1180,21,"note_off",12,96,0,0x8C)])
        before=next(row for row in note_rows(midi) if row["note"]==96)
        rules={"__gate__":{},"__report__":{"mode":"strict","policy_version":"1","fail_closed":False}}
        result,report=optimize(midi,[],[],strength=1,rx_rules=rules,strumming_models=[{"scope_key":"global",
            "alternation_ratio":1.0,"velocity_by_16th":{"1":60},"timing_by_16th":{"1":.02}}],
            strumming_strength=1,strumming_humanize=1)
        after=next(row for row in note_rows(result) if row["note"]==96)
        self.assertEqual((after["start"],after["duration"],after["velocity"]),(before["start"],before["duration"],before["velocity"]))
        self.assertEqual(report["rx_evidence_gate"]["noise_events_protected"],1)


if __name__ == "__main__":
    unittest.main()