from pathlib import Path
import tempfile
import unittest

from rxoptimizer.advanced_analysis import analyze_midi
from rxoptimizer.midi import Event, MidiFile, encode_midi


def analysis_fixture():
    lead=[]; echo=[]; order=0
    pitches=(60,62,60,62,64,65,67,69)
    for index,pitch in enumerate(pitches):
        tick=index*120
        lead.extend([Event(tick,order,"note_on",0,pitch,90,0x90),Event(tick+60,order+1,"note_off",0,pitch,0,0x80)])
        echo.extend([Event(tick+360,order,"note_on",1,pitch,45,0x91),Event(tick+420,order+1,"note_off",1,pitch,0,0x81)])
        order+=2
    drums=[Event(0,0,"note_on",9,36,90,0x99),Event(60,1,"note_off",9,36,0,0x89)]
    return MidiFile(1,480,[lead,echo,drums])


class AdvancedAnalysisTest(unittest.TestCase):
    def test_detects_note_based_delay_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"delay.mid"; path.write_bytes(encode_midi(analysis_fixture()))
            report=analyze_midi(path)
            delay=report["cross_track_delay_candidates"][0]
            self.assertEqual(delay["offset_quarters"],.75)
            self.assertEqual(delay["score"],1.0)
            self.assertEqual(delay["lower_velocity_ratio"],1.0)

    def test_melodic_trill_is_not_counted_from_drum_track(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"trill.mid"; path.write_bytes(encode_midi(analysis_fixture()))
            report=analyze_midi(path)
            lead=next(row for row in report["tracks"] if row.get("track")==0 and row.get("channel")==0)
            drums=next(row for row in report["tracks"] if row.get("track")==2 and row.get("channel")==9)
            self.assertGreaterEqual(lead["ornaments"]["trill_count"],1)
            self.assertEqual(drums["ornaments"]["trill_count"],0)


if __name__ == "__main__":
    unittest.main()