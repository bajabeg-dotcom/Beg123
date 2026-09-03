"""Atomic context-qualified ANALYZE_ONLY SQLite materialization."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import sqlite3

from .midi import parse_midi
from .rhythm_context import bar_pattern_fingerprints
from .rhythm_context_join import build_channel_context, join_note_context
from .rhythm_negative_corpus import validate_negative_manifest


FORBIDDEN_IDENTIFIER_ROOTS = ("target", "candidate", "proposal", "repair", "apply", "commit", "mutation")
NONSEMANTIC_KEYS = {"timestamp", "created_at", "updated_at", "build_timestamp", "generated_at", "absolute_path"}
SEMANTIC_TABLES = ("source_context", "channel_state_events", "program_segments", "meter_segments",
    "tempo_segments", "note_context", "bar_context", "protection_observations", "negative_corpus_cases")

SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE TABLE source_context(source_sha256 TEXT PRIMARY KEY,corpus TEXT NOT NULL,member_path TEXT NOT NULL,
 metadata_json TEXT NOT NULL,quality_json TEXT NOT NULL,capability TEXT NOT NULL);
CREATE TABLE channel_state_events(source_sha256 TEXT NOT NULL,channel INTEGER NOT NULL,tick INTEGER NOT NULL,
 event_kind TEXT NOT NULL,semantic_value_sha256 TEXT NOT NULL,state_event_id TEXT NOT NULL UNIQUE,
 semantic_value_json TEXT NOT NULL,locators_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,channel,tick,event_kind,semantic_value_sha256),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE program_segments(source_sha256 TEXT NOT NULL,channel INTEGER NOT NULL,start_tick INTEGER NOT NULL,
 program_segment_id TEXT NOT NULL UNIQUE,end_tick INTEGER,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,
 status TEXT NOT NULL,segment_kind TEXT NOT NULL,locators_json TEXT NOT NULL,PRIMARY KEY(source_sha256,channel,start_tick,program_segment_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE meter_segments(source_sha256 TEXT NOT NULL,start_tick INTEGER NOT NULL,meter_segment_id TEXT NOT NULL UNIQUE,
 end_tick INTEGER,numerator INTEGER,denominator INTEGER,status TEXT NOT NULL,locators_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,start_tick,meter_segment_id),FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE tempo_segments(source_sha256 TEXT NOT NULL,start_tick INTEGER NOT NULL,tempo_segment_id TEXT NOT NULL UNIQUE,
 end_tick INTEGER,microseconds_per_quarter INTEGER,tempo_regime_key TEXT,status TEXT NOT NULL,locators_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,start_tick,tempo_segment_id),FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE note_context(source_sha256 TEXT NOT NULL,note_id TEXT NOT NULL,on_event_id TEXT NOT NULL,off_event_id TEXT NOT NULL,
 track_index INTEGER NOT NULL,channel INTEGER NOT NULL,note INTEGER NOT NULL,velocity INTEGER NOT NULL,start_tick INTEGER NOT NULL,
 end_tick INTEGER NOT NULL,duration_ticks INTEGER NOT NULL,bar_index INTEGER NOT NULL,beat_index INTEGER NOT NULL,
 program_segment_id TEXT NOT NULL,meter_segment_id TEXT NOT NULL,tempo_segment_id TEXT NOT NULL,
 context_json TEXT NOT NULL,eligibility_status TEXT NOT NULL,PRIMARY KEY(source_sha256,note_id),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256),
 FOREIGN KEY(program_segment_id) REFERENCES program_segments(program_segment_id),
 FOREIGN KEY(meter_segment_id) REFERENCES meter_segments(meter_segment_id),
 FOREIGN KEY(tempo_segment_id) REFERENCES tempo_segments(tempo_segment_id));
CREATE TABLE bar_context(source_sha256 TEXT NOT NULL,track_index INTEGER NOT NULL,channel INTEGER NOT NULL,bar_index INTEGER NOT NULL,
 topology_sha256 TEXT NOT NULL,exact_context_key TEXT,eligibility_status TEXT NOT NULL,context_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,track_index,channel,bar_index,topology_sha256),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE protection_observations(source_sha256 TEXT NOT NULL,stable_subject_id TEXT NOT NULL,rule_key TEXT NOT NULL,
 adapter_version TEXT NOT NULL,detection_status TEXT NOT NULL,evidence_status TEXT NOT NULL,observation_json TEXT NOT NULL,
 PRIMARY KEY(source_sha256,stable_subject_id,rule_key,adapter_version),
 FOREIGN KEY(source_sha256) REFERENCES source_context(source_sha256));
CREATE TABLE negative_corpus_cases(source_class TEXT NOT NULL,case_id TEXT NOT NULL,case_json TEXT NOT NULL,
 PRIMARY KEY(source_class,case_id));
CREATE TABLE semantic_digest(digest_algorithm TEXT NOT NULL,schema_version INTEGER NOT NULL,digest TEXT NOT NULL,
 PRIMARY KEY(digest_algorithm,schema_version));
"""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _is_nonsemantic_key(key) -> bool:
    lowered = str(key).lower()
    return lowered in NONSEMANTIC_KEYS or "timestamp" in lowered or lowered.endswith("_at")


