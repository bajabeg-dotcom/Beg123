"""Song-only Delay, existing Harmony and Gold-only Ornament DNA.

Harmony is deliberately analysis/optimization-only.  The engine must never
invent a third voice when the source song does not already contain one.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from io import BytesIO
import json
import math
from pathlib import Path
import sqlite3
from statistics import mean, median
from zipfile import ZipFile

from .advanced_analysis import _ornaments
from .features import extract_features, infer_role
from .midi import Event, MidiFile, note_rows, parse_midi


DELAY_SCHEMA="""
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE delay_pairs(id INTEGER PRIMARY KEY,filename TEXT,source_track INTEGER,source_channel INTEGER,
 echo_track INTEGER,echo_channel INTEGER,source_program INTEGER,echo_program INTEGER,offset_quarters REAL,
 match_count INTEGER,coverage REAL,velocity_ratio REAL,gate_ratio REAL,source_note_count INTEGER,
 echo_note_count INTEGER,evidence_json TEXT);
CREATE TABLE delay_models(id INTEGER PRIMARY KEY,scope_key TEXT UNIQUE,source_program INTEGER,
 sample_count INTEGER,note_count INTEGER,offset_quarters REAL,velocity_ratio REAL,gate_ratio REAL,
 coverage REAL,model_json TEXT);
CREATE TABLE delay_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT);
CREATE TABLE delay_phrase_occurrences(id INTEGER PRIMARY KEY,filename TEXT,source_track INTEGER,source_channel INTEGER,
 echo_track INTEGER,echo_channel INTEGER,source_program INTEGER,phrase_index INTEGER,start_tick INTEGER,end_tick INTEGER,
 note_count INTEGER,match_count INTEGER,source_recall REAL,target_precision REAL,classification TEXT,
 offset_quarters REAL,matched_positions_json TEXT,feature_json TEXT);
CREATE TABLE delay_phrase_models(id INTEGER PRIMARY KEY,scope_key TEXT UNIQUE,source_program INTEGER,sample_count INTEGER,
 file_count INTEGER,full_count INTEGER,partial_count INTEGER,skip_count INTEGER,full_ratio REAL,partial_ratio REAL,
 skip_ratio REAL,generation_decision TEXT,generation_allowed INTEGER,model_json TEXT);
CREATE TABLE delay_negative_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT);
"""

HARMONY_SCHEMA="""
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE harmony_pairs(id INTEGER PRIMARY KEY,filename TEXT,source_track INTEGER,source_channel INTEGER,
 harmony_track INTEGER,harmony_channel INTEGER,source_program INTEGER,harmony_program INTEGER,direction TEXT,
 minor_third_count INTEGER,major_third_count INTEGER,match_count INTEGER,coverage REAL,source_recall REAL,
 target_precision REAL,velocity_ratio REAL,
 gate_ratio REAL,evidence_json TEXT);
CREATE TABLE harmony_models(id INTEGER PRIMARY KEY,scope_key TEXT UNIQUE,source_program INTEGER,direction TEXT,
 sample_count INTEGER,note_count INTEGER,minor_ratio REAL,major_ratio REAL,coverage REAL,velocity_ratio REAL,
 gate_ratio REAL,model_json TEXT);
CREATE TABLE harmony_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT);
"""

ORNAMENT_SCHEMA="""
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE ornament_tracks(id INTEGER PRIMARY KEY,filename TEXT,track_index INTEGER,channel INTEGER,program INTEGER,
 family TEXT,tempo_bpm REAL,tempo_bucket INTEGER,note_count INTEGER,grace_count INTEGER,trill_count INTEGER,
 neighbor_count INTEGER,tremolo_count INTEGER,pitch_bend_count INTEGER,profile_json TEXT,
 UNIQUE(filename,track_index,channel));
CREATE TABLE ornament_models(id INTEGER PRIMARY KEY,scope_key TEXT UNIQUE,family TEXT,tempo_bucket INTEGER,
 track_count INTEGER,note_count INTEGER,grace_per_1000 REAL,trill_per_1000 REAL,neighbor_per_1000 REAL,
 tremolo_per_1000 REAL,bend_per_1000 REAL,model_json TEXT);
