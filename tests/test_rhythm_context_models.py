from hashlib import sha256
from pathlib import Path
import sqlite3

import pytest

from rxoptimizer.midi import Event, MidiFile, encode_midi
from rxoptimizer.rhythm_context_models import (build_context_qualified_database,
    canonical_semantic_rows, semantic_digest)
from rxoptimizer.rhythm_negative_corpus import REQUIRED_PROTECTION_RULES, load_negative_manifest


def clear_adapters():
    result = []
    for rule_key, version in REQUIRED_PROTECTION_RULES:
        def clear(rows, _key=rule_key):
            return [{"note_id": row["note_id"], "detection_status": "CLEAR",
                     "evidence_status": "CHECKED", "locator": row["evidence_locator"]} for row in rows]
        clear.rule_key = rule_key; clear.version = version; result.append(clear)
    return result


def source_record(note=60, quality="NORMAL"):
    midi = MidiFile(1, 480, [[Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0), Event(0, 2, "program", 0, 33, status=0xC0),
        Event(0, 3, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
        Event(0, 4, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")),
        Event(0, 5, "note_on", 0, note, 80, 0x90), Event(120, 6, "note_off", 0, note, 0, 0x80)]])
    data = encode_midi(midi)
    return {"bytes": data, "source_sha256": sha256(data).hexdigest(), "corpus": "factory",
        "member_path": f"Factory/{note}.mid", "quality_status": quality,
        "metadata": {"role": "BASS", "role_status": "EXACT", "style_name": "Test",
            "style_status": "EXPLICIT_METADATA", "section": "VARIATION", "section_no": 0,
            "section_status": "EXACT", "cv": 0, "cv_status": "CV_EXACT",
            "role_method": "RAW_TRACK", "role_locator": "Factory/Test.mid#track=0",
            "style_method": "EXPLICIT_METADATA", "style_locator": "Factory/Test.mid#style",
            "section_method": "EXPLICIT_METADATA", "section_locator": "Factory/Test.mid#section",
            "cv_method": "EXPLICIT_METADATA", "cv_locator": "Factory/Test.mid#cv"}}


def test_builder_is_raw_only_analyze_only_deterministic_and_integral(tmp_path):
    record = source_record(); original = bytes(record["bytes"])
    first = tmp_path / "first.sqlite3"; second = tmp_path / "second.sqlite3"
    config = {"protection_adapters": clear_adapters()}
    one = build_context_qualified_database([record], first, config)
    two = build_context_qualified_database([record], second, config)
    assert one["semantic_digest"] == two["semantic_digest"]
    assert canonical_semantic_rows(first) == canonical_semantic_rows(second)
    assert semantic_digest(first) == one["semantic_digest"]
    assert record["bytes"] == original and sha256(record["bytes"]).hexdigest() == record["source_sha256"]
    db = sqlite3.connect(first)
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT eligibility_status FROM note_context").fetchone()[0] == "EXACT_CONTEXT_MATCH"
    db.close()


def test_non_normal_is_materialized_but_not_eligible(tmp_path):
    output = tmp_path / "rare.sqlite3"
    build_context_qualified_database([source_record(quality="RARE")], output)
    db = sqlite3.connect(output)
    assert db.execute("SELECT eligibility_status FROM note_context").fetchone()[0] == "PROTECTED_CONTEXT"
    db.close()


def test_legacy_inputs_and_forbidden_source_are_hard_fail(tmp_path):
    record = source_record()
    with pytest.raises(ValueError, match="Legacy"):
        build_context_qualified_database([record], tmp_path / "legacy.sqlite3", {"consensus_path": "old.sqlite3"})
    with pytest.raises(ValueError, match="Forbidden source"):
        build_context_qualified_database([record], tmp_path / "forbidden.sqlite3", {"forbidden_sha256": [record["source_sha256"]]})
    with pytest.raises(ValueError, match="mutation_mode"):
        build_context_qualified_database([record], tmp_path / "unsafe-api.sqlite3", {"mutation_mode": "write"})


def test_complete_public_source_and_config_payloads_reject_nested_destructive_keys(tmp_path):
    top_level = source_record(); top_level["approved_repair"] = False
    with pytest.raises(ValueError, match="approved_repair"):
        build_context_qualified_database([top_level], tmp_path / "unsafe-source.sqlite3")
    nested = source_record(); nested["unknown_extension"] = {"safe": {"approved_repair": "prose value ignored"}}
    with pytest.raises(ValueError, match="approved_repair"):
        build_context_qualified_database([nested], tmp_path / "unsafe-nested.sqlite3")
    with pytest.raises(ValueError, match="approved_repair"):
        build_context_qualified_database([source_record()], tmp_path / "unsafe-config.sqlite3",
            {"extension": {"approved_repair": False}})


def test_failed_rebuild_preserves_previous_database(tmp_path):
    output = tmp_path / "atomic.sqlite3"; record = source_record()
    build_context_qualified_database([record], output); before = semantic_digest(output)
    invalid = dict(record); invalid["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA mismatch"):
        build_context_qualified_database([invalid], output)
    assert semantic_digest(output) == before


def test_natural_source_collision_hard_fails(tmp_path):
    record = source_record()
    with pytest.raises(ValueError, match="Duplicate RAW source"):
        build_context_qualified_database([record, record], tmp_path / "duplicate.sqlite3")


def test_builder_records_adapter_failure_as_preservation(tmp_path):
    def missing(_rows):
        raise RuntimeError("not available")
    missing.rule_key = "GUITAR_MODE"; missing.version = "1"
    output = tmp_path / "protected.sqlite3"
    build_context_qualified_database([source_record()], output, {"protection_adapters": [missing]})
    db = sqlite3.connect(output)
    assert db.execute("SELECT eligibility_status FROM note_context").fetchone()[0] == "PROTECTED_CONTEXT"
    assert db.execute("SELECT detection_status FROM protection_observations").fetchone()[0] == "ADAPTER_UNAVAILABLE"
    db.close()


def test_digest_ignores_timestamps_and_absolute_roots_but_preserves_member_locator(tmp_path):
    first_record = source_record(); second_record = source_record()
    first_record["metadata"].update({"timestamp_utc": "2026-01-01T00:00:00Z",
        "extracted_at": "2026-01-01T00:01:00Z", "observed_at": "2026-01-01T00:02:00Z",
        "diagnostic_path": "/first/root/evidence.json", "role_locator": "/first/root/role.json"})
    second_record["metadata"].update({"timestamp_utc": "2026-08-11T20:00:00Z",
        "extracted_at": "2026-08-11T20:01:00Z", "observed_at": "2026-08-11T20:02:00Z",
        "diagnostic_path": "/second/root/evidence.json", "role_locator": "/second/root/role.json"})
    first = tmp_path / "paths-a.sqlite3"; second = tmp_path / "paths-b.sqlite3"
    one = build_context_qualified_database([first_record], first)
    two = build_context_qualified_database([second_record], second)
    assert one["semantic_digest"] == two["semantic_digest"]
    rows = "\n".join(canonical_semantic_rows(first))
    assert "Factory/60.mid" in rows
    assert "/first/root" not in rows


def test_negative_fixture_is_validated_and_materialized(tmp_path):
    manifest = load_negative_manifest("tests/fixtures/x10_negative/manifest.json")
    output = tmp_path / "negative.sqlite3"
    build_context_qualified_database([source_record()], output, {"negative_manifest": manifest})
    db = sqlite3.connect(output)
    row = db.execute("SELECT source_class,case_id,case_json FROM negative_corpus_cases").fetchone()
    assert row[0:2] == ("SYNTHETIC_GUARD_FIXTURE", "synthetic-syncopation")
    assert "fixture_sha256" in row[2]
    db.close()


def test_every_note_program_segment_id_has_materialized_fk_row(tmp_path):
    midi = MidiFile(1, 480, [[Event(0, 0, "program", 0, 10, status=0xC0),
        Event(0, 1, "note_on", 0, 60, 80, 0x90), Event(0, 2, "program", 0, 11, status=0xC0),
        Event(0, 3, "note_on", 0, 62, 80, 0x90), Event(120, 4, "note_off", 0, 60, 0, 0x80),
        Event(120, 5, "note_off", 0, 62, 0, 0x80)]])
    data = encode_midi(midi); record = source_record(); record.update({"bytes": data,
        "source_sha256": sha256(data).hexdigest(), "member_path": "Factory/ordered.mid"})
    output = tmp_path / "program-fk.sqlite3"; build_context_qualified_database([record], output)
    db = sqlite3.connect(output)
    unmatched = db.execute("SELECT COUNT(*) FROM note_context n LEFT JOIN program_segments p "
        "ON p.program_segment_id=n.program_segment_id WHERE p.program_segment_id IS NULL").fetchone()[0]
    assert unmatched == 0
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT COUNT(*) FROM program_segments WHERE segment_kind='NOTE_ON_ATTRIBUTION'").fetchone()[0] == 2
    db.close()