from pathlib import Path
import base64
import tempfile
import unittest
from unittest.mock import patch

import app
from rxoptimizer.database import connect, seed_pa800_catalog


class AppGuardTest(unittest.TestCase):
    def test_six_song_references_are_forbidden_for_rx_noise_probes(self):
        path=Path("prism-uploads")/app.SONG_REFERENCE_FILENAMES[0]
        payload={"filename":path.name,"data_base64":base64.b64encode(path.read_bytes()).decode()}
        with self.assertRaisesRegex(ValueError,"Delay/Terca"):
            app.create_rx_noise_probes(payload)
        with self.assertRaisesRegex(ValueError,"Odaberi poseban MIDI"):
            app.create_rx_noise_probes({})

    def test_song_reference_cohort_excludes_generated_and_unapproved_midis(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            uploads=root/"prism-uploads"
            uploads.mkdir()
            approved=app.SONG_REFERENCE_FILENAMES[0]
            (uploads/approved).write_bytes(b"approved")
            (uploads/"generated-gold-rx.mid").write_bytes(b"generated")
            (uploads/"new-unapproved.mid").write_bytes(b"new")
            with patch.object(app,"ROOT",root):
                self.assertEqual([path.name for path in app.song_midi_paths()],[approved])

    def test_save_mapping_requires_catalog_target_and_same_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            factory=root/"factory.sqlite3"
            with connect(factory) as database:
                seed_pa800_catalog(database)
            patches=(
                patch.object(app,"FACTORY_DB",factory),
                patch.object(app,"GOLD_DB",root/"missing-gold.sqlite3"),
                patch.object(app,"VOICE_DB",root/"missing-voice.sqlite3"),
                patch.object(app,"RX_DB",root/"missing-rx.sqlite3"),
                patch.object(app,"PERFORMANCE_DB",root/"missing-performance.sqlite3"),
            )
            for item in patches:item.start()
            try:
                with self.assertRaisesRegex(ValueError,"potvrđenom Pa800 katalogu"):
                    app.save_mapping({"source_program":34,"role":"bass","rx_name":"Fake RX",
                        "target_bank_msb":1,"target_bank_lsb":2,"target_program":3})
                with self.assertRaisesRegex(ValueError,"cross-instrument"):
                    app.save_mapping({"source_program":34,"role":"bass","rx_name":"Clean Guitar RX1",
                        "target_bank_msb":121,"target_bank_lsb":14,"target_program":29})
                result=app.save_mapping({"source_program":34,"role":"bass","rx_name":"Finger Bass RX",
                    "target_bank_msb":121,"target_bank_lsb":13,"target_program":34})
                self.assertTrue(result["saved"])
                with connect(factory) as database:
                    row=database.execute("SELECT * FROM gm_rx_mappings WHERE source_program=33 AND role='bass'").fetchone()
                    self.assertEqual(row["provenance"],"user_catalog_identity_verified")
                    self.assertEqual(row["confidence"],.95)
            finally:
                for item in reversed(patches):item.stop()


if __name__ == "__main__":
    unittest.main()