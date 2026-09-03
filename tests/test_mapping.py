import unittest

from rxoptimizer.mapping import (
    apply_recommendations,
    coverage_report,
    recommend_mappings,
    recommend_profile,
)


CATALOG = [
    {"name": "Acous. Bass RX", "category": "bass", "bank_msb": 121, "bank_lsb": 7, "program": 32, "is_rx": 1},
    {"name": "Finger Bass RX", "category": "bass", "bank_msb": 121, "bank_lsb": 13, "program": 33, "is_rx": 1},
    {"name": "Picked Bass RX", "category": "bass", "bank_msb": 121, "bank_lsb": 10, "program": 34, "is_rx": 1},
    {"name": "FunkSlap Bass RX", "category": "bass", "bank_msb": 121, "bank_lsb": 3, "program": 36, "is_rx": 1},
    {"name": "SlapFing Bass RX", "category": "bass", "bank_msb": 121, "bank_lsb": 4, "program": 36, "is_rx": 1},
    {"name": "SlapPick Bass RX", "category": "bass", "bank_msb": 121, "bank_lsb": 5, "program": 36, "is_rx": 1},
    {"name": "Clean Guitar RX1", "category": "guitar", "bank_msb": 121, "bank_lsb": 14, "program": 28, "is_rx": 1},
    {"name": "Standard Kit RX2", "category": "drums", "bank_msb": 120, "bank_lsb": 0, "program": 1, "is_rx": 1},
    {"name": "Jazz Kit RX1", "category": "drums", "bank_msb": 120, "bank_lsb": 0, "program": 33, "is_rx": 1},
]


class MappingRecommendationTest(unittest.TestCase):
    def test_known_rx_identity_is_preserved_with_maximum_confidence(self):
        profile = {"bank_msb": 121, "bank_lsb": 5, "program": 36, "role": "bass", "name": "unknown"}
        result = recommend_profile(profile, CATALOG)
        self.assertEqual(result["rx_name"], "SlapPick Bass RX")
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["recommendation_method"], "known-rx-identity")

    def test_name_disambiguates_shared_slap_program(self):
        profile = {"bank_msb": 121, "bank_lsb": 99, "program": 36, "role": "bass", "name": "SlapFing Bass"}
        result = recommend_profile(profile, CATALOG)
        self.assertEqual((result["target_bank_msb"], result["target_bank_lsb"], result["target_program"]), (121, 4, 36))
        self.assertGreaterEqual(result["confidence"], .99)

    def test_gm_program_family_uses_only_catalog_target(self):
        profile = {"bank_msb": 0, "bank_lsb": 0, "program": 33, "role": "bass", "name": "GM Program 34"}
        result = recommend_profile(profile, CATALOG)
        self.assertEqual(result["rx_name"], "Finger Bass RX")
        self.assertIn("target address verified", result["provenance"])

    def test_missing_catalog_target_yields_no_recommendation(self):
        catalog = [row for row in CATALOG if row["name"] != "Finger Bass RX"]
        profile = {"bank_msb": 0, "bank_lsb": 0, "program": 33, "role": "bass", "name": "Finger Bass"}
        self.assertIsNone(recommend_profile(profile, catalog))

    def test_unrelated_family_is_not_guessed(self):
        profile = {"bank_msb": 0, "bank_lsb": 0, "program": 80, "role": "melodic", "name": "Square Lead"}
        self.assertIsNone(recommend_profile(profile, CATALOG))

    def test_recommendations_deduplicate_and_coverage_is_auditable(self):
        profiles = [
            {"bank_msb": 0, "bank_lsb": 0, "program": 33, "role": "bass", "name": "Finger Bass"},
            {"bank_msb": 0, "bank_lsb": 0, "program": 33, "role": "bass", "name": "duplicate"},
            {"bank_msb": 0, "bank_lsb": 0, "program": 27, "role": "guitar", "name": "Clean Guitar"},
            {"bank_msb": 0, "bank_lsb": 0, "program": 80, "role": "melodic", "name": "Square Lead"},
        ]
        recommendations = recommend_mappings(profiles, CATALOG)
        report = coverage_report(profiles, recommendations)
        self.assertEqual(len(recommendations), 2)
        self.assertEqual(report["profiles_total"], 3)
        self.assertEqual(report["profiles_mapped"], 2)
        self.assertEqual(report["by_role"]["melodic"]["unmapped"], 1)

    def test_application_keeps_existing_user_mapping_by_default(self):
        existing = [{
            "source_bank_msb": 0, "source_bank_lsb": 0, "source_program": 33, "role": "bass",
            "rx_name": "User choice", "target_bank_msb": 1, "target_bank_lsb": 2,
            "target_program": 3, "confidence": .5, "provenance": "user",
        }]
        recommendation = recommend_profile(
            {"bank_msb": 0, "bank_lsb": 0, "program": 33, "role": "bass", "name": "Finger Bass"}, CATALOG
        )
        merged, report = apply_recommendations(existing, [recommendation])
        self.assertEqual(merged[0]["rx_name"], "User choice")
        self.assertEqual(report["kept_existing"], 1)

    def test_application_can_explicitly_replace_weaker_row(self):
        existing = [{
            "source_bank_msb": 0, "source_bank_lsb": 0, "source_program": 33, "role": "bass",
            "rx_name": "Old", "target_bank_msb": 1, "target_bank_lsb": 1,
            "target_program": 1, "confidence": .5,
        }]
        recommendation = recommend_profile(
            {"bank_msb": 0, "bank_lsb": 0, "program": 33, "role": "bass", "name": "Finger Bass"}, CATALOG
        )
        merged, report = apply_recommendations(existing, [recommendation], replace_lower_confidence=True)
        self.assertEqual(merged[0]["rx_name"], "Finger Bass RX")
        self.assertEqual(report["replaced"], 1)


if __name__ == "__main__":
    unittest.main()