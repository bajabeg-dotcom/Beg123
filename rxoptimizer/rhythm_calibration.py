"""Grid-free robust calibration for repeated rhythm-pattern observations."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import sqlite3
from statistics import median
from zipfile import ZipFile

from .midi import parse_midi
from .rhythm_context import (
    bar_pattern_fingerprints,extract_rhythm_note_context,multi_bar_candidates,phrase_candidates,
)


MINIMUM_REPEATED_BARS=3

SCHEMA="""
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE phrase_candidates(
 id INTEGER PRIMARY KEY,corpus TEXT NOT NULL,source_sha256 TEXT NOT NULL,filename TEXT NOT NULL,
 track_index INTEGER NOT NULL,channel INTEGER NOT NULL,role TEXT NOT NULL,section TEXT NOT NULL,
 phrase_id TEXT NOT NULL,phrase_index INTEGER NOT NULL,start_tick INTEGER NOT NULL,end_tick INTEGER NOT NULL,
 start_bar INTEGER NOT NULL,end_bar INTEGER NOT NULL,note_count INTEGER NOT NULL,cross_bar INTEGER NOT NULL,
 boundary_status TEXT NOT NULL,end_reason TEXT NOT NULL,
 UNIQUE(corpus,source_sha256,track_index,channel,phrase_index));
CREATE TABLE multi_bar_patterns(
 id INTEGER PRIMARY KEY,corpus TEXT NOT NULL,source_sha256 TEXT NOT NULL,filename TEXT NOT NULL,
 track_index INTEGER NOT NULL,channel INTEGER NOT NULL,role TEXT NOT NULL,section TEXT NOT NULL,
 window_bars INTEGER NOT NULL,start_bar INTEGER NOT NULL,end_bar INTEGER NOT NULL,
 sequence_sha256 TEXT NOT NULL,occurrence_count INTEGER NOT NULL,sequence_json TEXT NOT NULL,
 UNIQUE(corpus,source_sha256,track_index,channel,window_bars,start_bar));
CREATE TABLE repeated_pattern_calibration(
 id INTEGER PRIMARY KEY,corpus TEXT NOT NULL,source_sha256 TEXT NOT NULL,filename TEXT NOT NULL,
 track_index INTEGER NOT NULL,channel INTEGER NOT NULL,role TEXT NOT NULL,section TEXT NOT NULL,
 meter_num INTEGER NOT NULL,meter_den INTEGER NOT NULL,topology_sha256 TEXT NOT NULL,
 bar_count INTEGER NOT NULL,event_count INTEGER NOT NULL,minimum_bars INTEGER NOT NULL,
 status TEXT NOT NULL,profile_json TEXT NOT NULL,
 UNIQUE(corpus,source_sha256,track_index,channel,topology_sha256));
