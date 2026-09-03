"""Builders for derived Rhythm, Performance, Voice and Optimizer DNA databases."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from .features import GoldDNAModel, track_feature_from_dict
from .solo import aggregate_solo_models, solo_descriptor
from .instrument_structure import build_instrument_structure_database
from .evidence_registry import load_runtime_evidence_policy


RHYTHM_SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE rhythm_tracks(id INTEGER PRIMARY KEY,source_file_id INTEGER,filename TEXT,style_name TEXT,
 section TEXT,section_no INTEGER,track_index INTEGER,channel INTEGER,role TEXT,cv INTEGER,
 tempo_bpm REAL,meter_num INTEGER,meter_den INTEGER,note_count INTEGER,density_per_quarter REAL,
 signature_hash TEXT,signature_json TEXT,UNIQUE(source_file_id,track_index,channel));
CREATE TABLE section_profiles(id INTEGER PRIMARY KEY,section TEXT,role TEXT,cv INTEGER,meter_num INTEGER,
 meter_den INTEGER,sample_count INTEGER,note_count INTEGER,profile_json TEXT,
 UNIQUE(section,role,cv,meter_num,meter_den));
"""

PERFORMANCE_SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE performance_tracks(id INTEGER PRIMARY KEY,source_file_id INTEGER,filename TEXT,track_index INTEGER,
 channel INTEGER,role TEXT,tempo_bpm REAL,tempo_bucket INTEGER,meter_num INTEGER,meter_den INTEGER,
 note_count INTEGER,feature_json TEXT,UNIQUE(source_file_id,track_index,channel));
CREATE TABLE performance_models(id INTEGER PRIMARY KEY,scope_key TEXT NOT NULL UNIQUE,role TEXT NOT NULL,
 tempo_bucket INTEGER,meter_num INTEGER,meter_den INTEGER,sample_count INTEGER,note_count INTEGER,
 model_hash TEXT NOT NULL,model_json TEXT NOT NULL);
"""

VOICE_SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE voice_catalog(id INTEGER PRIMARY KEY,name TEXT,category TEXT,bank_msb INTEGER,bank_lsb INTEGER,
 program INTEGER,is_rx INTEGER,source TEXT,UNIQUE(bank_msb,bank_lsb,program,name));
CREATE TABLE voice_mappings(id INTEGER PRIMARY KEY,source_bank_msb INTEGER,source_bank_lsb INTEGER,
 source_program INTEGER,role TEXT,rx_name TEXT,target_bank_msb INTEGER,target_bank_lsb INTEGER,
 target_program INTEGER,confidence REAL,provenance TEXT,is_default INTEGER,
 UNIQUE(source_bank_msb,source_bank_lsb,source_program,role));
CREATE TABLE articulation_zones(id INTEGER PRIMARY KEY,profile_name TEXT,oscillator INTEGER,articulation TEXT,
 velocity_min INTEGER,velocity_max INTEGER,key_min INTEGER,key_max INTEGER,switch_value INTEGER,notes TEXT);
CREATE TABLE drum_profiles(id INTEGER PRIMARY KEY,name TEXT,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,
 source_profile_count INTEGER,source_track_count INTEGER,metadata_json TEXT);
CREATE TABLE coverage_snapshots(id INTEGER PRIMARY KEY,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 profile_total INTEGER,profile_mapped INTEGER,track_total INTEGER,track_mapped INTEGER,note_total INTEGER,
 note_mapped INTEGER,details_json TEXT);
"""

RX_SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE rx_sounds(id INTEGER PRIMARY KEY,name TEXT,category TEXT,bank_msb INTEGER,bank_lsb INTEGER,
 program INTEGER,source TEXT,UNIQUE(bank_msb,bank_lsb,program,name));
CREATE TABLE rx_switch_rules(id INTEGER PRIMARY KEY,rx_name TEXT,oscillator INTEGER,articulation TEXT,
 velocity_min INTEGER,velocity_max INTEGER,key_min INTEGER,key_max INTEGER,switch_value INTEGER,
 notes TEXT,rule_source TEXT);
CREATE TABLE factory_rx_evidence(id INTEGER PRIMARY KEY,source_bank_msb INTEGER,source_bank_lsb INTEGER,
 source_program INTEGER,source_name TEXT,role TEXT,rx_name TEXT,target_bank_msb INTEGER,target_bank_lsb INTEGER,
 target_program INTEGER,confidence REAL,provenance TEXT,profile_use_count INTEGER,track_count INTEGER,
 note_count INTEGER,velocity_mean REAL,duration_quarters REAL,sections_json TEXT,
 UNIQUE(source_bank_msb,source_bank_lsb,source_program,role));
