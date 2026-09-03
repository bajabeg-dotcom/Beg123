#!/usr/bin/env python3
"""Local web application for Factory + Gold DNA MIDI analysis and GM-to-RX conversion."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import argparse
import sqlite3
from io import BytesIO
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib import request as urlrequest
from zipfile import ZipFile

from rxoptimizer.database import analyze_and_store, connect, rows, seed_pa800_catalog, seed_rx_zones
from rxoptimizer.features import GoldDNAModel, track_feature_from_dict
from rxoptimizer.mapping import catalog_rows, coverage_report, factory_profile_rows, recommend_mappings
from rxoptimizer.dna_databases import (
    build_all, build_optimizer_database, build_rx_database, build_voice_database,
    dna_status, load_performance_model, load_rx_rules, load_solo_models,
)
from rxoptimizer.webui import APP_JS, INDEX_HTML, STYLE_CSS
from rxoptimizer.midi import MidiError, encode_midi, parse_midi, validate_midi
from rxoptimizer.optimizer import optimize
from rxoptimizer.test_agents import (
    connect_test_database, create_test_suite, export_test_pack, record_test_result, test_agent_status,
)
from rxoptimizer.strumming import build_strumming_database, load_strumming_models
from rxoptimizer.song_dna import (
    apply_song_dna, build_delay_harmony_databases, build_gold_ornament_database,
    detect_delay_pairs, detect_harmony_pairs, load_models,load_delay_phrase_models,select_song_lead,
)
from rxoptimizer.sound_intelligence import build_sound_intelligence_database,load_sound_intelligence
from rxoptimizer.instrument_structure import load_instrument_structure
from rxoptimizer.instrument_identity import identities_compatible
from rxoptimizer.evidence import build_evidence_inventory
from rxoptimizer.evidence_registry import build_evidence_registry
from rxoptimizer.trill_dna import build_musical_intelligence_database,register_trill_observations
from rxoptimizer.database_layout import migrate_split_layout
from rxoptimizer.rhythm_validation import build_rhythm_validation_database
from rxoptimizer.rhythm_calibration import build_rhythm_calibration_database
from rxoptimizer.rhythm_consensus import build_rhythm_consensus_database
from rxoptimizer.rx_noise_probe import (
    connect_probe_database, generate_probe_pack, probe_status, record_probe_result,
)
from rxoptimizer.articulation_probe import (
    articulation_promotion_queue_status,build_articulation_promotion_queue,build_single_articulation_probes,
    file_articulation_probe_status,record_file_articulation_result,
)


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
STATIC = ROOT / "static"
FACTORY_DB = DATA / "factory.sqlite3"
GOLD_DB = DATA / "gold_dna.sqlite3"
RHYTHM_DB = DATA / "rhythm_dna.sqlite3"
PERFORMANCE_DB = DATA / "performance_dna.sqlite3"
VOICE_DB = DATA / "voice_dna.sqlite3"
RX_DB = DATA / "rx_dna.sqlite3"
SOLO_DB = DATA / "solo_dna.sqlite3"
STRUMMING_DB = DATA / "strumming_dna.sqlite3"
DELAY_DB = DATA / "delay_dna.sqlite3"
HARMONY_DB = DATA / "harmony_dna.sqlite3"
ORNAMENT_DB = DATA / "ornament_dna.sqlite3"
SOUND_INTELLIGENCE_DB = DATA / "sound_intelligence_dna.sqlite3"
INSTRUMENT_STRUCTURE_DB = DATA / "instrument_structure_dna.sqlite3"
OPTIMIZER_DB = DATA / "optimizer_dna.sqlite3"
HARDWARE_TEST_DB = DATA / "hardware_test_dna.sqlite3"
EVIDENCE_REGISTRY_DB = DATA / "evidence_registry.sqlite3"
MUSICAL_INTELLIGENCE_DB = DATA / "musical_intelligence_dna.sqlite3"
RX_NOISE_PROBE_DB = DATA / "rx_noise_probe.sqlite3"
HARDWARE_TESTS = ROOT / "hardware-tests"
RX_NOISE_PROBES = HARDWARE_TESTS / "rx-noise-probes"
ARTICULATION_PROBE_DB = DATA / "articulation_probe.sqlite3"
ARTICULATION_PROBES = HARDWARE_TESTS / "single-articulation-probes"
ARTICULATION_MANIFEST = ARTICULATION_PROBES / "single-articulation-manifest.json"
ARTICULATION_RESULTS = ARTICULATION_PROBES / "articulation-results.json"
ARTICULATION_PROMOTION_QUEUE = ARTICULATION_PROBES / "evidence-promotion-queue.json"
RHYTHM_VALIDATION_DB = DATA / "rhythm_validation.sqlite3"
RHYTHM_CALIBRATION_DB = DATA / "rhythm_calibration.sqlite3"
RHYTHM_CONSENSUS_DB = DATA / "rhythm_consensus.sqlite3"
MAX_BODY = 32 * 1024 * 1024
SONG_REFERENCE_FILENAMES = (
    "Danima te cekam - Saban Saulic ).mid",
    "Dao bih ovo malo zivota - Milance Radosavljevic ).mid",
    "Dao sam ti dusu - Gm Alen Slavica ).mid",
    "Devet hiljada metara - Zeljko Samardzic ).mid",
    "Disem za tebe - Sako Polumenta ).mid",
    "Dva galeba bela - Saban Saulic ).mid",
)


def init_app() -> None:
    DATA.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    for corpus in ("factory", "gold"):
        (DATA / corpus).mkdir(exist_ok=True)
    with connect(FACTORY_DB) as database:
        seed_rx_zones(database)
        seed_pa800_catalog(database)
    with connect(GOLD_DB):
        pass
    with connect_test_database(HARDWARE_TEST_DB):
        pass
    with connect_probe_database(RX_NOISE_PROBE_DB):
        pass


def safe_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    return clean[:120] or "upload.mid"


def decode_midi_payload(payload: dict) -> tuple[str, bytes]:
    filename = safe_filename(str(payload.get("filename", "upload.mid")))
    if Path(filename).suffix.lower() not in (".mid", ".midi"):
        raise ValueError("MVP prihvata .mid i .midi fajlove")
    try:
        data = base64.b64decode(payload["data_base64"], validate=True)
    except Exception as error:
        raise ValueError("Nevažeći base64 MIDI sadržaj") from error
    if not data or len(data) > MAX_BODY:
        raise ValueError("MIDI fajl je prazan ili prevelik")
    return filename, data


def import_midi(payload: dict) -> dict:
    corpus = payload.get("corpus")
    if corpus not in ("factory", "gold"):
        raise ValueError("Corpus mora biti factory ili gold")
    filename, data = decode_midi_payload(payload)
    midi = parse_midi(data)
    source_validation=validate_midi(midi)
    digest = hashlib.sha256(data).hexdigest()
    db_path = FACTORY_DB if corpus == "factory" else GOLD_DB
    stored = DATA / corpus / f"{digest[:12]}-{filename}"
    with connect(db_path) as database:
        existing = database.execute("SELECT id FROM midi_files WHERE sha256=?", (digest,)).fetchone()
        if existing:
            return {"deduplicated": True, "file_id": existing[0], "sha256": digest}
        cursor = database.execute(
            "INSERT INTO midi_files(filename, sha256, midi_format, division, track_count) VALUES(?,?,?,?,?)",
            (filename, digest, midi.format, midi.division, len(midi.tracks)),
        )
        analyze_and_store(database, cursor.lastrowid, midi, corpus)
        if corpus == "factory":
            refresh_mapping_recommendations(database)
        stats = rows(database, "SELECT * FROM track_stats WHERE file_id=?", (cursor.lastrowid,))
        temp=stored.with_suffix(stored.suffix+".tmp"); temp.write_bytes(data); temp.replace(stored)
    return {"deduplicated": False, "file_id": cursor.lastrowid, "sha256": digest, "track_stats": stats}


def import_dna_archive(path: Path) -> dict:
    """Expand nested DNA.zip directly into both databases without extracting files."""
    totals = {"factory": {"imported": 0, "duplicate": 0, "errors": 0}, "gold": {"imported": 0, "duplicate": 0, "errors": 0}}
    with ZipFile(path) as outer:
        for nested_name in outer.namelist():
            lower = nested_name.lower()
            corpus = "gold" if "gold" in lower else "factory" if "factory" in lower else None
            if not corpus or not lower.endswith(".zip"):
                continue
            db_path = GOLD_DB if corpus == "gold" else FACTORY_DB
            with ZipFile(BytesIO(outer.read(nested_name))) as archive, connect(db_path) as database:
                for info in archive.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid", ".midi"):
                        continue
                    try:
                        data = archive.read(info)
                        digest = hashlib.sha256(data).hexdigest()
                        existing = database.execute("SELECT id FROM midi_files WHERE sha256=?", (digest,)).fetchone()
                        if existing:
                            totals[corpus]["duplicate"] += 1
                            continue
                        midi = parse_midi(data)
                        cursor = database.execute(
                            "INSERT INTO midi_files(filename,sha256,midi_format,division,track_count) VALUES(?,?,?,?,?)",
                            (info.filename, digest, midi.format, midi.division, len(midi.tracks)),
                        )
                        analyze_and_store(database, cursor.lastrowid, midi, corpus)
                        totals[corpus]["imported"] += 1
                    except Exception as error:
                        database.execute("INSERT INTO import_errors(filename,error) VALUES(?,?)", (info.filename, str(error)))
                        totals[corpus]["errors"] += 1
                if corpus == "factory":
                    refresh_mapping_recommendations(database)
                database.commit()
    totals["dna"] = build_all(FACTORY_DB,GOLD_DB,DATA)
    totals["dna"]["strumming"] = build_strumming_database(path,STRUMMING_DB)
    totals["dna"]["song_layers"] = build_delay_harmony_databases(song_midi_paths(),DELAY_DB,HARMONY_DB)
    totals["dna"]["ornament"] = build_gold_ornament_database(path,ORNAMENT_DB)
    totals["dna"]["sound_intelligence"] = build_sound_intelligence_database(FACTORY_DB,GOLD_DB,path,SOUND_INTELLIGENCE_DB)
    inventory=build_evidence_inventory(Path("."),Path("analysis/evidence_inventory.json"))
    totals["dna"]["evidence_registry"]=build_evidence_registry(Path("analysis/evidence_inventory.json"),FACTORY_DB,EVIDENCE_REGISTRY_DB)
    totals["dna"]["musical_intelligence"]=build_musical_intelligence_database(path,song_midi_paths(),MUSICAL_INTELLIGENCE_DB)
    totals["dna"]["trill_registry"]=register_trill_observations(EVIDENCE_REGISTRY_DB,MUSICAL_INTELLIGENCE_DB)
    totals["layout"]=migrate_split_layout(FACTORY_DB,GOLD_DB,DATA)
    totals["rhythm_validation"]=build_rhythm_validation_database(path,FACTORY_DB,GOLD_DB,RHYTHM_VALIDATION_DB)
    totals["rhythm_calibration"]=build_rhythm_calibration_database(path,RHYTHM_VALIDATION_DB,RHYTHM_CALIBRATION_DB)
    totals["rhythm_consensus"]=build_rhythm_consensus_database(RHYTHM_CALIBRATION_DB,RHYTHM_CONSENSUS_DB)
    return totals


def refresh_archive_features(path: Path) -> dict:
    """Recompute feature rows for an already imported archive without losing audits or mappings."""
    totals={"factory":0,"gold":0,"missing":0,"errors":0}
    with ZipFile(path) as outer:
        for nested_name in outer.namelist():
            lower=nested_name.lower()
            corpus="gold" if "gold" in lower else "factory" if "factory" in lower else None
            if not corpus or not lower.endswith(".zip"): continue
            db_path=GOLD_DB if corpus=="gold" else FACTORY_DB
            with ZipFile(BytesIO(outer.read(nested_name))) as archive, connect(db_path) as database:
                for info in archive.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"): continue
                    try:
                        data=archive.read(info); digest=hashlib.sha256(data).hexdigest()
                        row=database.execute("SELECT id FROM midi_files WHERE sha256=?",(digest,)).fetchone()
                        if row is None: totals["missing"]+=1; continue
                        database.execute("DELETE FROM performance_features WHERE file_id=?",(row[0],))
                        database.execute("DELETE FROM track_stats WHERE file_id=?",(row[0],))
                        analyze_and_store(database,row[0],parse_midi(data),corpus); totals[corpus]+=1
                    except Exception as error:
                        database.execute("INSERT INTO import_errors(filename,error) VALUES(?,?)",(info.filename,f"feature refresh: {error}"))
                        totals["errors"]+=1
                if corpus=="factory": refresh_mapping_recommendations(database)
                database.commit()
    totals["dna"]=build_all(FACTORY_DB,GOLD_DB,DATA)
    totals["dna"]["strumming"]=build_strumming_database(path,STRUMMING_DB)
    totals["dna"]["song_layers"]=build_delay_harmony_databases(song_midi_paths(),DELAY_DB,HARMONY_DB)
    totals["dna"]["ornament"]=build_gold_ornament_database(path,ORNAMENT_DB)
    totals["dna"]["sound_intelligence"]=build_sound_intelligence_database(FACTORY_DB,GOLD_DB,path,SOUND_INTELLIGENCE_DB)
    build_evidence_inventory(Path("."),Path("analysis/evidence_inventory.json"))
    totals["dna"]["evidence_registry"]=build_evidence_registry(Path("analysis/evidence_inventory.json"),FACTORY_DB,EVIDENCE_REGISTRY_DB)
    totals["dna"]["musical_intelligence"]=build_musical_intelligence_database(path,song_midi_paths(),MUSICAL_INTELLIGENCE_DB)
    totals["dna"]["trill_registry"]=register_trill_observations(EVIDENCE_REGISTRY_DB,MUSICAL_INTELLIGENCE_DB)
    totals["layout"]=migrate_split_layout(FACTORY_DB,GOLD_DB,DATA)
    totals["rhythm_validation"]=build_rhythm_validation_database(path,FACTORY_DB,GOLD_DB,RHYTHM_VALIDATION_DB)
    totals["rhythm_calibration"]=build_rhythm_calibration_database(path,RHYTHM_VALIDATION_DB,RHYTHM_CALIBRATION_DB)
    totals["rhythm_consensus"]=build_rhythm_consensus_database(RHYTHM_CALIBRATION_DB,RHYTHM_CONSENSUS_DB)
    return totals


def song_midi_paths() -> list[Path]:
    """Return only the six user-approved Delay/Harmony reference songs.

    Generated optimizer output and later uploads must never silently enter the
    evidence cohort.
    """
    folder=ROOT/"prism-uploads"
    return [folder/name for name in SONG_REFERENCE_FILENAMES if (folder/name).is_file()]


def create_rx_noise_probes(payload: dict | None = None) -> dict:
    payload=payload or {}
    if not payload.get("data_base64"):
        raise ValueError("Odaberi poseban MIDI fajl; šest Delay/Terca referenci se ne koriste za RX Noise probe")
    filename,data=decode_midi_payload(payload)
    digest=hashlib.sha256(data).hexdigest()
    reserved={hashlib.sha256(path.read_bytes()).hexdigest() for path in song_midi_paths()}
    if digest in reserved:
        raise ValueError("Ovaj MIDI pripada strogo zaključanom Delay/Terca skupu i ne smije se koristiti za RX Noise")
    sources=[(filename,data)]
    return generate_probe_pack(sources,FACTORY_DB,RX_NOISE_PROBES,RX_NOISE_PROBE_DB,
        velocities=payload.get("velocities",(1,42,84,127)))


def save_rx_noise_probe_result(payload: dict) -> dict:
    return record_probe_result(RX_NOISE_PROBE_DB,int(payload["probe_file_id"]),str(payload["status"]),
        payload.get("confirmed_events",payload.get("confirmed_notes",[])),
        payload.get("rejected_events",payload.get("rejected_notes",[])),str(payload.get("comments","")))


def create_single_articulation_probes(_payload:dict|None=None)->dict:
    archive=ROOT/"prism-uploads"/"DNA.zip"
    if not archive.exists():raise ValueError("Nedostaje prism-uploads/DNA.zip")
    return build_single_articulation_probes(archive,FACTORY_DB,ARTICULATION_PROBES,ARTICULATION_PROBE_DB)


def save_articulation_probe_result(payload:dict)->dict:
    return record_file_articulation_result(ARTICULATION_MANIFEST,ARTICULATION_RESULTS,int(payload["probe_file_id"]),
        str(payload["status"]),str(payload.get("heard_articulation","")),str(payload.get("comments","")),
        str(payload.get("pa800_os","")),str(payload.get("resources_version","")),
        str(payload.get("tested_at","")),str(payload.get("audio_chain","")))


def create_articulation_promotion_queue(_payload:dict|None=None)->dict:
    return build_articulation_promotion_queue(ARTICULATION_MANIFEST,ARTICULATION_RESULTS,ARTICULATION_PROMOTION_QUEUE)


def refresh_mapping_recommendations(database) -> dict:
    recommendations = recommend_mappings(factory_profile_rows(database), catalog_rows(database), min_confidence=.90)
    # Rebuild only generated defaults so stricter identity rules immediately
    # remove stale cross-family recommendations. Explicit user rows survive.
    removed=database.execute("DELETE FROM gm_rx_mappings WHERE is_default=1").rowcount
    added = 0
    for item in recommendations:
        cursor = database.execute("""INSERT OR IGNORE INTO gm_rx_mappings(
            source_bank_msb,source_bank_lsb,source_program,role,rx_name,target_bank_msb,target_bank_lsb,
            target_program,confidence,provenance,is_default) VALUES(?,?,?,?,?,?,?,?,?,?,1)""",
            (item["source_bank_msb"],item["source_bank_lsb"],item["source_program"],item["role"],item["rx_name"],
             item["target_bank_msb"],item["target_bank_lsb"],item["target_program"],item["confidence"],item["provenance"]))
        added += cursor.rowcount
    database.commit()
    return {"recommended":len(recommendations),"added":added,"removed_stale_defaults":removed,
            "coverage":coverage_report(factory_profile_rows(database),recommendations)}


def database_status() -> dict:
    result = {}
    for label, path in (("factory", FACTORY_DB), ("gold", GOLD_DB)):
        with connect(path) as database:
            result[label] = {
                "files": database.execute("SELECT COUNT(*) FROM midi_files").fetchone()[0],
                "profiles": database.execute("SELECT COUNT(*) FROM instrument_profiles").fetchone()[0],
                "tracks": database.execute("SELECT COUNT(*) FROM track_stats").fetchone()[0],
            }
    with connect(FACTORY_DB) as database:
        result["factory"]["rx_zones"] = database.execute("SELECT COUNT(*) FROM rx_zones").fetchone()[0]
        result["factory"]["mappings"] = database.execute("SELECT COUNT(*) FROM gm_rx_mappings").fetchone()[0]
        result["factory"]["pa800_catalog"] = database.execute("SELECT COUNT(*) FROM pa800_voice_catalog").fetchone()[0]
    result["openai_available"] = bool(os.environ.get("OPENAI_API_KEY"))
    result["ready"] = result["factory"]["files"] > 0 and result["gold"]["files"] > 0
    result["dna"] = dna_status(DATA)
    result["test_agents"] = test_agent_status(HARDWARE_TEST_DB)["gate"]
    return result


def mapping_coverage() -> dict:
    with connect(FACTORY_DB) as database:
        recommendations=recommend_mappings(factory_profile_rows(database),catalog_rows(database),min_confidence=.90)
        report=coverage_report(factory_profile_rows(database),recommendations)
        report["active_mappings"]=database.execute("SELECT COUNT(*) FROM gm_rx_mappings").fetchone()[0]
        mapped_tracks,mapped_notes=database.execute("""SELECT COUNT(*),COALESCE(SUM(ts.note_count),0)
            FROM track_stats ts JOIN gm_rx_mappings m ON ts.bank_msb=m.source_bank_msb AND ts.bank_lsb=m.source_bank_lsb
            AND ts.program=m.source_program AND ts.role=m.role""").fetchone()
        total_tracks,total_notes=database.execute("SELECT COUNT(*),COALESCE(SUM(note_count),0) FROM track_stats").fetchone()
        report.update({"mapped_tracks":mapped_tracks,"total_tracks":total_tracks,
            "track_coverage_percent":round(100*mapped_tracks/total_tracks,2) if total_tracks else 0,
            "mapped_notes":mapped_notes,"total_notes":total_notes,
            "note_coverage_percent":round(100*mapped_notes/total_notes,2) if total_notes else 0})
        return report


def gold_model_summary() -> dict:
    with connect(GOLD_DB) as database:
        feature_rows=database.execute("SELECT feature_json FROM performance_features").fetchall()
    model=GoldDNAModel.fit([track_feature_from_dict(json.loads(row[0])) for row in feature_rows])
    return {"feature_tracks":len(feature_rows),"roles":model.to_dict()["profiles"]}


def solo_model_summary() -> dict:
    if not SOLO_DB.exists():
        return {"tracks":0,"candidates":0,"models":[]}
    database=sqlite3.connect(SOLO_DB); database.row_factory=sqlite3.Row
    result={"tracks":database.execute("SELECT COUNT(*) FROM solo_tracks").fetchone()[0],
        "candidates":database.execute("SELECT COUNT(*) FROM solo_tracks WHERE is_solo_candidate=1").fetchone()[0],
        "models":[dict(row) for row in database.execute("SELECT family,tempo_bucket,meter_num,meter_den,track_count,note_count FROM solo_models ORDER BY family,tempo_bucket")],
        "rules":[dict(row) for row in database.execute("SELECT * FROM solo_application_rules ORDER BY id")]}
    database.close(); return result


def strumming_model_summary() -> dict:
    if not STRUMMING_DB.exists(): return {"tracks":0,"models":0,"commands":[],"rules":[]}
    database=sqlite3.connect(STRUMMING_DB); database.row_factory=sqlite3.Row
    result={"tracks":database.execute("SELECT COUNT(*) FROM strumming_tracks").fetchone()[0],
        "events":database.execute("SELECT COALESCE(SUM(command_count),0) FROM strumming_tracks").fetchone()[0],
        "models":database.execute("SELECT COUNT(*) FROM strumming_models").fetchone()[0],
        "sound_profiles":database.execute("SELECT COUNT(*) FROM guitar_sound_profiles").fetchone()[0],
        "commands":[dict(row) for row in database.execute("SELECT * FROM guitar_mode_commands ORDER BY note")],
        "chord_types":[dict(row) for row in database.execute("SELECT * FROM chord_velocity_types ORDER BY velocity")],
        "rules":[dict(row) for row in database.execute("SELECT * FROM guitar_mode_rules ORDER BY id")],
        "sounds":[dict(row) for row in database.execute("SELECT instrument_name,program,track_count,event_count,velocity_mean,density_per_quarter FROM guitar_sound_profiles ORDER BY track_count DESC")],
        "chord_profiles":[dict(row) for row in database.execute("SELECT velocity,chord_type,event_count,root_hist_json FROM chord_progression_profiles ORDER BY velocity")],
        "sections":[dict(row) for row in database.execute("SELECT section,COUNT(*) tracks,SUM(command_count) events FROM strumming_tracks GROUP BY section ORDER BY section")]}
    database.close(); return result


def song_dna_summary() -> dict:
    result={}
    specs=(("delay",DELAY_DB,"delay_pairs","delay_models"),("harmony",HARMONY_DB,"harmony_pairs","harmony_models"),
           ("ornament",ORNAMENT_DB,"ornament_tracks","ornament_models"))
    for name,path,tracks,models in specs:
        if not path.exists(): result[name]={"exists":False}; continue
        database=sqlite3.connect(path); database.row_factory=sqlite3.Row
        result[name]={"exists":True,"tracks":database.execute(f"SELECT COUNT(*) FROM {tracks}").fetchone()[0],
            "models":database.execute(f"SELECT COUNT(*) FROM {models}").fetchone()[0],
            "integrity":database.execute("PRAGMA integrity_check").fetchone()[0]}
        if name=="delay": result[name]["rows"]=[dict(row) for row in database.execute("SELECT * FROM delay_pairs ORDER BY coverage DESC")]
        elif name=="harmony": result[name]["rows"]=[dict(row) for row in database.execute("SELECT * FROM harmony_pairs ORDER BY coverage DESC")]
        else:
            result[name]["source"]="gold_only"; result[name]["trills"]=database.execute("SELECT COALESCE(SUM(trill_count),0) FROM ornament_tracks").fetchone()[0]
        database.close()
    return result


def musical_intelligence_summary() -> dict:
    if not MUSICAL_INTELLIGENCE_DB.exists():return {"exists":False}
    database=sqlite3.connect(MUSICAL_INTELLIGENCE_DB);database.row_factory=sqlite3.Row
    result={"exists":True,
        "candidates":[dict(row) for row in database.execute("SELECT source_class,COUNT(*) candidates,SUM(accepted) accepted FROM trill_occurrences GROUP BY source_class")],
        "confidence":[dict(row) for row in database.execute("""SELECT o.source_class,c.category,COUNT(*) count
          FROM trill_confidence c JOIN trill_occurrences o ON o.id=c.occurrence_id
          GROUP BY o.source_class,c.category ORDER BY o.source_class,c.category""")],
        "patterns":database.execute("SELECT COUNT(*) FROM trill_patterns").fetchone()[0],
        "top_patterns":[dict(row) for row in database.execute("SELECT source_class,instrument_family,trill_type,direction,interval_semitones,subdivision,occurrence_count,file_count,confidence_mean FROM trill_patterns ORDER BY occurrence_count DESC LIMIT 30")],
        "relationships":[dict(row) for row in database.execute("SELECT filename,layer_type,source_track,source_channel,target_track,target_channel,coverage,velocity_ratio,creation_allowed FROM layer_relationships ORDER BY filename,layer_type")],
        "layer_trill_behavior":[dict(row) for row in database.execute("""SELECT r.layer_type,b.target_behavior,COUNT(*) count
          FROM layer_trill_behavior b JOIN layer_relationships r ON r.id=b.relationship_id
          GROUP BY r.layer_type,b.target_behavior ORDER BY r.layer_type,count DESC""")],
        "negative_rules":[dict(row) for row in database.execute("SELECT * FROM trill_negative_rules ORDER BY id")],
        "layer_rules":[dict(row) for row in database.execute("SELECT * FROM layer_rules ORDER BY id")],
        "terca_generation":database.execute("SELECT value FROM build_info WHERE key='terca_generation'").fetchone()[0],
        "integrity":database.execute("PRAGMA integrity_check").fetchone()[0]}
    database.close();return result


def sound_intelligence_summary() -> dict:
    if not SOUND_INTELLIGENCE_DB.exists():return {"exists":False}
    database=sqlite3.connect(SOUND_INTELLIGENCE_DB);database.row_factory=sqlite3.Row
    result={"exists":True,
        "sound_profiles":database.execute("SELECT COUNT(*) FROM factory_sound_profiles").fetchone()[0],
        "role_models":database.execute("SELECT COUNT(*) FROM role_models").fetchone()[0],
        "mix_profiles":[dict(row) for row in database.execute("SELECT corpus,role,track_count,note_count,velocity_mean,velocity_p95,cc7_median,cc11_median,effective_level_p95 FROM mix_profiles ORDER BY corpus,role")],
        "rules":[dict(row) for row in database.execute("SELECT * FROM application_rules ORDER BY id")],
        "integrity":database.execute("PRAGMA integrity_check").fetchone()[0]}
    database.close();return result


def instrument_structure_summary() -> dict:
    if not INSTRUMENT_STRUCTURE_DB.exists():return {"exists":False}
    database=sqlite3.connect(INSTRUMENT_STRUCTURE_DB);database.row_factory=sqlite3.Row
    result={"exists":True,
        "gm_instruments":database.execute("SELECT COUNT(*) FROM gm_instrument_catalog").fetchone()[0],
        "factory_structures":database.execute("SELECT COUNT(*) FROM factory_instrument_structures").fetchone()[0],
        "factory_identity_models":database.execute("SELECT COUNT(*) FROM factory_identity_models").fetchone()[0],
        "factory_identities":database.execute("SELECT COUNT(DISTINCT identity) FROM factory_instrument_structures").fetchone()[0],
        "gold_corrections":database.execute("SELECT COUNT(*) FROM gold_instrument_corrections").fetchone()[0],
        "gold_identities":database.execute("SELECT COUNT(DISTINCT identity) FROM gold_instrument_corrections").fetchone()[0],
        "conversion_rules":database.execute("SELECT COUNT(*) FROM identity_conversion_rules").fetchone()[0],
        "rules":[dict(row) for row in database.execute("SELECT * FROM application_rules ORDER BY id")],
        "integrity":database.execute("PRAGMA integrity_check").fetchone()[0]}
    database.close();return result


def midi_context(midi) -> dict:
    tempo=None; meter=(4,4)
    for events in midi.tracks:
        for event in events:
            if event.kind=="meta" and event.data1==0x51 and len(event.raw)==3 and tempo is None:
                micros=int.from_bytes(event.raw,"big"); tempo=60_000_000/micros if micros else None
            elif event.kind=="meta" and event.data1==0x58 and len(event.raw)>=2:
                meter=(event.raw[0],2**event.raw[1])
    return {"tempo_bpm":tempo,"meter_num":meter[0],"meter_den":meter[1]}


def local_plans(context: str) -> list[dict]:
    status = database_status()
    inventory = (
        f"Factory: {status['factory']['files']} fajlova, {status['factory']['profiles']} profila; "
        f"Gold DNA: {status['gold']['files']} fajlova, {status['gold']['tracks']} analiziranih traka; "
        f"RX mapiranja: {status['factory']['mappings']}."
    )
    return [
        {"agent": "ChatGPT Planner (local)", "plan": (
            f"Muzički plan — {inventory}\n1. Uvesti reprezentativne Factory i Gold DNA MIDI fajlove. "
            "2. Usporediti uloge, velocity, trajanje i gustoću nota po melodic/drums grupi. "
            "3. Zadržati Factory note i ritmičku strukturu, a Gold DNA koristiti kao cilj dinamike i gate-a. "
            "4. RX artikulacije aktivirati samo u potvrđenim velocity/key zonama. "
            f"5. A/B provjeriti na istom RX rendereru. Cilj korisnika: {context or 'GM Voice convert to RX Sounds'}."
        )},
        {"agent": "Codex Planner (local)", "plan": (
            f"Tehnički plan — {inventory}\n1. Dovršiti inventar MSB/LSB/Program događaja. "
            "2. Ručno potvrditi RX pozivne brojeve koji nedostaju u Oscilatori.txt. "
            "3. Pokrenuti konverziju u prefer-RX režimu i prijaviti sve fallback profile. "
            "4. Validirati ponovni parse, note-on/off parove i raspon 0–127. "
            "5. Tek nakon testnog korpusa podesiti jačinu Gold DNA transformacije."
        )},
    ]


def openai_plan(agent: str, context: str) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY nije postavljen")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4")
    prompt = (
        f"Ti si {agent} planner za MIDI projekt. Napiši kratak plan na B/H/S jeziku. "
        "Ne izmišljaj bank/program brojeve. Factory daje osnovu; Gold DNA daje dinamiku i izvedbeni profil; "
        "cilj je GM Voice -> RX Sounds. Inventar: " + json.dumps(database_status(), ensure_ascii=False) +
        "\nKorisnički cilj: " + (context or "GM Voice convert to RX Sounds")
    )
    body = json.dumps({"model": model, "input": prompt}).encode()
    call = urlrequest.Request(
        "https://api.openai.com/v1/responses", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST",
    )
    with urlrequest.urlopen(call, timeout=60) as response:
        payload = json.load(response)
    if payload.get("output_text"):
        return payload["output_text"]
    texts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
    return "\n".join(texts).strip() or "Agent nije vratio tekst."


def generate_plans(payload: dict) -> list[dict]:
    context = str(payload.get("context", ""))[:4000]
    plans = local_plans(context)
    if payload.get("use_openai"):
        plans = [
            {"agent": "ChatGPT Planner", "plan": openai_plan("ChatGPT music analyst", context)},
            {"agent": "Codex Planner", "plan": openai_plan("Codex technical architect", context)},
        ]
    with connect(FACTORY_DB) as database:
        database.executemany(
            "INSERT INTO project_plans(agent, plan) VALUES(?,?)",
            [(item["agent"], item["plan"]) for item in plans],
        )
        database.commit()
    return plans


def save_mapping(payload: dict) -> dict:
    fields = {
        "source_bank_msb": int(payload.get("source_bank_msb", 0)),
        "source_bank_lsb": int(payload.get("source_bank_lsb", 0)),
        "source_program": int(payload["source_program"]) - 1,
        "role": str(payload.get("role", "melodic")),
        "rx_name": str(payload["rx_name"]).strip(),
        "target_bank_msb": int(payload["target_bank_msb"]),
        "target_bank_lsb": int(payload["target_bank_lsb"]),
        "target_program": int(payload["target_program"]) - 1,
    }
    numeric = [value for key, value in fields.items() if key not in ("role", "rx_name")]
    allowed_roles = {"melodic", "bass", "guitar", "accompaniment", "percussion", "drums"}
    if not fields["rx_name"] or fields["role"] not in allowed_roles or not all(0 <= n <= 127 for n in numeric):
        raise ValueError("Mapiranje mora imati naziv i MIDI vrijednosti 0–127 (Program u GUI-u 1–128)")
    with connect(FACTORY_DB) as database:
        target=database.execute("""SELECT name,category,program FROM pa800_voice_catalog
            WHERE bank_msb=? AND bank_lsb=? AND program=? AND name=?""",
            (fields["target_bank_msb"],fields["target_bank_lsb"],fields["target_program"],fields["rx_name"])).fetchone()
        if target is None:
            raise ValueError("Ciljna RX adresa i naziv moraju postojati u potvrđenom Pa800 katalogu")
        if not identities_compatible(fields["source_program"],"",fields["target_program"],target["name"],fields["role"]):
            raise ValueError("Blokirano cross-instrument mapiranje: izvor i RX cilj nemaju isti identitet")
        database.execute(
            """INSERT INTO gm_rx_mappings(source_bank_msb,source_bank_lsb,source_program,role,rx_name,target_bank_msb,target_bank_lsb,target_program,confidence,provenance,is_default)
               VALUES(:source_bank_msb,:source_bank_lsb,:source_program,:role,:rx_name,:target_bank_msb,:target_bank_lsb,:target_program,0.95,'user_catalog_identity_verified',0)
               ON CONFLICT(source_bank_msb,source_bank_lsb,source_program,role) DO UPDATE SET
               rx_name=excluded.rx_name,target_bank_msb=excluded.target_bank_msb,target_bank_lsb=excluded.target_bank_lsb,
               target_program=excluded.target_program,confidence=excluded.confidence,provenance=excluded.provenance,is_default=0""",
            fields,
        )
        database.commit()
    if VOICE_DB.exists() and FACTORY_DB.exists() and GOLD_DB.exists():
        build_voice_database(FACTORY_DB,GOLD_DB,VOICE_DB)
        build_rx_database(FACTORY_DB,GOLD_DB,RX_DB)
        if PERFORMANCE_DB.exists():
            build_optimizer_database(FACTORY_DB,GOLD_DB,OPTIMIZER_DB,PERFORMANCE_DB,RX_DB)
    return {"saved": True}


def run_optimizer(payload: dict) -> dict:
    filename, data = decode_midi_payload(payload)
    midi = parse_midi(data)
    # Identify existing song layers before Gold micro-timing can move the two
    # related tracks by slightly different amounts.
    detected_delays=detect_delay_pairs(midi,filename)
    detected_harmonies=detect_harmony_pairs(midi,filename)
    primary_song_source=select_song_lead(midi,detected_delays,detected_harmonies)
    source_validation=validate_midi(midi)
    context=midi_context(midi)
    with connect(GOLD_DB) as database:
        if database.execute("SELECT COUNT(*) FROM midi_files").fetchone()[0] == 0:
            raise ValueError("Gold DNA baza je prazna; prvo pokreni import-archive")
        gold_stats = rows(database, "SELECT ts.*, mf.division FROM track_stats ts JOIN midi_files mf ON mf.id=ts.file_id")
        feature_rows=database.execute("""SELECT pf.feature_json,mf.tempo_bpm,mf.meter_num,mf.meter_den
            FROM performance_features pf JOIN midi_files mf ON mf.id=pf.file_id""").fetchall()
        compatible=[row for row in feature_rows if int(row[2] or 4)==context["meter_num"] and int(row[3] or 4)==context["meter_den"]
            and (context["tempo_bpm"] is None or row[1] is None or abs(float(row[1])-context["tempo_bpm"])<=30)]
        selected_rows=compatible or feature_rows
        if PERFORMANCE_DB.exists():
            gold_model,derived_cohort=load_performance_model(PERFORMANCE_DB,context["tempo_bpm"],context["meter_num"],context["meter_den"])
        else:
            gold_model=GoldDNAModel.fit([track_feature_from_dict(json.loads(row[0])) for row in selected_rows]); derived_cohort=None
    with connect(FACTORY_DB) as database:
        mappings = rows(database, "SELECT * FROM gm_rx_mappings")
    strength=float(payload.get("strength", .7))
    rx_rules=load_rx_rules(RX_DB,EVIDENCE_REGISTRY_DB) if RX_DB.exists() else {"__gate__":{},"__report__":{"mode":"strict","fail_closed":True,"fail_closed_reason":"missing_rx_database"}}
    solo_models=load_solo_models(SOLO_DB) if SOLO_DB.exists() else []
    solo_strength=float(payload.get("solo_strength",.65)) if payload.get("solo_enabled",True) else 0
    solo_channels=[int(value) for value in payload.get("solo_channels",[]) if 0 <= int(value) <= 15]
    strumming_models=load_strumming_models(STRUMMING_DB) if STRUMMING_DB.exists() else []
    sound_intelligence=load_sound_intelligence(SOUND_INTELLIGENCE_DB) if SOUND_INTELLIGENCE_DB.exists() else {}
    instrument_structure=load_instrument_structure(INSTRUMENT_STRUCTURE_DB) if INSTRUMENT_STRUCTURE_DB.exists() else {}
    match=re.search(r"_(Intro|Var|Fill|End|Ending|Break)(\d*)",filename,re.I)
    style_section={"var":"variation","end":"ending"}.get(match.group(1).lower(),match.group(1).lower()) if match else None
    result, report = optimize(midi, gold_stats, mappings, strength, gold_model=gold_model,rx_rules=rx_rules,
        solo_models=solo_models,solo_strength=solo_strength,solo_channels=solo_channels,
        strumming_models=strumming_models,strumming_strength=float(payload.get("strumming_strength",.7)),
        strumming_humanize=float(payload.get("strumming_humanize",.5)),
        strumming_variation=bool(payload.get("strumming_variation",True)),style_section=style_section,
        capo=int(payload.get("capo",0)),sound_intelligence=sound_intelligence,
        assign_unknown_sounds=bool(payload.get("assign_unknown_sounds",True)),
        mix_headroom=bool(payload.get("mix_headroom",True)),headroom_strength=float(payload.get("headroom_strength",.85)),
        guitar_repair=bool(payload.get("guitar_repair",True)),guitar_repair_strength=float(payload.get("guitar_repair_strength",.65)),
        instrument_structure=instrument_structure,rx_mapping_mode=str(payload.get("rx_mapping_mode","strict")))
    delay_models=load_models(DELAY_DB,"delay_models") if DELAY_DB.exists() else []
    delay_phrase_models=load_delay_phrase_models(DELAY_DB) if DELAY_DB.exists() else []
    harmony_models=load_models(HARMONY_DB,"harmony_models") if HARMONY_DB.exists() else []
    ornament_models=load_models(ORNAMENT_DB,"ornament_models") if ORNAMENT_DB.exists() else []
    result,song_report=apply_song_dna(result,delay_models,harmony_models,ornament_models,
        delay_enabled=bool(payload.get("delay_enabled",True)),delay_create=False,
        delay_strength=float(payload.get("delay_strength",.8)),harmony_enabled=bool(payload.get("harmony_enabled",True)),
        harmony_create=False,harmony_strength=float(payload.get("harmony_strength",.75)),
        ornament_enabled=bool(payload.get("ornament_enabled",True)),allow_replace=bool(payload.get("allow_track_replacement",False)),
        detected_delays=detected_delays,detected_harmonies=detected_harmonies,primary_source=primary_song_source,
        delay_phrase_models=delay_phrase_models)
    report["song_dna"]=song_report
    encoded = encode_midi(result)
    parsed_output=parse_midi(encoded)
    validation=validate_midi(parsed_output)
    source_unmatched=source_validation["unmatched_note_on"]+source_validation["unmatched_note_off"]
    output_unmatched=validation["unmatched_note_on"]+validation["unmatched_note_off"]
    if validation["invalid_values"]>source_validation["invalid_values"] or output_unmatched>source_unmatched:
        raise ValueError("Optimizer je pogoršao MIDI semantičku validaciju")
    stem = Path(filename).stem
    digest = hashlib.sha256(encoded).hexdigest()[:10]
    output_name = safe_filename(f"{stem}-gold-rx-{digest}.mid")
    temp=OUTPUT / (output_name+".tmp"); temp.write_bytes(encoded); temp.replace(OUTPUT/output_name)
    report.update({"output_name": output_name, "bytes": len(encoded)})
    report["validation"]={"source":source_validation,"output":validation,
        "unmatched_delta":output_unmatched-source_unmatched,"preserved_or_improved":output_unmatched<=source_unmatched}
    report["gold_cohort"]={"selected_tracks":len(selected_rows),"all_tracks":len(feature_rows),
        "tempo_bpm":context["tempo_bpm"],"meter":f'{context["meter_num"]}/{context["meter_den"]}',
        "fallback_all":not bool(compatible),"derived_model":derived_cohort}
    with connect(FACTORY_DB) as database:
        database.execute("""INSERT INTO optimizer_runs(source_name,source_sha256,output_name,output_sha256,config_json,report_json)
            VALUES(?,?,?,?,?,?)""",(filename,hashlib.sha256(data).hexdigest(),output_name,hashlib.sha256(encoded).hexdigest(),
            json.dumps({"strength":strength,"solo_strength":solo_strength,"solo_channels":solo_channels,
                "model_roles":sorted(gold_model.profiles),
                "delay_enabled":bool(payload.get("delay_enabled",True)),
                "delay_create":False,
                "delay_strength":float(payload.get("delay_strength",.8)),
                "harmony_enabled":bool(payload.get("harmony_enabled",True)),
                "harmony_create":False,
                "harmony_policy":"existing_velocity_volume_only",
                "harmony_strength":float(payload.get("harmony_strength",.75)),
                "ornament_enabled":bool(payload.get("ornament_enabled",True)),
                "allow_track_replacement":bool(payload.get("allow_track_replacement",False)),
                "assign_unknown_sounds":bool(payload.get("assign_unknown_sounds",True)),
                "mix_headroom":bool(payload.get("mix_headroom",True)),
                "headroom_strength":float(payload.get("headroom_strength",.85)),
                "guitar_repair":bool(payload.get("guitar_repair",True)),
                "guitar_repair_strength":float(payload.get("guitar_repair_strength",.65)),
                "rx_mapping_mode":str(payload.get("rx_mapping_mode","strict"))},ensure_ascii=False),
            json.dumps(report,ensure_ascii=False)))
        database.commit()
    if OPTIMIZER_DB.exists():
        database=sqlite3.connect(OPTIMIZER_DB)
        database.execute("""INSERT INTO optimizer_runs(source_name,source_sha256,output_name,output_sha256,config_json,report_json,created_at)
            VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""",(filename,hashlib.sha256(data).hexdigest(),output_name,
            hashlib.sha256(encoded).hexdigest(),json.dumps({"strength":strength},ensure_ascii=False),json.dumps(report,ensure_ascii=False)))
        database.commit(); database.close()
    return {"filename": output_name, "data_base64": base64.b64encode(encoded).decode(), "report": report}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self) -> None:
        try:
            if self.path in ("/", "/index.html"):
                return self.raw_response(INDEX_HTML,"text/html; charset=utf-8")
            if self.path == "/styles.css":
                return self.raw_response(STYLE_CSS,"text/css; charset=utf-8")
            if self.path == "/app.js":
                return self.raw_response(APP_JS,"text/javascript; charset=utf-8")
            if self.path == "/favicon.ico":
                self.send_response(204); self.end_headers(); return
            if self.path == "/api/status":
                return self.json_response(database_status())
            if self.path == "/api/profiles":
                with connect(FACTORY_DB) as database:
                    return self.json_response(rows(database, "SELECT *, program+1 AS program_ui FROM instrument_profiles ORDER BY role,name"))
            if self.path == "/api/rx-zones":
                with connect(FACTORY_DB) as database:
                    return self.json_response(rows(database, "SELECT * FROM rx_zones ORDER BY profile_name,oscillator"))
            if self.path == "/api/mappings":
                with connect(FACTORY_DB) as database:
                    return self.json_response(rows(database, "SELECT *, source_program+1 AS source_program_ui, target_program+1 AS target_program_ui FROM gm_rx_mappings ORDER BY source_program"))
            if self.path == "/api/pa800-catalog":
                with connect(FACTORY_DB) as database:
                    return self.json_response(rows(database, "SELECT *, program+1 AS program_ui FROM pa800_voice_catalog ORDER BY category,name"))
            if self.path == "/api/coverage":
                return self.json_response(mapping_coverage())
            if self.path == "/api/gold-model":
                return self.json_response(gold_model_summary())
            if self.path == "/api/solo-model":
                return self.json_response(solo_model_summary())
            if self.path == "/api/strumming-model":
                return self.json_response(strumming_model_summary())
            if self.path == "/api/song-dna":
                return self.json_response(song_dna_summary())
            if self.path == "/api/musical-intelligence":
                return self.json_response(musical_intelligence_summary())
            if self.path == "/api/sound-intelligence":
                return self.json_response(sound_intelligence_summary())
            if self.path == "/api/instrument-structure":
                return self.json_response(instrument_structure_summary())
            if self.path == "/api/runs":
                with connect(FACTORY_DB) as database:
                    return self.json_response(rows(database,"SELECT * FROM optimizer_runs ORDER BY id DESC LIMIT 20"))
            if self.path == "/api/dna-status":
                return self.json_response(dna_status(DATA))
            if self.path == "/api/test-agents":
                return self.json_response(test_agent_status(HARDWARE_TEST_DB))
            if self.path == "/api/rx-noise-probes":
                return self.json_response(probe_status(RX_NOISE_PROBE_DB))
            if self.path == "/api/articulation-probes":
                return self.json_response(file_articulation_probe_status(ARTICULATION_MANIFEST,ARTICULATION_RESULTS))
            if self.path == "/api/articulation-promotion-queue":
                return self.json_response(articulation_promotion_queue_status(ARTICULATION_PROMOTION_QUEUE))
            if self.path == "/api/plans":
                with connect(FACTORY_DB) as database:
                    return self.json_response(rows(database, "SELECT * FROM project_plans ORDER BY id DESC LIMIT 10"))
            return super().do_GET()
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY * 2:
                raise ValueError("Zahtjev je prazan ili prevelik")
            payload = json.loads(self.rfile.read(length))
            routes = {
                "/api/import": import_midi,
                "/api/plan": generate_plans,
                "/api/mappings": save_mapping,
                "/api/optimize": run_optimizer,
                "/api/recommend-mappings": lambda _payload: self.recommend_mappings(),
                "/api/build-dna": lambda _payload: self.build_databases(),
                "/api/test-agents/create": lambda payload: create_test_suite(
                    HARDWARE_TEST_DB, OUTPUT, FACTORY_DB, str(payload.get("name", "Pa800 A/B Release"))
                ),
                "/api/test-agents/result": lambda payload: record_test_result(HARDWARE_TEST_DB, payload),
                "/api/test-agents/export": lambda payload: export_test_pack(
                    HARDWARE_TEST_DB, HARDWARE_TESTS, payload.get("suite_id")
                ),
                "/api/rx-noise-probes/create": create_rx_noise_probes,
                "/api/rx-noise-probes/result": save_rx_noise_probe_result,
                "/api/articulation-probes/create": create_single_articulation_probes,
                "/api/articulation-probes/result": save_articulation_probe_result,
                "/api/articulation-promotion-queue/create": create_articulation_promotion_queue,
            }
            if self.path not in routes:
                return self.json_response({"error": "Nepoznata ruta"}, 404)
            self.json_response(routes[self.path](payload))
        except (ValueError, KeyError, MidiError, json.JSONDecodeError) as error:
            self.json_response({"error": str(error)}, 400)
        except Exception as error:
            self.json_response({"error": f"Interna greška: {error}"}, 500)

    def json_response(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def raw_response(self, payload: str, content_type: str, status: int = 200) -> None:
        body=payload.encode("utf-8"); self.send_response(status)
        self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)

    def recommend_mappings(self):
        with connect(FACTORY_DB) as database:
            return refresh_mapping_recommendations(database)

    def build_databases(self):
        result=build_all(FACTORY_DB,GOLD_DB,DATA)
        archive=ROOT/"prism-uploads"/"DNA.zip"
        if archive.exists():
            result["strumming"]=build_strumming_database(archive,STRUMMING_DB)
            result["ornament"]=build_gold_ornament_database(archive,ORNAMENT_DB)
            result["sound_intelligence"]=build_sound_intelligence_database(FACTORY_DB,GOLD_DB,archive,SOUND_INTELLIGENCE_DB)
        result["song_layers"]=build_delay_harmony_databases(song_midi_paths(),DELAY_DB,HARMONY_DB)
        build_evidence_inventory(Path("."),Path("analysis/evidence_inventory.json"))
        result["evidence_registry"]=build_evidence_registry(Path("analysis/evidence_inventory.json"),FACTORY_DB,EVIDENCE_REGISTRY_DB)
        if archive.exists():
            result["musical_intelligence"]=build_musical_intelligence_database(archive,song_midi_paths(),MUSICAL_INTELLIGENCE_DB)
            result["trill_registry"]=register_trill_observations(EVIDENCE_REGISTRY_DB,MUSICAL_INTELLIGENCE_DB)
            result["rhythm_validation"]=build_rhythm_validation_database(archive,FACTORY_DB,GOLD_DB,RHYTHM_VALIDATION_DB)
            result["rhythm_calibration"]=build_rhythm_calibration_database(archive,RHYTHM_VALIDATION_DB,RHYTHM_CALIBRATION_DB)
            result["rhythm_consensus"]=build_rhythm_consensus_database(RHYTHM_CALIBRATION_DB,RHYTHM_CONSENSUS_DB)
        return result

    def log_message(self, fmt: str, *args) -> None:
        print("[web]", fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="GM to RX MIDI Optimizer")
    parser.add_argument("command", nargs="?", choices=("serve", "status", "import-archive", "refresh-features", "build-dna", "evidence-inventory", "migrate-layout", "build-rhythm-validation", "build-rhythm-calibration", "build-rhythm-consensus", "build-rx-noise-probes", "build-articulation-probes"), default="serve")
    parser.add_argument("path", nargs="?", default="prism-uploads/DNA.zip")
    args = parser.parse_args()
    init_app()
    if args.command == "status":
        print(json.dumps(database_status(), ensure_ascii=False, indent=2)); return
    if args.command == "import-archive":
        print(json.dumps(import_dna_archive(Path(args.path)), ensure_ascii=False, indent=2))
        print(json.dumps(database_status(), ensure_ascii=False, indent=2)); return
    if args.command == "refresh-features":
        print(json.dumps(refresh_archive_features(Path(args.path)),ensure_ascii=False,indent=2)); return
    if args.command == "build-dna":
        result=build_all(FACTORY_DB,GOLD_DB,DATA)
        archive=Path(args.path)
        if archive.exists():
            result["strumming"]=build_strumming_database(archive,STRUMMING_DB)
            result["ornament"]=build_gold_ornament_database(archive,ORNAMENT_DB)
            result["sound_intelligence"]=build_sound_intelligence_database(FACTORY_DB,GOLD_DB,archive,SOUND_INTELLIGENCE_DB)
        result["song_layers"]=build_delay_harmony_databases(song_midi_paths(),DELAY_DB,HARMONY_DB)
        build_evidence_inventory(Path("."),Path("analysis/evidence_inventory.json"))
        result["evidence_registry"]=build_evidence_registry(Path("analysis/evidence_inventory.json"),FACTORY_DB,EVIDENCE_REGISTRY_DB)
        if archive.exists():
            result["musical_intelligence"]=build_musical_intelligence_database(archive,song_midi_paths(),MUSICAL_INTELLIGENCE_DB)
            result["trill_registry"]=register_trill_observations(EVIDENCE_REGISTRY_DB,MUSICAL_INTELLIGENCE_DB)
            result["rhythm_validation"]=build_rhythm_validation_database(archive,FACTORY_DB,GOLD_DB,RHYTHM_VALIDATION_DB)
            result["rhythm_calibration"]=build_rhythm_calibration_database(archive,RHYTHM_VALIDATION_DB,RHYTHM_CALIBRATION_DB)
            result["rhythm_consensus"]=build_rhythm_consensus_database(RHYTHM_CALIBRATION_DB,RHYTHM_CONSENSUS_DB)
        print(json.dumps(result,ensure_ascii=False,indent=2)); return
    if args.command == "evidence-inventory":
        result=build_evidence_inventory(Path("."),Path("analysis/evidence_inventory.json"))
        registry=build_evidence_registry(Path("analysis/evidence_inventory.json"),FACTORY_DB,EVIDENCE_REGISTRY_DB)
        print(json.dumps({"inventory":result["summary"],"registry":registry},ensure_ascii=False,indent=2)); return
    if args.command == "migrate-layout":
        print(json.dumps(migrate_split_layout(FACTORY_DB,GOLD_DB,DATA),ensure_ascii=False,indent=2));return
    if args.command == "build-rhythm-validation":
        print(json.dumps(build_rhythm_validation_database(Path(args.path),FACTORY_DB,GOLD_DB,RHYTHM_VALIDATION_DB),ensure_ascii=False,indent=2));return
    if args.command == "build-rhythm-calibration":
        print(json.dumps(build_rhythm_calibration_database(Path(args.path),RHYTHM_VALIDATION_DB,RHYTHM_CALIBRATION_DB),ensure_ascii=False,indent=2));return
    if args.command == "build-rhythm-consensus":
        print(json.dumps(build_rhythm_consensus_database(RHYTHM_CALIBRATION_DB,RHYTHM_CONSENSUS_DB),ensure_ascii=False,indent=2));return
    if args.command == "build-rx-noise-probes":
        raise SystemExit("RX Noise probe zahtijeva MIDI upload kroz GUI/API; šest Delay/Terca pjesama je zabranjeno koristiti")
    if args.command == "build-articulation-probes":
        print(json.dumps(create_single_articulation_probes(),ensure_ascii=False,indent=2));return
    # Bind externally by default so the app works in containers and hosted previews.
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8765"))
    print(f"GM to RX Optimizer: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()