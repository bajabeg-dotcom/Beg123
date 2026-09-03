import unittest

from rxoptimizer.midi import Event,MidiFile
from rxoptimizer.rhythm_context import (
    bar_pattern_fingerprints,extract_rhythm_note_context,multi_bar_candidates,phrase_candidates,stable_event_id,
)


class RhythmContextTest(unittest.TestCase):
    def test_event_and_note_ids_are_deterministic_and_tick_sensitive(self):
        event=Event(10,2,"note_on",0,60,80,0x90)
        first=stable_event_id("a"*64,0,event);second=stable_event_id("a"*64,0,event)
        self.assertEqual(first,second)
        event.tick=11
        self.assertNotEqual(first,stable_event_id("a"*64,0,event))

    def test_context_tracks_meter_cross_bar_and_neighbours(self):
        midi=MidiFile(1,480,[[
            Event(0,0,"meta",data1=0x58,raw=bytes((3,2,24,8))),
            Event(0,1,"note_on",0,60,80,0x90),Event(240,2,"note_off",0,60,0,0x80),
            Event(1320,3,"note_on",0,62,82,0x90),Event(1560,4,"note_off",0,62,0,0x80),
        ]])
        rows=extract_rhythm_note_context(midi,"b"*64)
        self.assertEqual((rows[0]["meter_num"],rows[0]["meter_den"]),(3,4))
        self.assertFalse(rows[0]["cross_bar"])
        self.assertTrue(rows[1]["cross_bar"])
        self.assertEqual(rows[0]["next_note_id"],rows[1]["note_id"])
        self.assertEqual(rows[1]["previous_note_id"],rows[0]["note_id"])

    def test_identical_exact_bars_share_fingerprint_without_grid(self):
        midi=MidiFile(1,480,[[
            Event(0,0,"note_on",0,60,80,0x90),Event(120,1,"note_off",0,60,0,0x80),
            Event(480,2,"note_on",0,62,90,0x90),Event(600,3,"note_off",0,62,0,0x80),
            Event(1920,4,"note_on",0,60,80,0x90),Event(2040,5,"note_off",0,60,0,0x80),
            Event(2400,6,"note_on",0,62,90,0x90),Event(2520,7,"note_off",0,62,0,0x80),
        ]])
        patterns=bar_pattern_fingerprints(extract_rhythm_note_context(midi,"c"*64))
        self.assertEqual(len(patterns),2)
        self.assertEqual(patterns[0]["onset_cluster_count"],2)
        self.assertEqual(patterns[0]["pattern_sha256"],patterns[1]["pattern_sha256"])
        self.assertEqual(patterns[0]["rhythm_pattern_sha256"],patterns[1]["rhythm_pattern_sha256"])
        phrases=phrase_candidates(extract_rhythm_note_context(midi,"c"*64))
        self.assertEqual(len(phrases),2)
        repeated=[row for row in multi_bar_candidates(extract_rhythm_note_context(midi,"c"*64),(2,)) if row["occurrence_count"]>1]
        self.assertEqual(repeated,[])


if __name__=="__main__":unittest.main()