def _normalize(value):
    if isinstance(value, dict): return {key: _normalize(value[key]) for key in sorted(value) if not _is_nonsemantic_key(key)}
    if isinstance(value, (list, tuple)): return [_normalize(item) for item in value]
    if isinstance(value, Path): return PurePosixPath(value).as_posix()
    if isinstance(value, bytes): return {"sha256": sha256(value).hexdigest()}
    if isinstance(value, str):
        path = value.replace("\\", "/")
        if path.startswith("/") or (len(path) > 2 and path[1] == ":" and path[2] == "/"):
            return f"ABSOLUTE_PATH/{PurePosixPath(path).name}"
    return value


def _forbidden_identifier(value) -> bool:
    lowered = str(value).lower()
    return any(root in lowered for root in FORBIDDEN_IDENTIFIER_ROOTS)


def _record_bytes(record):
    data = record.get("bytes", record.get("data"))
    if not isinstance(data, bytes): raise ValueError("RAW source record requires bytes")
    return data


def _reject_forbidden_fields(value, location="root"):
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            if _forbidden_identifier(lower):
                raise ValueError(f"Analyze-only forbidden field at {location}.{key}")
            _reject_forbidden_fields(item, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value): _reject_forbidden_fields(item, f"{location}[{index}]")


def assert_analyze_only_schema(database_path) -> None:
    database = sqlite3.connect(database_path)
    try:
        rows = database.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()
        for (name,) in rows:
            if name.startswith("sqlite_"): continue
            if _forbidden_identifier(name):
                raise ValueError(f"Forbidden analyze-only schema identifier in {name}")
            for column in database.execute(f'PRAGMA table_info("{name}")'):
                if _forbidden_identifier(column[1]):
                    raise ValueError(f"Forbidden analyze-only schema identifier in {name}.{column[1]}")
        info = dict(database.execute("SELECT key,value_json FROM build_info"))
        if json.loads(info.get("capability", 'null')) != "ANALYZE_ONLY" or json.loads(info.get("mutation_capability", 'null')) != "NONE":
            raise ValueError("Database does not declare ANALYZE_ONLY/NONE")
    finally: database.close()


def canonical_semantic_rows(database_path) -> list[str]:
    database = sqlite3.connect(database_path); database.row_factory = sqlite3.Row
    rows = []
    try:
        for table in SEMANTIC_TABLES:
            exists = database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists: continue
            values = []
            for row in database.execute(f'SELECT * FROM "{table}"'):
                item = dict(row)
                for key, value in list(item.items()):
                    if key.endswith("_json") and isinstance(value, str):
                        try: item[key] = json.loads(value)
                        except json.JSONDecodeError: pass
                values.append(_normalize(item))
            values.sort(key=_json)
            rows.extend(_json({"table": table, "row": value}) for value in values)
    finally: database.close()
    return rows


