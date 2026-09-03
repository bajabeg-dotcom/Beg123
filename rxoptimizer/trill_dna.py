"""Deterministic, evidence-preserving trill and layer-relationship DNA."""

from __future__ import annotations

from collections import Counter,defaultdict
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import re
import sqlite3
from statistics import mean,pstdev
from zipfile import ZipFile

from .features import infer_role
from .midi import MidiFile,note_rows,parse_midi
from .song_dna import detect_delay_pairs,detect_harmony_pairs


SCHEMA="""
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE trill_patterns(id INTEGER PRIMARY KEY,pattern_key TEXT UNIQUE,source_class TEXT,instrument_family TEXT,
 trill_type TEXT,direction TEXT,interval_semitones INTEGER,subdivision TEXT,occurrence_count INTEGER,file_count INTEGER,
 accepted_count INTEGER,confidence_mean REAL,pattern_json TEXT);
CREATE TABLE trill_occurrences(id INTEGER PRIMARY KEY,source_class TEXT,filename TEXT,file_sha256 TEXT,style_name TEXT,
 section TEXT,track_index INTEGER,channel INTEGER,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,role TEXT,
 start_tick INTEGER,end_tick INTEGER,start_order INTEGER,end_order INTEGER,main_note INTEGER,neighbor_note INTEGER,
 accepted INTEGER,occurrence_json TEXT);
CREATE TABLE trill_features(occurrence_id INTEGER PRIMARY KEY REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 repetition_count INTEGER,total_duration_quarters REAL,average_note_duration REAL,interval_semitones INTEGER,
 pitch_stability REAL,phrase_position TEXT,feature_json TEXT);
CREATE TABLE trill_context(occurrence_id INTEGER PRIMARY KEY REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 previous_note INTEGER,next_note INTEGER,previous_gap_quarters REAL,next_gap_quarters REAL,entry_relation TEXT,
 exit_relation TEXT,context_json TEXT);
CREATE TABLE trill_harmony(occurrence_id INTEGER PRIMARY KEY REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 tonic INTEGER,mode TEXT,key_confidence REAL,chord_name TEXT,main_is_chord_tone INTEGER,neighbor_is_scale_tone INTEGER,
 harmonic_json TEXT);
CREATE TABLE trill_timing(occurrence_id INTEGER PRIMARY KEY REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 mean_spacing_quarters REAL,spacing_std REAL,acceleration REAL,subdivision TEXT,swing_ratio REAL,timing_json TEXT);
CREATE TABLE trill_velocity(occurrence_id INTEGER PRIMARY KEY REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 velocity_mean REAL,velocity_std REAL,main_velocity_mean REAL,neighbor_velocity_mean REAL,velocity_slope REAL,
 pattern_type TEXT,velocity_json TEXT);
CREATE TABLE trill_articulation(occurrence_id INTEGER PRIMARY KEY REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 pitch_bend_events INTEGER,pressure_events INTEGER,cc1_events INTEGER,noise_note_events INTEGER,rx_status TEXT,
 articulation_json TEXT);
CREATE TABLE trill_evidence(id INTEGER PRIMARY KEY,occurrence_id INTEGER REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 evidence_type TEXT,evidence_status TEXT,source_locator TEXT,evidence_json TEXT);
CREATE TABLE trill_confidence(occurrence_id INTEGER PRIMARY KEY REFERENCES trill_occurrences(id) ON DELETE CASCADE,
 pitch_pattern_score REAL,interval_score REAL,repetition_score REAL,timing_score REAL,duration_score REAL,
 context_score REAL,harmonic_score REAL,factory_pattern_score REAL,final_score REAL,category TEXT,reasons_json TEXT);
CREATE TABLE trill_negative_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT,enabled INTEGER DEFAULT 1);
CREATE TABLE layer_relationships(id INTEGER PRIMARY KEY,filename TEXT,layer_type TEXT,source_track INTEGER,
 source_channel INTEGER,target_track INTEGER,target_channel INTEGER,offset_quarters REAL,coverage REAL,
 velocity_ratio REAL,gate_ratio REAL,creation_allowed INTEGER,relationship_json TEXT);
CREATE TABLE layer_trill_behavior(id INTEGER PRIMARY KEY,relationship_id INTEGER REFERENCES layer_relationships(id),
 source_start_tick INTEGER,source_end_tick INTEGER,target_behavior TEXT,source_repetitions INTEGER,
 target_repetitions INTEGER,behavior_json TEXT);
CREATE TABLE layer_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT);
"""


