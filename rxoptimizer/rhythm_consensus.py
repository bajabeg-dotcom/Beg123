"""Fail-closed cross-file rhythm consensus and analyze-only anomaly review."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
from statistics import median

from .rhythm_context import bar_pattern_fingerprints


DEFAULT_CONSENSUS_CONFIG={"version":1,"minimum_distinct_files":3,"minimum_total_bars":9,
    "maximum_dominant_source_share":.5,"exact_context_only":True,"repair_capability":"NONE"}

NEGATIVE_RULES=(
    ("CROSS_BAR_PROTECTED",1,"PRESERVE","Cross-bar note or phrase requires boundary-aware review."),
    ("SECTION_SENSITIVE",1,"PRESERVE","Intro/Fill/Break/Ending timing is transition-sensitive."),
    ("LOCAL_REPEAT_SUPPORTS_ORIGINAL",1,"PRESERVE","Repeated local pattern is evidence that the original may be intentional."),
    ("MULTIMODAL_UNASSESSED",1,"PRESERVE","Consensus distribution has not passed multimodality analysis."),
    ("UNKNOWN_OR_LOW_ROLE",0,"PRESERVE_UNTIL_IMPLEMENTED","Role confidence gate is not yet available in calibration records."),
    ("METER_OR_TEMPO_CHANGE_WINDOW",0,"PRESERVE_UNTIL_IMPLEMENTED","Tempo/meter transition window detector is pending."),
    ("GUITAR_MODE_OR_RX_DNC",0,"PRESERVE_UNTIL_IMPLEMENTED","Guitar Mode and RX/DNC event protection must be joined by stable event ID."),
    ("ORNAMENT_TRILL_GRACE",0,"PRESERVE_UNTIL_IMPLEMENTED","Ornament evidence must be joined before anomaly authorization."),
    ("DRUM_FLAM_ROLL_GHOST",0,"PRESERVE_UNTIL_IMPLEMENTED","Drum articulation-specific role model is pending."),
    ("ONSET_CLUSTER_AMBIGUITY",0,"PRESERVE_UNTIL_IMPLEMENTED","Ambiguous cluster/voice alignment blocks authorization."),
    ("FACTORY_GOLD_CONFLICT",0,"PRESERVE_UNTIL_IMPLEMENTED","Unresolved corpus disagreement blocks authorization."),
    ("ZERO_VARIANCE_REFERENCE",0,"REVIEW","Mismatch against exact repeats is not proof of anomaly."),
)

SCHEMA="""
CREATE TABLE consensus_build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE consensus_context(
 id INTEGER PRIMARY KEY,consensus_key TEXT NOT NULL UNIQUE,corpus TEXT NOT NULL,role TEXT NOT NULL,
 section TEXT NOT NULL,meter_num INTEGER NOT NULL,meter_den INTEGER NOT NULL,topology_sha256 TEXT NOT NULL,
 event_count INTEGER NOT NULL,distinct_files INTEGER NOT NULL,profile_count INTEGER NOT NULL,total_bars INTEGER NOT NULL,
 dominant_source_share REAL NOT NULL,status TEXT NOT NULL,variation_status TEXT NOT NULL,
 conflict_status TEXT NOT NULL DEFAULT 'UNASSESSED',repair_capability TEXT NOT NULL DEFAULT 'NONE',profile_json TEXT NOT NULL);
CREATE INDEX consensus_lookup ON consensus_context(corpus,role,section,meter_num,meter_den,topology_sha256,event_count);
CREATE TABLE consensus_event_slot(
 id INTEGER PRIMARY KEY,context_id INTEGER NOT NULL,event_index INTEGER NOT NULL,distinct_files INTEGER NOT NULL,
 phase_json TEXT NOT NULL,duration_json TEXT NOT NULL,velocity_json TEXT NOT NULL,multimodal_status TEXT NOT NULL,
 boundary_wrap INTEGER NOT NULL,FOREIGN KEY(context_id) REFERENCES consensus_context(id) ON DELETE CASCADE,
 UNIQUE(context_id,event_index));
CREATE TABLE consensus_evidence(
 id INTEGER PRIMARY KEY,context_id INTEGER NOT NULL,corpus TEXT NOT NULL,source_sha256 TEXT NOT NULL,
 filename TEXT NOT NULL,track_index INTEGER NOT NULL,channel INTEGER NOT NULL,local_profile_id INTEGER NOT NULL,
 bar_count INTEGER NOT NULL,status TEXT NOT NULL,FOREIGN KEY(context_id) REFERENCES consensus_context(id) ON DELETE CASCADE,
 UNIQUE(context_id,local_profile_id));