def semantic_digest(database_path) -> str:
    payload = "\n".join(canonical_semantic_rows(database_path)).encode("utf-8")
    return sha256(payload).hexdigest()


def _insert_timelines(db, context):
    for row in context["channel_state_events"]:
        db.execute("INSERT INTO channel_state_events VALUES(?,?,?,?,?,?,?,?)", (row["source_sha256"], row["channel"], row["tick"],
            row["event_kind"], row["semantic_value_sha256"], row["state_event_id"], _json(row["semantic_value"]), _json(row["evidence_locators"])))
    for row in context["program_segments"]:
        db.execute("INSERT INTO program_segments VALUES(?,?,?,?,?,?,?,?,?,?,?)", (row["source_sha256"], row["channel"], row["start_tick"],
            row["program_segment_id"], row["end_tick"], row["bank_msb"], row["bank_lsb"], row["program"], row["status"],
            row["segment_kind"], _json(row["evidence_locators"])))
    for row in context["meter_segments"]:
        db.execute("INSERT INTO meter_segments VALUES(?,?,?,?,?,?,?,?)", (row["source_sha256"], row["start_tick"], row["meter_segment_id"],
            row["end_tick"], row["numerator"], row["denominator"], row["status"], _json(row["evidence_locators"])))
    for row in context["tempo_segments"]:
        db.execute("INSERT INTO tempo_segments VALUES(?,?,?,?,?,?,?,?)", (row["source_sha256"], row["start_tick"], row["tempo_segment_id"],
            row["end_tick"], row["microseconds_per_quarter"], row["tempo_regime_key"], row["status"], _json(row["evidence_locators"])))


