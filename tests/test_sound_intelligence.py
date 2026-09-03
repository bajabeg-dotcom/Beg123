import unittest

from rxoptimizer.midi import Event,MidiFile,note_rows
from rxoptimizer.sound_intelligence import (
    analyze_track_assignments,apply_midi_headroom,factory_calibrated_velocity,
    repair_regular_rhythm_guitars,soft_limit_velocity,
)
from rxoptimizer.optimizer import optimize


def bass_midi():
    events=[Event(0,0,"control",0,0,125,0xB0),Event(0,1,"control",0,32,7,0xB0),Event(0,2,"program",0,100,None,0xC0)]
    for index,note in enumerate((36,38,40,41,43,40,38,36)*2):
        tick=index*240;events.extend((Event(tick,10+index*2,"note_on",0,note,110,0x90),Event(tick+180,11+index*2,"note_off",0,note,0,0x80)))
    return MidiFile(1,480,[events])


def intelligence():
    bass={"bank_msb":121,"bank_lsb":13,"program":33,"role":"bass","name":"Finger Bass RX","track_count":20,"note_count":2000,
        "vector":{"pitch_mean":40,"pitch_std":4,"density":2,"duration":.4,"monophony":1,"overlap":0,"step":.7,"repeat":.1,"velocity_mean":100,"velocity_std":12}}
    guitar={"bank_msb":121,"bank_lsb":14,"program":28,"role":"guitar","name":"Clean Guitar RX1","track_count":20,"note_count":2000,
        "vector":{"pitch_mean":61,"pitch_std":7,"density":4,"duration":.5,"monophony":.4,"overlap":.6,"step":.2,"repeat":.1,"velocity_mean":82,"velocity_std":14}}
    return {"sounds":[bass,guitar],"roles":[{"role":"bass","vector":bass["vector"]},{"role":"guitar","vector":guitar["vector"]}],
        "mix":{"bass":{"velocity_mean":100,"velocity_p95":120,"cc7_median":110,"cc11_median":106,"effective_level_p95":104,
                         "factory":{"velocity_mean":100,"velocity_p95":120},"gold":{"velocity_mean":117,"velocity_p95":127}},
               "guitar":{"velocity_mean":82,"velocity_p95":120,"cc7_median":110,"cc11_median":100,"effective_level_p95":104,
                           "factory":{"velocity_mean":82,"velocity_p95":120},"gold":{"velocity_mean":96,"velocity_p95":127}}}}


class SoundIntelligenceTest(unittest.TestCase):
    def test_unknown_user_sound_is_inferred_from_pattern(self):
        assignment=analyze_track_assignments(bass_midi(),intelligence())[(0,0)]
        self.assertTrue(assignment["unknown_user_sound"])
        self.assertEqual(assignment["role"],"bass")
        self.assertEqual(assignment["recommendation"]["name"],"Finger Bass RX")

    def test_optimizer_assigns_recommended_factory_address(self):
        result,report=optimize(bass_midi(),[],[],strength=0,sound_intelligence=intelligence(),
            assign_unknown_sounds=True,mix_headroom=False,guitar_repair=False)
        program=next(event for event in result.tracks[0] if event.kind=="program")
        banks=[event for event in result.tracks[0] if event.kind=="control" and event.data1 in (0,32)]
        self.assertEqual(program.data1,33)
        self.assertTrue(any(event.data1==0 and event.data2==121 for event in banks))
        self.assertEqual(report["factory_sound_assignments"][0]["target"]["name"],"Finger Bass RX")

    def test_optimizer_rejects_cross_instrument_mapping(self):
        bad=[{"source_bank_msb":125,"source_bank_lsb":7,"source_program":100,"role":"bass",
              "rx_name":"Picked Bass RX","target_bank_msb":121,"target_bank_lsb":10,"target_program":34}]
        result,report=optimize(bass_midi(),[],bad,strength=0,sound_intelligence=intelligence(),
            assign_unknown_sounds=False,mix_headroom=False,guitar_repair=False)
        program=next(event for event in result.tracks[0] if event.kind=="program")
        self.assertEqual(program.data1,100)
        self.assertEqual(report["instrument_identity_rejections"][0]["reason"],"cross_instrument_identity")

    def test_headroom_adds_safe_volume_and_expression(self):
        midi=bass_midi();report=apply_midi_headroom(midi,lambda *_:"bass",intelligence()["mix"],1)
        controls={(event.data1,event.data2) for event in midi.tracks[0] if event.kind=="control"}
        self.assertIn((7,110),controls)
        self.assertTrue(any(controller==11 and value<127 for controller,value in controls))
        self.assertGreaterEqual(report["controller_events_added"],1)
        self.assertEqual(soft_limit_velocity(127,"bass",intelligence()["mix"]),122)
        self.assertEqual(factory_calibrated_velocity(127,127,"bass",intelligence()["mix"],1),120)

    def test_regular_rhythm_guitar_repair_preserves_chord_pitches(self):
        events=[Event(0,0,"program",1,25,None,0xC1)];order=1
        for chord in range(10):
            for note in (55,59,62,67):
                tick=chord*480;events.extend((Event(tick,order,"note_on",1,note,85,0x91),Event(tick+420,order+1,"note_off",1,note,0,0x81)));order+=2
        midi=MidiFile(1,480,[events]);before=sorted(row["note"] for row in note_rows(midi))
        report=repair_regular_rhythm_guitars(midi,lambda *_:"guitar",1)
        after=sorted(row["note"] for row in note_rows(midi))
        self.assertEqual(before,after)
        self.assertEqual(report["pitch_notes_changed"],0)
        self.assertEqual(len(report["tracks"]),1)
        starts=sorted({row["start"] for row in note_rows(midi) if row["start"]<480})
        self.assertGreater(len(starts),1)


if __name__=="__main__":unittest.main()