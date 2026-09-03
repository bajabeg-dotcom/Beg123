"""SQLite persistence for Factory and Gold DNA corpora."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from copy import copy
import re
from statistics import mean, pstdev
from .midi import MidiFile, note_rows
from .features import extract_features, track_feature_to_dict

GM_NAMES = ["Acoustic Grand Piano","Bright Acoustic Piano","Electric Grand Piano","Honky-tonk Piano","Electric Piano 1","Electric Piano 2","Harpsichord","Clavinet","Celesta","Glockenspiel","Music Box","Vibraphone","Marimba","Xylophone","Tubular Bells","Dulcimer"] + [f"GM Program {n}" for n in range(17,129)]

SCHEMA = """
CREATE TABLE IF NOT EXISTS midi_files(id INTEGER PRIMARY KEY,filename TEXT NOT NULL,sha256 TEXT NOT NULL UNIQUE,midi_format INTEGER,division INTEGER,track_count INTEGER,style_name TEXT DEFAULT '',section TEXT DEFAULT '',section_no INTEGER DEFAULT 0,tempo_bpm REAL,meter_num INTEGER DEFAULT 4,meter_den INTEGER DEFAULT 4,imported_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS instrument_profiles(id INTEGER PRIMARY KEY,bank_msb INTEGER NOT NULL DEFAULT 0,bank_lsb INTEGER NOT NULL DEFAULT 0,program INTEGER NOT NULL,role TEXT NOT NULL,name TEXT NOT NULL,source TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}',UNIQUE(bank_msb,bank_lsb,program,role,source));
CREATE TABLE IF NOT EXISTS track_stats(id INTEGER PRIMARY KEY,file_id INTEGER NOT NULL,track_index INTEGER NOT NULL,channel INTEGER NOT NULL,role TEXT NOT NULL,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,note_count INTEGER,velocity_mean REAL,velocity_std REAL,duration_mean REAL,duration_quarters REAL,density_per_quarter REAL,FOREIGN KEY(file_id) REFERENCES midi_files(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS rx_zones(id INTEGER PRIMARY KEY,profile_name TEXT NOT NULL,oscillator INTEGER NOT NULL,articulation TEXT NOT NULL,velocity_min INTEGER,velocity_max INTEGER,key_min INTEGER,key_max INTEGER,switch_value INTEGER,notes TEXT);
CREATE TABLE IF NOT EXISTS gm_rx_mappings(id INTEGER PRIMARY KEY,source_bank_msb INTEGER NOT NULL DEFAULT 0,source_bank_lsb INTEGER NOT NULL DEFAULT 0,source_program INTEGER NOT NULL,role TEXT NOT NULL,rx_name TEXT NOT NULL,target_bank_msb INTEGER NOT NULL,target_bank_lsb INTEGER NOT NULL,target_program INTEGER NOT NULL,confidence REAL NOT NULL DEFAULT 1.0,provenance TEXT NOT NULL DEFAULT 'user',is_default INTEGER NOT NULL DEFAULT 0,UNIQUE(source_bank_msb,source_bank_lsb,source_program,role));
CREATE TABLE IF NOT EXISTS project_plans(id INTEGER PRIMARY KEY,agent TEXT NOT NULL,plan TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS import_errors(id INTEGER PRIMARY KEY,filename TEXT NOT NULL,error TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS pa800_voice_catalog(id INTEGER PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,bank_msb INTEGER NOT NULL,bank_lsb INTEGER NOT NULL,program INTEGER NOT NULL,is_rx INTEGER NOT NULL DEFAULT 1,source TEXT NOT NULL,UNIQUE(bank_msb,bank_lsb,program,name));
CREATE TABLE IF NOT EXISTS performance_features(id INTEGER PRIMARY KEY,file_id INTEGER NOT NULL,track_index INTEGER NOT NULL,channel INTEGER NOT NULL,role TEXT NOT NULL,section TEXT DEFAULT '',cv INTEGER DEFAULT 0,feature_json TEXT NOT NULL,FOREIGN KEY(file_id) REFERENCES midi_files(id) ON DELETE CASCADE,UNIQUE(file_id,track_index,channel));
CREATE TABLE IF NOT EXISTS instrument_segments(id INTEGER PRIMARY KEY,file_id INTEGER NOT NULL,track_index INTEGER NOT NULL,
 channel INTEGER NOT NULL,segment_index INTEGER NOT NULL,start_tick INTEGER NOT NULL,end_tick INTEGER NOT NULL,
 bank_msb INTEGER NOT NULL DEFAULT 0,bank_lsb INTEGER NOT NULL DEFAULT 0,program INTEGER NOT NULL DEFAULT 0,
 role TEXT NOT NULL,name TEXT NOT NULL,note_count INTEGER NOT NULL,feature_json TEXT NOT NULL,
 FOREIGN KEY(file_id) REFERENCES midi_files(id) ON DELETE CASCADE,
 UNIQUE(file_id,track_index,channel,segment_index));
CREATE TABLE IF NOT EXISTS optimizer_runs(id INTEGER PRIMARY KEY,source_name TEXT NOT NULL,source_sha256 TEXT NOT NULL,output_name TEXT NOT NULL,output_sha256 TEXT NOT NULL,config_json TEXT NOT NULL,report_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


class ClosingConnection(sqlite3.Connection):
    """Make ``with connect(...)`` close, not merely commit/rollback."""
    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()

def connect(path: Path):
    db=sqlite3.connect(path,factory=ClosingConnection); db.row_factory=sqlite3.Row; db.execute("PRAGMA foreign_keys=ON"); db.executescript(SCHEMA)
    # CREATE TABLE IF NOT EXISTS does not update databases created by older builds.
    columns={row[1] for row in db.execute("PRAGMA table_info(gm_rx_mappings)")}
    for name, declaration in (
        ("confidence", "REAL NOT NULL DEFAULT 1.0"),
        ("provenance", "TEXT NOT NULL DEFAULT 'user'"),
        ("is_default", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in columns:
            db.execute(f"ALTER TABLE gm_rx_mappings ADD COLUMN {name} {declaration}")
    track_columns={row[1] for row in db.execute("PRAGMA table_info(track_stats)")}
    if "duration_quarters" not in track_columns:
        db.execute("ALTER TABLE track_stats ADD COLUMN duration_quarters REAL")
    midi_columns={row[1] for row in db.execute("PRAGMA table_info(midi_files)")}
    for name,declaration in (("style_name","TEXT DEFAULT ''"),("section","TEXT DEFAULT ''"),
                             ("section_no","INTEGER DEFAULT 0"),("tempo_bpm","REAL"),
                             ("meter_num","INTEGER DEFAULT 4"),("meter_den","INTEGER DEFAULT 4")):
        if name not in midi_columns:
            db.execute(f"ALTER TABLE midi_files ADD COLUMN {name} {declaration}")
    db.commit(); return db

def seed_rx_zones(db):
    if db.execute("SELECT COUNT(*) FROM rx_zones").fetchone()[0]:
        db.execute("""UPDATE rx_zones SET switch_value=87,
            notes='C-1–B6; corrected from 94 using user knowledge + Factory velocity analysis; verify in Pa800 Sound Edit'
            WHERE profile_name IN ('SlapFing Bass RX','SlapPick Bass RX') AND oscillator=2""")
        db.commit(); return
    zones=[]
    for name in ["Finger Bass RX","Picked Bass RX"]:
        zones += [(name,1,"Harm",114,127,0,95,1,"C-1–B6"),(name,2,"Radni Bass",53,113,0,95,94,"C-1–B6"),(name,3,"Stop",23,52,0,95,39,"C-1–B6"),(name,4,"Gliss",1,22,0,95,1,"C-1–B6"),(name,5,"Noise",1,127,96,127,1,"C7–G9")]
    for name in ["SlapFing Bass RX","SlapPick Bass RX"]:
        zones += [(name,1,"Slap/Harmonic",114,127,0,95,1,"C-1–B6"),(name,2,"Radni Slap/Pick",53,113,0,95,87,"C-1–B6; corrected from 94; verify in Pa800 Sound Edit")]
    for name in [f"Clean Guitar RX{i}" for i in range(1,7)]:
        zones += [(name,1,"Clean Slap/Slide",94,127,0,95,114,"C-1–B6"),(name,2,"Radni",53,93,0,95,74,"C-1–B6"),(name,3,"Clean Dead/Mute",23,52,0,95,39,"C-1–B6"),(name,4,"Clean Harm/Ghost",1,22,0,95,1,"C-1–B6"),(name,5,"Clean Noise",1,127,96,127,1,"C7–G9")]
    zones += [("Pop Std. Kit RX",1,"B1/C2",1,127,35,36,None,"1 oscillator"),("Pop Std. Kit RX",2,"D2/E2 layers",1,127,38,40,None,"switch 26,47,68,89,110; 6 layers"),("Pop Std. Kit RX",3,"F#2 layers",1,127,42,42,None,"switch 68,87,106; 4 layers"),("Pop Std. Kit RX",4,"Single layer",1,127,41,50,None,"F2,G2,A2,B2,C3,D3"),("Pop Std. Kit RX",5,"G#2/A#2",1,127,44,46,68,"2 oscillators")]
    db.executemany("INSERT INTO rx_zones(profile_name,oscillator,articulation,velocity_min,velocity_max,key_min,key_max,switch_value,notes) VALUES(?,?,?,?,?,?,?,?,?)",zones); db.commit()

def seed_pa800_catalog(db):
    source="KORG Pa800 Owner's Manual, Factory data appendix (PC 0-127)"
    voices=[
        ("Acous. Bass RX","bass",121,7,32,1,source),("Finger Bass RX","bass",121,13,33,1,source),
        ("Picked Bass RX","bass",121,10,34,1,source),("FunkSlap Bass RX","bass",121,3,36,1,source),
        ("SlapFing Bass RX","bass",121,4,36,1,source),("SlapPick Bass RX","bass",121,5,36,1,source),
        ("Clean Guitar RX1","guitar",121,14,28,1,source),("Clean Guitar RX2","guitar",121,15,28,1,source),
        ("Clean Guitar RX3","guitar",121,16,28,1,source),("Clean Guitar RX4","guitar",121,17,28,1,source),
        ("Clean Guitar RX5","guitar",121,18,28,1,source),("Clean Guitar RX6","guitar",121,20,28,1,source),
        ("Standard Kit GM","drums",120,0,0,0,source),("Standard Kit RX2","drums",120,0,1,1,source),
        ("Standard Kit RX3","drums",120,0,2,1,source),("Ambient Kit RX","drums",120,0,3,1,source),
        ("Pop Std. Kit RX","drums",120,0,4,1,source),("Standard Kit RX1","drums",120,0,5,1,source),
        ("Jazz Kit RX1","drums",120,0,33,1,source),("Jazz Kit RX2","drums",120,0,34,1,source),
        ("Jazz Kit RX3","drums",120,0,35,1,source),
    ]
    db.executemany("""INSERT OR IGNORE INTO pa800_voice_catalog(name,category,bank_msb,bank_lsb,program,is_rx,source)
        VALUES(?,?,?,?,?,?,?)""",voices); db.commit()
    # Defaults bootstrap a new database only. Re-seeding on every application
    # start can resurrect a row intentionally replaced by the generated,
    # identity-safe recommendation set and desynchronize derived Voice DNA.
    if db.execute("SELECT COUNT(*) FROM gm_rx_mappings").fetchone()[0]==0:
        seed_default_gm_rx_mappings(db)

def seed_default_gm_rx_mappings(db):
    """Seed conservative GM-bank recommendations backed by the Pa800 catalog.

    Only direct family matches are included. Existing user rows win because the
    table's source identity is unique and defaults are inserted with OR IGNORE.
    Program values are MIDI's 0-127 values (not the UI's 1-128 numbering).
    """
    provenance="KORG Pa800 Factory data appendix target; GM Level 1 source family"
    mappings=[
        (0,0,32,"bass","Acous. Bass RX",121,7,32,.98,provenance,1),
        (0,0,33,"bass","Finger Bass RX",121,13,33,.99,provenance,1),
        (0,0,34,"bass","Picked Bass RX",121,10,34,.99,provenance,1),
        (0,0,36,"bass","FunkSlap Bass RX",121,3,36,.96,provenance,1),
        (0,0,37,"bass","SlapPick Bass RX",121,5,36,.92,provenance,1),
        (0,0,27,"guitar","Clean Guitar RX1",121,14,28,.96,provenance,1),
        (0,0,0,"drums","Standard Kit RX2",120,0,1,.95,provenance,1),
    ]
    db.executemany("""INSERT OR IGNORE INTO gm_rx_mappings(
        source_bank_msb,source_bank_lsb,source_program,role,rx_name,
        target_bank_msb,target_bank_lsb,target_program,confidence,provenance,is_default)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",mappings)
    db.commit()

def _meta_texts(events, meta_type):
    return [e.raw.decode("latin1", "replace").strip(" \x00") for e in events
            if e.kind == "meta" and e.data1 == meta_type and e.raw]

def _track_label(events):
    names = [value for value in _meta_texts(events, 3) if value and not value.startswith("SN:") and value != "PartInfo"]
    return names[0] if names else ""

def _instrument_name(events):
    for value in _meta_texts(events, 1):
        upper = value.upper()
        if value and " BAR" not in upper and not upper.startswith(("INTRO", "VARIATION", "FILL", "BREAK", "ENDING")):
            return value
    return ""

def _role(source, channel, program, label):
    upper = label.upper()
    if "DRUM" in upper or channel == 9: return "drums"
    if "PERC" in upper: return "percussion"
    if "BASS" in upper or 32 <= program <= 39: return "bass"
    if "GUIT" in upper or 24 <= program <= 31: return "guitar"
    if "ACC" in upper or (source == "factory" and 11 <= channel <= 15): return "accompaniment"
    if source == "factory" and channel == 8: return "bass"
    if source == "factory" and channel == 10: return "percussion"
    return "melodic"

def _file_metadata(filename, midi):
    stem=Path(filename).stem
    match=re.search(r"_(Intro|Var|Fill|End|Ending|Break)(\d*)$",stem,re.I)
    if match:
        raw=match.group(1).lower(); section={"var":"variation","end":"ending"}.get(raw,raw)
        section_no=int(match.group(2) or 0); style=stem[:match.start()]
    else:
        section="song"; section_no=0; style=Path(filename).parent.name or stem
    tempo=None; meter_num=4; meter_den=4
    for events in midi.tracks:
        for event in events:
            if event.kind=="meta" and event.data1==0x51 and len(event.raw)==3 and tempo is None:
                micros=int.from_bytes(event.raw,"big"); tempo=60_000_000/micros if micros else None
            elif event.kind=="meta" and event.data1==0x58 and len(event.raw)>=2:
                meter_num=event.raw[0]; meter_den=2**event.raw[1]
    return style,section,section_no,tempo,meter_num,meter_den

def _program_segments(events,channel:int,end_tick:int):
    """Return active Bank/Program intervals for one MIDI channel.

    Bank Select is pending until Program Change, matching MIDI device
    semantics.  Notes are attributed by their Note On tick.
    """
    pending=[0,0];active=(0,0,0);start=(0,-2**31);segments=[]
    for event in sorted(events,key=lambda item:(item.tick,item.order)):
        if int(event.channel or 0)!=channel:continue
        if event.kind=="control" and event.data1 in (0,32):
            pending[0 if event.data1==0 else 1]=int(event.data2 or 0)
        elif event.kind=="program":
            key=(int(event.tick),int(event.order));new_state=(pending[0],pending[1],int(event.data1 or 0))
            if new_state==active:continue
            if key>start:segments.append((*start,*key,*active))
            active=new_state;start=key
    end=(max(start[0]+1,end_tick+1),2**31-1)
    segments.append((*start,*end,*active))
    return segments

def _segment_feature(midi:MidiFile,track_index:int,channel:int,start_key:tuple[int,int],end_key:tuple[int,int],selected:list[dict],role:str):
    note_events={id(row["on_event"]) for row in selected}|{id(row["off_event"]) for row in selected}
    events=[]
    for event in midi.tracks[track_index]:
        if id(event) in note_events:
            cloned=copy(event);cloned.tick=max(0,int(event.tick)-start_key[0]);events.append(cloned);continue
        key=(int(event.tick),int(event.order))
        if int(event.channel or 0)==channel and start_key<=key<end_key and event.kind in (
            "control","pitch","pressure","poly_pressure"):
            cloned=copy(event);cloned.tick=max(0,int(event.tick)-start_key[0]);events.append(cloned)
    feature=extract_features(MidiFile(midi.format,midi.division,[events]),{(0,channel):role})
    return feature[0] if feature else None

def analyze_and_store(db,file_id:int,midi:MidiFile,source:str):
    notes=note_rows(midi)
    filename=db.execute("SELECT filename FROM midi_files WHERE id=?",(file_id,)).fetchone()[0]
    style,section,section_no,tempo,meter_num,meter_den=_file_metadata(filename,midi)
    db.execute("UPDATE midi_files SET style_name=?,section=?,section_no=?,tempo_bpm=?,meter_num=?,meter_den=? WHERE id=?",
               (style,section,section_no,tempo,meter_num,meter_den,file_id))
    role_map={}; cv_map={}
    db.execute("DELETE FROM instrument_segments WHERE file_id=?",(file_id,))
    for ti,events in enumerate(midi.tracks):
        label=_track_label(events); instrument_name=_instrument_name(events)
        cv_match=re.search(r"CV\s*(\d+)",label,re.I); cv=int(cv_match.group(1)) if cv_match else 0
        banks={c:[0,0] for c in range(16)}; programs={c:0 for c in range(16)}; seen=set()
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            ch=int(event.channel or 0)
            if event.kind=="control" and event.data1 in (0,32): banks[ch][0 if event.data1==0 else 1]=int(event.data2 or 0)
            elif event.kind=="program":
                programs[ch]=int(event.data1 or 0); seen.add(ch); role=_role(source,ch,programs[ch],label)
                name=instrument_name or ("GM Drums" if role=="drums" else GM_NAMES[programs[ch]])
                metadata=json.dumps({"auto_registered":True,"track_label":label},ensure_ascii=False)
                db.execute("""INSERT INTO instrument_profiles(bank_msb,bank_lsb,program,role,name,source,metadata_json)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(bank_msb,bank_lsb,program,role,source) DO UPDATE SET
                    name=CASE WHEN excluded.name NOT LIKE 'GM Program %' AND excluded.name!='GM Drums' THEN excluded.name ELSE name END,
                    metadata_json=excluded.metadata_json""",(*banks[ch],programs[ch],role,name,source,metadata))
        channels=sorted({r["channel"] for r in notes if r["track"]==ti})
        for ch in channels:
            selected=[r for r in notes if r["track"]==ti and r["channel"]==ch]; vel=[r["velocity"] for r in selected]; dur=[r["duration"] for r in selected]
            max_tick=max((e.tick for e in events),default=midi.division)
            segments=[]
            timeline=_program_segments(events,ch,max_tick)
            for segment_index,(start_tick,start_order,end_tick,end_order,msb,lsb,program) in enumerate(timeline):
                start_key=(start_tick,start_order);end_key=(end_tick,end_order)
                segment_notes=[row for row in selected if start_key<=(row["start"],row["on_event"].order)<end_key]
                if not segment_notes:continue
                role=_role(source,ch,program,label)
                multi_program=len({item[6] for item in timeline})>1
                name=(instrument_name if instrument_name and not multi_program else
                      "GM Drums" if role=="drums" else GM_NAMES[program])
                metadata=json.dumps({"auto_registered":True,"track_label":label,"segment_aware":True,
                    "start_tick":start_tick,"start_order":start_order,"end_tick":end_tick,"end_order":end_order},ensure_ascii=False)
                db.execute("""INSERT INTO instrument_profiles(bank_msb,bank_lsb,program,role,name,source,metadata_json)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(bank_msb,bank_lsb,program,role,source) DO UPDATE SET
                    name=CASE WHEN excluded.name NOT LIKE 'GM Program %' AND excluded.name!='GM Drums' THEN excluded.name ELSE name END,
                    metadata_json=excluded.metadata_json""",(msb,lsb,program,role,name,source,metadata))
                feature=_segment_feature(midi,ti,ch,start_key,end_key,segment_notes,role)
                if feature is None:continue
                db.execute("""INSERT INTO instrument_segments(file_id,track_index,channel,segment_index,start_tick,end_tick,
                    bank_msb,bank_lsb,program,role,name,note_count,feature_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (file_id,ti,ch,segment_index,start_tick,end_tick,msb,lsb,program,role,name,len(segment_notes),
                     json.dumps(track_feature_to_dict(feature),ensure_ascii=False,separators=(',',':'))))
                segments.append((len(segment_notes),msb,lsb,program,role))
            # Legacy aggregate tables remain one row per track/channel for
            # compatibility.  Their identity is the dominant note segment,
            # never the final Program Change state.
            dominant=max(segments,default=(len(selected),0,0,0,_role(source,ch,0,label)),key=lambda item:item[0])
            _,dominant_msb,dominant_lsb,dominant_program,role=dominant
            role_map[(ti,ch)]=role; cv_map[(ti,ch)]=cv
            db.execute("INSERT INTO track_stats(file_id,track_index,channel,role,bank_msb,bank_lsb,program,note_count,velocity_mean,velocity_std,duration_mean,duration_quarters,density_per_quarter) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(file_id,ti,ch,role,dominant_msb,dominant_lsb,dominant_program,len(selected),mean(vel),pstdev(vel),mean(dur),mean(dur)/midi.division,len(selected)/max(1,max_tick/midi.division)))
    for feature in extract_features(midi,role_map):
        db.execute("""INSERT OR REPLACE INTO performance_features(file_id,track_index,channel,role,section,cv,feature_json)
            VALUES(?,?,?,?,?,?,?)""",(file_id,feature.track,feature.channel,feature.role,section,
            cv_map.get((feature.track,feature.channel),0),json.dumps(track_feature_to_dict(feature),ensure_ascii=False,separators=(',',':'))))
    db.commit()

def rows(db,query,params=()): return [dict(r) for r in db.execute(query,params).fetchall()]