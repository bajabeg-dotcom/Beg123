"""Read-only corpus validation and robust rhythm outlier registry.

This module never repairs MIDI and never mutates a source corpus.  It records
archive lineage, parser/semantic observations and robust track-level quality
classifications that a later X10 calibration engine may review.
"""

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

from .midi import MidiError, parse_midi, validate_midi


SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE corpus_members(
 id INTEGER PRIMARY KEY,corpus TEXT NOT NULL,member_path TEXT NOT NULL,sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL,duplicate_rank INTEGER NOT NULL,in_raw_database INTEGER NOT NULL,
 raw_file_id INTEGER,validation_status TEXT NOT NULL,validation_json TEXT NOT NULL,
 UNIQUE(corpus,member_path));
CREATE INDEX corpus_members_sha ON corpus_members(corpus,sha256);
CREATE TABLE calibration_contexts(
 context_key TEXT PRIMARY KEY,corpus TEXT NOT NULL,role TEXT NOT NULL,section TEXT NOT NULL,
 meter_num INTEGER NOT NULL,meter_den INTEGER NOT NULL,specificity TEXT NOT NULL,
 sample_count INTEGER NOT NULL,minimum_samples INTEGER NOT NULL,statistics_json TEXT NOT NULL,
 model_status TEXT NOT NULL);
CREATE TABLE track_quality(
 id INTEGER PRIMARY KEY,corpus TEXT NOT NULL,source_file_id INTEGER NOT NULL,source_sha256 TEXT NOT NULL,
 filename TEXT NOT NULL,track_index INTEGER NOT NULL,channel INTEGER NOT NULL,role TEXT NOT NULL,
 section TEXT NOT NULL,meter_num INTEGER NOT NULL,meter_den INTEGER NOT NULL,context_key TEXT,
 source_validation_status TEXT NOT NULL,
 sample_count INTEGER NOT NULL,classification TEXT NOT NULL,max_robust_score REAL NOT NULL,
 metrics_json TEXT NOT NULL,scores_json TEXT NOT NULL,reasons_json TEXT NOT NULL,
 eligible_for_validated_dna INTEGER NOT NULL,review_required INTEGER NOT NULL,
 UNIQUE(corpus,source_file_id,track_index,channel));