def _new(path:Path)->sqlite3.Connection:
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+".tmp");temp.unlink(missing_ok=True)
    db=sqlite3.connect(temp);db.row_factory=sqlite3.Row;db.execute("PRAGMA foreign_keys=ON");db.executescript(SCHEMA);return db


def _finish(db:sqlite3.Connection,path:Path):
    integrity=db.execute("PRAGMA integrity_check").fetchone()[0];fk=db.execute("PRAGMA foreign_key_check").fetchall()
    temp=Path(db.execute("PRAGMA database_list").fetchone()[2]);db.commit();db.close()
    if integrity!="ok" or fk:temp.unlink(missing_ok=True);raise ValueError("Trill DNA integrity failure")
    temp.replace(path)


def _key_profile(rows:list[dict])->tuple[int,bool,float]:
    major=(6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88)
    minor=(6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17)
    histogram=[0.0]*12
    for row in rows:histogram[row["note"]%12]+=row["duration"]*max(1,row["velocity"])
    scores=[]
    for tonic in range(12):
        scores.extend(((sum(histogram[(pc+tonic)%12]*major[pc] for pc in range(12)),tonic,False),
                       (sum(histogram[(pc+tonic)%12]*minor[pc] for pc in range(12)),tonic,True)))
    ranked=sorted(scores,reverse=True);best,second=ranked[:2]
    return best[1],best[2],max(0,min(1,(best[0]-second[0])/max(1,abs(best[0]))))


def _program_at(events,channel:int,tick:int,order:int)->tuple[int,int,int]:
    pending=[0,0];active=(0,0,0);target=(tick,order)
    for event in sorted(events,key=lambda item:(item.tick,item.order)):
        if (event.tick,event.order)>target:break
        if int(event.channel or 0)!=channel:continue
        if event.kind=="control" and event.data1 in (0,32):pending[0 if event.data1==0 else 1]=int(event.data2 or 0)
        elif event.kind=="program":active=(pending[0],pending[1],int(event.data1 or 0))
    return active


def _note_program_segments(events,channel:int,notes:list[dict])->list[tuple[tuple[int,int,int],list[dict]]]:
    """Assign notes to active Program state in one linear pass."""
    relevant=sorted([event for event in events if int(event.channel or 0)==channel and
        (event.kind=="program" or event.kind=="control" and event.data1 in (0,32))],key=lambda item:(item.tick,item.order))
    pending=[0,0];active=(0,0,0);event_index=0;segment_index=0;result=[];current=[];current_state=active
    for note in sorted(notes,key=lambda row:(row["start"],row["on_event"].order)):
        key=(note["start"],note["on_event"].order)
        while event_index<len(relevant) and (relevant[event_index].tick,relevant[event_index].order)<=key:
            event=relevant[event_index]
            if event.kind=="control":pending[0 if event.data1==0 else 1]=int(event.data2 or 0)
            else:
                new_state=(pending[0],pending[1],int(event.data1 or 0))
                if new_state!=active:
                    if current:result.append((current_state,current));current=[]
                    active=new_state;current_state=active;segment_index+=1
            event_index+=1
        current.append(note)
    if current:result.append((current_state,current))
    return result


def _family(program:int)->str:
    if 24<=program<=31:return "guitar"
    if 32<=program<=39:return "bass"
    if 40<=program<=55:return "strings"
    if 56<=program<=63:return "brass"
    if 64<=program<=71:return "reed"
    if 72<=program<=79:return "pipe"
    return "melodic"


def _subdivision(spacing:float)->tuple[str,float]:
    choices=(("1/4",1.0),("1/8",.5),("1/8_triplet",1/3),("1/16",.25),
             ("1/16_triplet",1/6),("1/32",.125),("1/32_triplet",1/12))
    name,value=min(choices,key=lambda item:abs(item[1]-spacing))
    relative=abs(value-spacing)/max(value,1e-9)
    return (name if relative<=.25 else "irregular"),relative


