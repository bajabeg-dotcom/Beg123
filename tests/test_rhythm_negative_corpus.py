import json

import pytest

from rxoptimizer.rhythm_negative_corpus import (apply_protection_adapters,
    load_negative_manifest, validate_negative_manifest)


def test_manifest_keeps_source_classes_separate_and_loads_fixture():
    manifest = load_negative_manifest("tests/fixtures/x10_negative/manifest.json")
    validated = validate_negative_manifest(manifest)
    assert validated["cases"][0]["source_class"] == "SYNTHETIC_GUARD_FIXTURE"
    assert validated["cases"][0]["expected_action"] == "PRESERVE"


def test_forbidden_sha_is_blocked_after_rename():
    digest = "a" * 64
    manifest = {"schema_version": 1, "cases": [{"case_id": "renamed", "source_class":
        "REFERENCE_NEGATIVE_OBSERVATION", "source_sha256": digest, "member_path": "renamed.mid"}]}
    with pytest.raises(ValueError, match="Forbidden source SHA"):
        validate_negative_manifest(manifest, [digest])


def test_synthetic_cannot_claim_factory_evidence():
    manifest = {"schema_version": 1, "cases": [{"case_id": "bad", "source_class":
        "SYNTHETIC_GUARD_FIXTURE", "claims_factory_evidence": True}]}
    with pytest.raises(ValueError, match="cannot claim Factory"):
        validate_negative_manifest(manifest)


@pytest.mark.parametrize("source_class", ["FACTORY_NEGATIVE_OBSERVATION",
    "REFERENCE_NEGATIVE_OBSERVATION", "HUMAN_VALIDATED_NEGATIVE"])
def test_evidence_negative_cases_require_source_sha(source_class):
    with pytest.raises(ValueError, match="requires source_sha256"):
        validate_negative_manifest({"schema_version": 1, "cases": [{"case_id": "missing", "source_class": source_class}]})


def test_unavailable_and_unjoinable_adapter_fail_closed():
    rows = [{"source_sha256": "1" * 64, "note_id": "note-1", "eligibility_status": "EXACT_CONTEXT_MATCH",
             "preservation_reasons": []}]
    def unavailable(_rows):
        raise RuntimeError("offline")
    unavailable.rule_key = "RX_DNC"; unavailable.version = "1"
    protected = apply_protection_adapters(rows, [unavailable])
    assert protected[0]["eligibility_status"] == "PROTECTED_CONTEXT"
    assert "ADAPTER_UNAVAILABLE" in protected[0]["preservation_reasons"][0]
    def wrong_id(_rows):
        return {"note_id": "not-present", "detection_status": "DETECTED"}
    wrong_id.rule_key = "ORNAMENT"; wrong_id.version = "1"
    protected = apply_protection_adapters(rows, [wrong_id])
    assert any("EVIDENCE_UNJOINABLE" in reason for reason in protected[0]["preservation_reasons"])


def test_invalid_adapter_result_is_preserved_not_raised():
    rows = [{"source_sha256": "1" * 64, "note_id": "note-1", "eligibility_status": "EXACT_CONTEXT_MATCH",
             "preservation_reasons": []}]
    def invalid(_rows): return "not-an-observation"
    invalid.rule_key = "BAD_ADAPTER"; invalid.version = "1"
    protected = apply_protection_adapters(rows, [invalid])
    assert protected[0]["eligibility_status"] == "PROTECTED_CONTEXT"
    assert protected[0]["protection_observations"][0]["evidence_status"] == "INVALID_ADAPTER_RESULT"