CREATE INDEX track_quality_class ON track_quality(corpus,classification,role,section);
CREATE TABLE quality_summary(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
"""

METRICS=("velocity_mean","velocity_std","duration_quarters","density_per_quarter","note_count_log")
MINIMUM_CONTEXT_SAMPLES=20
RARE_SCORE=3.5
OUTLIER_SCORE=6.0


def note_pair_diagnostics(midi)->dict:
    """Locate unmatched note events and describe edge concentration only."""
    tracks=[];total_on=total_off=0
    for track_index,events in enumerate(midi.tracks):
        active=defaultdict(list);unmatched_off=[]
        ordered=sorted(events,key=lambda event:(event.tick,event.order));max_tick=max((int(event.tick) for event in ordered),default=0)
        for event in ordered:
            if event.channel is None:continue
            key=(int(event.channel),int(event.data1 or 0))
            if event.kind=="note_on" and int(event.data2 or 0)>0:active[key].append(event)
            elif event.kind=="note_off":
                if active[key]:active[key].pop(0)
                else:unmatched_off.append(event)
        unmatched_on=[event for values in active.values() for event in values]
        if not unmatched_on and not unmatched_off:continue
        start_edge=sum(int(event.tick)<=midi.division for event in unmatched_off)
        end_edge=sum(int(event.tick)>=max(0,max_tick-midi.division) for event in unmatched_on)
        warning_count=len(unmatched_on)+len(unmatched_off);edge_count=start_edge+end_edge
        concentration=edge_count/warning_count if warning_count else 0.0
        tracks.append({"track":track_index,"max_tick":max_tick,"unmatched_note_on":len(unmatched_on),
            "unmatched_note_off":len(unmatched_off),"off_near_start":start_edge,"on_near_end":end_edge,
            "edge_concentration":concentration,"boundary_observation":"EDGE_CONCENTRATED" if concentration>=.8 else "DISTRIBUTED",
            "sample_on_ticks":[int(event.tick) for event in unmatched_on[:20]],
            "sample_off_ticks":[int(event.tick) for event in unmatched_off[:20]]})
        total_on+=len(unmatched_on);total_off+=len(unmatched_off)
    return {"unmatched_note_on":total_on,"unmatched_note_off":total_off,"tracks":tracks,
        "interpretation":"OBSERVATION_ONLY_NOT_AUTOMATIC_ERROR"}


def _file_sha(path:Path)->str:
    digest=sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()


def _percentile(values:list[float],fraction:float)->float:
    if not values:return 0.0
    ordered=sorted(values);position=(len(ordered)-1)*fraction
    lower=int(math.floor(position));upper=int(math.ceil(position))
    if lower==upper:return float(ordered[lower])
    weight=position-lower
    return float(ordered[lower]*(1-weight)+ordered[upper]*weight)


def robust_statistics(rows:list[dict])->dict:
    result={}
    for metric in METRICS:
        values=[float(row[metric]) for row in rows if math.isfinite(float(row[metric]))]
        center=median(values) if values else 0.0
        deviations=[abs(value-center) for value in values]
        q1=_percentile(values,.25);q3=_percentile(values,.75)
        result[metric]={"median":center,"mad":median(deviations) if deviations else 0.0,
            "q1":q1,"q3":q3,"iqr":q3-q1,"p05":_percentile(values,.05),
            "p95":_percentile(values,.95),"count":len(values)}
    return result


def robust_scores(metrics:dict,statistics:dict)->dict:
    scores={}
    for metric in METRICS:
        value=float(metrics[metric]);stats=statistics[metric]
        scale=1.4826*float(stats["mad"])
        if scale<=1e-12:scale=float(stats["iqr"])/1.349
        if scale<=1e-12:scores[metric]=0.0 if abs(value-float(stats["median"]))<=1e-12 else 99.0
        else:scores[metric]=abs(value-float(stats["median"]))/scale
    return scores


def classify_metrics(metrics:dict,statistics:dict,sample_count:int)->tuple[str,dict,list[str]]:
    if sample_count<MINIMUM_CONTEXT_SAMPLES:
        return "RARE",{},["insufficient_exact_or_fallback_context_samples"]
    if any(not math.isfinite(float(metrics[name])) or float(metrics[name])<0 for name in METRICS):
        return "INVALID",{},["invalid_or_non_finite_metric"]
    scores=robust_scores(metrics,statistics);maximum=max(scores.values(),default=0.0)
    elevated=sum(score>=RARE_SCORE for score in scores.values())
    if maximum>=OUTLIER_SCORE and elevated>=2:
        return "OUTLIER",scores,[name for name,score in scores.items() if score>=RARE_SCORE]
    if maximum>=RARE_SCORE:
        return "RARE",scores,[name for name,score in scores.items() if score>=RARE_SCORE]
    return "NORMAL",scores,[]


def _context_key(corpus:str,role:str,section:str,meter_num:int,meter_den:int,specificity:str)->str:
    return f"{corpus}:{role}:{section}:{meter_num}/{meter_den}:{specificity}"


def _track_rows(path:Path,corpus:str)->list[dict]:
    database=sqlite3.connect(path);database.row_factory=sqlite3.Row
    rows=[]
    for row in database.execute("""SELECT ts.file_id,mf.sha256,mf.filename,ts.track_index,ts.channel,ts.role,
      COALESCE(mf.section,'') section,COALESCE(mf.meter_num,4) meter_num,COALESCE(mf.meter_den,4) meter_den,
      ts.note_count,ts.velocity_mean,ts.velocity_std,ts.duration_quarters,ts.density_per_quarter
      FROM track_stats ts JOIN midi_files mf ON mf.id=ts.file_id"""):
        item=dict(row);item["corpus"]=corpus
        item["note_count_log"]=math.log1p(max(0,int(item["note_count"] or 0)))
        for key in ("velocity_mean","velocity_std","duration_quarters","density_per_quarter"):
            item[key]=float(item[key] or 0.0)
        rows.append(item)
    database.close();return rows


def _raw_files(path:Path)->dict[str,tuple[int,str]]:
    database=sqlite3.connect(path)
    result={str(row[1]):(int(row[0]),str(row[2])) for row in database.execute("SELECT id,sha256,filename FROM midi_files")}
    database.close();return result


def build_rhythm_validation_database(archive_path:Path,factory_db:Path,gold_db:Path,output_path:Path)->dict:
    """Build an atomic, read-only-observation database from archive and RAW DBs."""
    temp=output_path.with_suffix(output_path.suffix+".tmp");temp.unlink(missing_ok=True)
    database=sqlite3.connect(temp);database.executescript(SCHEMA)
    database.executemany("INSERT INTO build_info VALUES(?,?)",(
        ("schema_version","1"),("builder_version","1"),("archive_sha256",_file_sha(archive_path)),
        ("factory_database_sha256",_file_sha(factory_db)),("gold_database_sha256",_file_sha(gold_db)),
        ("repair_capability","NONE_ANALYZE_ONLY"),("minimum_context_samples",str(MINIMUM_CONTEXT_SAMPLES)),
        ("rare_score",str(RARE_SCORE)),("outlier_score",str(OUTLIER_SCORE))))
    raw_maps={"factory":_raw_files(factory_db),"gold":_raw_files(gold_db)}
    member_counts=defaultdict(int);file_status=defaultdict(int);source_statuses={}
    with ZipFile(archive_path) as outer:
        for nested_name in outer.namelist():
            lower=nested_name.lower();corpus="gold" if "gold" in lower else "factory" if "factory" in lower else None
            if not corpus or not lower.endswith(".zip"):continue
            with ZipFile(BytesIO(outer.read(nested_name))) as nested:
                for info in nested.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"):continue
                    data=nested.read(info);digest=sha256(data).hexdigest();member_counts[(corpus,digest)]+=1
                    raw=raw_maps[corpus].get(digest);status="VALID";validation={}
                    try:
                        midi=parse_midi(data);validation=validate_midi(midi)
                        validation.update({"format":midi.format,"division":midi.division,"tracks":len(midi.tracks)})
                        if midi.division<=0 or validation["invalid_values"]:status="INVALID"
                        elif validation["unmatched_note_on"] or validation["unmatched_note_off"]:
                            status="WARNING_NOTE_PAIR";validation["note_pair_diagnostics"]=note_pair_diagnostics(midi)
                    except (MidiError,ValueError) as error:
                        status="INVALID";validation={"error":str(error)}
                    file_status[(corpus,status)]+=1
                    previous=source_statuses.get((corpus,digest),"VALID")
                    source_statuses[(corpus,digest)]=status if status!="VALID" else previous
                    database.execute("""INSERT INTO corpus_members(corpus,member_path,sha256,size_bytes,duplicate_rank,
                      in_raw_database,raw_file_id,validation_status,validation_json) VALUES(?,?,?,?,?,?,?,?,?)""",
                      (corpus,info.filename,digest,len(data),member_counts[(corpus,digest)],int(raw is not None),
                       raw[0] if raw else None,status,json.dumps(validation,separators=(',',':'))))

    tracks=_track_rows(factory_db,"factory")+_track_rows(gold_db,"gold")
    groups=defaultdict(list)
    for row in tracks:
        section=row["section"] or "*";meter_num=int(row["meter_num"]);meter_den=int(row["meter_den"])
        groups[(row["corpus"],row["role"],section,meter_num,meter_den,"exact")].append(row)
        groups[(row["corpus"],row["role"],"*",meter_num,meter_den,"role_meter")].append(row)
        groups[(row["corpus"],row["role"],"*",0,0,"role")].append(row)
    models={}
    for key,rows in sorted(groups.items()):
        corpus,role,section,meter_num,meter_den,specificity=key;stats=robust_statistics(rows)
        context=_context_key(*key);models[key]=(context,len(rows),stats)
        database.execute("INSERT INTO calibration_contexts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (context,corpus,role,section,meter_num,meter_den,specificity,len(rows),MINIMUM_CONTEXT_SAMPLES,
           json.dumps(stats,separators=(',',':')),"SUFFICIENT" if len(rows)>=MINIMUM_CONTEXT_SAMPLES else "INSUFFICIENT"))

    classifications=defaultdict(int);eligible_total=review_total=source_warning_tracks=0
    for row in tracks:
        exact=(row["corpus"],row["role"],row["section"] or "*",int(row["meter_num"]),int(row["meter_den"]),"exact")
        fallbacks=(exact,(row["corpus"],row["role"],"*",int(row["meter_num"]),int(row["meter_den"]),"role_meter"),
            (row["corpus"],row["role"],"*",0,0,"role"))
        selected=next((models[key] for key in fallbacks if key in models and models[key][1]>=MINIMUM_CONTEXT_SAMPLES),models[exact])
        context,sample_count,stats=selected
        metrics={name:float(row[name]) for name in METRICS}
        classification,scores,reasons=classify_metrics(metrics,stats,sample_count)
        classifications[(row["corpus"],classification)]+=1
        source_status=source_statuses.get((row["corpus"],row["sha256"]),"MISSING_ARCHIVE_MEMBER")
        if source_status!="VALID":reasons=[f"source_validation:{source_status}",*reasons]
        eligible=source_status=="VALID" and classification in ("NORMAL","RARE")
        review=source_status!="VALID" or classification in ("RARE","OUTLIER","INVALID")
        eligible_total+=int(eligible);review_total+=int(review);source_warning_tracks+=int(source_status!="VALID")
        database.execute("""INSERT INTO track_quality(corpus,source_file_id,source_sha256,filename,track_index,
          channel,role,section,meter_num,meter_den,context_key,source_validation_status,sample_count,classification,max_robust_score,
          metrics_json,scores_json,reasons_json,eligible_for_validated_dna,review_required)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (row["corpus"],row["file_id"],row["sha256"],row["filename"],row["track_index"],row["channel"],
           row["role"],row["section"],row["meter_num"],row["meter_den"],context,source_status,sample_count,classification,
           max(scores.values(),default=0.0),json.dumps(metrics,separators=(',',':')),
           json.dumps(scores,separators=(',',':')),json.dumps(reasons,separators=(',',':')),int(eligible),int(review)))
    summary={"members":{f"{corpus}:{status}":count for (corpus,status),count in sorted(file_status.items())},
        "tracks":{f"{corpus}:{status}":count for (corpus,status),count in sorted(classifications.items())},
        "contexts":len(models),"track_total":len(tracks),"eligible_for_validated_dna":eligible_total,
        "review_required":review_total,"source_warning_tracks":source_warning_tracks,"analyze_only":True}
    database.execute("INSERT INTO quality_summary VALUES('summary',?)",(json.dumps(summary,separators=(',',':')),))
    integrity=database.execute("PRAGMA integrity_check").fetchone()[0];database.commit();database.close()
    if integrity!="ok":temp.unlink(missing_ok=True);raise ValueError(f"Rhythm validation integrity failed: {integrity}")
    temp.replace(output_path)
    return summary


def rhythm_validation_status(path:Path)->dict:
    if not path.exists():return {"exists":False}
    database=sqlite3.connect(path)
    try:
        summary=json.loads(database.execute("SELECT value_json FROM quality_summary WHERE key='summary'").fetchone()[0])
        return {"exists":True,"bytes":path.stat().st_size,"integrity":database.execute("PRAGMA integrity_check").fetchone()[0],**summary}
    finally:database.close()