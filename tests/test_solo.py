import unittest

from rxoptimizer.features import extract_features
from rxoptimizer.midi import Event, MidiFile, note_rows
from rxoptimizer.optimizer import optimize
from rxoptimizer.solo import solo_descriptor


def solo_fixture():
    events=[Event(0,0,"program",0,80,None,0xC0)]
    order=1
    for index,note in enumerate((60,62,64,67,65,64,62,60)):
        tick=index*240
        events.extend([Event(tick,order,"note_on",0,note,78+index,0x90),
                       Event(tick+210,order+1,"note_off",0,note,0,0x80)])
        order+=2
    events += [Event(120,order,"control",0,1,45,0xB0),Event(360,order+1,"control",0,11,92,0xB0),
               Event(480,order+2,"pressure",0,70,None,0xD0),
               Event(600,order+3,"pitch",0,0,72,0xE0),Event(840,order+4,"pitch",0,0,56,0xE0)]
    return MidiFile(1,480,[events])


class SoloDNATest(unittest.TestCase):
    def test_extracts_detailed_solo_expression(self):
        feature=extract_features(solo_fixture())[0]
        self.assertEqual(feature.pitch.minimum,60)
        self.assertGreater(feature.monophony_ratio,.9)
        self.assertGreater(feature.step_ratio,0)
        self.assertEqual(feature.pitch_bend.values.count,2)
        self.assertEqual(feature.pressure.values.count,1)

    def test_solo_classifier_uses_expression_and_monophony(self):
        descriptor=solo_descriptor(extract_features(solo_fixture())[0],80)
        self.assertEqual(descriptor["family"],"synth_lead")
        self.assertTrue(descriptor["is_solo_candidate"])
        self.assertGreaterEqual(descriptor["solo_score"],.62)

    def test_optimizer_applies_solo_phrasing_without_changing_notes(self):
        midi=solo_fixture(); before=[row["note"] for row in note_rows(midi)]
        models=[{"family":"synth_lead","tempo_bucket":120,"meter_num":4,"meter_den":4,
                 "profile":{"legato_ratio":.8,"pitch_bend_range":1400}}]
        result,report=optimize(midi,[],[],strength=0,solo_models=models,solo_strength=1,solo_channels=[0])
        self.assertEqual(before,[row["note"] for row in note_rows(result)])
        self.assertEqual(len(report["solo_candidates"]),1)
        self.assertGreater(report["solo_velocity_notes_changed"],0)
        self.assertGreater(report["solo_gate_notes_changed"],0)
        self.assertGreater(report["solo_pitch_bend_events_changed"],0)


if __name__ == "__main__":
    unittest.main()