"""Atomic immutable RAW / mutable application-state snapshot layout."""

from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3


RAW_TABLES=("midi_files","instrument_profiles","track_stats","performance_features","instrument_segments")
STATE_TABLES=("pa800_voice_catalog","rx_zones","gm_rx_mappings","project_plans","optimizer_runs","import_errors")


def _encode(value)->bytes:
    if value is None:return b"N"
    if isinstance(value,bytes):payload=value;tag=b"B"
    elif isinstance(value,int):payload=str(value).encode();tag=b"I"
    elif isinstance(value,float):payload=value.hex().encode();tag=b"F"
    else:payload=str(value).encode("utf-8");tag=b"T"
    return tag+len(payload).to_bytes(8,"big")+payload


def semantic_digest(path:Path,tables=RAW_TABLES)->str:
    db=sqlite3.connect(path);digest=sha256()
    try:
        existing={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in tables:
            if table not in existing:continue
            columns=[row[1] for row in db.execute(f"PRAGMA table_info({table})")]
            digest.update(_encode(table));digest.update(_encode(columns))
            order="id" if "id" in columns else ",".join(columns)
            for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                for value in row:digest.update(_encode(value))
    finally:db.close()
    return digest.hexdigest()


def _drop_tables(path:Path,tables)->None:
    db=sqlite3.connect(path);db.execute("PRAGMA foreign_keys=OFF")
    for table in tables:db.execute(f"DROP TABLE IF EXISTS {table}")
    db.commit();db.execute("VACUUM");db.close()


def _counts(path:Path,tables)->dict:
    db=sqlite3.connect(path);result={}
    for table in tables:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
        if exists:result[table]=db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if "track_stats" in tables and "track_stats" in result:
        result["track_note_sum"]=db.execute("SELECT COALESCE(SUM(note_count),0) FROM track_stats").fetchone()[0]
    db.close();return result


def _integrity(path:Path)->tuple[str,int]:
    db=sqlite3.connect(path);integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys=len(db.execute("PRAGMA foreign_key_check").fetchall());db.close();return integrity,foreign_keys


def _prepare_state(factory_source:Path,gold_source:Path,target:Path)->None:
    shutil.copy2(factory_source,target)
    _drop_tables(target,("performance_features","instrument_segments","track_stats","instrument_profiles","midi_files"))
    db=sqlite3.connect(target)
    columns={row[1] for row in db.execute("PRAGMA table_info(import_errors)")}
    if "corpus" not in columns:db.execute("ALTER TABLE import_errors ADD COLUMN corpus TEXT NOT NULL DEFAULT 'factory'")
    if "source_error_id" not in columns:db.execute("ALTER TABLE import_errors ADD COLUMN source_error_id INTEGER")
    db.execute("UPDATE import_errors SET corpus='factory',source_error_id=COALESCE(source_error_id,id)")
    gold=sqlite3.connect(gold_source);gold.row_factory=sqlite3.Row
    if gold.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_errors'").fetchone():
        for row in gold.execute("SELECT id,filename,error,created_at FROM import_errors"):
            db.execute("INSERT INTO import_errors(filename,error,created_at,corpus,source_error_id) VALUES(?,?,?,?,?)",
                (row["filename"],row["error"],row["created_at"],"gold",row["id"]))
    gold.close();db.commit();db.close()


def migrate_split_layout(factory_source:Path,gold_source:Path,data_dir:Path)->dict:
    """Create an immutable generation and atomically swap a JSON pointer."""
    data_dir.mkdir(parents=True,exist_ok=True);generations=data_dir/"generations";generations.mkdir(exist_ok=True)
    source_counts={"factory":_counts(factory_source,RAW_TABLES),"gold":_counts(gold_source,RAW_TABLES)}
    for corpus,counts in source_counts.items():
        if counts.get("midi_files",0)<=0 or counts.get("track_stats",0)<=0:
            raise ValueError(
                f"Refusing empty {corpus} RAW snapshot: import/restore the authoritative corpus first"
            )
    factory_hash=semantic_digest(factory_source);gold_hash=semantic_digest(gold_source)
    state_source_hash=semantic_digest(factory_source,STATE_TABLES)
    generation_id=sha256(f"{factory_hash}:{gold_hash}:{state_source_hash}".encode()).hexdigest()[:20]
    final=generations/generation_id;temp=generations/(generation_id+".tmp")
    if not final.exists():
        if temp.exists():shutil.rmtree(temp)
        temp.mkdir()
        factory_raw=temp/"factory_raw.sqlite3";gold_raw=temp/"gold_raw.sqlite3";state=temp/"application_state.sqlite3"
        shutil.copy2(factory_source,factory_raw);_drop_tables(factory_raw,STATE_TABLES)
        shutil.copy2(gold_source,gold_raw);_drop_tables(gold_raw,STATE_TABLES)
        _prepare_state(factory_source,gold_source,state)
        expected={"factory":factory_hash,"gold":gold_hash}
        actual={"factory":semantic_digest(factory_raw),"gold":semantic_digest(gold_raw)}
        if actual!=expected:
            shutil.rmtree(temp);raise ValueError(f"RAW semantic parity failed: expected={expected}, actual={actual}")
        for path in (factory_raw,gold_raw,state):
            integrity,fk=_integrity(path)
            if integrity!="ok" or fk:
                shutil.rmtree(temp);raise ValueError(f"Layout integrity failed for {path.name}")
        os.chmod(factory_raw,0o444);os.chmod(gold_raw,0o444);temp.replace(final)
    layout={"schema_version":1,"generation_id":generation_id,"created_at":datetime.now(timezone.utc).isoformat(),
        "factory_raw":str((final/"factory_raw.sqlite3").relative_to(data_dir.parent)),
        "gold_raw":str((final/"gold_raw.sqlite3").relative_to(data_dir.parent)),
        "application_state":str((final/"application_state.sqlite3").relative_to(data_dir.parent)),
        "semantic_sha256":{"factory":factory_hash,"gold":gold_hash,"state_source":state_source_hash},
        "counts":{"factory":_counts(final/"factory_raw.sqlite3",RAW_TABLES),"gold":_counts(final/"gold_raw.sqlite3",RAW_TABLES),
                  "state":_counts(final/"application_state.sqlite3",STATE_TABLES)}}
    pointer=data_dir/"database-layout.json";pointer_temp=pointer.with_suffix(".json.tmp")
    pointer_temp.write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding="utf-8");pointer_temp.replace(pointer)
    return layout


def connect_raw(path:Path)->sqlite3.Connection:
    db=sqlite3.connect(f"file:{path}?mode=ro",uri=True);db.row_factory=sqlite3.Row;db.execute("PRAGMA query_only=ON");return db