CREATE TABLE factory_gold_links(
 id INTEGER PRIMARY KEY,factory_context_id INTEGER NOT NULL,reference_context_id INTEGER NOT NULL,
 relationship TEXT NOT NULL,details_json TEXT NOT NULL,
 FOREIGN KEY(factory_context_id) REFERENCES consensus_context(id),
 FOREIGN KEY(reference_context_id) REFERENCES consensus_context(id),
 UNIQUE(factory_context_id,reference_context_id));
CREATE TABLE negative_rules(
 rule_key TEXT PRIMARY KEY,detectable INTEGER NOT NULL,default_action TEXT NOT NULL,description TEXT NOT NULL,
 rules_version INTEGER NOT NULL);
CREATE TABLE consensus_summary(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
"""


def _file_sha(path:Path)->str:
    digest=sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()


def _percentile(values:list[float],fraction:float)->float:
    ordered=sorted(values)
    if not ordered:return 0.0
    position=(len(ordered)-1)*fraction;lower=int(math.floor(position));upper=int(math.ceil(position))
    if lower==upper:return float(ordered[lower])
    weight=position-lower
    return float(ordered[lower]*(1-weight)+ordered[upper]*weight)


def _stats(values:list[float])->dict:
    center=median(values) if values else 0.0;deviations=[abs(value-center) for value in values]
    q1=_percentile(values,.25);q3=_percentile(values,.75)
    return {"count":len(values),"median":center,"mad":median(deviations) if deviations else 0.0,
        "q1":q1,"q3":q3,"iqr":q3-q1,"p05":_percentile(values,.05),"p95":_percentile(values,.95)}


def _context_key(key:tuple)->str:
    return sha256(json.dumps(key,separators=(',',':')).encode()).hexdigest()


def build_rhythm_consensus_database(calibration_path:Path,output_path:Path,config:dict|None=None)->dict:
    """Aggregate per-file medians with equal source-file voting."""
    if not calibration_path.exists():raise ValueError("Rhythm calibration database is missing")
    cfg={**DEFAULT_CONSENSUS_CONFIG,**(config or {})};temp=output_path.with_suffix(output_path.suffix+".tmp");temp.unlink(missing_ok=True)
    source=sqlite3.connect(calibration_path);source.row_factory=sqlite3.Row
    required=source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='repeated_pattern_calibration'").fetchone()
    if not required:source.close();raise ValueError("Rhythm calibration table is missing")
    database=sqlite3.connect(temp);database.execute("PRAGMA foreign_keys=ON");database.executescript(SCHEMA)
    database.executemany("INSERT INTO consensus_build_info VALUES(?,?)",(
        ("schema_version","1"),("builder_version","1"),("calibration_sha256",_file_sha(calibration_path)),
        ("config_json",json.dumps(cfg,separators=(',',':'))),("mode","ANALYZE_ONLY"),("repair_capability","NONE")))
    database.executemany("INSERT INTO negative_rules VALUES(?,?,?,?,?)",
        ((key,detectable,action,description,int(cfg["version"])) for key,detectable,action,description in NEGATIVE_RULES))
    groups=defaultdict(list)
    for row in source.execute("SELECT * FROM repeated_pattern_calibration"):
        profile=json.loads(row["profile_json"]);key=(row["corpus"],row["role"],row["section"],row["meter_num"],row["meter_den"],
            row["topology_sha256"],row["event_count"])
        groups[key].append((dict(row),profile))
    context_rows=[];summary=defaultdict(int)
    for key,items in sorted(groups.items()):
        per_source=defaultdict(list)
        for row,profile in items:per_source[row["source_sha256"]].append((row,profile))
        distinct=len(per_source);total_bars=sum(int(row["bar_count"]) for row,_ in items)
        source_bars={digest:sum(int(row["bar_count"]) for row,_ in values) for digest,values in per_source.items()}
        dominant=max(source_bars.values(),default=0)/max(1,total_bars)
        sufficient=distinct>=int(cfg["minimum_distinct_files"]) and total_bars>=int(cfg["minimum_total_bars"]) and dominant<=float(cfg["maximum_dominant_source_share"])
        status=("FACTORY_CONSENSUS" if key[0]=="factory" else "REFERENCE_CONSENSUS_CANDIDATE") if sufficient else "INSUFFICIENT_CROSS_FILE_EVIDENCE"
        slots=[];any_variation=False;boundary_wrap=False
        for event_index in range(int(key[6])):
            phases=[];durations=[];velocities=[]
            for digest,values in sorted(per_source.items()):
                phases.append(median([float(profile["event_profiles"][event_index]["phase"]["median"]) for _,profile in values]))
                durations.append(median([float(profile["event_profiles"][event_index]["duration_quarters"]["median"]) for _,profile in values]))
                velocities.append(median([float(profile["event_profiles"][event_index]["velocity"]["median"]) for _,profile in values]))
                boundary_wrap|=any(bool(profile.get("boundary_wrap")) for _,profile in values)
            phase_stats=_stats(phases);any_variation|=phase_stats["mad"]>0 or phase_stats["iqr"]>0
            slots.append({"event_index":event_index,"phase":phase_stats,"duration":_stats(durations),"velocity":_stats(velocities)})
        variation="OBSERVED_CROSS_FILE_VARIATION" if any_variation else "EXACT_CROSS_FILE_REFERENCE_NO_TOLERANCE"
        profile={"config_version":cfg["version"],"corpus":key[0],"role":key[1],"section":key[2],"meter_num":key[3],
            "meter_den":key[4],"topology_sha256":key[5],"event_count":key[6],"distinct_files":distinct,
            "profile_count":len(items),"total_bars":total_bars,"dominant_source_share":dominant,"status":status,
            "variation_status":variation,"multimodal_status":"UNASSESSED","boundary_wrap":boundary_wrap,
            "event_slots":slots,"repair_capability":"NONE_ANALYZE_ONLY"}
        cursor=database.execute("""INSERT INTO consensus_context(consensus_key,corpus,role,section,meter_num,meter_den,
          topology_sha256,event_count,distinct_files,profile_count,total_bars,dominant_source_share,status,variation_status,
          repair_capability,profile_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (_context_key(key),*key[:6],key[6],distinct,len(items),total_bars,dominant,status,variation,"NONE",json.dumps(profile,separators=(',',':'))))
        context_id=cursor.lastrowid;context_rows.append((context_id,key,profile));summary[status]+=1
        for slot in slots:
            database.execute("INSERT INTO consensus_event_slot(context_id,event_index,distinct_files,phase_json,duration_json,velocity_json,multimodal_status,boundary_wrap) VALUES(?,?,?,?,?,?,?,?)",
              (context_id,slot["event_index"],distinct,json.dumps(slot["phase"],separators=(',',':')),
               json.dumps(slot["duration"],separators=(',',':')),json.dumps(slot["velocity"],separators=(',',':')),
               "UNASSESSED",int(boundary_wrap)))
        for row,_ in items:
            database.execute("INSERT INTO consensus_evidence(context_id,corpus,source_sha256,filename,track_index,channel,local_profile_id,bar_count,status) VALUES(?,?,?,?,?,?,?,?,?)",
              (context_id,row["corpus"],row["source_sha256"],row["filename"],row["track_index"],row["channel"],row["id"],row["bar_count"],row["status"]))
    factories=[row for row in context_rows if row[1][0]=="factory" and row[2]["status"]=="FACTORY_CONSENSUS"]
    references=[row for row in context_rows if row[1][0]=="gold" and row[2]["status"]=="REFERENCE_CONSENSUS_CANDIDATE"]
    reference_index=defaultdict(list)
    for row in references:reference_index[(row[1][1],row[1][3],row[1][4],row[1][5],row[1][6])].append(row)
    for factory in factories:
        match_key=(factory[1][1],factory[1][3],factory[1][4],factory[1][5],factory[1][6])
        for reference in reference_index.get(match_key,[]):
            differences=[abs(a["phase"]["median"]-b["phase"]["median"]) for a,b in zip(factory[2]["event_slots"],reference[2]["event_slots"])]
            relationship="SUPPORT_REVIEW" if max(differences,default=0)<=max(
                [slot["phase"]["iqr"] for slot in factory[2]["event_slots"]]+[0]) else "POTENTIAL_CONTRADICTION"
            database.execute("INSERT INTO factory_gold_links(factory_context_id,reference_context_id,relationship,details_json) VALUES(?,?,?,?)",
              (factory[0],reference[0],relationship,json.dumps({"phase_median_differences":differences},separators=(',',':'))))
            summary[f"factory_gold_{relationship.lower()}"]+=1
    summary.update({"contexts":len(context_rows),"source_profiles":sum(len(items) for items in groups.values()),
        "mode":"ANALYZE_ONLY","repair_capability":False,"config":cfg})
    database.execute("INSERT INTO consensus_summary VALUES('summary',?)",(json.dumps(dict(summary),separators=(',',':')),))
    integrity=database.execute("PRAGMA integrity_check").fetchone()[0];fk=len(database.execute("PRAGMA foreign_key_check").fetchall())
    source.close();database.commit();database.close()
    if integrity!="ok" or fk:temp.unlink(missing_ok=True);raise ValueError(f"Consensus integrity failed: {integrity}, fk={fk}")
    temp.replace(output_path);return dict(summary)


def load_factory_consensus(path:Path)->list[dict]:
    if not path.exists():return []
    database=sqlite3.connect(path)
    try:return [json.loads(row[0]) for row in database.execute("SELECT profile_json FROM consensus_context WHERE status='FACTORY_CONSENSUS'")]
    finally:database.close()


def analyze_against_consensus(observations:list[dict],profiles:list[dict],role:str,section:str)->list[dict]:
    """Classify observations for review; never propose or apply a repair."""
    index={(row["role"],row["section"],row["meter_num"],row["meter_den"],row["topology_sha256"],row["event_count"]):row for row in profiles}
    bars=bar_pattern_fingerprints(observations);local_counts=defaultdict(int)
    for bar in bars:local_counts[(bar["track"],bar["channel"],bar["rhythm_pattern_sha256"])]+=1
    note_groups=defaultdict(list)
    for row in observations:note_groups[(row["track"],row["channel"],row["bar"])].append(row)
    output=[]
    for bar in bars:
        key=(role,section,bar["meter_num"],bar["meter_den"],bar["topology_sha256"],bar["onset_cluster_count"]);profile=index.get(key)
        negative=[];rows=note_groups[(bar["track"],bar["channel"],bar["bar"])]
        if any(row["cross_bar"] for row in rows):negative.append("CROSS_BAR_PROTECTED")
        if section.lower() in ("intro","fill","break","ending"):negative.append("SECTION_SENSITIVE")
        if local_counts[(bar["track"],bar["channel"],bar["rhythm_pattern_sha256"])]>1:negative.append("LOCAL_REPEAT_SUPPORTS_ORIGINAL")
        if profile is None:
            output.append({"track":bar["track"],"channel":bar["channel"],"bar":bar["bar"],"status":"NO_EXACT_FACTORY_CONSENSUS",
                "negative_rules":negative,"repair_allowed":False});continue
        if profile.get("multimodal_status")!="ASSESSED_UNIMODAL":negative.append("MULTIMODAL_UNASSESSED")
        clusters=[]
        for row in sorted(rows,key=lambda item:(item["tick_in_bar"],item["note"],item["note_id"])):
            if not clusters or clusters[-1][0]["tick_in_bar"]!=row["tick_in_bar"]:clusters.append([row])
            else:clusters[-1].append(row)
        scores=[];outside=False;zero_variance=False
        for cluster,slot in zip(clusters,profile["event_slots"]):
            phase=cluster[0]["tick_in_bar"]/max(1,cluster[0]["bar_ticks"]);stats=slot["phase"]
            variation=float(stats["mad"])>0 or float(stats["iqr"])>0
            zero_variance|=not variation
            is_outside=phase<float(stats["p05"]) or phase>float(stats["p95"]);outside|=is_outside
            scores.append({"note_ids":[row["note_id"] for row in cluster],"observed_phase":phase,
                "empirical_p05":stats["p05"],"empirical_p95":stats["p95"],"outside_empirical_range":is_outside})
        status="OBSERVED_WITHIN_EMPIRICAL_RANGE"
        if outside and zero_variance:status="OUTSIDE_EXACT_REFERENCE_REVIEW"
        elif outside:status="ANOMALY_CANDIDATE_REVIEW"
        if negative:status="PROTECTED_REVIEW" if outside else "PROTECTED_OBSERVATION"
        output.append({"track":bar["track"],"channel":bar["channel"],"bar":bar["bar"],"status":status,
            "consensus_key":_context_key(key),"event_scores":scores,"negative_rules":negative,
            "explanation":"Classification only; no target tick or mutation generated.","repair_allowed":False})
    return output