def _chord_at(all_rows:list[dict],tick:int,exclude:tuple[int,int])->tuple[str|None,set[int]]:
    pcs={row["note"]%12 for row in all_rows if (row["track"],row["channel"])!=exclude
         and row["start"]<=tick<row["start"]+row["duration"] and row["channel"]!=9}
    for root in range(12):
        if {root,(root+4)%12,(root+7)%12}.issubset(pcs):return f"{root}:major",pcs
        if {root,(root+3)%12,(root+7)%12}.issubset(pcs):return f"{root}:minor",pcs
    return None,pcs


def detect_trills(rows:list[dict],division:int,events:list|None=None,all_rows:list[dict]|None=None,
                  track:int=0,channel:int=0,role:str="melodic")->list[dict]:
    """Return segmented alternating-note candidates with explicit rejection scores."""
    ordered=sorted(rows,key=lambda row:(row["start"],row["on_event"].order,row["note"]));result=[];consumed=set()
    tonic,minor,key_conf=_key_profile(ordered) if ordered else (0,False,0)
    scale={0,2,3,5,7,8,10} if minor else {0,2,4,5,7,9,11}
    onset_counts=Counter(row["start"] for row in ordered)
    for start in range(max(0,len(ordered)-3)):
        if start in consumed:continue
        first,second=ordered[start:start+2];interval=abs(second["note"]-first["note"])
        if onset_counts[first["start"]]>1 or onset_counts[second["start"]]>1:continue
        if interval not in (1,2,3,4) or second["start"]<=first["start"]:continue
        pitches=(first["note"],second["note"]);cursor=start+2
        while cursor<len(ordered):
            expected=pitches[(cursor-start)%2];previous=ordered[cursor-1];current=ordered[cursor]
            spacing=(current["start"]-previous["start"])/division
            if onset_counts[current["start"]]>1 or current["note"]!=expected or spacing<=0 or spacing>.375 or current["duration"]/division>.5:break
            cursor+=1
        selected=ordered[start:cursor]
        if len(selected)<4:continue
        spacings=[(b["start"]-a["start"])/division for a,b in zip(selected,selected[1:])]
        durations=[row["duration"]/division for row in selected];velocities=[row["velocity"] for row in selected]
        spacing_mean=mean(spacings);spacing_std=pstdev(spacings) if len(spacings)>1 else 0
        subdivision,sub_error=_subdivision(spacing_mean)
        previous=ordered[start-1] if start else None;following=ordered[cursor] if cursor<len(ordered) else None
        previous_gap=(first["start"]-(previous["start"]+previous["duration"]))/division if previous else None
        next_gap=(following["start"]-(selected[-1]["start"]+selected[-1]["duration"]))/division if following else None
        phrase_start=previous is None or previous_gap is not None and previous_gap>=.5
        phrase_end=following is None or next_gap is not None and next_gap>=.5
        phrase_position="isolated" if phrase_start and phrase_end else "start" if phrase_start else "end" if phrase_end else "middle"
        main=first["note"]
        if previous and previous["note"] in pitches:main=previous["note"]
        elif following and following["note"] in pitches:main=following["note"]
        neighbor=pitches[1] if pitches[0]==main else pitches[0]
        direction="upper" if neighbor>main else "lower" if neighbor<main else "ambiguous"
        chord_name,chord_pcs=_chord_at(all_rows or ordered,first["start"],(track,channel))
        main_scale=(main-tonic)%12 in scale;neighbor_scale=(neighbor-tonic)%12 in scale
        if key_conf<.01:trill_type="UNKNOWN_TRILL"
        else:trill_type=("DIATONIC" if main_scale and neighbor_scale else "CHROMATIC")+"_TRILL"
        pitch_score=1.0;interval_score={1:1.0,2:1.0,3:.65,4:.35}[interval]
        repetition_score=min(1,(len(selected)-3)/5)
        timing_score=max(0,1-spacing_std/max(spacing_mean,.001))*(1-min(1,sub_error))
        duration_score=max(0,1-(mean(durations)/.5))
        context_score=.55+.15*phrase_end+.1*phrase_start+.1*(following is not None)+.1*(previous is not None)
        if role in ("accompaniment","bass"):context_score=max(0,context_score-.2)
        harmonic_score=.5 if key_conf<.01 else .75 if neighbor_scale else .4
        final=(pitch_score*.2+interval_score*.12+repetition_score*.18+timing_score*.18+
               duration_score*.12+context_score*.12+harmonic_score*.08)
        category="HIGH_CONFIDENCE" if final>=.82 else "MEDIUM_CONFIDENCE" if final>=.68 else "LOW_CONFIDENCE" if final>=.5 else "REJECTED"
        if len(selected)==4 and category in ("HIGH_CONFIDENCE","MEDIUM_CONFIDENCE"):category="LOW_CONFIDENCE"
        half=max(1,len(spacings)//2);acceleration=mean(spacings[-half:])-mean(spacings[:half])
        main_vel=[row["velocity"] for row in selected if row["note"]==main];neighbor_vel=[row["velocity"] for row in selected if row["note"]==neighbor]
        slope=(velocities[-1]-velocities[0])/max(1,len(velocities)-1)
        velocity_type="alternating_accent" if abs(mean(main_vel)-mean(neighbor_vel))>=5 else "decay" if slope<=-1 else "growth" if slope>=1 else "even"
        window=(first["start"],selected[-1]["start"]+selected[-1]["duration"])
        relevant=[event for event in (events or []) if window[0]<=event.tick<=window[1] and int(event.channel or 0)==channel]
        articulation={"pitch_bend_events":sum(event.kind=="pitch" for event in relevant),
            "pressure_events":sum(event.kind in ("pressure","poly_pressure") for event in relevant),
            "cc1_events":sum(event.kind=="control" and event.data1==1 for event in relevant),
            "noise_note_events":sum(row["note"]>=96 and window[0]<=row["start"]<=window[1] for row in (all_rows or [])),
            "rx_status":"UNKNOWN"}
        result.append({"start_tick":first["start"],"end_tick":window[1],"start_order":first["on_event"].order,
            "end_order":selected[-1]["off_event"].order,"main_note":main,"neighbor_note":neighbor,
            "interval_semitones":interval,"direction":direction,"trill_type":trill_type,"interval_class":"half_step" if interval==1 else "whole_step" if interval==2 else "minor_third" if interval==3 else "major_third",
            "repetition_count":len(selected),"total_duration_quarters":(window[1]-window[0])/division,
            "average_note_duration":mean(durations),"pitch_stability":1.0,"phrase_position":phrase_position,
            "previous_note":previous["note"] if previous else None,"next_note":following["note"] if following else None,
            "previous_gap_quarters":previous_gap,"next_gap_quarters":next_gap,
            "entry_relation":"rest" if phrase_start else "step" if previous and abs(previous["note"]-main)<=2 else "leap",
            "exit_relation":"rest" if phrase_end else "step" if following and abs(following["note"]-main)<=2 else "leap",
            "tonic":tonic,"mode":"minor" if minor else "major","key_confidence":key_conf,"chord_name":chord_name,
            "main_is_chord_tone":main%12 in chord_pcs if chord_pcs else None,"neighbor_is_scale_tone":neighbor_scale,
            "mean_spacing_quarters":spacing_mean,"spacing_std":spacing_std,"acceleration":acceleration,
            "subdivision":subdivision,"swing_ratio":mean(spacings[::2])/max(.0001,mean(spacings[1::2])) if len(spacings)>2 and spacings[1::2] else 1,
            "velocity_mean":mean(velocities),"velocity_std":pstdev(velocities) if len(velocities)>1 else 0,
            "main_velocity_mean":mean(main_vel),"neighbor_velocity_mean":mean(neighbor_vel),"velocity_slope":slope,
            "velocity_pattern":velocity_type,"scores":{"pitch_pattern_score":pitch_score,"interval_score":interval_score,
            "repetition_score":repetition_score,"timing_score":timing_score,"duration_score":duration_score,
            "context_score":context_score,"harmonic_score":harmonic_score,"factory_pattern_score":0,"final_score":final},
            "confidence":category,"accepted":category in ("HIGH_CONFIDENCE","MEDIUM_CONFIDENCE") and len(selected)>=5,
            "articulation":articulation,
            "notes":[{"tick":row["start"],"pitch":row["note"],"velocity":row["velocity"],"duration":row["duration"]} for row in selected]})
        consumed.update(range(start,cursor))
    return result


def _style(filename:str)->tuple[str,str]:
    stem=Path(filename).stem;match=re.search(r"_(Intro|Var|Fill|End|Ending|Break)(\d*)$",stem,re.I)
    if not match:return stem,"song"
    section={"var":"variation","end":"ending"}.get(match.group(1).lower(),match.group(1).lower())
    return stem[:match.start()],section


def _insert_occurrence(db,row,source_class,filename,digest,style,section,track,channel,address,role)->int:
    db.execute("""INSERT INTO trill_occurrences(source_class,filename,file_sha256,style_name,section,track_index,channel,
      bank_msb,bank_lsb,program,role,start_tick,end_tick,start_order,end_order,main_note,neighbor_note,accepted,occurrence_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(source_class,filename,digest,style,section,track,channel,*address,role,
      row["start_tick"],row["end_tick"],row["start_order"],row["end_order"],row["main_note"],row["neighbor_note"],int(row["accepted"]),json.dumps(row,separators=(',',':'))))
    occurrence=db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute("INSERT INTO trill_features VALUES(?,?,?,?,?,?,?,?)",(occurrence,row["repetition_count"],row["total_duration_quarters"],row["average_note_duration"],row["interval_semitones"],row["pitch_stability"],row["phrase_position"],json.dumps(row,separators=(',',':'))))
    db.execute("INSERT INTO trill_context VALUES(?,?,?,?,?,?,?,?)",(occurrence,row["previous_note"],row["next_note"],row["previous_gap_quarters"],row["next_gap_quarters"],row["entry_relation"],row["exit_relation"],json.dumps({k:row[k] for k in ("phrase_position","previous_note","next_note")},separators=(',',':'))))
    db.execute("INSERT INTO trill_harmony VALUES(?,?,?,?,?,?,?,?)",(occurrence,row["tonic"],row["mode"],row["key_confidence"],row["chord_name"],row["main_is_chord_tone"],int(row["neighbor_is_scale_tone"]),json.dumps({k:row[k] for k in ("trill_type","interval_class")},separators=(',',':'))))
    db.execute("INSERT INTO trill_timing VALUES(?,?,?,?,?,?,?)",(occurrence,row["mean_spacing_quarters"],row["spacing_std"],row["acceleration"],row["subdivision"],row["swing_ratio"],json.dumps(row["notes"],separators=(',',':'))))
    db.execute("INSERT INTO trill_velocity VALUES(?,?,?,?,?,?,?,?)",(occurrence,row["velocity_mean"],row["velocity_std"],row["main_velocity_mean"],row["neighbor_velocity_mean"],row["velocity_slope"],row["velocity_pattern"],json.dumps(row["notes"],separators=(',',':'))))
    art=row["articulation"];db.execute("INSERT INTO trill_articulation VALUES(?,?,?,?,?,?,?)",(occurrence,art["pitch_bend_events"],art["pressure_events"],art["cc1_events"],art["noise_note_events"],art["rx_status"],json.dumps(art,separators=(',',':'))))
    scores=row["scores"];db.execute("INSERT INTO trill_confidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(occurrence,*[scores[key] for key in ("pitch_pattern_score","interval_score","repetition_score","timing_score","duration_score","context_score","harmonic_score","factory_pattern_score","final_score")],row["confidence"],json.dumps({"deterministic":True},separators=(',',':'))))
    db.execute("INSERT INTO trill_evidence(occurrence_id,evidence_type,evidence_status,source_locator,evidence_json) VALUES(?,?,?,?,?)",
        (occurrence,"RAW_MIDI_SEQUENCE","OBSERVED",f"{filename}#track={track}&channel={channel}&ticks={row['start_tick']}-{row['end_tick']}",json.dumps(row["notes"],separators=(',',':'))))
    return occurrence


def _target_trill_behavior(source:dict,target_rows:list[dict],division:int,offset:int=0)->tuple[str,int]:
    start=source["start_tick"]+offset;end=source["end_tick"]+offset
    selected=[row for row in target_rows if start<=row["start"]<=end]
    if not selected:return "absent",0
    trills=detect_trills(selected,division) if selected else []
    if trills:
        repetitions=max(row["repetition_count"] for row in trills)
        return ("mirrored_trill" if repetitions>=source["repetition_count"]*.75 else "simplified_trill"),repetitions
    if len(selected)<=2 and any(row["duration"]>=max(1,end-start)*.6 for row in selected):return "held_note",len(selected)
    return "simplified_notes",len(selected)


def build_musical_intelligence_database(archive_path:Path,song_paths:list[Path],output_path:Path)->dict:
    db=_new(output_path);db.executemany("INSERT INTO build_info VALUES(?,?)",(("kind","musical_intelligence"),("terca_generation","disabled"),("builder_version","1")))
    counts=Counter();pattern_rows=[]
    with ZipFile(archive_path) as outer:
        for nested_name in outer.namelist():
            if not nested_name.lower().endswith(".zip"):continue
            source_class="factory_raw" if "factory" in nested_name.lower() else "balkan_reference_raw" if "gold" in nested_name.lower() else None
            if source_class is None:continue
            with ZipFile(BytesIO(outer.read(nested_name))) as archive:
                for info in archive.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"):continue
                    data=archive.read(info);midi=parse_midi(data);digest=sha256(data).hexdigest();all_notes=note_rows(midi);groups=defaultdict(list)
                    for note in all_notes:groups[(note["track"],note["channel"])].append(note)
                    style,section=_style(info.filename)
                    for (track,channel),selected in groups.items():
                        for address,segment_notes in _note_program_segments(midi.tracks[track],channel,selected):
                            role=infer_role(channel,address[2])
                            if role in ("drums","percussion") or len(segment_notes)<4:continue
                            for trill in detect_trills(segment_notes,midi.division,midi.tracks[track],all_notes,track,channel,role):
                                _insert_occurrence(db,trill,source_class,info.filename,digest,style,section,track,channel,address,role)
                                counts[(source_class,"candidates")]+=1;counts[(source_class,"accepted")]+=int(trill["accepted"])
                                if trill["accepted"]:pattern_rows.append((source_class,_family(address[2]),trill,info.filename))
    grouped=defaultdict(list)
    for source_class,family,trill,filename in pattern_rows:
        key=(source_class,family,trill["trill_type"],trill["direction"],trill["interval_semitones"],trill["subdivision"])
        grouped[key].append((trill,filename))
    for key,selected in grouped.items():
        pattern_key=":".join(map(str,key))
        payload={"source_class":key[0],"family":key[1],"trill_type":key[2],"direction":key[3],
            "interval":key[4],"subdivision":key[5],"source_count":len({filename for _,filename in selected}),
            "occurrence_count":len(selected),"supporting_examples":[filename for _,filename in selected[:20]],
            "contradicting_examples":[]}
        db.execute("INSERT INTO trill_patterns(pattern_key,source_class,instrument_family,trill_type,direction,interval_semitones,subdivision,occurrence_count,file_count,accepted_count,confidence_mean,pattern_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (pattern_key,*key,len(selected),len({filename for _,filename in selected}),len(selected),mean(item[0]["scores"]["final_score"] for item in selected),json.dumps(payload,separators=(',',':'))))
    # The six approved songs may identify Delay/Terca track relationships only.
    # They must never provide trill, ornament, RX, PowerChord or other DNA.
    for path in song_paths:
        midi=parse_midi(path.read_bytes())
        for layer_type,pairs in (("delay",detect_delay_pairs(midi,path.name)),("harmony",detect_harmony_pairs(midi,path.name))):
            for pair in pairs:
                source_key=(pair["source_track"],pair["source_channel"]);target_key=((pair["echo_track"],pair["echo_channel"]) if layer_type=="delay" else (pair["harmony_track"],pair["harmony_channel"]))
                offset=round(float(pair.get("offset_quarters",0))*midi.division)
                relationship={"layer_type":layer_type,"source":source_key,"target":target_key,"pair":pair,
                    "terca_generation_allowed":False if layer_type=="harmony" else None}
                db.execute("INSERT INTO layer_relationships(filename,layer_type,source_track,source_channel,target_track,target_channel,offset_quarters,coverage,velocity_ratio,gate_ratio,creation_allowed,relationship_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (path.name,layer_type,*source_key,*target_key,pair.get("offset_quarters",0),pair["coverage"],pair["velocity_ratio"],pair["gate_ratio"],int(layer_type=="delay"),json.dumps(relationship,separators=(',',':'))))
    db.executemany("INSERT INTO trill_negative_rules(rule_key,description) VALUES(?,?)",(
        ("minimum_four","Dvije ili tri note nisu dovoljne za trill."),("exclude_drums","Drum roll nije melodic trill."),
        ("exclude_tremolo","Ponavljanje iste note je tremolo, ne trill."),("exclude_scale","Monotoni scale run nije alternirajući trill."),
        ("exclude_arpeggio","Tri ili više cikličnih pitch klasa nisu trill."),("short_window","Duga accompaniment alternacija se ne prihvata bez ornamentalnog konteksta."),
        ("no_random_generation","Trill generator ostaje isključen dok context/harmony/RX gate nije potvrđen.")))
    db.executemany("INSERT INTO layer_rules(rule_key,description) VALUES(?,?)",(
        ("terca_existing_only","Solo→Terca odnos se uči, ali se terca ne generiše."),
        ("delay_evidence_only","Delay se kreira samo kroz dokazani relationship model."),
        ("trill_not_blind_copy","Solo trill se ne kopira automatski u Terca ili Delay layer."),
        ("pitch_lock","Postojećoj terci se ne mijenjaju pitch, onset ni trajanje.")))
    summary={"factory_candidates":counts[("factory_raw","candidates")],"factory_accepted":counts[("factory_raw","accepted")],
        "reference_candidates":counts[("balkan_reference_raw","candidates")],"reference_accepted":counts[("balkan_reference_raw","accepted")],
        "patterns":len(grouped),"relationships":db.execute("SELECT COUNT(*) FROM layer_relationships").fetchone()[0],
        "layer_trill_behaviors":db.execute("SELECT COUNT(*) FROM layer_trill_behavior").fetchone()[0]}
    _finish(db,output_path);return summary


def register_trill_observations(registry_path:Path,trill_path:Path)->dict:
    registry=sqlite3.connect(registry_path);registry.row_factory=sqlite3.Row;trills=sqlite3.connect(trill_path);trills.row_factory=sqlite3.Row
    attempted=0
    for row in trills.execute("SELECT id,source_class,filename,file_sha256,track_index,channel,start_tick,end_tick,occurrence_json FROM trill_occurrences WHERE accepted=1"):
        attempted+=1
        source=registry.execute("SELECT id FROM evidence_sources WHERE source_type='midi_member' AND member_path=? AND sha256=?",(row["filename"],row["file_sha256"])).fetchone()
        if source is None:continue
        locator_json=json.dumps({"trill_occurrence_id":row["id"]},separators=(',',':'))
        registry.execute("INSERT INTO evidence_locators(source_id,locator_type,member_path,track_index,channel,tick_start,tick_end,locator_json) VALUES(?,?,?,?,?,?,?,?)",
            (source[0],"MIDI_TRILL",row["filename"],row["track_index"],row["channel"],row["start_tick"],row["end_tick"],locator_json))
        locator=registry.execute("SELECT last_insert_rowid()").fetchone()[0]
        payload=json.loads(row["occurrence_json"]);key=f"trill:{row['source_class']}:{row['file_sha256']}:{row['track_index']}:{row['channel']}:{row['start_tick']}"
        fingerprint=sha256(key.encode()).hexdigest()
        registry.execute("INSERT OR IGNORE INTO observations(observation_key,locator_id,metric_key,value_json,unit,sample_count,extractor_name,extractor_version,parameters_json,fingerprint) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (key,locator,"TRILL_OCCURRENCE",json.dumps(payload,separators=(',',':')),None,payload["repetition_count"],"deterministic_trill_detector","1",json.dumps({"min_notes":4},separators=(',',':')),fingerprint))
    registry.commit();integrity=registry.execute("PRAGMA integrity_check").fetchone()[0];fk=len(registry.execute("PRAGMA foreign_key_check").fetchall())
    total=registry.execute("SELECT COUNT(*) FROM observations WHERE metric_key='TRILL_OCCURRENCE'").fetchone()[0]
    registry.close();trills.close();return {"attempted":attempted,"inserted_unique":total,
        "duplicate_observations":attempted-total,"total":total,"integrity":integrity,"foreign_key_errors":fk}