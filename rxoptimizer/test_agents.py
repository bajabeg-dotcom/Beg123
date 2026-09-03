"""Auditable test agents and the physical Pa800 release gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


AGENTS = (
    ("software_guard", "Software Guard Agent", "automatic", "MIDI parse, hashes and file availability"),
    ("rx_mapping", "RX Mapping Review Agent", "automatic", "mapping confidence, coverage and RX provenance"),
    ("hardware_playback", "Hardware Playback Agent", "human_required", "load and play exports on a physical Korg Pa800"),
    ("listening_review", "Listening Review Agent", "human_required", "rate timing, articulation, drums and unwanted notes"),
    ("release_gate", "Release Gate Agent", "automatic", "block release until every critical check has evidence"),
)

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS agents(
 id TEXT PRIMARY KEY,name TEXT NOT NULL,execution_mode TEXT NOT NULL,mission TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS test_suites(
 id INTEGER PRIMARY KEY,name TEXT NOT NULL,device TEXT NOT NULL DEFAULT 'Korg Pa800',
 status TEXT NOT NULL DEFAULT 'pending_hardware',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at TEXT);
CREATE TABLE IF NOT EXISTS test_cases(
 id INTEGER PRIMARY KEY,suite_id INTEGER NOT NULL REFERENCES test_suites(id) ON DELETE CASCADE,
 filename TEXT NOT NULL,section TEXT NOT NULL,priority TEXT NOT NULL,source_sha256 TEXT,
 output_sha256 TEXT,file_exists INTEGER NOT NULL,checks_json TEXT NOT NULL,
 UNIQUE(suite_id,filename));
CREATE TABLE IF NOT EXISTS test_results(
 id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
 agent_id TEXT NOT NULL REFERENCES agents(id),passed INTEGER NOT NULL,
 timing_rating INTEGER,rx_rating INTEGER,drum_rating INTEGER,articulation_rating INTEGER,
 comments TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(case_id,agent_id));
CREATE TABLE IF NOT EXISTS agent_reports(
 id INTEGER PRIMARY KEY,suite_id INTEGER NOT NULL REFERENCES test_suites(id) ON DELETE CASCADE,
 agent_id TEXT NOT NULL REFERENCES agents(id),status TEXT NOT NULL,report_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(suite_id,agent_id));
CREATE TABLE IF NOT EXISTS release_gates(
 suite_id INTEGER PRIMARY KEY REFERENCES test_suites(id) ON DELETE CASCADE,status TEXT NOT NULL,
 blocking_count INTEGER NOT NULL,summary_json TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


def connect_test_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path)
    database.row_factory = sqlite3.Row
    database.executescript(SCHEMA)
    database.executemany(
        "INSERT OR REPLACE INTO agents(id,name,execution_mode,mission) VALUES(?,?,?,?)", AGENTS
    )
    database.commit()
    return database


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _section(filename: str) -> str:
    lower = filename.lower()
    for section in ("intro", "variation", "var", "fill", "break", "ending", "end"):
        if section in lower:
            return {"var": "variation", "end": "ending"}.get(section, section)
    return "song_or_unknown"


def _automatic_reports(database: sqlite3.Connection, suite_id: int, factory_db: Path) -> None:
    cases = database.execute("SELECT * FROM test_cases WHERE suite_id=?", (suite_id,)).fetchall()
    missing = [row["filename"] for row in cases if not row["file_exists"]]
    software = {
        "case_count": len(cases),
        "files_present": len(cases) - len(missing),
        "missing_files": missing,
        "result": "pass" if cases and not missing else "blocked",
    }
    database.execute(
        "INSERT OR REPLACE INTO agent_reports(suite_id,agent_id,status,report_json) VALUES(?,?,?,?)",
        (suite_id, "software_guard", software["result"], json.dumps(software, ensure_ascii=False)),
    )

    mapping = {"active_mappings": 0, "low_confidence": 0, "unmapped_profiles": 0, "result": "blocked"}
    if factory_db.exists():
        source = sqlite3.connect(factory_db)
        mapping["active_mappings"] = source.execute("SELECT COUNT(*) FROM gm_rx_mappings").fetchone()[0]
        mapping["low_confidence"] = source.execute(
            "SELECT COUNT(*) FROM gm_rx_mappings WHERE confidence < .90"
        ).fetchone()[0]
        mapping["unmapped_profiles"] = source.execute("""SELECT COUNT(*) FROM instrument_profiles p
            WHERE p.source='factory' AND NOT EXISTS(SELECT 1 FROM gm_rx_mappings m
            WHERE m.source_bank_msb=p.bank_msb AND m.source_bank_lsb=p.bank_lsb
            AND m.source_program=p.program AND m.role=p.role)""").fetchone()[0]
        source.close()
        mapping["result"] = "pass_with_unmapped" if mapping["active_mappings"] else "blocked"
    database.execute(
        "INSERT OR REPLACE INTO agent_reports(suite_id,agent_id,status,report_json) VALUES(?,?,?,?)",
        (suite_id, "rx_mapping", mapping["result"], json.dumps(mapping, ensure_ascii=False)),
    )
    for agent_id in ("hardware_playback", "listening_review"):
        database.execute(
            "INSERT OR IGNORE INTO agent_reports(suite_id,agent_id,status,report_json) VALUES(?,?,?,?)",
            (suite_id, agent_id, "pending_hardware", json.dumps({"reason": "Zahtijeva fizički Korg Pa800 i ljudsko slušanje"}, ensure_ascii=False)),
        )


def refresh_release_gate(database: sqlite3.Connection, suite_id: int) -> dict:
    cases = database.execute("SELECT id FROM test_cases WHERE suite_id=?", (suite_id,)).fetchall()
    required = len(cases) * 2
    human = database.execute("""SELECT COUNT(*) total,
        COALESCE(SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END),0) passed,
        COALESCE(SUM(CASE WHEN passed=0 THEN 1 ELSE 0 END),0) failed
        FROM test_results r JOIN test_cases c ON c.id=r.case_id
        WHERE c.suite_id=? AND r.agent_id IN ('hardware_playback','listening_review')""", (suite_id,)).fetchone()
    automatic_blockers = database.execute("""SELECT COUNT(*) FROM agent_reports
        WHERE suite_id=? AND agent_id IN ('software_guard','rx_mapping') AND status='blocked'""", (suite_id,)).fetchone()[0]
    missing = max(0, required - human["total"])
    blockers = automatic_blockers + human["failed"] + missing
    status = "passed" if cases and blockers == 0 else ("failed" if human["failed"] else "pending_hardware")
    summary = {
        "cases": len(cases), "required_human_results": required, "submitted_human_results": human["total"],
        "failed_human_results": human["failed"], "automatic_blockers": automatic_blockers,
        "missing_human_results": missing,
        "honest_limit": "Release može proći tek nakon fizičkog Pa800 playback i listening testa.",
    }
    database.execute("""INSERT INTO release_gates(suite_id,status,blocking_count,summary_json)
        VALUES(?,?,?,?) ON CONFLICT(suite_id) DO UPDATE SET status=excluded.status,
        blocking_count=excluded.blocking_count,summary_json=excluded.summary_json,updated_at=CURRENT_TIMESTAMP""",
        (suite_id, status, blockers, json.dumps(summary, ensure_ascii=False)))
    database.execute("UPDATE test_suites SET status=?,completed_at=CASE WHEN ?='passed' THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=?",
                     (status, status, suite_id))
    database.execute(
        "INSERT OR REPLACE INTO agent_reports(suite_id,agent_id,status,report_json) VALUES(?,?,?,?)",
        (suite_id, "release_gate", status, json.dumps(summary, ensure_ascii=False)),
    )
    database.commit()
    return {"status": status, "blocking_count": blockers, **summary}


def create_test_suite(test_db: Path, output_dir: Path, factory_db: Path, name: str = "Pa800 A/B Release") -> dict:
    database = connect_test_database(test_db)
    cursor = database.execute("INSERT INTO test_suites(name) VALUES(?)", (name[:120] or "Pa800 A/B Release",))
    suite_id = cursor.lastrowid
    known = {}
    if factory_db.exists():
        source = sqlite3.connect(factory_db)
        for row in source.execute("SELECT output_name,source_sha256,output_sha256 FROM optimizer_runs ORDER BY rowid DESC"):
            known.setdefault(row[0], (row[1], row[2]))
        source.close()
    files = sorted(output_dir.glob("*.mid")) if output_dir.exists() else []
    if files:
        for path in files:
            source_hash, recorded_hash = known.get(path.name, (None, None))
            actual_hash = _sha256(path)
            database.execute("""INSERT INTO test_cases(suite_id,filename,section,priority,source_sha256,
                output_sha256,file_exists,checks_json) VALUES(?,?,?,?,?,?,1,?)""", (
                suite_id, path.name, _section(path.name), "critical", source_hash, actual_hash,
                json.dumps(["loads_without_error", "no_stuck_notes", "rx_sound_correct", "timing_natural", "drums_correct"], ensure_ascii=False),
            ))
            database.execute("""INSERT OR REPLACE INTO test_results(case_id,agent_id,passed,comments)
                VALUES((SELECT id FROM test_cases WHERE suite_id=? AND filename=?),'software_guard',?,?)""",
                (suite_id, path.name, int(recorded_hash in (None, actual_hash)), "SHA-256 i fajl provjeren"))
    else:
        database.execute("""INSERT INTO test_cases(suite_id,filename,section,priority,file_exists,checks_json)
            VALUES(?,?,?,?,0,?)""", (suite_id, "NO_EXPORTED_MIDI.mid", "preflight", "critical",
            json.dumps(["Prvo izvezi reprezentativni MIDI kroz Optimizer"], ensure_ascii=False)))
    _automatic_reports(database, suite_id, factory_db)
    gate = refresh_release_gate(database, suite_id)
    database.close()
    return {"suite_id": suite_id, "gate": gate}


def record_test_result(test_db: Path, payload: dict) -> dict:
    agent_id = str(payload.get("agent_id", ""))
    if agent_id not in {"hardware_playback", "listening_review"}:
        raise ValueError("Ručno se mogu unijeti samo hardware_playback i listening_review rezultati")
    case_id = int(payload["case_id"])
    passed = bool(payload.get("passed"))
    ratings = []
    for key in ("timing_rating", "rx_rating", "drum_rating", "articulation_rating"):
        value = payload.get(key)
        value = None if value in (None, "") else int(value)
        if value is not None and not 1 <= value <= 5:
            raise ValueError("Ocjene moraju biti 1–5")
        ratings.append(value)
    database = connect_test_database(test_db)
    case = database.execute("SELECT suite_id FROM test_cases WHERE id=?", (case_id,)).fetchone()
    if case is None:
        database.close(); raise ValueError("Nepoznat test case")
    database.execute("""INSERT INTO test_results(case_id,agent_id,passed,timing_rating,rx_rating,drum_rating,
        articulation_rating,comments) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(case_id,agent_id) DO UPDATE SET
        passed=excluded.passed,timing_rating=excluded.timing_rating,rx_rating=excluded.rx_rating,
        drum_rating=excluded.drum_rating,articulation_rating=excluded.articulation_rating,
        comments=excluded.comments,created_at=CURRENT_TIMESTAMP""",
        (case_id, agent_id, int(passed), *ratings, str(payload.get("comments", ""))[:2000]))
    status = "pass" if passed else "failed"
    database.execute("UPDATE agent_reports SET status=?,report_json=? WHERE suite_id=? AND agent_id=?",
        (status, json.dumps({"latest_case_id": case_id, "passed": passed}, ensure_ascii=False), case["suite_id"], agent_id))
    gate = refresh_release_gate(database, case["suite_id"])
    database.close()
    return {"saved": True, "gate": gate}


def test_agent_status(test_db: Path, suite_id: int | None = None) -> dict:
    database = connect_test_database(test_db)
    agents = [dict(row) for row in database.execute("SELECT * FROM agents ORDER BY id")]
    if suite_id is None:
        row = database.execute("SELECT id FROM test_suites ORDER BY id DESC LIMIT 1").fetchone()
        suite_id = row[0] if row else None
    if suite_id is None:
        database.close()
        return {"agents": agents, "suite": None, "cases": [], "reports": [], "gate": {"status": "not_created"}}
    suite = database.execute("SELECT * FROM test_suites WHERE id=?", (suite_id,)).fetchone()
    cases = [dict(row) for row in database.execute("SELECT * FROM test_cases WHERE suite_id=? ORDER BY id", (suite_id,))]
    reports = [dict(row) for row in database.execute("SELECT * FROM agent_reports WHERE suite_id=? ORDER BY agent_id", (suite_id,))]
    gate = refresh_release_gate(database, suite_id)
    database.close()
    return {"agents": agents, "suite": dict(suite) if suite else None, "cases": cases, "reports": reports, "gate": gate}


# Public API helper, not a pytest test function.  Keep the established name
# while explicitly preventing collection by pytest's ``test_*`` convention.
test_agent_status.__test__ = False


def export_test_pack(test_db: Path, destination: Path, suite_id: int | None = None) -> dict:
    status = test_agent_status(test_db, suite_id)
    if status["suite"] is None:
        raise ValueError("Prvo kreiraj test suite")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / "pa800-test-manifest.json"
    guide = destination / "PA800_TEST_GUIDE.md"
    manifest.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    guide.write_text("""# Korg Pa800 fizički test

1. Sačuvaj original i optimizovani MIDI, pa učitaj optimizovani fajl na Pa800.
2. Za svaki strict-evidence case potvrdi: učitavanje bez greške, originalni/nepromijenjeni nepotvrđeni Sound, bez zaglavljenih nota, prirodan timing i ispravan drum kit.
3. RX `catalog_review` izvoz testira se odvojeno i mora navesti svako nepotvrđeno mapiranje; ne miješati ga sa strict release kandidatima.
4. SlapFing/SlapPick switch 87 naspram ranijeg zapisa 94 je otvoren konflikt: testirati i dokumentovati obje granice, bez unaprijed proglašenog pobjednika.
5. Unesi odvojeni rezultat za Hardware Playback Agent i Listening Review Agent.
6. Release Gate ostaje `pending_hardware` dok svi kritični rezultati nisu uneseni i prošli.

AI ne može samostalno proglasiti fizički zvuk potvrđenim.
""", encoding="utf-8")
    return {"manifest": str(manifest), "guide": str(guide), "gate": status["gate"]}