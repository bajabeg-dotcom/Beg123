import unittest

from rxoptimizer.features import GoldDNAModel, aggregate_profiles, extract_features
from rxoptimizer.midi import Event, MidiFile


def expressive_fixture() -> MidiFile:
    division = 480
    events = [
        Event(0, 0, "program", 0, 33, None, 0xC0),
        Event(0, 1, "control", 0, 1, 20, 0xB0),
        Event(0, 2, "control", 0, 11, 80, 0xB0),
    ]
    # Onsets 0, 2/3 and 1 quarter produce a 2:1 swing ratio. The next
    # notes provide all four quarter-beat positions and known microtiming.
    notes = [
        (0, 60, 70, 120),
        (320, 62, 90, 160),
        (480, 64, 80, 240),
        (610, 65, 100, 120),  # 10 ticks late from the nearest 16th
    ]
    order = 3
    for start, pitch, velocity, duration in notes:
        events.append(Event(start, order, "note_on", 0, pitch, velocity, 0x90)); order += 1
        events.append(Event(start + duration, order, "note_off", 0, pitch, 0, 0x80)); order += 1
    events += [
        Event(720, order, "control", 0, 1, 60, 0xB0),
        Event(720, order + 1, "control", 0, 11, 100, 0xB0),
    ]
    return MidiFile(1, division, [events])


class FeatureExtractionTest(unittest.TestCase):
    def test_extracts_role_grid_gate_density_cc_and_swing(self):
        feature = extract_features(expressive_fixture())[0]
        self.assertEqual(feature.role, "bass")
        self.assertEqual(feature.note_count, 4)
        self.assertAlmostEqual(feature.swing_ratio.mean, 2.0, places=6)
        self.assertEqual(feature.velocity_by_16th[0].mean, 70)
        self.assertEqual(feature.velocity_by_16th[3].mean, 90)
        self.assertAlmostEqual(feature.duration_quarters.mean, 1 / 3, places=6)
        self.assertAlmostEqual(feature.timing_by_16th[5].mean, 10 / 480, places=6)
        self.assertEqual(feature.cc1.values.mean, 40)
        self.assertEqual(feature.cc11.values.mean, 90)
        self.assertGreater(feature.density_per_quarter, 2)

    def test_role_map_can_override_inference(self):
        feature = extract_features(expressive_fixture(), {(0, 0): "lead"})[0]
        self.assertEqual(feature.role, "lead")

    def test_aggregate_merges_event_and_database_statistics(self):
        features = extract_features(expressive_fixture())
        profiles = aggregate_profiles(features, [{
            "role": "bass", "note_count": 4, "velocity_mean": 110,
            "duration_quarters": .5, "density_per_quarter": 8,
        }])
        profile = profiles["bass"]
        self.assertEqual(profile.note_count, 8)
        self.assertEqual(profile.track_count, 2)
        self.assertAlmostEqual(profile.velocity.mean, 97.5)
        self.assertEqual(profile.velocity_by_16th[3].mean, 90)

    def test_model_is_position_aware_and_deterministic(self):
        model = GoldDNAModel.fit(extract_features(expressive_fixture()))
        first = model.transform_note("bass", 3, 64, .5, strength=1)
        second = model.transform_note("bass", 3, 64, .5, strength=1)
        self.assertEqual(first, second)
        self.assertEqual(first.velocity, 90)
        self.assertAlmostEqual(first.duration_quarters, 1 / 3, places=6)
        self.assertIn("bass", model.to_dict()["profiles"])

    def test_empty_model_preserves_note(self):
        target = GoldDNAModel.fit([]).transform_note("bass", 0, 77, .25)
        self.assertEqual((target.velocity, target.duration_quarters), (77, .25))


if __name__ == "__main__":
    unittest.main()