CREATE TABLE ornament_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT);
"""


def _new_database(path: Path, schema: str) -> sqlite3.Connection:
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+".tmp"); temp.unlink(missing_ok=True)
    database=sqlite3.connect(temp); database.executescript(schema); return database


def _finish(database: sqlite3.Connection, path: Path) -> None:
    temp=Path(database.execute("PRAGMA database_list").fetchone()[2]); database.commit(); database.close(); temp.replace(path)


def _programs(midi: MidiFile) -> dict[tuple[int,int],int]:
    result={}
    for ti,events in enumerate(midi.tracks):
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            if event.kind=="program": result[(ti,int(event.channel or 0))]=int(event.data1 or 0)
    return result


def _groups(midi: MidiFile) -> dict[tuple[int,int],list[dict]]:
    result=defaultdict(list)
    for row in note_rows(midi): result[(row["track"],row["channel"])].append(row)
    for rows in result.values(): rows.sort(key=lambda row:(row["start"],row["note"]))
    return dict(result)


def _note_index(rows: list[dict]) -> dict[tuple[int,int],dict]:
    return {(row["start"],row["note"]):row for row in rows}


def detect_delay_pairs(midi: MidiFile, filename: str="") -> list[dict]:
    groups=_groups(midi); programs=_programs(midi); keys=list(groups); candidates=[]
    offsets=sorted(set(round(midi.division*x) for x in (.125,.25,1/3,.5,.75,1,1.5,2)))
    for i,left in enumerate(keys):
        if len(groups[left])<8 or left[1]==9: continue
        left_index=_note_index(groups[left])
        for right in keys[i+1:]:
            if len(groups[right])<8 or right[1]==9: continue
            right_index=_note_index(groups[right]); best=None
            for offset in offsets:
                ratios=[]; gate=[]; matches=lower=0
                for (tick,note),source in left_index.items():
                    echo=right_index.get((tick+offset,note))
                    if echo is None: continue
                    matches+=1; lower+=echo["velocity"]<source["velocity"]
                    ratios.append(echo["velocity"]/max(1,source["velocity"])); gate.append(echo["duration"]/max(1,source["duration"]))
                coverage=matches/max(1,min(len(left_index),len(right_index)))
                if matches>=8 and coverage>=.8 and lower/max(1,matches)>=.8:
                    item={"filename":filename,"source_track":left[0],"source_channel":left[1],
                        "echo_track":right[0],"echo_channel":right[1],"source_program":programs.get(left,0),
                        "echo_program":programs.get(right,0),"offset_quarters":offset/midi.division,
                        "match_count":matches,"coverage":coverage,"velocity_ratio":median(ratios),
                        "gate_ratio":median(gate),"source_note_count":len(left_index),"echo_note_count":len(right_index)}
                    if best is None or (item["coverage"],item["match_count"])>(best["coverage"],best["match_count"]): best=item
            if best: candidates.append(best)
    # Keep only the strongest source for each echo track.
    strongest={}
    for item in candidates:
        key=(item["echo_track"],item["echo_channel"])
        if key not in strongest or (item["coverage"],item["match_count"])>(strongest[key]["coverage"],strongest[key]["match_count"]): strongest[key]=item
    return sorted(strongest.values(),key=lambda item:(item["filename"],item["source_track"],item["echo_track"]))


def detect_harmony_pairs(midi: MidiFile, filename: str="") -> list[dict]:
    groups=_groups(midi); programs=_programs(midi); keys=list(groups); result=[]
    for i,left in enumerate(keys):
        if len(groups[left])<8 or left[1]==9: continue
        for right in keys[i+1:]:
            if len(groups[right])<8 or right[1]==9: continue
            # Orient the louder line as source.
            left_mean=mean(row["velocity"] for row in groups[left]); right_mean=mean(row["velocity"] for row in groups[right])
            source_key,target_key=(left,right) if left_mean>=right_mean else (right,left)
            source=groups[source_key]; target=groups[target_key]; target_by_tick=defaultdict(list)
            for row in target: target_by_tick[row["start"]].append(row)
            deltas=[]; ratios=[]; gate=[]
            for row in source:
                options=[other for other in target_by_tick.get(row["start"],[]) if abs(other["note"]-row["note"]) in (3,4)]
                if not options: continue
                other=min(options,key=lambda item:abs(item["note"]-row["note"])); deltas.append(other["note"]-row["note"])
                ratios.append(other["velocity"]/max(1,row["velocity"])); gate.append(other["duration"]/max(1,row["duration"]))
            source_recall=len(deltas)/max(1,len(source));target_precision=len(deltas)/max(1,len(target))
            coverage=min(source_recall,target_precision)
            if len(deltas)<8 or source_recall<.55 or target_precision<.75: continue
            direction="up" if sum(delta>0 for delta in deltas)>=sum(delta<0 for delta in deltas) else "down"
            signed=[delta for delta in deltas if (delta>0)==(direction=="up")]
            if len(signed)/len(deltas)<.8: continue
            result.append({"filename":filename,"source_track":source_key[0],"source_channel":source_key[1],
                "harmony_track":target_key[0],"harmony_channel":target_key[1],"source_program":programs.get(source_key,0),
                "harmony_program":programs.get(target_key,0),"direction":direction,
                "minor_third_count":sum(abs(delta)==3 for delta in signed),"major_third_count":sum(abs(delta)==4 for delta in signed),
                "match_count":len(signed),"coverage":min(len(signed)/max(1,len(source)),len(signed)/max(1,len(target))),
                "source_recall":len(signed)/max(1,len(source)),"target_precision":len(signed)/max(1,len(target)),
                "velocity_ratio":median(ratios),"gate_ratio":median(gate)})
    # A single harmony track can accidentally match more than one melodic line.
    # Keep the strongest musical explanation for that target, as with Delay DNA.
    strongest={}
    for item in result:
        key=(item["harmony_track"],item["harmony_channel"])
        score=(item["coverage"],item["match_count"])
        if key not in strongest or score>(strongest[key]["coverage"],strongest[key]["match_count"]):
            strongest[key]=item
    return sorted(strongest.values(),key=lambda item:-item["coverage"])


def _aggregate_models(rows: list[dict], kind: str) -> list[dict]:
    groups=defaultdict(list)
    for row in rows:
        key=(row["source_program"],row.get("direction","")); groups[key].append(row)
    groups[(None,"")]=rows
    result=[]
    for (program,direction),selected in groups.items():
        if not selected: continue
        weights=[row["match_count"] for row in selected]; total=sum(weights)
        weighted=lambda key:sum(row[key]*weight for row,weight in zip(selected,weights))/max(1,total)
        model={"scope_key":"global" if program is None else f"program:{program}:{direction or kind}",
            "source_program":program,"direction":direction or None,"sample_count":len(selected),"note_count":total,
            "coverage":weighted("coverage"),"velocity_ratio":weighted("velocity_ratio"),"gate_ratio":weighted("gate_ratio")}
        if kind=="delay": model["offset_quarters"]=weighted("offset_quarters")
        else:
            minor=sum(row["minor_third_count"] for row in selected); major=sum(row["major_third_count"] for row in selected)
            model.update({"minor_ratio":minor/max(1,minor+major),"major_ratio":major/max(1,minor+major)})
        result.append(model)
    return result


def _segment_delay_phrases(rows:list[dict],division:int)->list[list[dict]]:
    ordered=sorted(rows,key=lambda row:(row["start"],row["on_event"].order,row["note"]));phrases=[];phrase=[]
    for row in ordered:
        if phrase:
            gap=(row["start"]-(phrase[-1]["start"]+phrase[-1]["duration"]))/division
            if gap>=.5:phrases.append(phrase);phrase=[]
        phrase.append(row)
    if phrase:phrases.append(phrase)
    return phrases


def _delay_phrase_rows(midi:MidiFile,pair:dict)->list[dict]:
    groups=_groups(midi);source=groups.get((pair["source_track"],pair["source_channel"]),[])
    target=groups.get((pair["echo_track"],pair["echo_channel"]),[]);offset=round(pair["offset_quarters"]*midi.division)
    target_index={(row["start"],row["note"]):row for row in target};rows=[]
    for phrase_index,phrase in enumerate(_segment_delay_phrases(source,midi.division)):
        matched=[index for index,row in enumerate(phrase) if (row["start"]+offset,row["note"]) in target_index]
        start=phrase[0]["start"];end=max(row["start"]+row["duration"] for row in phrase)
        target_window=[row for row in target if start+offset<=row["start"]<=end+offset]
        recall=len(matched)/max(1,len(phrase));precision=len(matched)/max(1,len(target_window))
        classification="FULL" if recall>=.95 and precision>=.75 else "PARTIAL" if len(matched)>=3 and recall>=.2 else "SKIP"
        duration=max(1,(end-start)/midi.division);positions=[index/max(1,len(phrase)-1) for index in matched]
        rows.append({"filename":pair.get("filename",""),"source_track":pair["source_track"],"source_channel":pair["source_channel"],
            "echo_track":pair["echo_track"],"echo_channel":pair["echo_channel"],"source_program":pair["source_program"],
            "phrase_index":phrase_index,"start_tick":start,"end_tick":end,"note_count":len(phrase),"match_count":len(matched),
            "source_recall":recall,"target_precision":precision,"classification":classification,
            "offset_quarters":pair["offset_quarters"],"matched_positions":positions,
            "feature":{"duration_quarters":duration,"density":len(phrase)/duration,"pitch_mean":mean(row["note"] for row in phrase),
            "velocity_mean":mean(row["velocity"] for row in phrase),"entry_rest_threshold":.5}})
    return rows


def _aggregate_delay_phrase_models(rows:list[dict])->list[dict]:
    groups=defaultdict(list)
    for row in rows:groups[row["source_program"]].append(row)
    groups[None]=rows;models=[]
    for program,selected in groups.items():
        if not selected:continue
        counts=Counter(row["classification"] for row in selected);files=len({row["filename"] for row in selected});total=len(selected)
        full=counts["FULL"]/total;partial=counts["PARTIAL"]/total;skip=counts["SKIP"]/total
        # Generation is admitted only for an exact source program supported by
        # at least two independent files and five phrases. PARTIAL remains
        # disabled until a much larger, stable positional-mask corpus exists.
        # These six songs are identification-only evidence for existing Delay/Terca tracks.
        # They must never authorize creation of a new layer.
        if program is not None and files>=2 and total>=5 and full>=.75:decision="FULL_IDENTIFICATION_ONLY";allowed=False
        elif program is not None and files>=2 and total>=5 and skip>=.6:decision="SKIP";allowed=True
        else:decision="NO_DECISION";allowed=False
        model={"scope_key":"global_analytic" if program is None else f"program:{program}","source_program":program,
            "sample_count":total,"file_count":files,"full_count":counts["FULL"],"partial_count":counts["PARTIAL"],
            "skip_count":counts["SKIP"],"full_ratio":full,"partial_ratio":partial,"skip_ratio":skip,
            "generation_decision":decision,"generation_allowed":allowed,"partial_generation_allowed":False,
            "source_scope":"six_song_delay_terca_identification_only",
            "provenance":"six approved song relationship files"}
        models.append(model)
    return models


def build_delay_harmony_databases(song_paths: list[Path], delay_path: Path, harmony_path: Path) -> dict:
    delay_rows=[]; harmony_rows=[];delay_phrase_rows=[]
    for path in song_paths:
        midi=parse_midi(path.read_bytes()); pairs=detect_delay_pairs(midi,path.name);delay_rows.extend(pairs)
        for pair in pairs:delay_phrase_rows.extend(_delay_phrase_rows(midi,pair))
        harmony_rows.extend(detect_harmony_pairs(midi,path.name))
    delay_db=_new_database(delay_path,DELAY_SCHEMA); delay_db.execute("INSERT INTO build_info VALUES('source','uploaded song MIDI files')")
    for row in delay_rows:
        delay_db.execute("""INSERT INTO delay_pairs(filename,source_track,source_channel,echo_track,echo_channel,
            source_program,echo_program,offset_quarters,match_count,coverage,velocity_ratio,gate_ratio,
            source_note_count,echo_note_count,evidence_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*[row[key] for key in ("filename","source_track","source_channel","echo_track","echo_channel","source_program","echo_program",
              "offset_quarters","match_count","coverage","velocity_ratio","gate_ratio","source_note_count","echo_note_count")],json.dumps(row,separators=(',',':'))))
    delay_models=_aggregate_models(delay_rows,"delay")
    for model in delay_models:
        delay_db.execute("INSERT INTO delay_models(scope_key,source_program,sample_count,note_count,offset_quarters,velocity_ratio,gate_ratio,coverage,model_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (model["scope_key"],model["source_program"],model["sample_count"],model["note_count"],model["offset_quarters"],model["velocity_ratio"],model["gate_ratio"],model["coverage"],json.dumps(model,separators=(',',':'))))
    delay_db.executemany("INSERT INTO delay_rules(rule_key,description) VALUES(?,?)",[
        ("existing_first","Ako postoji dokazani echo track, optimizuj njega i ne kreiraj drugi."),
        ("separate_track","Novi echo uvijek ide na poseban MIDI track."),
        ("slot_order","Slobodan kanal > prazan track > sigurni slabi duplikat > novi track na source kanalu."),
        ("protect_core","Drum, bass, tempo/meta i jedini lead track se ne zamjenjuju."),
    ])
    for row in delay_phrase_rows:
        delay_db.execute("""INSERT INTO delay_phrase_occurrences(filename,source_track,source_channel,echo_track,echo_channel,
          source_program,phrase_index,start_tick,end_tick,note_count,match_count,source_recall,target_precision,classification,
          offset_quarters,matched_positions_json,feature_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (*[row[key] for key in ("filename","source_track","source_channel","echo_track","echo_channel","source_program",
          "phrase_index","start_tick","end_tick","note_count","match_count","source_recall","target_precision","classification","offset_quarters")],
          json.dumps(row["matched_positions"],separators=(',',':')),json.dumps(row["feature"],separators=(',',':'))))
    delay_phrase_models=_aggregate_delay_phrase_models(delay_phrase_rows)
    for model in delay_phrase_models:
        delay_db.execute("""INSERT INTO delay_phrase_models(scope_key,source_program,sample_count,file_count,full_count,
          partial_count,skip_count,full_ratio,partial_ratio,skip_ratio,generation_decision,generation_allowed,model_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(model["scope_key"],model["source_program"],model["sample_count"],model["file_count"],
          model["full_count"],model["partial_count"],model["skip_count"],model["full_ratio"],model["partial_ratio"],model["skip_ratio"],
          model["generation_decision"],int(model["generation_allowed"]),json.dumps(model,separators=(',',':'))))
    delay_db.executemany("INSERT INTO delay_negative_rules(rule_key,description) VALUES(?,?)",[
        ("no_global_generation","Global model je analitički; generacija zahtijeva exact source-program cohort."),
        ("partial_disabled","PARTIAL generation je isključena dok nema najmanje 10 stabilnih fraza iz tri fajla."),
        ("unique_channel","Novi Delay zahtijeva slobodan, jedinstven non-drum MIDI kanal."),
        ("phrase_skip","SKIP fraza nikada ne dobija echo note."),
        ("no_random_mask","Note selection je deterministička i evidence-based."),
    ]); _finish(delay_db,delay_path)
    harmony_db=_new_database(harmony_path,HARMONY_SCHEMA); harmony_db.execute("INSERT INTO build_info VALUES('source','uploaded song MIDI files')")
    for row in harmony_rows:
        harmony_db.execute("""INSERT INTO harmony_pairs(filename,source_track,source_channel,harmony_track,harmony_channel,
            source_program,harmony_program,direction,minor_third_count,major_third_count,match_count,coverage,
            source_recall,target_precision,velocity_ratio,gate_ratio,evidence_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*[row[key] for key in ("filename","source_track","source_channel","harmony_track","harmony_channel","source_program","harmony_program",
              "direction","minor_third_count","major_third_count","match_count","coverage","source_recall","target_precision","velocity_ratio","gate_ratio")],json.dumps(row,separators=(',',':'))))
    harmony_models=_aggregate_models(harmony_rows,"harmony")
    for model in harmony_models:
        harmony_db.execute("INSERT INTO harmony_models(scope_key,source_program,direction,sample_count,note_count,minor_ratio,major_ratio,coverage,velocity_ratio,gate_ratio,model_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (model["scope_key"],model["source_program"],model["direction"],model["sample_count"],model["note_count"],model["minor_ratio"],model["major_ratio"],model["coverage"],model["velocity_ratio"],model["gate_ratio"],json.dumps(model,separators=(',',':'))))
    harmony_db.executemany("INSERT INTO harmony_rules(rule_key,description) VALUES(?,?)",[
        ("separate_track","Terca uvijek koristi poseban MIDI track."),
        ("existing_only","Terca se nikada ne generiše; obrađuje se samo dokazani postojeći harmony track."),
        ("pitch_lock","Pitch, onset i trajanje postojeće terce ostaju netaknuti."),
        ("velocity_volume_only","Dozvoljene su samo konzervativne korekcije velocityja i postojećih CC7/CC11 događaja."),
    ]); _finish(harmony_db,harmony_path)
    return {"delay":{"pairs":len(delay_rows),"models":len(delay_models),"phrases":len(delay_phrase_rows),
            "phrase_models":len(delay_phrase_models),"phrase_classes":dict(Counter(row["classification"] for row in delay_phrase_rows))},
            "harmony":{"pairs":len(harmony_rows),"models":len(harmony_models)}}


def _family(program: int) -> str:
    if 24<=program<=31:return "guitar"
    if 56<=program<=63:return "brass"
    if 64<=program<=71:return "reed"
    if 72<=program<=79:return "pipe"
    if 80<=program<=87:return "synth_lead"
    if 40<=program<=55:return "strings"
    return "melodic"


def build_gold_ornament_database(archive_path: Path, output_path: Path) -> dict:
    database=_new_database(output_path,ORNAMENT_SCHEMA)
    database.execute("INSERT INTO build_info VALUES('source','Gold DNA only')")
    database.execute("INSERT INTO build_info VALUES('provenance','Gold DNA.zip; Factory and uploaded song files excluded')")
    rows=[]
    with ZipFile(archive_path) as outer:
        nested=next(name for name in outer.namelist() if "gold" in name.lower() and name.lower().endswith(".zip"))
        with ZipFile(BytesIO(outer.read(nested))) as archive:
            for info in archive.infolist():
                if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"): continue
                midi=parse_midi(archive.read(info)); programs=_programs(midi); groups=_groups(midi)
                tempo=None
                for events in midi.tracks:
                    for event in events:
                        if event.kind=="meta" and event.data1==0x51 and len(event.raw)==3 and tempo is None:
                            micros=int.from_bytes(event.raw,"big"); tempo=60_000_000/micros if micros else None
                for (track,channel),notes in groups.items():
                    program=programs.get((track,channel),0); role=infer_role(channel,program)
                    if role not in ("melodic","guitar") or len(notes)<8: continue
                    ornaments=_ornaments(notes,midi.division)
                    pitch_bend=sum(event.kind=="pitch" and int(event.channel or 0)==channel for event in midi.tracks[track])
                    row={"filename":info.filename,"track_index":track,"channel":channel,"program":program,
                        "family":_family(program),"tempo_bpm":tempo,"tempo_bucket":round(float(tempo or 0)/20)*20 if tempo else 0,
                        "note_count":len(notes),"grace_count":ornaments["grace_notes"],"trill_count":ornaments["trill_count"],
                        "neighbor_count":ornaments["neighbor_ornament_count"],"tremolo_count":ornaments["tremolo_count"],
                        "pitch_bend_count":pitch_bend,"examples":{"trills":ornaments["trill_sequences"][:20],
                        "neighbors":ornaments["neighbor_ornaments"][:20]}}
                    rows.append(row)
                    database.execute("""INSERT INTO ornament_tracks(filename,track_index,channel,program,family,tempo_bpm,
                        tempo_bucket,note_count,grace_count,trill_count,neighbor_count,tremolo_count,pitch_bend_count,
                        profile_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(row["filename"],track,channel,program,row["family"],tempo,
                        row["tempo_bucket"],row["note_count"],row["grace_count"],row["trill_count"],row["neighbor_count"],
                        row["tremolo_count"],pitch_bend,json.dumps(row,separators=(',',':'))))
    grouped=defaultdict(list)
    for row in rows: grouped[(row["family"],row["tempo_bucket"])].append(row)
    grouped[("global",0)]=rows
    models=[]
    for (family,bucket),selected in grouped.items():
        notes=sum(row["note_count"] for row in selected)
        rate=lambda key:1000*sum(row[key] for row in selected)/max(1,notes)
        model={"scope_key":"global" if family=="global" else f"{family}:{bucket}","family":family,
            "tempo_bucket":bucket,"track_count":len(selected),"note_count":notes,"grace_per_1000":rate("grace_count"),
            "trill_per_1000":rate("trill_count"),"neighbor_per_1000":rate("neighbor_count"),
            "tremolo_per_1000":rate("tremolo_count"),"bend_per_1000":rate("pitch_bend_count")}
        models.append(model); database.execute("""INSERT INTO ornament_models(scope_key,family,tempo_bucket,track_count,
            note_count,grace_per_1000,trill_per_1000,neighbor_per_1000,tremolo_per_1000,bend_per_1000,model_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(model["scope_key"],family,bucket,model["track_count"],notes,model["grace_per_1000"],
            model["trill_per_1000"],model["neighbor_per_1000"],model["tremolo_per_1000"],model["bend_per_1000"],json.dumps(model,separators=(',',':'))))
    database.executemany("INSERT INTO ornament_rules(rule_key,description) VALUES(?,?)",[
        ("gold_only","Svi trill/ornament modeli koriste isključivo Gold DNA fajlove."),
        ("existing_default","Default je optimizacija postojećih ukrasa, bez automatskog dodavanja novih nota."),
        ("exclude_rhythm","Drums, percussion, bass i accompaniment nisu melodic trill izvor."),
        ("preserve_pitch","Postojeći ornament pitch obrazac se ne mijenja bez eksplicitnog create režima."),
    ]); _finish(database,output_path)
    return {"tracks":len(rows),"models":len(models),"trills":sum(row["trill_count"] for row in rows),
            "grace":sum(row["grace_count"] for row in rows),"source":"gold_only"}


def load_models(path: Path, table: str) -> list[dict]:
    database=sqlite3.connect(path); result=[json.loads(row[0]) for row in database.execute(f"SELECT model_json FROM {table}")]; database.close(); return result


def load_delay_phrase_models(path:Path)->list[dict]:
    return load_models(path,"delay_phrase_models")


def _choose_model(models: list[dict], program: int) -> dict:
    return next((model for model in models if model.get("source_program")==program),None) or next((model for model in models if model.get("scope_key")=="global"),{})


def _used_channels(midi: MidiFile) -> set[int]:
    return {int(event.channel or 0) for events in midi.tracks for event in events if event.channel is not None}


def _track_importance(midi: MidiFile, track_index: int) -> float:
    rows=[row for row in note_rows(midi) if row["track"]==track_index]
    if not rows:return 0
    channels={row["channel"] for row in rows}; role_penalty=10000 if 9 in channels or 1 in channels else 0
    return role_penalty+len(rows)+mean(row["velocity"] for row in rows)/10


def choose_layer_slot(midi: MidiFile, source_track: int, source_channel: int, allow_replace: bool=False) -> dict:
    used=_used_channels(midi); preferred=(15,14,13,12,11,10,8,7,6,5,4,3,2,0)
    free=next((channel for channel in preferred if channel not in used),None)
    if free is not None:return {"track":len(midi.tracks),"channel":free,"method":"free_channel","replace":False}
    empty=next((index for index,events in enumerate(midi.tracks) if index!=source_track
        and not any(event.kind=="note_on" and event.data2 for event in events)
        and not any(event.kind=="meta" and event.data1 in (0x51,0x58,0x59) for event in events)),None)
    if empty is not None:return {"track":empty,"channel":source_channel,"method":"empty_track","replace":True}
    if allow_replace:
        candidates=[index for index in range(len(midi.tracks)) if index!=source_track and _track_importance(midi,index)<40]
        if candidates:
            target=min(candidates,key=lambda index:_track_importance(midi,index))
            return {"track":target,"channel":source_channel,"method":"low_importance_track","replace":True}
    return {"track":len(midi.tracks),"channel":source_channel,"method":"new_track_same_channel","replace":False}


def _initial_events(midi: MidiFile, source_track: int, source_channel: int, target_channel: int, name: str) -> list[Event]:
    result=[Event(0,-10,"meta",data1=3,raw=name.encode("ascii","replace"))]
    for event in sorted(midi.tracks[source_track],key=lambda e:(e.tick,e.order)):
        if event.tick>0:break
        if int(event.channel or 0)!=source_channel:continue
        if event.kind in ("program","control"):
            copied=Event(event.tick,event.order,event.kind,target_channel,event.data1,event.data2,
                ((event.status or 0)&0xF0)|target_channel,event.raw); result.append(copied)
    return result


def _detect_key(rows: list[dict]) -> tuple[int,bool,float]:
    major=(6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88)
    minor=(6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17)
    histogram=[0.0]*12
    for row in rows:histogram[row["note"]%12]+=row["duration"]*max(1,row["velocity"])
    scores=[]
    for tonic in range(12):
        scores.append((sum(histogram[(pc+tonic)%12]*major[pc] for pc in range(12)),tonic,False))
        scores.append((sum(histogram[(pc+tonic)%12]*minor[pc] for pc in range(12)),tonic,True))
    ranked=sorted(scores,reverse=True); best=ranked[0]; second=ranked[1]
    # Confidence is the winning profile's margin over the runner-up.  The old
    # best/sum metric was naturally close to 0.05 even for a clear tonal center.
    confidence=max(0.0,min(1.0,(best[0]-second[0])/max(1.0,abs(best[0]))))
    return best[1],best[2],confidence


def _snap_offset(value: float) -> float:
    """Snap learned echo time to a musically stable subdivision."""
    choices=(.125,.25,1/3,.5,.75,1,1.5,2)
    return min(choices,key=lambda choice:abs(choice-value))


def _diatonic_third(note: int, tonic: int, minor: bool, direction: str) -> int | None:
    scale=(0,2,3,5,7,8,10) if minor else (0,2,4,5,7,9,11); pc=(note-tonic)%12
    if pc not in scale:return None
    degree=scale.index(pc); target_degree=degree+(2 if direction=="up" else -2)
    octave=math.floor(target_degree/7); target_pc=scale[target_degree%7]
    return note+(target_pc-pc)+12*octave


def _lead_candidate(midi: MidiFile, excluded: set[tuple[int,int]]) -> tuple[int,int,int] | None:
    programs=_programs(midi); best=None
    for feature in extract_features(midi):
        key=(feature.track,feature.channel); program=programs.get(key,0); role=infer_role(feature.channel,program)
        if key in excluded or role not in ("melodic","guitar") or feature.note_count<12:continue
        score=(feature.monophony_ratio*.45+min(1,feature.pitch_bend.changes_per_quarter)*.2+
            min(1,feature.note_count/300)*.15+(feature.pitch.mean>=55)*.1+
            (feature.channel in (0,3,4,5,6))*.1)
        if best is None or score>best[0]:best=(score,feature.track,feature.channel,program)
    return best[1:] if best else None


def select_song_lead(midi: MidiFile, delays: list[dict] | None=None,
                     harmonies: list[dict] | None=None) -> tuple[int,int,int] | None:
    """Select the creation source before any optimizer changes its voice/role."""
    delays=delays if delays is not None else detect_delay_pairs(midi)
    harmonies=harmonies if harmonies is not None else detect_harmony_pairs(midi)
    excluded={(pair["echo_track"],pair["echo_channel"]) for pair in delays}
    excluded|={(pair["harmony_track"],pair["harmony_channel"]) for pair in harmonies}
    return _lead_candidate(midi,excluded)


def _optimize_existing_delay(midi: MidiFile, pair: dict, model: dict, strength: float) -> dict:
    groups=_groups(midi); source=groups.get((pair["source_track"],pair["source_channel"]),[])
    echo_by_pitch=defaultdict(list)
    for row in groups.get((pair["echo_track"],pair["echo_channel"]),[]):echo_by_pitch[row["note"]].append(row)
    target_velocity=float(model.get("velocity_ratio",pair["velocity_ratio"])); target_gate=float(model.get("gate_ratio",pair["gate_ratio"])); changed=0
    offset=round(pair["offset_quarters"]*midi.division); tolerance=max(1,round(.20*midi.division)); used=set(); matched=0
    for src in source:
        expected=src["start"]+offset
        options=[row for row in echo_by_pitch.get(src["note"],[]) if id(row) not in used and abs(row["start"]-expected)<=tolerance]
        if not options:continue
        row=min(options,key=lambda item:abs(item["start"]-expected));used.add(id(row));matched+=1
        velocity=max(1,min(127,round(row["velocity"]*(1-strength)+src["velocity"]*target_velocity*strength)))
        duration=max(1,round(row["duration"]*(1-strength)+src["duration"]*target_gate*strength))
        if velocity!=row["velocity"]:row["on_event"].data2=velocity;changed+=1
        if duration!=row["duration"]:row["off_event"].tick=row["start"]+duration;changed+=1
    return {"mode":"optimized_existing","pair":pair,"events_changed":changed,"notes_matched":matched,"detected_before_gold":True}


def _optimize_existing_harmony(midi: MidiFile, pair: dict, model: dict, strength: float) -> dict:
    groups=_groups(midi); source=groups[(pair["source_track"],pair["source_channel"])]
    target=groups.get((pair["harmony_track"],pair["harmony_channel"]),[])
    velocity_ratio=float(model.get("velocity_ratio",pair["velocity_ratio"])); changed=0
    direction=pair["direction"];tolerance=max(1,round(.20*midi.division));used=set();matched=0
    for row in source:
        options=[other for other in target if id(other) not in used and abs(other["start"]-row["start"])<=tolerance
                 and abs(other["note"]-row["note"]) in (3,4)
                 and ((other["note"]>row["note"])==(direction=="up"))]
        if not options:continue
        harmony=min(options,key=lambda item:(abs(item["start"]-row["start"]),abs(item["note"]-row["note"])));used.add(id(harmony));matched+=1
        velocity=max(1,min(127,round(harmony["velocity"]*(1-strength)+row["velocity"]*velocity_ratio*strength)))
        if velocity!=harmony["velocity"]:harmony["on_event"].data2=velocity;changed+=1
    # Volume/expression are optimized only when both source and harmony
    # already contain the corresponding controller.  We never synthesize a
    # missing CC because that would change the song's mixer design without
    # direct evidence.
    control_changed=0
    source_events=sorted(midi.tracks[pair["source_track"]],key=lambda event:(event.tick,event.order))
    target_events=sorted(midi.tracks[pair["harmony_track"]],key=lambda event:(event.tick,event.order))
    for controller in (7,11):
        source_controls=[event for event in source_events if event.kind=="control" and event.channel==pair["source_channel"] and event.data1==controller]
        target_controls=[event for event in target_events if event.kind=="control" and event.channel==pair["harmony_channel"] and event.data1==controller]
        if not source_controls or not target_controls:continue
        for target_event in target_controls:
            preceding=[event for event in source_controls if event.tick<=target_event.tick]
            source_event=preceding[-1] if preceding else source_controls[0]
            desired=max(0,min(127,round(int(source_event.data2 or 0)*velocity_ratio)))
            value=max(0,min(127,round(int(target_event.data2 or 0)*(1-strength)+desired*strength)))
            if value!=target_event.data2:
                target_event.data2=value;control_changed+=1
    changed+=control_changed
    return {"mode":"optimized_existing","policy":"velocity_volume_only","pair":pair,"events_changed":changed,
        "velocity_notes_matched":matched,"controls_changed":control_changed,"pitch_changed":0,
        "timing_changed":0,"duration_changed":0,"detected_before_gold":True}


def _create_delay(midi: MidiFile, source_key: tuple[int,int], program: int, model: dict,
                  phrase_models:list[dict],strength: float,allow_replace: bool) -> dict:
    phrase_model=next((item for item in phrase_models if item.get("source_program")==program),None)
    if not phrase_model or not phrase_model.get("generation_allowed"):
        return {"mode":"skipped","reason":"insufficient_phrase_evidence","source":{"track":source_key[0],"channel":source_key[1],"program":program},
            "phrase_model":phrase_model,"notes_created":0}
    decision=phrase_model.get("generation_decision")
    if decision!="FULL":
        return {"mode":"skipped","reason":"phrase_model_skip" if decision=="SKIP" else "partial_generation_disabled",
            "source":{"track":source_key[0],"channel":source_key[1],"program":program},"phrase_model":phrase_model,"notes_created":0}
    used=_used_channels(midi);preferred=(15,14,13,12,11,10,8,7,6,5,4,3,2,1,0)
    free=next((channel for channel in preferred if channel!=9 and channel not in used),None)
    if free is None:
        return {"mode":"skipped","reason":"no_safe_channel","source":{"track":source_key[0],"channel":source_key[1],"program":program},
            "phrase_model":phrase_model,"notes_created":0}
    slot={"track":len(midi.tracks),"channel":free,"method":"free_unique_channel","replace":False};rows=_groups(midi)[source_key]
    midi.tracks.append([])
    events=_initial_events(midi,source_key[0],source_key[1],slot["channel"],"DNA DELAY")
    offset_quarters=_snap_offset(float(model.get("offset_quarters",.75)))
    offset=round(offset_quarters*midi.division); attenuation=float(model.get("velocity_ratio",.5)); gate=float(model.get("gate_ratio",1))
    selected_rows=[row for phrase in _segment_delay_phrases(rows,midi.division) for row in phrase]
    last_off_by_pitch={}
    for index,row in enumerate(selected_rows):
        tick=row["start"]+offset; velocity=max(1,min(127,round(row["velocity"]*(1-strength+attenuation*strength))))
        duration=max(1,round(row["duration"]*(1-strength+gate*strength))); order=1000+index*2
        previous_off=last_off_by_pitch.get(row["note"])
        if previous_off is not None and previous_off.tick>=tick:previous_off.tick=max(0,tick-1)
        off=Event(tick+duration,order+1,"note_off",slot["channel"],row["note"],0,0x80|slot["channel"])
        events.extend([Event(tick,order,"note_on",slot["channel"],row["note"],velocity,0x90|slot["channel"]),off]);last_off_by_pitch[row["note"]]=off
    midi.tracks[slot["track"]]=events
    return {"mode":"created","source":{"track":source_key[0],"channel":source_key[1],"program":program},
        "target":slot,"notes_created":len(selected_rows),"offset_quarters":offset/midi.division,"velocity_ratio":attenuation,
        "phrase_model":phrase_model,"phrase_gate":"FULL"}


def apply_song_dna(midi: MidiFile, delay_models: list[dict], harmony_models: list[dict], ornament_models: list[dict],
                   delay_enabled: bool=True,delay_create: bool=True,delay_strength: float=.8,
                   harmony_enabled: bool=True,harmony_create: bool=False,harmony_strength: float=.75,
                   ornament_enabled: bool=True,allow_replace: bool=False,
                   detected_delays: list[dict] | None=None,
                   detected_harmonies: list[dict] | None=None,
                   primary_source: tuple[int,int,int] | None=None,
                   delay_phrase_models:list[dict]|None=None) -> tuple[MidiFile,dict]:
    delays=detected_delays if detected_delays is not None else detect_delay_pairs(midi)
    harmonies=detected_harmonies if detected_harmonies is not None else detect_harmony_pairs(midi)
    programs=_programs(midi)
    if primary_source is None:primary_source=select_song_lead(midi,delays,harmonies)
    report={"output_mode":"song","delay":None,
        "harmony":{"mode":"not_detected","creation_allowed":False,"policy":"existing_velocity_volume_only"},
        "ornament":{"source":"gold_only","mode":"off"}}
    if delay_enabled:
        if delays:
            pair=max(delays,key=lambda item:(item["coverage"],item["match_count"]));
            report["delay"]=_optimize_existing_delay(midi,pair,_choose_model(delay_models,pair["source_program"]),max(0,min(1,delay_strength)))
        elif delay_create:
            source=primary_source
            if source:
                report["delay"]=_create_delay(midi,(source[0],source[1]),source[2],_choose_model(delay_models,source[2]),
                    delay_phrase_models or [],max(0,min(1,delay_strength)),allow_replace)
    if harmony_enabled:
        if harmonies:
            pair=max(harmonies,key=lambda item:(item["coverage"],item["match_count"]));
            report["harmony"]=_optimize_existing_harmony(midi,pair,_choose_model(harmony_models,pair["source_program"]),max(0,min(1,harmony_strength)))
        # ``harmony_create`` is retained only for backwards-compatible API
        # calls.  It is intentionally ignored and can never create notes.
    if ornament_enabled:
        groups=_groups(midi); existing=0
        for (track,channel),rows in groups.items():
            program=programs.get((track,channel),0); role=infer_role(channel,program)
            if role in ("melodic","guitar"):existing+=_ornaments(rows,midi.division)["trill_count"]
        report["ornament"]={"source":"gold_only","mode":"optimize_existing","existing_trills_detected":existing,
            "new_notes_created":0,"models_loaded":len(ornament_models)}
    return midi,report