"""Korg Pa800 Guitar Mode command map, Factory extraction and Strumming DNA."""

from __future__ import annotations

from collections import Counter, defaultdict
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from statistics import mean, pstdev
from zipfile import ZipFile

from .midi import MidiFile, note_rows, parse_midi


STRUM_COMMANDS = {
    24:"full_down",25:"full_down_mute",26:"full_up",27:"full_up_mute",
    28:"full_down_mute_body",29:"full_down_slow",30:"full_down_slow_mute",
    31:"full_up_slow",32:"up_mute_4_strings",33:"down_4_strings",
    34:"down_mute_4_strings",35:"up_4_strings",
}

STRING_COMMANDS = {
    36:"string_6_low_e",37:"recognized_chord_root",38:"string_5_a",
    39:"recognized_chord_fifth",40:"string_4_d",41:"string_3_g",
    42:"mute_all",43:"string_2_b",44:"power_chord",45:"string_1_high_e",
    46:"full_down_up",47:"down_up_4_strings",
}

CHORD_VELOCITIES = {
    1:"major",2:"major_6",3:"major_7",4:"major_7_flat_5",5:"sus_4",6:"sus_2",
    7:"major_7_sus_4",8:"minor",9:"minor_6",10:"minor_7",11:"minor_7_flat_5",
    12:"minor_major_7",13:"dominant_7",14:"7_flat_5",15:"7_sus_4",16:"diminished",
    17:"diminished_major_7",18:"augmented",19:"augmented_7",20:"augmented_major_7",
    21:"major_without_3rd",22:"major_without_3rd_and_5th",23:"flat_5",24:"diminished_7",
}

OFFICIAL_RULES = (
    ("track_type","Style/Pad track mora biti Type=Gtr; Tension se automatski uključuje."),
    ("external_channel","Eksterni sequencer kanal mora odgovarati Style Acc1–Acc5 MIDI IN kanalu."),
    ("strum_octave","C1–B1 bira 12 Pa800 strumming komandi."),
    ("string_octave","C2–B2 bira šest žica, root, fifth, mute, power chord i dvije arpeggio komande."),
    ("rx_noise","Gornje tri oktave okidaju RX Noise događaje zavisno od izabranog Sounda."),
    ("humanize_gtr","Humanize GTR utiče na poziciju, velocity i dužinu samo Guitar trake."),
    ("rx_noise_level","Noise/Guitar stranica odvojeno kontroliše RX Noise nivo."),
    ("capo","Capo podržava 0 i pozicije I–X; mijenja položaj/timbar i može utišati neke žice."),
    ("key_chord","Key/Chord je monitoring referenca; u Intro1/Ending1 je referenca chord progressiona."),
    ("chord_progression","U Intro1/Ending1 note C-1–B-1 i velocity 1–24 kodiraju root i chord type."),
    ("ntt","NTT Type/Table nije primjenjiv na Guitar track; Guitar Mode koristi stvarne guitar pozicije."),
    ("regular_pattern","Regularne note mogu se koristiti za kratke završetke ili melodijske prolaze."),
)

SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE guitar_mode_commands(note INTEGER PRIMARY KEY,note_name TEXT,command TEXT,group_name TEXT,
 direction TEXT,muted INTEGER,slow INTEGER,four_strings INTEGER,source TEXT);
CREATE TABLE chord_velocity_types(velocity INTEGER PRIMARY KEY,chord_type TEXT,source TEXT);
CREATE TABLE strumming_tracks(id INTEGER PRIMARY KEY,filename TEXT,style_name TEXT,section TEXT,section_no INTEGER,
 track_index INTEGER,channel INTEGER,program INTEGER,track_label TEXT,instrument_name TEXT,detection_method TEXT,
 tempo_bpm REAL,meter_num INTEGER,meter_den INTEGER,
 note_count INTEGER,command_count INTEGER,strum_count INTEGER,string_count INTEGER,chord_code_count INTEGER,
 rx_noise_count INTEGER,regular_count INTEGER,down_count INTEGER,up_count INTEGER,mute_count INTEGER,
 slow_count INTEGER,four_string_count INTEGER,alternation_ratio REAL,velocity_mean REAL,velocity_std REAL,
 density_per_quarter REAL,profile_json TEXT,UNIQUE(filename,track_index,channel));