CREATE INDEX calibration_context ON repeated_pattern_calibration(corpus,role,section,meter_num,meter_den);
CREATE TABLE build_summary(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
"""


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


def calibrate_repeated_patterns(observations:list[dict],minimum_bars:int=MINIMUM_REPEATED_BARS)->list[dict]:
    """Learn event-index phase distributions only from repeated topology.

    No grid location is constructed.  Bars align only when track/channel,
    meter and musical topology match, then each event index is measured as an
    observed fraction of its real bar length.
    """
    bar_meta={(row["track"],row["channel"],row["bar"]):row for row in bar_pattern_fingerprints(observations)}
    notes=defaultdict(list)
    for row in observations:notes[(row["track"],row["channel"],row["bar"])].append(row)
    topology_groups=defaultdict(list)
    for key,meta in bar_meta.items():
        topology_groups[(meta["track"],meta["channel"],meta["meter_num"],meta["meter_den"],meta["topology_sha256"])].append(key)
    profiles=[]
    for key,bar_keys in sorted(topology_groups.items()):
        if len(bar_keys)<minimum_bars:continue
        aligned=[]
        for bar_key in sorted(bar_keys,key=lambda item:item[2]):
            rows=sorted(notes[bar_key],key=lambda item:(item["tick_in_bar"],item["note"],item["note_id"]))
            clusters=[]
            for row in rows:
                if not clusters or clusters[-1][0]["tick_in_bar"]!=row["tick_in_bar"]:clusters.append([row])
                else:clusters[-1].append(row)
            aligned.append(clusters)
        event_count=len(aligned[0])
        if not event_count or any(len(rows)!=event_count for rows in aligned):continue
        event_profiles=[]
        for index in range(event_count):
            phases=[clusters[index][0]["tick_in_bar"]/max(1,clusters[index][0]["bar_ticks"]) for clusters in aligned]
            durations=[median([row["duration_quarters"] for row in clusters[index]]) for clusters in aligned]
            velocities=[median([float(row["velocity"]) for row in clusters[index]]) for clusters in aligned]
            cluster_sizes=[len(clusters[index]) for clusters in aligned]
            event_profiles.append({"event_index":index,"onset_cluster":True,"cluster_size":_stats(cluster_sizes),
                "phase":_stats(phases),"duration_quarters":_stats(durations),"velocity":_stats(velocities)})
        varying_events=sum(profile["phase"]["mad"]>0 or profile["phase"]["iqr"]>0 for profile in event_profiles)
        status="ROBUST_VARIATION_PROFILE" if varying_events else "EXACT_REPEAT_REFERENCE"
        boundary_wrap=any(any(row["cross_bar"] for cluster in clusters for row in cluster) for clusters in aligned)
        profiles.append({"track":key[0],"channel":key[1],"meter_num":key[2],"meter_den":key[3],
            "topology_sha256":key[4],"bar_count":len(aligned),"event_count":event_count,
            "minimum_bars":minimum_bars,"status":status,"varying_event_count":varying_events,
            "tolerance_capability":"OBSERVED_VARIATION" if varying_events else "ZERO_VARIANCE_NO_TOLERANCE",
            "alignment":"ONSET_CLUSTER","boundary_wrap":boundary_wrap,"event_profiles":event_profiles,
            "repair_capability":"NONE_ANALYZE_ONLY"})
    return profiles


def evaluate_bar_against_profile(rows:list[dict],profile:dict)->dict:
    """Describe deviation from a profile; never return a repair target."""
    ordered=sorted(rows,key=lambda item:(item["tick_in_bar"],item["note"],item["note_id"]));selected=[]
    for row in ordered:
        if not selected or selected[-1][0]["tick_in_bar"]!=row["tick_in_bar"]:selected.append([row])
        else:selected[-1].append(row)
    if len(selected)!=int(profile["event_count"]):
        return {"status":"STRUCTURE_MISMATCH","event_scores":[],"repair_allowed":False}
    scores=[]
    for cluster,event_profile in zip(selected,profile["event_profiles"]):
        row=cluster[0];value=row["tick_in_bar"]/max(1,row["bar_ticks"]);stats=event_profile["phase"]
        scale=1.4826*float(stats["mad"])
        if scale<=1e-12:scale=float(stats["iqr"])/1.349
        score=0.0 if scale<=1e-12 and abs(value-float(stats["median"]))<=1e-12 else 99.0 if scale<=1e-12 else abs(value-float(stats["median"]))/scale
        scores.append({"note_ids":[item["note_id"] for item in cluster],"event_index":event_profile["event_index"],
            "observed_phase":value,"robust_score":score})
    negative=[]
    if any(row["cross_bar"] for row in ordered):negative.append("CROSS_BAR_PROTECTED")
    if profile.get("boundary_wrap"):negative.append("BOUNDARY_WRAP_PROFILE")
    return {"status":"OBSERVED","event_scores":scores,"max_robust_score":max((row["robust_score"] for row in scores),default=0.0),
        "negative_rules":negative,"repair_allowed":False}


def _file_sha(path:Path)->str:
    digest=sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()


def _eligible_tracks(validation_path:Path)->dict[tuple[str,str],dict[tuple[int,int],dict]]:
    database=sqlite3.connect(validation_path);database.row_factory=sqlite3.Row;result=defaultdict(dict)
    for row in database.execute("""SELECT corpus,source_sha256,track_index,channel,role,section
      FROM track_quality WHERE eligible_for_validated_dna=1 AND source_validation_status='VALID'"""):
        result[(row["corpus"],row["source_sha256"])][(row["track_index"],row["channel"])]=dict(row)
    database.close();return result


def build_rhythm_calibration_database(archive_path:Path,validation_path:Path,output_path:Path)->dict:
    """Materialize phrase/multi-bar candidates and local repeated-pattern calibration."""
    temp=output_path.with_suffix(output_path.suffix+".tmp");temp.unlink(missing_ok=True)
    database=sqlite3.connect(temp);database.executescript(SCHEMA)
    database.executemany("INSERT INTO build_info VALUES(?,?)",(
        ("schema_version","1"),("builder_version","1"),("archive_sha256",_file_sha(archive_path)),
        ("validation_database_sha256",_file_sha(validation_path)),("mode","ANALYZE_ONLY"),
        ("repair_capability","NONE"),("minimum_repeated_bars",str(MINIMUM_REPEATED_BARS))))
    eligible=_eligible_tracks(validation_path);seen=set();counts=defaultdict(int)
    with ZipFile(archive_path) as outer:
        for nested_name in outer.namelist():
            lower=nested_name.lower();corpus="gold" if "gold" in lower else "factory" if "factory" in lower else None
            if not corpus or not lower.endswith(".zip"):continue
            with ZipFile(BytesIO(outer.read(nested_name))) as nested:
                for info in nested.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"):continue
                    data=nested.read(info);digest=sha256(data).hexdigest()
                    if (corpus,digest) in seen:continue
                    seen.add((corpus,digest));track_meta=eligible.get((corpus,digest),{})
                    if not track_meta:counts[f"{corpus}_files_skipped"]+=1;continue
                    midi=parse_midi(data);observations=extract_rhythm_note_context(midi,digest)
                    for key,meta in sorted(track_meta.items()):
                        selected=[row for row in observations if (row["track"],row["channel"])==key]
                        if not selected:continue
                        counts[f"{corpus}_tracks"]+=1
                        for phrase in phrase_candidates(selected):
                            database.execute("""INSERT INTO phrase_candidates(corpus,source_sha256,filename,track_index,
                              channel,role,section,phrase_id,phrase_index,start_tick,end_tick,start_bar,end_bar,note_count,
                              cross_bar,boundary_status,end_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (corpus,digest,info.filename,key[0],key[1],meta["role"],meta["section"],phrase["phrase_id"],
                               phrase["phrase_index"],phrase["start_tick"],phrase["end_tick"],phrase["start_bar"],
                               phrase["end_bar"],phrase["note_count"],int(phrase["cross_bar"]),phrase["boundary_status"],phrase["end_reason"]))
                            counts["phrases"]+=1
                        for pattern in multi_bar_candidates(selected):
                            database.execute("""INSERT INTO multi_bar_patterns(corpus,source_sha256,filename,track_index,
                              channel,role,section,window_bars,start_bar,end_bar,sequence_sha256,occurrence_count,sequence_json)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (corpus,digest,info.filename,key[0],key[1],meta["role"],meta["section"],pattern["window_bars"],
                               pattern["start_bar"],pattern["end_bar"],pattern["sequence_sha256"],pattern["occurrence_count"],
                               json.dumps(pattern["bar_pattern_ids"],separators=(',',':'))))
                            counts["multi_bar_instances"]+=1
                            if pattern["occurrence_count"]>1:counts["repeated_multi_bar_instances"]+=1
                        for profile in calibrate_repeated_patterns(selected):
                            database.execute("""INSERT INTO repeated_pattern_calibration(corpus,source_sha256,filename,
                              track_index,channel,role,section,meter_num,meter_den,topology_sha256,bar_count,event_count,
                              minimum_bars,status,profile_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (corpus,digest,info.filename,key[0],key[1],meta["role"],meta["section"],profile["meter_num"],
                               profile["meter_den"],profile["topology_sha256"],profile["bar_count"],profile["event_count"],
                               profile["minimum_bars"],profile["status"],json.dumps(profile,separators=(',',':'))))
                            counts["calibration_profiles"]+=1
                            counts[profile["status"].lower()]+=1
    summary={**dict(sorted(counts.items())),"source_files_seen":len(seen),"mode":"ANALYZE_ONLY","repair_capability":False}
    database.execute("INSERT INTO build_summary VALUES('summary',?)",(json.dumps(summary,separators=(',',':')),))
    integrity=database.execute("PRAGMA integrity_check").fetchone()[0];foreign_keys=len(database.execute("PRAGMA foreign_key_check").fetchall())
    database.commit();database.close()
    if integrity!="ok" or foreign_keys:
        temp.unlink(missing_ok=True);raise ValueError(f"Rhythm calibration integrity failed: {integrity}, fk={foreign_keys}")
    temp.replace(output_path);return summary


def rhythm_calibration_status(path:Path)->dict:
    if not path.exists():return {"exists":False}
    database=sqlite3.connect(path)
    try:
        summary=json.loads(database.execute("SELECT value_json FROM build_summary WHERE key='summary'").fetchone()[0])
        return {"exists":True,"bytes":path.stat().st_size,"integrity":database.execute("PRAGMA integrity_check").fetchone()[0],**summary}
    finally:database.close()