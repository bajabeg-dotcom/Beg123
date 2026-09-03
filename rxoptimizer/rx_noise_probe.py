"""Generate explicitly unverified Pa800 RX Noise hardware probe MIDI files."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .midi import Event, encode_midi, parse_midi, validate_midi


SCHEMA = """
CREATE TABLE IF NOT EXISTS probe_batches(
 id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, source_count INTEGER NOT NULL,
 candidate_count INTEGER NOT NULL, file_count INTEGER NOT NULL, policy TEXT NOT NULL,
 fingerprint TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS probe_files(
 id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES probe_batches(id),
 source_name TEXT NOT NULL, source_sha256 TEXT NOT NULL, output_name TEXT NOT NULL UNIQUE,
 output_sha256 TEXT NOT NULL, profile_name TEXT NOT NULL, articulation TEXT NOT NULL,
 bank_msb INTEGER NOT NULL, bank_lsb INTEGER NOT NULL, program INTEGER NOT NULL,
 channel INTEGER NOT NULL, channel_reused INTEGER NOT NULL, key_min INTEGER NOT NULL,
 key_max INTEGER NOT NULL, velocities_json TEXT NOT NULL, evidence_status TEXT NOT NULL,
 result_status TEXT NOT NULL DEFAULT 'pending_hardware', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS probe_steps(
 id INTEGER PRIMARY KEY, probe_file_id INTEGER NOT NULL REFERENCES probe_files(id) ON DELETE CASCADE,
 sequence_index INTEGER NOT NULL, tick INTEGER NOT NULL, note INTEGER NOT NULL,
 velocity INTEGER NOT NULL, UNIQUE(probe_file_id,sequence_index));
CREATE TABLE IF NOT EXISTS probe_results(
 id INTEGER PRIMARY KEY, probe_file_id INTEGER NOT NULL REFERENCES probe_files(id),
 status TEXT NOT NULL CHECK(status IN('confirmed','rejected','partial')),
 confirmed_notes_json TEXT NOT NULL DEFAULT '[]', rejected_notes_json TEXT NOT NULL DEFAULT '[]',
 comments TEXT NOT NULL DEFAULT '', device TEXT NOT NULL DEFAULT 'Korg Pa800',
 created_at TEXT NOT NULL);
"""


def connect_probe_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys=ON")
    database.executescript(SCHEMA)
    columns={row[1] for row in database.execute("PRAGMA table_info(probe_batches)")}
    if "fingerprint" not in columns:
        database.execute("ALTER TABLE probe_batches ADD COLUMN fingerprint TEXT")
    database.commit()
    return database


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")[:90] or "midi"


def _probe_output_name(source_name: str, profile_name: str, digest: str) -> str:
    base=_slug(f"{Path(source_name).stem}__RX_NOISE_PROBE__{profile_name}")[:92]
    return f"{base}__{digest[:10]}.mid"


def load_noise_candidates(factory_db: Path) -> list[dict]:
    database = sqlite3.connect(factory_db)
    database.row_factory = sqlite3.Row
    rows = [dict(row) for row in database.execute("""
        SELECT rz.profile_name,rz.oscillator,rz.articulation,rz.velocity_min,rz.velocity_max,
               rz.key_min,rz.key_max,rz.switch_value,rz.notes,
               vc.bank_msb,vc.bank_lsb,vc.program
        FROM rx_zones rz JOIN pa800_voice_catalog vc ON vc.name=rz.profile_name
        WHERE lower(rz.articulation) LIKE '%noise%'
        ORDER BY rz.profile_name,rz.oscillator
    """)]
    database.close()
    for row in rows:
        row["evidence_status"] = "UNVERIFIED_HARDWARE_PROBE"
    return rows


def _probe_channel(midi) -> tuple[int, bool]:
    used = {int(event.channel) for track in midi.tracks for event in track if event.channel is not None}
    free = [channel for channel in range(16) if channel != 9 and channel not in used]
    return (free[0], False) if free else (15, True)


def _build_probe(source, candidate: dict, velocities: tuple[int, ...]):
    midi = deepcopy(source)
    end_tick = max((event.tick for track in midi.tracks for event in track), default=0)
    bar = max(1, midi.division * 4)
    start = ((end_tick + bar - 1) // bar + 1) * bar
    channel, reused = _probe_channel(midi)
    duration = max(1, midi.division // 8)
    gap = max(1, midi.division // 8)
    events = [
        Event(start, 0, "meta", data1=3, raw=f"RX NOISE PROBE {candidate['profile_name']}".encode()),
        Event(start, 1, "meta", data1=1, raw=b"UNVERIFIED HARDWARE PROBE"),
        Event(start, 2, "control", channel, 0, int(candidate["bank_msb"]), 0xB0 | channel),
        Event(start, 3, "control", channel, 32, int(candidate["bank_lsb"]), 0xB0 | channel),
        Event(start, 4, "program", channel, int(candidate["program"]), None, 0xC0 | channel),
    ]
    steps = []
    tick = start + midi.division
    sequence = 0
    for note in range(int(candidate["key_min"]), int(candidate["key_max"]) + 1):
        for velocity in velocities:
            events.append(Event(tick, 10 + sequence * 2, "note_on", channel, note, velocity, 0x90 | channel))
            events.append(Event(tick + duration, 11 + sequence * 2, "note_off", channel, note, 0, 0x80 | channel))
            steps.append({"sequence_index": sequence, "tick": tick, "note": note, "velocity": velocity})
            sequence += 1
            tick += duration + gap
    midi.tracks.append(events)
    return midi, steps, channel, reused


def _write_support_files(output_dir: Path, manifest: dict) -> None:
    (output_dir / "rx-noise-probe-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lines=["probe_file_id,source,profile,msb,lsb,program_raw,program_ui,status,confirmed_notes,rejected_notes,comments"]
    for row in manifest["files"]:
        address=row["address"]
        values=[row["probe_file_id"],row["source"],row["profile"],*address,int(address[2])+1,"pending_hardware","","",""]
        lines.append(",".join('"'+str(value).replace('"','""')+'"' for value in values))
    (output_dir / "RX_NOISE_CONFIRMATION.csv").write_text("\n".join(lines)+"\n",encoding="utf-8")
    (output_dir / "RX_NOISE_TEST_GUIDE.md").write_text("""# Korg Pa800 RX Noise probe test

Svaki fajl je **UNVERIFIED hardware probe**, a ne potvrđena RX artikulacija.

1. Učitaj jedan probe MIDI na Pa800 i pusti pjesmu do kraja.
2. Poslije jedne prazne mjere počinje track `RX NOISE PROBE <Sound>`.
3. Redom se testiraju MIDI note 96–127. Svaka nota se ponavlja na velocity 1, 42, 84 i 127.
4. Zapiši koje `nota:velocity` kombinacije stvarno proizvode noise, slide, release, mute ili drugi zvuk.
5. U GUI unesi `Probe file ID`, status i liste potvrđenih/odbačenih događaja, na primjer `96:42,96:84`.
6. `confirmed` koristi samo kada je cijeli raspon jasno provjeren; inače koristi `partial`.

Program u manifestu je zapisan i kao MIDI 0–127 vrijednost. Ako Pa800/sequencer prikazuje 1–128, koristi `program_ui = program_raw + 1`.

Rezultat ne ulazi u produkcijski RX engine dok nije sačuvan kao fizički Pa800 dokaz.
""",encoding="utf-8")


def generate_probe_pack(sources: list[tuple[str, bytes]], factory_db: Path, output_dir: Path,
                        probe_db: Path, velocities=(1, 42, 84, 127)) -> dict:
    candidates = load_noise_candidates(factory_db)
    if not candidates:
        raise ValueError("Nema RX Noise kandidata u katalogu/zonskoj bazi")
    velocities = tuple(sorted({max(1, min(127, int(value))) for value in velocities}))
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    database = connect_probe_database(probe_db)
    source_hashes=[(name,hashlib.sha256(data).hexdigest()) for name,data in sources]
    fingerprint=hashlib.sha256(json.dumps({"sources":source_hashes,"candidates":candidates,"velocities":velocities},
        sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    existing=database.execute("SELECT id FROM probe_batches WHERE fingerprint=?",(fingerprint,)).fetchone()
    if existing:
        batch_id=existing[0]
        files=[dict(row) for row in database.execute("SELECT * FROM probe_files WHERE batch_id=? ORDER BY id",(batch_id,))]
        for row in files:
            corrected=_probe_output_name(row["source_name"],row["profile_name"],row["output_sha256"])
            if row["output_name"]!=corrected:
                old=output_dir/row["output_name"];new=output_dir/corrected
                if old.exists() and not new.exists():old.replace(new)
                database.execute("UPDATE probe_files SET output_name=? WHERE id=?",(corrected,row["id"]))
                row["output_name"]=corrected
        database.commit()
        manifest={"batch_id":batch_id,"created_at":created_at,"policy":"hardware_probe_only","sources":len(sources),
            "candidates":len(candidates),"files":[{"probe_file_id":row["id"],"source":row["source_name"],"output":row["output_name"],
            "profile":row["profile_name"],"articulation":row["articulation"],"address":[row["bank_msb"],row["bank_lsb"],row["program"]],
            "channel":row["channel"],"channel_reused":bool(row["channel_reused"]),"key_range":[row["key_min"],row["key_max"]],
            "velocities":json.loads(row["velocities_json"]),"steps":database.execute("SELECT COUNT(*) FROM probe_steps WHERE probe_file_id=?",(row["id"],)).fetchone()[0],
            "evidence_status":row["evidence_status"],"sha256":row["output_sha256"]} for row in files]}
        database.close();_write_support_files(output_dir,manifest)
        return {"batch_id":batch_id,"sources":len(sources),"candidates":len(candidates),"files_created":0,
            "files_reused":len(files),"steps_per_file":(int(candidates[0]["key_max"])-int(candidates[0]["key_min"])+1)*len(velocities),
            "output_dir":str(output_dir),"manifest":str(output_dir/"rx-noise-probe-manifest.json")}
    legacy=database.execute("SELECT id FROM probe_batches WHERE fingerprint IS NULL AND source_count=? AND candidate_count=? AND file_count=? ORDER BY id DESC LIMIT 1",
        (len(sources),len(candidates),len(sources)*len(candidates))).fetchone()
    if legacy:
        database.execute("UPDATE probe_batches SET fingerprint=? WHERE id=?",(fingerprint,legacy[0]));database.commit();database.close()
        return generate_probe_pack(sources,factory_db,output_dir,probe_db,velocities)
    batch = database.execute("INSERT INTO probe_batches(created_at,source_count,candidate_count,file_count,policy,fingerprint) VALUES(?,?,?,?,?,?)",
        (created_at, len(sources), len(candidates), len(sources) * len(candidates),
         "UNVERIFIED; isolated hardware discovery; never training evidence before confirmation",fingerprint))
    batch_id = batch.lastrowid
    manifest_files = []
    for source_name, source_data in sources:
        source = parse_midi(source_data)
        source_sha = hashlib.sha256(source_data).hexdigest()
        source_validation = validate_midi(source)
        for candidate in candidates:
            probe, steps, channel, reused = _build_probe(source, candidate, velocities)
            encoded = encode_midi(probe)
            validation = validate_midi(parse_midi(encoded))
            source_unmatched=source_validation["unmatched_note_on"]+source_validation["unmatched_note_off"]
            output_unmatched=validation["unmatched_note_on"]+validation["unmatched_note_off"]
            if (validation["invalid_values"] > source_validation["invalid_values"] or
                    output_unmatched > source_unmatched):
                database.close()
                raise ValueError(f"RX Noise probe MIDI validation failed: {source_name} / {candidate['profile_name']}")
            digest = hashlib.sha256(encoded).hexdigest()
            output_name = _probe_output_name(source_name,candidate["profile_name"],digest)
            target = output_dir / output_name
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(encoded)
            temporary.replace(target)
            cursor = database.execute("""INSERT INTO probe_files(
                batch_id,source_name,source_sha256,output_name,output_sha256,profile_name,articulation,
                bank_msb,bank_lsb,program,channel,channel_reused,key_min,key_max,velocities_json,
                evidence_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (batch_id,source_name,source_sha,output_name,digest,candidate["profile_name"],candidate["articulation"],
                 candidate["bank_msb"],candidate["bank_lsb"],candidate["program"],channel,int(reused),
                 candidate["key_min"],candidate["key_max"],json.dumps(velocities),candidate["evidence_status"],created_at))
            probe_file_id = cursor.lastrowid
            database.executemany("INSERT INTO probe_steps(probe_file_id,sequence_index,tick,note,velocity) VALUES(?,?,?,?,?)",
                [(probe_file_id, step["sequence_index"], step["tick"], step["note"], step["velocity"]) for step in steps])
            manifest_files.append({"probe_file_id": probe_file_id, "source": source_name, "output": output_name,
                "profile": candidate["profile_name"], "articulation": candidate["articulation"],
                "address": [candidate["bank_msb"], candidate["bank_lsb"], candidate["program"]],
                "channel": channel, "channel_reused": reused, "key_range": [candidate["key_min"], candidate["key_max"]],
                "velocities": list(velocities), "steps": len(steps), "evidence_status": candidate["evidence_status"],
                "sha256": digest})
    database.commit()
    database.close()
    manifest = {"batch_id": batch_id, "created_at": created_at, "policy": "hardware_probe_only",
        "sources": len(sources), "candidates": len(candidates), "files": manifest_files}
    _write_support_files(output_dir,manifest)
    steps_per_file=(int(candidates[0]["key_max"])-int(candidates[0]["key_min"])+1)*len(velocities)
    return {"batch_id": batch_id, "sources": len(sources), "candidates": len(candidates),
        "files_created": len(manifest_files), "steps_per_file": steps_per_file,
        "output_dir": str(output_dir), "manifest": str(output_dir / "rx-noise-probe-manifest.json")}


def record_probe_result(path: Path, probe_file_id: int, status: str, confirmed_notes=None,
                        rejected_notes=None, comments: str = "") -> dict:
    if status not in ("confirmed", "rejected", "partial"):
        raise ValueError("status mora biti confirmed, rejected ili partial")
    database = connect_probe_database(path)
    row = database.execute("SELECT id FROM probe_files WHERE id=?", (int(probe_file_id),)).fetchone()
    if row is None:
        database.close()
        raise ValueError("Nepoznat RX Noise probe_file_id")
    database.execute("INSERT INTO probe_results(probe_file_id,status,confirmed_notes_json,rejected_notes_json,comments,created_at) VALUES(?,?,?,?,?,?)",
        (int(probe_file_id), status, json.dumps(confirmed_notes or []), json.dumps(rejected_notes or []), comments,
         datetime.now(timezone.utc).isoformat()))
    database.execute("UPDATE probe_files SET result_status=? WHERE id=?", (status, int(probe_file_id)))
    database.commit()
    result = dict(database.execute("SELECT * FROM probe_files WHERE id=?", (int(probe_file_id),)).fetchone())
    database.close()
    return result


def probe_status(path: Path) -> dict:
    database = connect_probe_database(path)
    counts = dict(database.execute("SELECT result_status,COUNT(*) FROM probe_files GROUP BY result_status").fetchall())
    latest = database.execute("SELECT * FROM probe_batches ORDER BY id DESC LIMIT 1").fetchone()
    database.close()
    return {"latest_batch": dict(latest) if latest else None, "results": counts}