CREATE TABLE strumming_models(id INTEGER PRIMARY KEY,scope_key TEXT UNIQUE,section TEXT,tempo_bucket INTEGER,
 meter_num INTEGER,meter_den INTEGER,track_count INTEGER,event_count INTEGER,model_json TEXT);
CREATE TABLE guitar_sound_profiles(id INTEGER PRIMARY KEY,instrument_name TEXT,program INTEGER,track_count INTEGER,
 event_count INTEGER,velocity_mean REAL,density_per_quarter REAL,sections_json TEXT,command_hist_json TEXT,
 UNIQUE(instrument_name,program));
CREATE TABLE chord_progression_profiles(id INTEGER PRIMARY KEY,velocity INTEGER,chord_type TEXT,event_count INTEGER,
 root_hist_json TEXT,UNIQUE(velocity,chord_type));
CREATE TABLE guitar_mode_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT,source TEXT);
"""


def _note_name(note: int) -> str:
    names=("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")
    return f"{names[note%12]}{note//12-1}"


def _command_attributes(note: int, command: str) -> tuple[str,str,int,int,int]:
    group="strum" if note in STRUM_COMMANDS else "string_arpeggio"
    direction="down" if "down" in command and "up" not in command else "up" if "up" in command and "down" not in command else "both" if "down_up" in command else "none"
    return group,direction,int("mute" in command),int("slow" in command),int("4_strings" in command)


def _metadata(filename: str, midi: MidiFile):
    stem=Path(filename).stem; match=re.search(r"_(Intro|Var|Fill|End|Ending|Break)(\d*)$",stem,re.I)
    if match:
        raw=match.group(1).lower(); section={"var":"variation","end":"ending"}.get(raw,raw)
        section_no=int(match.group(2) or 0); style=stem[:match.start()]
    else: section="song"; section_no=0; style=Path(filename).parent.name or stem
    tempo=None; meter=(4,4)
    for events in midi.tracks:
        for event in events:
            if event.kind=="meta" and event.data1==0x51 and len(event.raw)==3 and tempo is None:
                micros=int.from_bytes(event.raw,"big"); tempo=60_000_000/micros if micros else None
            elif event.kind=="meta" and event.data1==0x58 and len(event.raw)>=2:
                meter=(int(event.raw[0]),2**int(event.raw[1]))
    return style,section,section_no,tempo,*meter


def _programs(midi: MidiFile) -> dict[tuple[int,int],int]:
    result={}
    for ti,events in enumerate(midi.tracks):
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            if event.kind=="program": result[(ti,int(event.channel or 0))]=int(event.data1 or 0)
    return result


def _track_text(events, meta_type: int) -> list[str]:
    return [event.raw.decode("latin1","replace").strip(" \x00") for event in events
            if event.kind=="meta" and event.data1==meta_type and event.raw]


def _guitar_evidence(events, program: int, command_count: int, note_count: int) -> tuple[bool,str,str,str]:
    labels=_track_text(events,3); texts=_track_text(events,1)
    track_label=next((text for text in labels if text and text!="PartInfo"),"")
    instrument=next((text for text in texts if text and not re.search(r"\b(Bars?|Intro|Variation|Fill|Ending|Break)\b",text,re.I)),"")
    combined=f"{track_label} {instrument}".lower()
    positive=("guitar","gtr","nylon","steel guitar","steel str","12 string","distort","jazz gt",
              "clean gt","clean funk","funk stein","mandolin")
    negative=(" kit","kit ","drum","perc","piano","organ","bass","choir","sax","brass","synth","pad")
    named=any(token in combined for token in positive)
    explicitly_not_guitar=any(token in f" {combined} " for token in negative)
    program_family=24<=program<=31 and not instrument
    ratio=command_count/max(1,note_count)
    dense_control=ratio>=.75 and command_count>=4 and not instrument and not explicitly_not_guitar
    method="name" if named else "program_family" if program_family else "dense_command_ratio" if dense_control else ""
    return bool(method),method,track_label,instrument


def extract_strumming_tracks(filename: str, midi: MidiFile) -> list[dict]:
    style,section,section_no,tempo,meter_num,meter_den=_metadata(filename,midi)
    programs=_programs(midi); groups=defaultdict(list)
    for row in note_rows(midi): groups[(row["track"],row["channel"])].append(row)
    result=[]
    for (track,channel),selected in groups.items():
        program=programs.get((track,channel),0)
        commands=[row for row in selected if row["note"] in STRUM_COMMANDS or row["note"] in STRING_COMMANDS]
        # Pa800 Style Guitar tracks normally live on Acc1–Acc5. Program-family
        # evidence is also accepted for imported/externally sequenced material.
        evidence,method,track_label,instrument=_guitar_evidence(midi.tracks[track],program,len(commands),len(selected))
        if channel in (9,10) or len(commands)<2 or not evidence or not (11<=channel<=15 or 24<=program<=31): continue
        selected.sort(key=lambda row:(row["start"],row["note"]))
        names=[STRUM_COMMANDS.get(row["note"],STRING_COMMANDS.get(row["note"])) for row in commands]
        strums=[row for row in commands if row["note"] in STRUM_COMMANDS]
        strings=[row for row in commands if row["note"] in STRING_COMMANDS]
        directions=[]
        for name in names:
            if "down" in name and "up" not in name: directions.append("down")
            elif "up" in name and "down" not in name: directions.append("up")
        alternations=sum(a!=b for a,b in zip(directions,directions[1:]))/max(1,len(directions)-1)
        length=max((event.tick for event in midi.tracks[track]),default=midi.division)/midi.division
        chord_codes=[row for row in selected if 0<=row["note"]<=11 and row["velocity"] in CHORD_VELOCITIES]
        rx_noise=[row for row in selected if row["note"]>=96]
        regular=[row for row in selected if 48<=row["note"]<=95]
        velocities=[row["velocity"] for row in commands]
        position_velocity=defaultdict(list); position_timing=defaultdict(list); transitions=Counter()
        previous=None
        for row in commands:
            position=round((row["start"]/midi.division)*4)%16
            position_velocity[position].append(row["velocity"])
            grid=round(row["start"]/(midi.division/4))*(midi.division/4)
            position_timing[position].append((row["start"]-grid)/midi.division)
            name=STRUM_COMMANDS.get(row["note"],STRING_COMMANDS.get(row["note"]))
            if previous: transitions[(previous,name)]+=1
            previous=name
        profile={"command_hist":dict(Counter(names)),
            "velocity_by_16th":{str(k):mean(v) for k,v in position_velocity.items()},
            "timing_by_16th":{str(k):mean(v) for k,v in position_timing.items()},
            "transitions":{f"{a}>{b}":n for (a,b),n in transitions.items()},
            "chord_type_hist":dict(Counter(CHORD_VELOCITIES[row["velocity"]] for row in chord_codes)),
            "chord_root_hist":dict(Counter(_note_name(row["note"]) for row in chord_codes)),
            "chord_joint_hist":dict(Counter(f'{row["velocity"]}:{_note_name(row["note"])}' for row in chord_codes)),
            "rx_noise_hist":dict(Counter(_note_name(row["note"]) for row in rx_noise))}
        result.append({"filename":filename,"style_name":style,"section":section,"section_no":section_no,
            "track_index":track,"channel":channel,"program":program,"tempo_bpm":tempo,
            "track_label":track_label,"instrument_name":instrument,"detection_method":method,
            "tempo_bucket":round(float(tempo or 0)/20)*20 if tempo else 0,"meter_num":meter_num,"meter_den":meter_den,
            "note_count":len(selected),"command_count":len(commands),"strum_count":len(strums),"string_count":len(strings),
            "chord_code_count":len(chord_codes),"rx_noise_count":len(rx_noise),"regular_count":len(regular),
            "down_count":sum("down" in n and "up" not in n for n in names),
            "up_count":sum("up" in n and "down" not in n for n in names),"mute_count":sum("mute" in n for n in names),
            "slow_count":sum("slow" in n for n in names),"four_string_count":sum("4_strings" in n for n in names),
            "alternation_ratio":alternations,"velocity_mean":mean(velocities),"velocity_std":pstdev(velocities),
            "density_per_quarter":len(commands)/max(length,1e-9),"profile":profile})
    return result


def _aggregate(rows: list[dict], scope_key: str, section=None, tempo_bucket=None, meter_num=None, meter_den=None) -> dict:
    total=sum(row["command_count"] for row in rows); hist=Counter(); transitions=Counter(); vel=defaultdict(list); timing=defaultdict(list)
    for row in rows:
        profile=row["profile"]; hist.update(profile["command_hist"]); transitions.update(profile["transitions"])
        for key,value in profile["velocity_by_16th"].items(): vel[key].append((value,row["command_count"]))
        for key,value in profile["timing_by_16th"].items(): timing[key].append((value,row["command_count"]))
    weighted=lambda values: sum(v*w for v,w in values)/max(1,sum(w for _,w in values))
    model={"scope_key":scope_key,"section":section,"tempo_bucket":tempo_bucket,"meter_num":meter_num,"meter_den":meter_den,
        "track_count":len(rows),"event_count":total,"command_hist":dict(hist),"transitions":dict(transitions),
        "velocity_by_16th":{key:weighted(value) for key,value in vel.items()},
        "timing_by_16th":{key:weighted(value) for key,value in timing.items()},
        "alternation_ratio":sum(row["alternation_ratio"]*row["command_count"] for row in rows)/max(1,total),
        "mute_ratio":sum(row["mute_count"] for row in rows)/max(1,total),
        "slow_ratio":sum(row["slow_count"] for row in rows)/max(1,total),
        "four_string_ratio":sum(row["four_string_count"] for row in rows)/max(1,total)}
    return model


def build_strumming_database(archive_path: Path, output_path: Path) -> dict:
    temp=output_path.with_suffix(output_path.suffix+".tmp"); temp.unlink(missing_ok=True)
    database=sqlite3.connect(temp); database.executescript(SCHEMA)
    database.execute("INSERT INTO build_info VALUES('kind','strumming')")
    database.execute("INSERT INTO build_info VALUES('schema_version','1')")
    database.execute("INSERT INTO build_info VALUES('archive_sha256',?)",(hashlib.sha256(archive_path.read_bytes()).hexdigest(),))
    for note,command in {**STRUM_COMMANDS,**STRING_COMMANDS}.items():
        group,direction,muted,slow,four=_command_attributes(note,command)
        database.execute("INSERT INTO guitar_mode_commands VALUES(?,?,?,?,?,?,?,?,?)",
            (note,_note_name(note),command,group,direction,muted,slow,four,"Korg Pa800 OS 1.60 Guitar Mode"))
    database.executemany("INSERT INTO chord_velocity_types VALUES(?,?,?)",
        [(velocity,name,"Korg Pa800 OS 1.60 Guitar Mode") for velocity,name in CHORD_VELOCITIES.items()])
    database.executemany("INSERT INTO guitar_mode_rules(rule_key,description,source) VALUES(?,?,?)",
        [(key,description,"Korg Pa800 OS 1.60 Upgrade Manual") for key,description in OFFICIAL_RULES])
    tracks=[]
    with ZipFile(archive_path) as outer:
        nested=next(name for name in outer.namelist() if "factory" in name.lower() and name.lower().endswith(".zip"))
        with ZipFile(BytesIO(outer.read(nested))) as archive:
            for info in archive.infolist():
                if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"): continue
                tracks.extend(extract_strumming_tracks(info.filename,parse_midi(archive.read(info))))
    for row in tracks:
        database.execute("""INSERT INTO strumming_tracks(filename,style_name,section,section_no,track_index,channel,
            program,track_label,instrument_name,detection_method,tempo_bpm,meter_num,meter_den,note_count,command_count,strum_count,string_count,chord_code_count,
            rx_noise_count,regular_count,down_count,up_count,mute_count,slow_count,four_string_count,alternation_ratio,
            velocity_mean,velocity_std,density_per_quarter,profile_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row["filename"],row["style_name"],row["section"],row["section_no"],row["track_index"],row["channel"],
             row["program"],row["track_label"],row["instrument_name"],row["detection_method"],row["tempo_bpm"],row["meter_num"],row["meter_den"],row["note_count"],row["command_count"],
             row["strum_count"],row["string_count"],row["chord_code_count"],row["rx_noise_count"],row["regular_count"],
             row["down_count"],row["up_count"],row["mute_count"],row["slow_count"],row["four_string_count"],
             row["alternation_ratio"],row["velocity_mean"],row["velocity_std"],row["density_per_quarter"],
             json.dumps(row["profile"],separators=(',',':'))))
    models=[]
    if tracks: models.append(_aggregate(tracks,"global"))
    groups=defaultdict(list)
    for row in tracks: groups[(row["section"],row["tempo_bucket"],row["meter_num"],row["meter_den"])].append(row)
    for key,selected in groups.items(): models.append(_aggregate(selected,f"{key[0]}:{key[1]}:{key[2]}/{key[3]}",*key))
    for model in models:
        database.execute("INSERT INTO strumming_models(scope_key,section,tempo_bucket,meter_num,meter_den,track_count,event_count,model_json) VALUES(?,?,?,?,?,?,?,?)",
            (model["scope_key"],model["section"],model["tempo_bucket"],model["meter_num"],model["meter_den"],model["track_count"],model["event_count"],json.dumps(model,separators=(',',':'))))
    sound_groups=defaultdict(list)
    for row in tracks: sound_groups[(row["instrument_name"] or "Unknown Guitar",row["program"])].append(row)
    for (instrument,program),selected in sound_groups.items():
        events=sum(row["command_count"] for row in selected); hist=Counter()
        for row in selected: hist.update(row["profile"]["command_hist"])
        database.execute("""INSERT INTO guitar_sound_profiles(instrument_name,program,track_count,event_count,
            velocity_mean,density_per_quarter,sections_json,command_hist_json) VALUES(?,?,?,?,?,?,?,?)""",
            (instrument,program,len(selected),events,
             sum(row["velocity_mean"]*row["command_count"] for row in selected)/max(1,events),
             sum(row["density_per_quarter"]*row["command_count"] for row in selected)/max(1,events),
             json.dumps(sorted({row["section"] for row in selected})),json.dumps(dict(hist),separators=(',',':'))))
    chord_roots=defaultdict(Counter); chord_counts=Counter()
    for row in tracks:
        profile=row["profile"]
        for chord_type,count in profile["chord_type_hist"].items(): chord_counts[chord_type]+=count
        for joint,count in profile["chord_joint_hist"].items():
            velocity_text,root=joint.split(":",1); chord_roots[CHORD_VELOCITIES[int(velocity_text)]][root]+=count
    for velocity,chord_type in CHORD_VELOCITIES.items():
        database.execute("INSERT INTO chord_progression_profiles(velocity,chord_type,event_count,root_hist_json) VALUES(?,?,?,?)",
            (velocity,chord_type,chord_counts[chord_type],json.dumps(dict(chord_roots[chord_type]),separators=(',',':'))))
    database.commit(); database.close(); temp.replace(output_path)
    return {"tracks":len(tracks),"models":len(models),"commands":len(STRUM_COMMANDS)+len(STRING_COMMANDS),
            "chord_types":len(CHORD_VELOCITIES),"rules":len(OFFICIAL_RULES),
            "sound_profiles":len(sound_groups),"events":sum(row["command_count"] for row in tracks)}


def load_strumming_models(path: Path) -> list[dict]:
    database=sqlite3.connect(path)
    result=[json.loads(row[0]) for row in database.execute("SELECT model_json FROM strumming_models")]
    database.close(); return result


def choose_strumming_model(models: list[dict], section: str | None, tempo_bpm: float | None,
                           meter_num: int, meter_den: int) -> dict | None:
    if not models: return None
    bucket=round(float(tempo_bpm or 0)/20)*20 if tempo_bpm else 0
    candidates=[model for model in models if model.get("scope_key")!="global" and model.get("meter_num")==meter_num and model.get("meter_den")==meter_den]
    if section: candidates=[model for model in candidates if model.get("section")==section] or candidates
    return min(candidates,key=lambda model:abs(int(model.get("tempo_bucket") or 0)-bucket)) if candidates else next((m for m in models if m.get("scope_key")=="global"),models[0])