CREATE TABLE rx_behavior_profiles(id INTEGER PRIMARY KEY,rx_name TEXT,role TEXT,source_track_count INTEGER,
 note_count INTEGER,model_hash TEXT,model_json TEXT,UNIQUE(rx_name,role));
CREATE TABLE rx_section_usage(id INTEGER PRIMARY KEY,rx_name TEXT,section TEXT,cv INTEGER,track_count INTEGER,
 note_count INTEGER,velocity_mean REAL,density_per_quarter REAL,UNIQUE(rx_name,section,cv));
CREATE TABLE rx_drum_layers(id INTEGER PRIMARY KEY,rx_name TEXT,note_min INTEGER,note_max INTEGER,
 velocity_switches TEXT,articulation TEXT,source TEXT);
"""

OPTIMIZER_SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE corpus_versions(id INTEGER PRIMARY KEY,name TEXT UNIQUE,file_count INTEGER,profile_count INTEGER,
 feature_count INTEGER,database_sha256 TEXT);
CREATE TABLE optimizer_runs(id INTEGER PRIMARY KEY,source_name TEXT,source_sha256 TEXT,output_name TEXT,
 output_sha256 TEXT,config_json TEXT,report_json TEXT,created_at TEXT);
CREATE TABLE model_versions(id INTEGER PRIMARY KEY,name TEXT,version_hash TEXT,metadata_json TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

SOLO_SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE solo_tracks(id INTEGER PRIMARY KEY,source_file_id INTEGER,filename TEXT,track_index INTEGER,
 channel INTEGER,role TEXT,program INTEGER,family TEXT,tempo_bpm REAL,tempo_bucket INTEGER,
 meter_num INTEGER,meter_den INTEGER,note_count INTEGER,solo_score REAL,is_solo_candidate INTEGER,
 feature_json TEXT,UNIQUE(source_file_id,track_index,channel));
CREATE TABLE solo_models(id INTEGER PRIMARY KEY,family TEXT,tempo_bucket INTEGER,meter_num INTEGER,
 meter_den INTEGER,track_count INTEGER,note_count INTEGER,model_json TEXT,
 UNIQUE(family,tempo_bucket,meter_num,meter_den));
CREATE TABLE solo_application_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT,
 minimum REAL,maximum REAL,enabled INTEGER NOT NULL DEFAULT 1);
"""


def _rows(connection, query: str, parameters=()):
    return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def _sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""): digest.update(block)
    return digest.hexdigest()


def _new_database(path: Path, schema: str) -> sqlite3.Connection:
    temp=path.with_suffix(path.suffix+".tmp")
    temp.unlink(missing_ok=True)
    database=sqlite3.connect(temp); database.row_factory=sqlite3.Row; database.executescript(schema)
    return database


def _finish(database: sqlite3.Connection, path: Path) -> None:
    temp=Path(database.execute("PRAGMA database_list").fetchone()[2])
    database.commit(); database.close(); temp.replace(path)


def _build_info(database, source_factory: Path, source_gold: Path, kind: str):
    values={"kind":kind,"schema_version":"1","factory_sha256":_sha256(source_factory),
            "gold_sha256":_sha256(source_gold)}
    database.executemany("INSERT INTO build_info(key,value) VALUES(?,?)",values.items())