def test_required_adapter_version_mismatch_is_fail_closed():
    rows = [{"source_sha256": "1" * 64, "note_id": "note-1", "eligibility_status": "EXACT_CONTEXT_MATCH",
             "preservation_reasons": []}]
    def clear(current):
        return [{"note_id": row["note_id"], "detection_status": "CLEAR"} for row in current]
    clear.rule_key = "GUITAR_MODE"; clear.version = "999"
    protected = apply_protection_adapters(rows, [clear])
    assert any(item["evidence_status"] == "ADAPTER_VERSION_MISMATCH"
               for item in protected[0]["protection_observations"])
    assert protected[0]["eligibility_status"] == "PROTECTED_CONTEXT"


@pytest.mark.parametrize("result", [
    {"detection_status": "CLEAR", "evidence_status": "CHECKED", "locator": None},
    {"detection_status": "CLEAR", "evidence_status": "UNVERIFIED",
     "locator": {"source_sha256": "1" * 64, "note_id": "note-1"}},
    {"detection_status": "MAGIC_SAFE", "evidence_status": "CHECKED",
     "locator": {"source_sha256": "1" * 64, "note_id": "note-1"}},
])
def test_clear_without_exact_validated_evidence_and_unknown_status_fail_closed(result):
    rows = [{"source_sha256": "1" * 64, "note_id": "note-1", "on_event_id": "on-1",
             "off_event_id": "off-1", "eligibility_status": "EXACT_CONTEXT_MATCH", "preservation_reasons": []}]
    def adapter(_rows): return {"note_id": "note-1", **result}
    adapter.rule_key = "GUITAR_MODE"; adapter.version = "1"
    protected = apply_protection_adapters(rows, [adapter], required_rules=(("GUITAR_MODE", "1"),))
    assert protected[0]["eligibility_status"] == "PROTECTED_CONTEXT"


def test_clear_with_validated_exact_stable_id_locator_can_remain_exact():
    rows = [{"source_sha256": "1" * 64, "note_id": "note-1", "on_event_id": "on-1",
             "off_event_id": "off-1", "eligibility_status": "EXACT_CONTEXT_MATCH", "preservation_reasons": []}]
    def adapter(_rows):
        return {"note_id": "note-1", "detection_status": "CLEAR", "evidence_status": "VALIDATED",
                "locator": {"source_sha256": "1" * 64, "on_event_id": "on-1"}}
    adapter.rule_key = "GUITAR_MODE"; adapter.version = "1"
    protected = apply_protection_adapters(rows, [adapter], required_rules=(("GUITAR_MODE", "1"),))
    assert protected[0]["eligibility_status"] == "EXACT_CONTEXT_MATCH"


def test_fixture_digest_and_content_are_verified(tmp_path):
    fixture = tmp_path / "case.json"; fixture.write_text('{"case_id":"fixture"}', encoding="utf-8")
    manifest = {"schema_version": 1, "_manifest_dir": str(tmp_path), "cases": [{"case_id": "fixture",
        "source_class": "SYNTHETIC_GUARD_FIXTURE", "fixture_path": "case.json", "fixture_sha256": "0" * 64}]}
    with pytest.raises(ValueError, match="Fixture SHA mismatch"):
        validate_negative_manifest(manifest)


def test_manifest_case_and_fixture_nested_destructive_keys_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="approved_repair"):
        validate_negative_manifest({"schema_version": 1, "cases": [{"case_id": "bad",
            "source_class": "REFERENCE_NEGATIVE_OBSERVATION", "source_sha256": "a" * 64,
            "nested": {"approved_repair": False}}]})
    fixture = tmp_path / "bad.json"
    fixture.write_text('{"case_id":"bad-fixture","nested":{"approved_repair":false}}', encoding="utf-8")
    digest = __import__("hashlib").sha256(fixture.read_bytes()).hexdigest()
    manifest = {"schema_version": 1, "_manifest_dir": str(tmp_path), "cases": [{"case_id": "bad-fixture",
        "source_class": "SYNTHETIC_GUARD_FIXTURE", "fixture_path": "bad.json", "fixture_sha256": digest}]}
    with pytest.raises(ValueError, match="approved_repair"):
        validate_negative_manifest(manifest)