def build_context_qualified_database(source_records, output_path, config=None) -> dict:
    """Build an atomic RAW-derived database; never accepts a legacy model input."""
    cfg = dict(config or {})
    _reject_forbidden_fields(cfg, "config")
    for legacy in ("calibration_path", "consensus_path", "legacy_database"):
        if legacy in cfg: raise ValueError("Legacy calibration/consensus cannot be builder input")
    output_path = Path(output_path); temp = output_path.with_suffix(output_path.suffix + ".tmp"); temp.unlink(missing_ok=True)
    forbidden = {str(value).lower() for value in cfg.get("forbidden_sha256", ())}
    negative = validate_negative_manifest(cfg.get("negative_manifest", {"schema_version": 1, "cases": []}), forbidden)
    records = list(source_records)
    if not records: raise ValueError("At least one RAW source is required")
    db = sqlite3.connect(temp); db.execute("PRAGMA foreign_keys=ON"); db.executescript(SCHEMA)
    try:
        adapter_config = [{"rule_key": str(getattr(adapter, "rule_key", getattr(adapter, "__name__", "UNKNOWN_ADAPTER"))),
                           "version": str(getattr(adapter, "version", getattr(adapter, "__version__", "UNVERSIONED")))}
                          for adapter in cfg.get("protection_adapters", ())]
        stored_config = {key: value for key, value in cfg.items() if key not in {"negative_manifest", "protection_adapters"}}
        stored_config["protection_adapters"] = adapter_config
        db.executemany("INSERT INTO build_info VALUES(?,?)", (("schema_version", _json(1)), ("builder_version", _json(1)),
            ("capability", _json("ANALYZE_ONLY")), ("mutation_capability", _json("NONE")),
            ("config", _json(_normalize(stored_config)))))
        note_total = exact_total = 0; protection_seen = {}
        seen_sources = set()
        for record in records:
            _reject_forbidden_fields(record, "source_record")
            data = _record_bytes(record); before = sha256(data).hexdigest(); declared = str(record.get("source_sha256", before)).lower()
            if before != declared: raise ValueError("RAW source SHA mismatch")
            if declared in forbidden: raise ValueError("Forbidden source SHA")
            if declared in seen_sources: raise ValueError("Duplicate RAW source natural key")
            seen_sources.add(declared)
            corpus = str(record.get("corpus", "")).lower()
            if corpus not in {"factory", "gold", "reference"}: raise ValueError("Unsupported corpus")
            member = PurePosixPath(str(record.get("member_path", ""))).as_posix()
            if not member or member.startswith("/") or ".." in PurePosixPath(member).parts: raise ValueError("Invalid member path")
            metadata = dict(record.get("metadata") or {}); quality = record.get("quality_status", "INVALID")
            _reject_forbidden_fields(metadata)
            midi = parse_midi(data)
            db.execute("INSERT INTO source_context VALUES(?,?,?,?,?,?)", (declared, corpus, member, _json(metadata), _json(quality), "ANALYZE_ONLY"))
            timelines = build_channel_context(midi, declared); _insert_timelines(db, timelines)
            notes = join_note_context(midi, declared, metadata, quality, cfg.get("protection_adapters", ()))
            _reject_forbidden_fields(notes)
            for row in notes:
                note_total += 1; exact_total += int(row["eligibility_status"] == "EXACT_CONTEXT_MATCH")
                db.execute("INSERT INTO note_context VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (declared, row["note_id"], row["on_event_id"],
                    row["off_event_id"], row["track"], row["channel"], row["note"], row["velocity"], row["start_tick"], row["end_tick"],
                    row["duration_ticks"], row["bar"], row["beat"], row["program_segment_id"], row["meter_segment_id"], row["tempo_segment_id"],
                    _json(row), row["eligibility_status"]))
                for observation in row.get("protection_observations", []):
                    natural_key = (declared, observation["stable_subject_id"], observation["rule_key"], observation["adapter_version"])
                    semantic = _json(observation)
                    if natural_key in protection_seen:
                        if protection_seen[natural_key] != semantic:
                            raise ValueError("Contradictory protection observation natural key")
                        continue
                    protection_seen[natural_key] = semantic
                    db.execute("INSERT INTO protection_observations VALUES(?,?,?,?,?,?,?)", (*natural_key,
                        observation["detection_status"], observation.get("evidence_status", "UNVERIFIED"), semantic))
            by_bar = {}
            for pattern in bar_pattern_fingerprints(notes):
                group = [row for row in notes if row["track"] == pattern["track"] and row["channel"] == pattern["channel"] and row["bar"] == pattern["bar"]]
                exact_keys = {row["exact_context_key"] for row in group}
                exact_key = next(iter(exact_keys)) if len(exact_keys) == 1 and None not in exact_keys else None
                status = "EXACT_CONTEXT_MATCH" if exact_key and all(row["eligibility_status"] == "EXACT_CONTEXT_MATCH" for row in group) else "PROTECTED_CONTEXT"
                key = (declared, pattern["track"], pattern["channel"], pattern["bar"], pattern["topology_sha256"])
                if key in by_bar: raise ValueError("Contradictory bar natural key")
                by_bar[key] = True
                db.execute("INSERT INTO bar_context VALUES(?,?,?,?,?,?,?,?)", (*key, exact_key, status, _json({"pattern": pattern, "note_ids": [row["note_id"] for row in group]})))
            if sha256(data).hexdigest() != before: raise ValueError("RAW source mutated")
        for case in negative["cases"]:
            db.execute("INSERT INTO negative_corpus_cases VALUES(?,?,?)", (case["source_class"], case["case_id"], _json(case)))
        db.commit()
        assert_analyze_only_schema(temp)
        digest = semantic_digest(temp)
        db.execute("INSERT INTO semantic_digest VALUES('SHA-256',1,?)", (digest,)); db.commit()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        fk = db.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or fk: raise ValueError(f"SQLite validation failed: {integrity}, fk={len(fk)}")
        db.close(); temp.replace(output_path)
        return {"sources": len(records), "notes": note_total, "exact_notes": exact_total,
                "semantic_digest": digest, "capability": "ANALYZE_ONLY"}
    except Exception:
        db.close(); temp.unlink(missing_ok=True); raise