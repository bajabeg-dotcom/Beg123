import unittest

from rxoptimizer.midi import Event,MidiFile,note_rows
from rxoptimizer.trill_dna import detect_trills


def notes(pitches,spacing=60,duration=45,channel=0,velocities=None):
    events=[]
    for index,pitch in enumerate(pitches):
        velocity=(velocities or [90]*len(pitches))[index]
        tick=index*spacing
        events.extend([Event(tick,index*2,"note_on",channel,pitch,velocity,0x90|channel),
                       Event(tick+duration,index*2+1,"note_off",channel,pitch,0,0x80|channel)])
    return MidiFile(1,480,[events])


class TrillDNATest(unittest.TestCase):
    def test_extracts_segmented_upper_whole_step_trill(self):
        midi=notes([60,62,60,62,60,62,64],velocities=[100,78,98,76,96,74,90])
        rows=note_rows(midi)
        result=detect_trills(rows,midi.division,midi.tracks[0],rows,0,0,"melodic")
        self.assertEqual(len(result),1)
        trill=result[0]
        self.assertEqual((trill["main_note"],trill["neighbor_note"]),(60,62))
        self.assertEqual(trill["repetition_count"],6)
        self.assertEqual(trill["next_note"],64)
        self.assertEqual(trill["interval_class"],"whole_step")
        self.assertEqual(trill["velocity_pattern"],"alternating_accent")
        self.assertTrue(trill["accepted"])

    def test_two_three_and_four_notes_are_not_accepted(self):
        for pitches in ([60,62],[60,62,60],[60,62,60,62]):
            midi=notes(pitches);rows=note_rows(midi)
            result=detect_trills(rows,midi.division,midi.tracks[0],rows)
            self.assertFalse(any(item["accepted"] for item in result))

    def test_rejects_tremolo_scale_arpeggio_drums_and_chord_cluster(self):
        fixtures=(
            (notes([60,60,60,60,60]),"melodic"),
            (notes([60,62,64,65,67]),"melodic"),
            (notes([60,64,67,60,64,67]),"melodic"),
            (notes([36,38,36,38,36,38],channel=9),"drums"),
        )
        for midi,role in fixtures:
            rows=note_rows(midi)
            result=[] if role=="drums" else detect_trills(rows,midi.division,midi.tracks[0],rows,0,0,role)
            self.assertFalse(any(item["accepted"] for item in result))
        chord=MidiFile(1,480,[[
            Event(0,0,"note_on",0,60,90,0x90),Event(0,1,"note_on",0,62,90,0x90),
            Event(40,2,"note_off",0,60,0,0x80),Event(40,3,"note_off",0,62,0,0x80),
            Event(60,4,"note_on",0,60,90,0x90),Event(60,5,"note_on",0,62,90,0x90),
            Event(100,6,"note_off",0,60,0,0x80),Event(100,7,"note_off",0,62,0,0x80),
            Event(120,8,"note_on",0,60,90,0x90),Event(120,9,"note_on",0,62,90,0x90),
            Event(160,10,"note_off",0,60,0,0x80),Event(160,11,"note_off",0,62,0,0x80),
        ]])
        rows=note_rows(chord)
        self.assertFalse(any(item["accepted"] for item in detect_trills(rows,480,chord.tracks[0],rows)))


if __name__=="__main__":unittest.main()