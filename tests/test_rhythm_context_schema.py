import sqlite3

import pytest

from rxoptimizer.rhythm_context_models import SCHEMA, assert_analyze_only_schema


def test_schema_rejects_destructive_field(tmp_path):
    path = tmp_path / "unsafe.sqlite3"; db = sqlite3.connect(path)
    db.executescript("CREATE TABLE build_info(key TEXT PRIMARY KEY,value_json TEXT);"
        "INSERT INTO build_info VALUES('capability','\"ANALYZE_ONLY\"');"
        "INSERT INTO build_info VALUES('mutation_capability','\"NONE\"');"
        "CREATE TABLE unsafe(note_id TEXT,target_tick INTEGER);")
    db.commit(); db.close()
    with pytest.raises(ValueError, match="Forbidden"):
        assert_analyze_only_schema(path)


def test_schema_declares_no_mutation(tmp_path):
    path = tmp_path / "wrong.sqlite3"; db = sqlite3.connect(path)
    db.executescript("CREATE TABLE build_info(key TEXT PRIMARY KEY,value_json TEXT);"
        "INSERT INTO build_info VALUES('capability','\"ANALYZE_ONLY\"');"
        "INSERT INTO build_info VALUES('mutation_capability','\"WRITE\"');")
    db.commit(); db.close()
    with pytest.raises(ValueError, match="ANALYZE_ONLY"):
        assert_analyze_only_schema(path)


@pytest.mark.parametrize("identifier", ["target", "candidate_value", "proposalBlob", "repair",
    "approved_repair", "apply_now", "commit", "mutation_flag"])
def test_schema_rejects_bare_and_prefixed_destructive_identifiers(tmp_path, identifier):
    path = tmp_path / f"unsafe-{identifier}.sqlite3"; db = sqlite3.connect(path)
    db.executescript("CREATE TABLE build_info(key TEXT PRIMARY KEY,value_json TEXT);"
        "INSERT INTO build_info VALUES('capability','\"ANALYZE_ONLY\"');"
        "INSERT INTO build_info VALUES('mutation_capability','\"NONE\"');")
    db.execute(f'CREATE TABLE unsafe(note_id TEXT,"{identifier}" TEXT)')
    db.commit(); db.close()
    with pytest.raises(ValueError, match="Forbidden"):
        assert_analyze_only_schema(path)


def test_harmless_text_value_does_not_trigger_identifier_audit(tmp_path):
    path = tmp_path / "safe.sqlite3"; db = sqlite3.connect(path)
    db.executescript("CREATE TABLE build_info(key TEXT PRIMARY KEY,value_json TEXT);"
        "INSERT INTO build_info VALUES('capability','\"ANALYZE_ONLY\"');"
        "INSERT INTO build_info VALUES('mutation_capability','\"NONE\"');"
        "CREATE TABLE safe(note_id TEXT,description TEXT);"
        "INSERT INTO safe VALUES('n','repair is forbidden prose, not a field');")
    db.commit(); db.close()
    assert_analyze_only_schema(path)


@pytest.mark.parametrize("invalid_field", ["meter", "tempo"])
def test_note_context_rejects_unmaterialized_meter_and_tempo_segment_ids(tmp_path, invalid_field):
    path = tmp_path / f"invalid-{invalid_field}.sqlite3"; db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON"); db.executescript(SCHEMA)
    source = "1" * 64
    db.execute("INSERT INTO source_context VALUES(?,?,?,?,?,?)",
        (source, "factory", "Factory/Test.mid", "{}", '"NORMAL"', "ANALYZE_ONLY"))
    db.execute("INSERT INTO program_segments VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (source, 0, 0, "program-ok", None, 0, 0, 1, "PROGRAM_EXACT", "TIMELINE", "[]"))
    if invalid_field == "meter":
        meter_id = "meter-missing"
    else:
        meter_id = "meter-ok"
        db.execute("INSERT INTO meter_segments VALUES(?,?,?,?,?,?,?,?)",
            (source, 0, meter_id, None, 4, 4, "METER_EXACT", "[]"))
    if invalid_field == "tempo":
        tempo_id = "tempo-missing"
    else:
        tempo_id = "tempo-ok"
        db.execute("INSERT INTO tempo_segments VALUES(?,?,?,?,?,?,?,?)",
            (source, 0, tempo_id, None, 500000, "500000", "TEMPO_EXACT", "[]"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO note_context VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (source, "note-1", "on-1", "off-1", 0, 0, 60, 80, 0, 120, 120, 0, 0,
             "program-ok", meter_id, tempo_id, "{}", "PROTECTED_CONTEXT"))
    db.close()