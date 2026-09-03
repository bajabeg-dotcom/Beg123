from pathlib import Path
import sqlite3
import tempfile
import unittest

from rxoptimizer.test_agents import (
    create_test_suite, export_test_pack, record_test_result, test_agent_status,
)


def factory_database(path: Path) -> None:
    database = sqlite3.connect(path)
    database.executescript("""
    CREATE TABLE gm_rx_mappings(source_bank_msb INTEGER,source_bank_lsb INTEGER,
      source_program INTEGER,role TEXT,confidence REAL);
    CREATE TABLE instrument_profiles(source TEXT,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,role TEXT);
    CREATE TABLE optimizer_runs(output_name TEXT,source_sha256 TEXT,output_sha256 TEXT);
    INSERT INTO gm_rx_mappings VALUES(0,0,33,'bass',1.0);
    """)
    database.commit(); database.close()


class TestAgentsTest(unittest.TestCase):
    def test_empty_output_is_honestly_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); factory_database(root / "factory.sqlite3")
            created = create_test_suite(root / "tests.sqlite3", root / "output", root / "factory.sqlite3")
            self.assertEqual(created["gate"]["status"], "pending_hardware")
            self.assertEqual(created["gate"]["automatic_blockers"], 1)

    def test_human_results_are_required_before_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); factory_database(root / "factory.sqlite3")
            output = root / "output"; output.mkdir(); (output / "Demo-Variation.mid").write_bytes(b"MThd-demo")
            created = create_test_suite(root / "tests.sqlite3", output, root / "factory.sqlite3")
            status = test_agent_status(root / "tests.sqlite3", created["suite_id"])
            case_id = status["cases"][0]["id"]
            self.assertEqual(status["gate"]["missing_human_results"], 2)
            for agent in ("hardware_playback", "listening_review"):
                result = record_test_result(root / "tests.sqlite3", {
                    "case_id": case_id, "agent_id": agent, "passed": True,
                    "timing_rating": 5, "rx_rating": 4, "drum_rating": 4,
                    "articulation_rating": 5, "comments": "Pa800 potvrđeno",
                })
            self.assertEqual(result["gate"]["status"], "passed")

    def test_failed_hardware_result_blocks_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); factory_database(root / "factory.sqlite3")
            output = root / "output"; output.mkdir(); (output / "Fill.mid").write_bytes(b"x")
            suite = create_test_suite(root / "tests.sqlite3", output, root / "factory.sqlite3")
            case_id = test_agent_status(root / "tests.sqlite3")["cases"][0]["id"]
            result = record_test_result(root / "tests.sqlite3", {
                "case_id": case_id, "agent_id": "hardware_playback", "passed": False,
                "comments": "Pogrešan RX kit",
            })
            self.assertEqual(result["gate"]["status"], "failed")

    def test_export_pack_contains_manifest_and_guide(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); factory_database(root / "factory.sqlite3")
            create_test_suite(root / "tests.sqlite3", root / "output", root / "factory.sqlite3")
            result = export_test_pack(root / "tests.sqlite3", root / "pack")
            self.assertTrue(Path(result["manifest"]).exists())
            self.assertIn("pending_hardware", Path(result["manifest"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()