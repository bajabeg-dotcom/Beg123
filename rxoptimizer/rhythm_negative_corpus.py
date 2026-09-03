"""Declarative negative-corpus and fail-closed protection helpers for X10."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


SOURCE_CLASSES = {
    "FACTORY_NEGATIVE_OBSERVATION",
    "REFERENCE_NEGATIVE_OBSERVATION",
    "SYNTHETIC_GUARD_FIXTURE",
    "HUMAN_VALIDATED_NEGATIVE",
}

REQUIRED_PROTECTION_RULES = (
    ("GUITAR_MODE", "1"),
    ("RX_DNC", "1"),
    ("ORNAMENT_TRILL_GRACE", "1"),
    ("DRUM_FLAM_ROLL_GHOST", "1"),
    ("CROSS_BAR", "1"),
    ("SECTION_TRANSITION", "1"),
    ("TEMPO_METER_BOUNDARY", "1"),
    ("LOCAL_REPEATED_PATTERN", "1"),
    ("FACTORY_REFERENCE_CONFLICT", "1"),
)

ALLOWED_DETECTION_STATUSES = {
    "CLEAR", "NOT_DETECTED", "DETECTED", "AMBIGUOUS", "ADAPTER_UNAVAILABLE", "EVIDENCE_UNJOINABLE",
}
VALIDATED_CLEAR_EVIDENCE = {"VALIDATED", "CHECKED", "EXACT_STABLE_ID"}
DESTRUCTIVE_IDENTIFIER_TOKENS = ("target", "candidate", "proposal", "repair", "apply", "commit", "mutation")


def _reject_destructive_keys(value, location="manifest"):
    if isinstance(value, dict):
        for key, item in value.items():
            if any(token in str(key).lower() for token in DESTRUCTIVE_IDENTIFIER_TOKENS):
                raise ValueError(f"Analyze-only forbidden field at {location}.{key}")
            _reject_destructive_keys(item, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value): _reject_destructive_keys(item, f"{location}[{index}]")


def load_negative_manifest(path) -> dict:
    """Load a manifest without assigning evidence authority to its cases."""
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid negative manifest: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Negative manifest root must be an object")
    value["_manifest_dir"] = str(path.parent)
    return value


def validate_negative_manifest(manifest, forbidden_sha256=()) -> dict:
    """Validate source separation, stable case IDs and forbidden-source guards."""
    _reject_destructive_keys(manifest)
    if not isinstance(manifest, dict) or int(manifest.get("schema_version", 0)) != 1:
        raise ValueError("Unsupported negative manifest schema")
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Negative manifest cases must be a list")
    forbidden = {str(value).lower() for value in forbidden_sha256}
    seen = set()
    normalized = []
    manifest_dir = Path(str(manifest.get("_manifest_dir", ".")))
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Negative manifest case must be an object")
        source_class = str(case.get("source_class", ""))
        case_id = str(case.get("case_id", "")).strip()
        if source_class not in SOURCE_CLASSES or not case_id:
            raise ValueError("Negative case requires a valid source_class and case_id")
        natural_key = (source_class, case_id)
        if natural_key in seen:
            raise ValueError(f"Duplicate negative case: {source_class}/{case_id}")
        seen.add(natural_key)
        source_sha = case.get("source_sha256")
        if source_class != "SYNTHETIC_GUARD_FIXTURE" and source_sha is None:
            raise ValueError(f"Evidence negative case {case_id} requires source_sha256")
        if source_sha is not None:
            source_sha = str(source_sha).lower()
            if len(source_sha) != 64 or any(char not in "0123456789abcdef" for char in source_sha):
                raise ValueError(f"Invalid source SHA for negative case {case_id}")
            if source_sha in forbidden:
                raise ValueError(f"Forbidden source SHA in negative case {case_id}")
        if source_class == "SYNTHETIC_GUARD_FIXTURE" and case.get("claims_factory_evidence"):
            raise ValueError("Synthetic fixture cannot claim Factory evidence")
        fixture_path = case.get("fixture_path")
        fixture_sha = case.get("fixture_sha256")
        if source_class == "SYNTHETIC_GUARD_FIXTURE":
            if not fixture_path or not fixture_sha:
                raise ValueError(f"Synthetic negative case {case_id} requires fixture_path and fixture_sha256")
            relative = Path(str(fixture_path))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe fixture path for negative case {case_id}")
            fixture = manifest_dir / relative
            try: fixture_data = fixture.read_bytes()
            except OSError as error: raise ValueError(f"Missing fixture for negative case {case_id}") from error
            actual_fixture_sha = sha256(fixture_data).hexdigest()
            if actual_fixture_sha != str(fixture_sha).lower():
                raise ValueError(f"Fixture SHA mismatch for negative case {case_id}")
            try: fixture_json = json.loads(fixture_data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(f"Fixture is not declarative JSON for negative case {case_id}") from error
            if not isinstance(fixture_json, dict) or str(fixture_json.get("case_id", "")) != case_id:
                raise ValueError(f"Fixture case_id mismatch for negative case {case_id}")
            _reject_destructive_keys(fixture_json, f"fixture[{case_id}]")
        expected = str(case.get("expected_action", "PRESERVE"))
        if expected not in {"PRESERVE", "PRESERVE_UNTIL_IMPLEMENTED", "REVIEW_REQUIRED"}:
            raise ValueError(f"Unsafe expected action for negative case {case_id}")
        item = deepcopy(case)
        item.update({"case_id": case_id, "source_class": source_class,
                     "source_sha256": source_sha, "expected_action": expected})
        item.pop("_manifest_dir", None)
        normalized.append(item)
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {"schema_version": 1, "cases": normalized, "case_count": len(normalized),
            "manifest_sha256": sha256(canonical.encode()).hexdigest()}


def _adapter_observations(adapter, rows: list[dict]) -> list[dict]:
    version = str(getattr(adapter, "version", getattr(adapter, "__version__", "UNVERSIONED")))
    key = str(getattr(adapter, "rule_key", getattr(adapter, "__name__", "UNKNOWN_ADAPTER")))
    try:
        result = adapter(deepcopy(rows))
    except Exception as error:  # adapter failure is data, never authorization
        return [{"rule_key": key, "adapter_version": version, "detection_status": "ADAPTER_UNAVAILABLE",
                 "evidence_status": "UNAVAILABLE", "stable_subject_id": row["note_id"],
                 "note_id": row["note_id"], "source_sha256": row["source_sha256"],
                 "locator": None, "details": {"error_type": type(error).__name__}}
                for row in rows]
    if result is None:
        return [{"rule_key": key, "adapter_version": version, "detection_status": "ADAPTER_UNAVAILABLE",
                 "evidence_status": "UNAVAILABLE", "stable_subject_id": row["note_id"],
                 "note_id": row["note_id"], "source_sha256": row["source_sha256"], "locator": None}
                for row in rows]
    if isinstance(result, dict):
        result = [result]
    if not isinstance(result, list):
        return [{"rule_key": key, "adapter_version": version, "detection_status": "ADAPTER_UNAVAILABLE",
                 "evidence_status": "INVALID_ADAPTER_RESULT", "stable_subject_id": row["note_id"],
                 "note_id": row["note_id"], "source_sha256": row["source_sha256"], "locator": None}
                for row in rows]
    observations = []
    known = {row["note_id"]: row for row in rows}
    for raw in result:
        if not isinstance(raw, dict):
            observations.extend({"rule_key": key, "adapter_version": version,
                "detection_status": "ADAPTER_UNAVAILABLE", "evidence_status": "INVALID_ADAPTER_RESULT",
                "stable_subject_id": row["note_id"], "note_id": row["note_id"],
                "source_sha256": row["source_sha256"], "locator": None} for row in rows)
            continue
        note_id = raw.get("note_id") or raw.get("stable_subject_id")
        base = known.get(note_id)
        if base is None:
            observations.extend({"rule_key": key, "adapter_version": version,
                "detection_status": "EVIDENCE_UNJOINABLE", "evidence_status": "UNJOINABLE",
                "stable_subject_id": row["note_id"], "note_id": row["note_id"],
                "source_sha256": row["source_sha256"], "locator": raw.get("locator")}
                for row in rows)
            continue
        item = dict(raw)
        item["rule_key"] = key; item["adapter_version"] = version
        item.setdefault("stable_subject_id", note_id); item.setdefault("note_id", note_id)
        item.setdefault("source_sha256", base["source_sha256"]); item.setdefault("locator", None)
        item.setdefault("detection_status", "AMBIGUOUS"); item.setdefault("evidence_status", "UNVERIFIED")
        if item["source_sha256"] != base["source_sha256"]:
            item["detection_status"] = "EVIDENCE_UNJOINABLE"
            item["evidence_status"] = "UNJOINABLE"
        observations.append(item)
    return observations


def apply_protection_adapters(note_context, adapters, required_rules=REQUIRED_PROTECTION_RULES) -> list[dict]:
    """Attach stable-ID observations; every adapter gap fails closed to preserve."""
    rows = deepcopy(list(note_context))
    by_note = {row["note_id"]: [] for row in rows}
    supplied = {}
    for adapter in adapters:
        key = str(getattr(adapter, "rule_key", getattr(adapter, "__name__", "UNKNOWN_ADAPTER")))
        version = str(getattr(adapter, "version", getattr(adapter, "__version__", "UNVERSIONED")))
        if key in supplied and supplied[key] != version:
            raise ValueError(f"Conflicting protection adapter versions for {key}")
        supplied[key] = version
        observations = _adapter_observations(adapter, rows)
        observed_note_ids = set()
        for observation in observations:
            observed_note_ids.add(observation["note_id"])
            by_note.setdefault(observation["note_id"], []).append(observation)
        for row in rows:
            if row["note_id"] not in observed_note_ids:
                by_note[row["note_id"]].append({"rule_key": key, "adapter_version": version,
                    "detection_status": "ADAPTER_UNAVAILABLE", "evidence_status": "NO_NOTE_RESULT",
                    "stable_subject_id": row["note_id"], "note_id": row["note_id"],
                    "source_sha256": row["source_sha256"], "locator": None})
    for key, version in required_rules:
        if supplied.get(key) == version: continue
        for row in rows:
            by_note[row["note_id"]].append({"rule_key": key, "adapter_version": version,
                "detection_status": "ADAPTER_UNAVAILABLE", "evidence_status":
                    "ADAPTER_VERSION_MISMATCH" if key in supplied else "REQUIRED_ADAPTER_MISSING",
                "stable_subject_id": row["note_id"], "note_id": row["note_id"],
                "source_sha256": row["source_sha256"], "locator": None})
    preserve_statuses = {"DETECTED", "AMBIGUOUS", "ADAPTER_UNAVAILABLE", "EVIDENCE_UNJOINABLE"}
    for row in rows:
        observations = sorted(by_note.get(row["note_id"], []),
            key=lambda item: (item.get("rule_key", ""), item.get("adapter_version", ""),
                              item.get("detection_status", "")))
        row["protection_observations"] = observations
        reasons = list(row.get("preservation_reasons", []))
        for item in observations:
            status = str(item.get("detection_status", ""))
            if status not in ALLOWED_DETECTION_STATUSES:
                reasons.append(f"PRESERVE:{item.get('rule_key')}:UNKNOWN_STATUS")
                continue
            if status in {"CLEAR", "NOT_DETECTED"}:
                locator = item.get("locator"); exact_locator = False
                if isinstance(locator, dict) and locator.get("source_sha256") == row.get("source_sha256"):
                    exact_locator = (locator.get("note_id") == row.get("note_id") or
                        locator.get("on_event_id") == row.get("on_event_id") or
                        locator.get("off_event_id") == row.get("off_event_id") or
                        locator.get("event_id") in {row.get("on_event_id"), row.get("off_event_id")})
                if item.get("evidence_status") not in VALIDATED_CLEAR_EVIDENCE or not exact_locator:
                    reasons.append(f"PRESERVE:{item.get('rule_key')}:{status}_EVIDENCE_INVALID")
                continue
            if status in preserve_statuses:
                action = "PRESERVE_UNTIL_IMPLEMENTED" if status == "ADAPTER_UNAVAILABLE" else "PRESERVE"
                reasons.append(f"{action}:{item.get('rule_key')}:{status}")
        row["preservation_reasons"] = sorted(set(reasons))
        if row["preservation_reasons"]:
            row["eligibility_status"] = "PROTECTED_CONTEXT"
    return rows