def build_rhythm_database(factory_path: Path, gold_path: Path, output_path: Path) -> dict:
    source=sqlite3.connect(factory_path); source.row_factory=sqlite3.Row
    database=_new_database(output_path,RHYTHM_SCHEMA); _build_info(database,factory_path,gold_path,"rhythm")
    rows=_rows(source,"""SELECT pf.file_id,mf.filename,mf.style_name,mf.section,mf.section_no,pf.track_index,
        pf.channel,pf.role,pf.cv,mf.tempo_bpm,mf.meter_num,mf.meter_den,ts.note_count,ts.density_per_quarter,
        pf.feature_json FROM performance_features pf JOIN midi_files mf ON mf.id=pf.file_id
        JOIN track_stats ts ON ts.file_id=pf.file_id AND ts.track_index=pf.track_index AND ts.channel=pf.channel""")
    groups=defaultdict(list)
    for row in rows:
        signature=row.pop("feature_json"); signature_hash=hashlib.sha256(signature.encode()).hexdigest()
        database.execute("""INSERT INTO rhythm_tracks(source_file_id,filename,style_name,section,section_no,
            track_index,channel,role,cv,tempo_bpm,meter_num,meter_den,note_count,density_per_quarter,
            signature_hash,signature_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row["file_id"],row["filename"],row["style_name"],row["section"],row["section_no"],row["track_index"],
             row["channel"],row["role"],row["cv"],row["tempo_bpm"],row["meter_num"],row["meter_den"],
             row["note_count"],row["density_per_quarter"],signature_hash,signature))
        groups[(row["section"],row["role"],row["cv"],row["meter_num"],row["meter_den"])].append(track_feature_from_dict(json.loads(signature)))
    for key,features in groups.items():
        model=GoldDNAModel.fit(features); payload=json.dumps(model.to_dict(),separators=(',',':'))
        database.execute("""INSERT INTO section_profiles(section,role,cv,meter_num,meter_den,sample_count,
            note_count,profile_json) VALUES(?,?,?,?,?,?,?,?)""",(*key,len(features),sum(f.note_count for f in features),payload))
    source.close(); _finish(database,output_path)
    return {"tracks":len(rows),"section_profiles":len(groups)}


def build_performance_database(factory_path: Path, gold_path: Path, output_path: Path) -> dict:
    source=sqlite3.connect(gold_path); source.row_factory=sqlite3.Row
    database=_new_database(output_path,PERFORMANCE_SCHEMA); _build_info(database,factory_path,gold_path,"performance")
    rows=_rows(source,"""SELECT pf.file_id,mf.filename,pf.track_index,pf.channel,pf.role,mf.tempo_bpm,
        mf.meter_num,mf.meter_den,ts.note_count,pf.feature_json FROM performance_features pf
        JOIN midi_files mf ON mf.id=pf.file_id JOIN track_stats ts ON ts.file_id=pf.file_id
        AND ts.track_index=pf.track_index AND ts.channel=pf.channel""")
    all_features=[]; groups=defaultdict(list)
    for row in rows:
        tempo_bucket=round(float(row["tempo_bpm"] or 0)/20)*20 if row["tempo_bpm"] else 0
        database.execute("""INSERT INTO performance_tracks(source_file_id,filename,track_index,channel,role,
            tempo_bpm,tempo_bucket,meter_num,meter_den,note_count,feature_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (row["file_id"],row["filename"],row["track_index"],row["channel"],row["role"],row["tempo_bpm"],
             tempo_bucket,row["meter_num"],row["meter_den"],row["note_count"],row["feature_json"]))
        feature=track_feature_from_dict(json.loads(row["feature_json"])); all_features.append(feature)
        groups[(row["role"],tempo_bucket,row["meter_num"],row["meter_den"])].append(feature)
    global_model=GoldDNAModel.fit(all_features); global_json=json.dumps(global_model.to_dict(),separators=(',',':'))
    database.execute("INSERT INTO performance_models(scope_key,role,tempo_bucket,meter_num,meter_den,sample_count,note_count,model_hash,model_json) VALUES(?,?,?,?,?,?,?,?,?)",
        ("global","*",None,None,None,len(all_features),sum(f.note_count for f in all_features),hashlib.sha256(global_json.encode()).hexdigest(),global_json))
    for key,features in groups.items():
        model=GoldDNAModel.fit(features); payload=json.dumps(model.to_dict(),separators=(',',':'))
        scope=f"{key[0]}:{key[1]}:{key[2]}/{key[3]}"
        database.execute("INSERT INTO performance_models(scope_key,role,tempo_bucket,meter_num,meter_den,sample_count,note_count,model_hash,model_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (scope,*key,len(features),sum(f.note_count for f in features),hashlib.sha256(payload.encode()).hexdigest(),payload))
    source.close(); _finish(database,output_path)
    return {"tracks":len(rows),"models":len(groups)+1,"roles":sorted(global_model.profiles)}


def build_voice_database(factory_path: Path, gold_path: Path, output_path: Path) -> dict:
    source=sqlite3.connect(factory_path); source.row_factory=sqlite3.Row
    database=_new_database(output_path,VOICE_SCHEMA); _build_info(database,factory_path,gold_path,"voice")
    catalog=_rows(source,"SELECT name,category,bank_msb,bank_lsb,program,is_rx,source FROM pa800_voice_catalog")
    mappings=_rows(source,"SELECT source_bank_msb,source_bank_lsb,source_program,role,rx_name,target_bank_msb,target_bank_lsb,target_program,confidence,provenance,is_default FROM gm_rx_mappings")
    zones=_rows(source,"SELECT profile_name,oscillator,articulation,velocity_min,velocity_max,key_min,key_max,switch_value,notes FROM rx_zones")
    database.executemany("INSERT INTO voice_catalog(name,category,bank_msb,bank_lsb,program,is_rx,source) VALUES(:name,:category,:bank_msb,:bank_lsb,:program,:is_rx,:source)",catalog)
    database.executemany("""INSERT INTO voice_mappings(source_bank_msb,source_bank_lsb,source_program,role,rx_name,
        target_bank_msb,target_bank_lsb,target_program,confidence,provenance,is_default) VALUES(:source_bank_msb,
        :source_bank_lsb,:source_program,:role,:rx_name,:target_bank_msb,:target_bank_lsb,:target_program,
        :confidence,:provenance,:is_default)""",mappings)
    database.executemany("""INSERT INTO articulation_zones(profile_name,oscillator,articulation,velocity_min,
        velocity_max,key_min,key_max,switch_value,notes) VALUES(:profile_name,:oscillator,:articulation,:velocity_min,
        :velocity_max,:key_min,:key_max,:switch_value,:notes)""",zones)
    drums=[row for row in catalog if row["category"]=="drums"]
    for row in drums:
        profile_count=source.execute("SELECT COUNT(*) FROM instrument_profiles WHERE role IN ('drums','percussion') AND program=?",(row["program"],)).fetchone()[0]
        track_count=source.execute("SELECT COUNT(*) FROM track_stats WHERE role IN ('drums','percussion') AND program=?",(row["program"],)).fetchone()[0]
        database.execute("INSERT INTO drum_profiles(name,bank_msb,bank_lsb,program,source_profile_count,source_track_count,metadata_json) VALUES(?,?,?,?,?,?,?)",
            (row["name"],row["bank_msb"],row["bank_lsb"],row["program"],profile_count,track_count,json.dumps({"verified_target":True})))
    total_profiles=source.execute("SELECT COUNT(*) FROM instrument_profiles WHERE source='factory'").fetchone()[0]
    mapped_profiles=source.execute("""SELECT COUNT(*) FROM instrument_profiles p WHERE p.source='factory' AND EXISTS(
        SELECT 1 FROM gm_rx_mappings m WHERE p.bank_msb=m.source_bank_msb AND p.bank_lsb=m.source_bank_lsb
        AND p.program=m.source_program AND p.role=m.role)""").fetchone()[0]
    total_tracks,total_notes=source.execute("SELECT COUNT(*),COALESCE(SUM(note_count),0) FROM track_stats").fetchone()
    mapped_tracks,mapped_notes=source.execute("""SELECT COUNT(*),COALESCE(SUM(ts.note_count),0) FROM track_stats ts
        WHERE EXISTS(SELECT 1 FROM gm_rx_mappings m WHERE ts.bank_msb=m.source_bank_msb AND ts.bank_lsb=m.source_bank_lsb
        AND ts.program=m.source_program AND ts.role=m.role)""").fetchone()
    details={"profile_percent":round(100*mapped_profiles/total_profiles,2) if total_profiles else 0,
             "track_percent":round(100*mapped_tracks/total_tracks,2) if total_tracks else 0,
             "note_percent":round(100*mapped_notes/total_notes,2) if total_notes else 0}
    database.execute("INSERT INTO coverage_snapshots(profile_total,profile_mapped,track_total,track_mapped,note_total,note_mapped,details_json) VALUES(?,?,?,?,?,?,?)",
        (total_profiles,mapped_profiles,total_tracks,mapped_tracks,total_notes,mapped_notes,json.dumps(details)))
    source.close(); _finish(database,output_path)
    return {"catalog":len(catalog),"mappings":len(mappings),"zones":len(zones),"drum_profiles":len(drums),"coverage":details}


def build_rx_database(factory_path: Path, gold_path: Path, output_path: Path) -> dict:
    source=sqlite3.connect(factory_path); source.row_factory=sqlite3.Row
    database=_new_database(output_path,RX_SCHEMA); _build_info(database,factory_path,gold_path,"rx")
    catalog=_rows(source,"SELECT name,category,bank_msb,bank_lsb,program,source FROM pa800_voice_catalog WHERE is_rx=1")
    database.executemany("INSERT INTO rx_sounds(name,category,bank_msb,bank_lsb,program,source) VALUES(:name,:category,:bank_msb,:bank_lsb,:program,:source)",catalog)
    zones=_rows(source,"SELECT profile_name,oscillator,articulation,velocity_min,velocity_max,key_min,key_max,switch_value,notes FROM rx_zones")
    database.executemany("""INSERT INTO rx_switch_rules(rx_name,oscillator,articulation,velocity_min,velocity_max,
        key_min,key_max,switch_value,notes,rule_source) VALUES(:profile_name,:oscillator,:articulation,:velocity_min,
        :velocity_max,:key_min,:key_max,:switch_value,:notes,'Oscilatori.txt + Factory analysis')""",zones)
    evidence=_rows(source,"""SELECT p.bank_msb source_bank_msb,p.bank_lsb source_bank_lsb,p.program source_program,
        p.name source_name,p.role,m.rx_name,m.target_bank_msb,m.target_bank_lsb,m.target_program,m.confidence,
        m.provenance,1 profile_use_count,COUNT(ts.id) track_count,COALESCE(SUM(ts.note_count),0) note_count,
        AVG(ts.velocity_mean) velocity_mean,AVG(ts.duration_quarters) duration_quarters,
        GROUP_CONCAT(DISTINCT mf.section) sections
        FROM instrument_profiles p JOIN gm_rx_mappings m ON p.bank_msb=m.source_bank_msb
        AND p.bank_lsb=m.source_bank_lsb AND p.program=m.source_program AND p.role=m.role
        LEFT JOIN track_stats ts ON ts.bank_msb=p.bank_msb AND ts.bank_lsb=p.bank_lsb AND ts.program=p.program
        AND ts.role=p.role LEFT JOIN midi_files mf ON mf.id=ts.file_id WHERE p.source='factory'
        GROUP BY p.bank_msb,p.bank_lsb,p.program,p.role""")
    for row in evidence:
        sections=json.dumps(sorted(filter(None,(row.pop("sections") or "").split(','))))
        database.execute("""INSERT INTO factory_rx_evidence(source_bank_msb,source_bank_lsb,source_program,
            source_name,role,rx_name,target_bank_msb,target_bank_lsb,target_program,confidence,provenance,
            profile_use_count,track_count,note_count,velocity_mean,duration_quarters,sections_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(*row.values(),sections))
    behavior=defaultdict(list)
    feature_rows=_rows(source,"""SELECT m.rx_name,pf.role,pf.feature_json FROM performance_features pf
        JOIN track_stats ts ON ts.file_id=pf.file_id AND ts.track_index=pf.track_index AND ts.channel=pf.channel
        JOIN gm_rx_mappings m ON ts.bank_msb=m.source_bank_msb AND ts.bank_lsb=m.source_bank_lsb
        AND ts.program=m.source_program AND ts.role=m.role""")
    for row in feature_rows: behavior[(row["rx_name"],row["role"])].append(track_feature_from_dict(json.loads(row["feature_json"])))
    for (rx_name,role),features in behavior.items():
        payload=json.dumps(GoldDNAModel.fit(features).to_dict(),separators=(',',':'))
        database.execute("INSERT INTO rx_behavior_profiles(rx_name,role,source_track_count,note_count,model_hash,model_json) VALUES(?,?,?,?,?,?)",
            (rx_name,role,len(features),sum(f.note_count for f in features),hashlib.sha256(payload.encode()).hexdigest(),payload))
    usage=_rows(source,"""SELECT m.rx_name,mf.section,pf.cv,COUNT(*) track_count,SUM(ts.note_count) note_count,
        AVG(ts.velocity_mean) velocity_mean,AVG(ts.density_per_quarter) density_per_quarter
        FROM performance_features pf JOIN midi_files mf ON mf.id=pf.file_id JOIN track_stats ts ON ts.file_id=pf.file_id
        AND ts.track_index=pf.track_index AND ts.channel=pf.channel JOIN gm_rx_mappings m ON ts.bank_msb=m.source_bank_msb
        AND ts.bank_lsb=m.source_bank_lsb AND ts.program=m.source_program AND ts.role=m.role
        GROUP BY m.rx_name,mf.section,pf.cv""")
    database.executemany("""INSERT INTO rx_section_usage(rx_name,section,cv,track_count,note_count,velocity_mean,
        density_per_quarter) VALUES(:rx_name,:section,:cv,:track_count,:note_count,:velocity_mean,:density_per_quarter)""",usage)
    for zone in zones:
        if "Kit RX" in zone["profile_name"] or "Std. Kit RX" in zone["profile_name"]:
            switches=zone["notes"] if zone["switch_value"] is None else str(zone["switch_value"])
            database.execute("INSERT INTO rx_drum_layers(rx_name,note_min,note_max,velocity_switches,articulation,source) VALUES(?,?,?,?,?,?)",
                (zone["profile_name"],zone["key_min"],zone["key_max"],switches,zone["articulation"],"Oscilatori.txt"))
    source.close(); _finish(database,output_path)
    return {"sounds":len(catalog),"rules":len(zones),"evidence":len(evidence),"behavior_profiles":len(behavior),
            "section_usage":len(usage),"drum_layers":sum(1 for z in zones if "Kit RX" in z["profile_name"] or "Std. Kit RX" in z["profile_name"])}


def build_optimizer_database(factory_path: Path, gold_path: Path, output_path: Path, performance_path: Path, rx_path: Path) -> dict:
    source=sqlite3.connect(factory_path); source.row_factory=sqlite3.Row
    database=_new_database(output_path,OPTIMIZER_SCHEMA); _build_info(database,factory_path,gold_path,"optimizer")
    runs=_rows(source,"SELECT source_name,source_sha256,output_name,output_sha256,config_json,report_json,created_at FROM optimizer_runs")
    database.executemany("INSERT INTO optimizer_runs(source_name,source_sha256,output_name,output_sha256,config_json,report_json,created_at) VALUES(:source_name,:source_sha256,:output_name,:output_sha256,:config_json,:report_json,:created_at)",runs)
    for name,path in (("factory",factory_path),("gold",gold_path)):
        src=sqlite3.connect(path)
        files=src.execute("SELECT COUNT(*) FROM midi_files").fetchone()[0]; profiles=src.execute("SELECT COUNT(*) FROM instrument_profiles").fetchone()[0]
        features=src.execute("SELECT COUNT(*) FROM performance_features").fetchone()[0]
        database.execute("INSERT INTO corpus_versions(name,file_count,profile_count,feature_count,database_sha256) VALUES(?,?,?,?,?)",
            (name,files,profiles,features,_sha256(path))); src.close()
    perf=sqlite3.connect(performance_path)
    for row in perf.execute("SELECT scope_key,model_hash,sample_count,note_count FROM performance_models"):
        database.execute("INSERT INTO model_versions(name,version_hash,metadata_json) VALUES(?,?,?)",
            (row[0],row[1],json.dumps({"sample_count":row[2],"note_count":row[3]})))
    perf.close()
    rx=sqlite3.connect(rx_path)
    rx_meta={"sounds":rx.execute("SELECT COUNT(*) FROM rx_sounds").fetchone()[0],
             "rules":rx.execute("SELECT COUNT(*) FROM rx_switch_rules").fetchone()[0],
             "evidence":rx.execute("SELECT COUNT(*) FROM factory_rx_evidence").fetchone()[0]}
    database.execute("INSERT INTO model_versions(name,version_hash,metadata_json) VALUES(?,?,?)",
        ("rx-dna",_sha256(rx_path),json.dumps(rx_meta)))
    rx.close(); source.close(); _finish(database,output_path)
    return {"runs":len(runs),"corpora":2}


def build_solo_database(factory_path: Path, gold_path: Path, output_path: Path) -> dict:
    source=sqlite3.connect(gold_path); source.row_factory=sqlite3.Row
    database=_new_database(output_path,SOLO_SCHEMA); _build_info(database,factory_path,gold_path,"solo")
    rows=_rows(source,"""SELECT pf.file_id,mf.filename,pf.track_index,pf.channel,pf.role,ts.program,
        mf.tempo_bpm,mf.meter_num,mf.meter_den,ts.note_count,pf.feature_json
        FROM performance_features pf JOIN midi_files mf ON mf.id=pf.file_id
        JOIN track_stats ts ON ts.file_id=pf.file_id AND ts.track_index=pf.track_index AND ts.channel=pf.channel""")
    descriptors=[]
    for row in rows:
        feature=track_feature_from_dict(json.loads(row["feature_json"]))
        item=solo_descriptor(feature,row["program"])
        item.update({"source_file_id":row["file_id"],"filename":row["filename"],
            "tempo_bpm":row["tempo_bpm"],"tempo_bucket":round(float(row["tempo_bpm"] or 0)/20)*20 if row["tempo_bpm"] else 0,
            "meter_num":row["meter_num"],"meter_den":row["meter_den"]})
        descriptors.append(item)
        database.execute("""INSERT INTO solo_tracks(source_file_id,filename,track_index,channel,role,program,
            family,tempo_bpm,tempo_bucket,meter_num,meter_den,note_count,solo_score,is_solo_candidate,feature_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(row["file_id"],row["filename"],row["track_index"],row["channel"],
            row["role"],row["program"],item["family"],row["tempo_bpm"],item["tempo_bucket"],row["meter_num"],
            row["meter_den"],row["note_count"],item["solo_score"],item["is_solo_candidate"],json.dumps(item,separators=(',',':'))))
    models=aggregate_solo_models(descriptors)
    for model in models:
        database.execute("""INSERT INTO solo_models(family,tempo_bucket,meter_num,meter_den,track_count,
            note_count,model_json) VALUES(?,?,?,?,?,?,?)""",(model["family"],model["tempo_bucket"],model["meter_num"],
            model["meter_den"],model["track_count"],model["note_count"],json.dumps(model,separators=(',',':'))))
    rules=[
        ("preserve_notes","Ne mijenjaj pitch niti redoslijed odsviranih nota",0,0,1),
        ("phrase_arc_velocity","Frazni luk mijenja velocity najviše ±8",-8,8,1),
        ("solo_gate_ratio","Solo gate promjena je ograničena na ±15%",.85,1.15,1),
        ("legato_overlap_quarters","Legato overlap je ograničen na 0.03 četvrtinke",0,.03,1),
        ("preserve_bend_absence","Ne izmišljaj pitch bend ako ga izvor nema",0,0,1),
        ("pitch_bend_scale","Postojeći pitch bend amplitude mijenjaj najviše ±25%",.75,1.25,1),
        ("rx_zone_guard","Svaka solo velocity promjena ostaje u originalnoj RX artikulacijskoj zoni",0,1,1),
        ("eligible_roles","Solo DNA se primjenjuje samo na melodic/guitar kandidatima",0,1,1),
    ]
    database.executemany("INSERT INTO solo_application_rules(rule_key,description,minimum,maximum,enabled) VALUES(?,?,?,?,?)",rules)
    source.close(); _finish(database,output_path)
    return {"tracks":len(rows),"candidates":sum(item["is_solo_candidate"] for item in descriptors),
            "models":len(models),"rules":len(rules)}


def build_all(factory_path: Path, gold_path: Path, data_directory: Path) -> dict:
    for label,path in (("Factory",factory_path),("Gold",gold_path)):
        source=sqlite3.connect(path)
        try:
            exists=source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='midi_files'").fetchone()
            count=source.execute("SELECT COUNT(*) FROM midi_files").fetchone()[0] if exists else 0
        finally:
            source.close()
        if count<=0:
            raise ValueError(f"{label} corpus je prazan; build-dna je blokiran dok se ne pokrene import-archive")
    data_directory.mkdir(parents=True,exist_ok=True)
    paths={"rhythm":data_directory/"rhythm_dna.sqlite3","performance":data_directory/"performance_dna.sqlite3",
           "voice":data_directory/"voice_dna.sqlite3","rx":data_directory/"rx_dna.sqlite3",
           "optimizer":data_directory/"optimizer_dna.sqlite3","solo":data_directory/"solo_dna.sqlite3",
           "instrument_structure":data_directory/"instrument_structure_dna.sqlite3"}
    result={}
    result["rhythm"]=build_rhythm_database(factory_path,gold_path,paths["rhythm"])
    result["performance"]=build_performance_database(factory_path,gold_path,paths["performance"])
    result["voice"]=build_voice_database(factory_path,gold_path,paths["voice"])
    result["rx"]=build_rx_database(factory_path,gold_path,paths["rx"])
    result["solo"]=build_solo_database(factory_path,gold_path,paths["solo"])
    result["instrument_structure"]=build_instrument_structure_database(factory_path,gold_path,paths["instrument_structure"])
    result["optimizer"]=build_optimizer_database(factory_path,gold_path,paths["optimizer"],paths["performance"],paths["rx"])
    result["paths"]={name:str(path) for name,path in paths.items()}
    return result


def dna_status(data_directory: Path) -> dict:
    specs={"rhythm_dna.sqlite3":{"tracks":"rhythm_tracks","profiles":"section_profiles"},
           "performance_dna.sqlite3":{"tracks":"performance_tracks","profiles":"performance_models"},
           "voice_dna.sqlite3":{"tracks":"voice_mappings","profiles":"voice_catalog"},
           "rx_dna.sqlite3":{"tracks":"factory_rx_evidence","profiles":"rx_behavior_profiles"},
           "solo_dna.sqlite3":{"tracks":"solo_tracks","profiles":"solo_models"},
           "strumming_dna.sqlite3":{"tracks":"strumming_tracks","profiles":"strumming_models"},
           "delay_dna.sqlite3":{"tracks":"delay_pairs","profiles":"delay_models"},
           "harmony_dna.sqlite3":{"tracks":"harmony_pairs","profiles":"harmony_models"},
           "ornament_dna.sqlite3":{"tracks":"ornament_tracks","profiles":"ornament_models"},
           "sound_intelligence_dna.sqlite3":{"tracks":"factory_sound_profiles","profiles":"mix_profiles"},
           "instrument_structure_dna.sqlite3":{"tracks":"factory_instrument_structures","profiles":"gold_instrument_corrections"},
           "optimizer_dna.sqlite3":{"tracks":"optimizer_runs","profiles":"model_versions"},
           "hardware_test_dna.sqlite3":{"tracks":"test_cases","profiles":"agent_reports"},
           "rx_noise_probe.sqlite3":{"tracks":"probe_files","profiles":"probe_results"},
           "articulation_probe.sqlite3":{"tracks":"articulation_probe_files","profiles":"articulation_probe_results"}}
    specs["rhythm_validation.sqlite3"]={"tracks":"track_quality","profiles":"calibration_contexts"}
    specs["rhythm_calibration.sqlite3"]={"tracks":"phrase_candidates","profiles":"repeated_pattern_calibration"}
    specs["rhythm_consensus.sqlite3"]={"tracks":"consensus_context","profiles":"consensus_event_slot"}
    specs["evidence_registry.sqlite3"]={"tracks":"claims","profiles":"subjects"}
    specs["musical_intelligence_dna.sqlite3"]={"tracks":"trill_occurrences","profiles":"trill_patterns"}
    result={}
    for filename,tables in specs.items():
        path=data_directory/filename
        if not path.exists(): result[filename]={"exists":False}; continue
        database=sqlite3.connect(path)
        try:
            result[filename]={"exists":True,"bytes":path.stat().st_size,
                **{name:database.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for name,table in tables.items()},
                "integrity":database.execute("PRAGMA integrity_check").fetchone()[0]}
        except sqlite3.Error as error:
            result[filename]={"exists":True,"bytes":path.stat().st_size,"integrity":"error","error":str(error)}
        finally:
            database.close()
    return result


def load_rx_rules(path: Path,evidence_registry_path: Path|None=None) -> dict[str,list[dict]]:
    policy=load_runtime_evidence_policy(evidence_registry_path) if evidence_registry_path else None
    database=sqlite3.connect(path); database.row_factory=sqlite3.Row; result=defaultdict(list)
    for row in database.execute("SELECT * FROM rx_switch_rules ORDER BY rx_name,oscillator"):
        item=dict(row);zone_key=f"zone:{row['rx_name']}:{row['oscillator']}"
        gate=(policy or {}).get("zones",{}).get(zone_key,{})
        item["runtime_transform_allowed"]=bool(gate.get("transform_existing_allowed")) if policy else True
        item["runtime_generation_allowed"]=bool(gate.get("generate_articulation_allowed")) if policy else False
        item["evidence_statuses"]=gate.get("statuses",{})
        item["evidence_conflicted"]=bool(gate.get("conflicted"))
        malformed=any(value is not None and not 0<=int(value)<=127 for value in
            (item.get("velocity_min"),item.get("velocity_max"),item.get("key_min"),item.get("key_max"),item.get("switch_value")))
        malformed|=(item.get("velocity_min") is not None and item.get("velocity_max") is not None and
                    int(item["velocity_min"])>int(item["velocity_max"]))
        malformed|=(item.get("key_min") is not None and item.get("key_max") is not None and
                    int(item["key_min"])>int(item["key_max"]))
        item["malformed"]=bool(malformed)
        if malformed:item["runtime_transform_allowed"]=False;item["runtime_generation_allowed"]=False
        result[row["rx_name"]].append(item)
    database.close()
    output=dict(result);output["__gate__"]={name:{"transform_existing_allowed":any(rule["runtime_transform_allowed"] for rule in rules),
        "generate_articulation_allowed":any(rule["runtime_generation_allowed"] for rule in rules),
        "conflicted":any(rule["evidence_conflicted"] for rule in rules)} for name,rules in result.items()}
    output["__policy__"]=policy or {}
    output["__report__"]=({key:value for key,value in policy.items() if key not in ("zones","sounds")} if policy else
        {"mode":"legacy_no_registry","fail_closed":False,
        "rules_admitted_transform":sum(len(value) for value in result.values()),"rules_admitted_generation":0}
    )
    output["__report__"]["rx_rules_total"]=sum(len(value) for value in result.values())
    output["__report__"]["malformed_rules"]=sum(rule["malformed"] for value in result.values() for rule in value)
    return output


def load_performance_model(path: Path, tempo_bpm: float | None, meter_num: int, meter_den: int):
    """Load the closest derived role models, falling back to the global model."""
    database=sqlite3.connect(path); database.row_factory=sqlite3.Row
    global_row=database.execute("SELECT model_json,sample_count,note_count FROM performance_models WHERE scope_key='global'").fetchone()
    if global_row is None:
        database.close(); raise ValueError("Performance DNA nema globalni model")
    payload=json.loads(global_row[0]); chosen={}; target_bucket=round(float(tempo_bpm or 0)/20)*20 if tempo_bpm else 0
    for role in list(payload.get("profiles",{})):
        row=database.execute("""SELECT model_json,scope_key,sample_count,note_count,tempo_bucket FROM performance_models
            WHERE role=? AND meter_num=? AND meter_den=? ORDER BY ABS(tempo_bucket-?) LIMIT 1""",
            (role,meter_num,meter_den,target_bucket)).fetchone()
        if row:
            role_payload=json.loads(row[0]).get("profiles",{}).get(role)
            if role_payload: payload["profiles"][role]=role_payload
            chosen[role]={"scope":row[1],"sample_count":row[2],"note_count":row[3],"tempo_bucket":row[4]}
        else:
            chosen[role]={"scope":"global","sample_count":global_row[1],"note_count":global_row[2]}
    database.close()
    return GoldDNAModel.from_dict(payload),{"target_tempo_bucket":target_bucket,"meter":f"{meter_num}/{meter_den}","roles":chosen}


def load_solo_models(path: Path) -> list[dict]:
    database=sqlite3.connect(path); database.row_factory=sqlite3.Row
    result=[json.loads(row[0]) for row in database.execute("SELECT model_json FROM solo_models")]
    database.close(); return result