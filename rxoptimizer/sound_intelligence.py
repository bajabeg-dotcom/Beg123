"""Factory role/sound inference, MIDI headroom and regular rhythm-guitar repair."""

from __future__ import annotations

from collections import defaultdict
from io import BytesIO
import json
import math
from pathlib import Path
import sqlite3
from statistics import mean, median
from zipfile import ZipFile

from .features import extract_features, infer_role
from .instrument_identity import canonical_identity,identity_family
from .midi import Event, MidiFile, note_rows, parse_midi


SCHEMA = """
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE factory_sound_profiles(id INTEGER PRIMARY KEY,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,
 role TEXT,name TEXT,track_count INTEGER,note_count INTEGER,profile_json TEXT,
 UNIQUE(bank_msb,bank_lsb,program,role));
CREATE TABLE role_models(id INTEGER PRIMARY KEY,role TEXT UNIQUE,track_count INTEGER,note_count INTEGER,profile_json TEXT);
CREATE TABLE mix_profiles(id INTEGER PRIMARY KEY,corpus TEXT,role TEXT,track_count INTEGER,note_count INTEGER,
 velocity_mean REAL,velocity_p95 REAL,cc7_median REAL,cc7_p95 REAL,cc11_median REAL,cc11_p95 REAL,
 effective_level_p95 REAL,profile_json TEXT,UNIQUE(corpus,role));
CREATE TABLE application_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT);
"""

VECTOR_KEYS=("pitch_mean","pitch_std","density","duration","monophony","overlap","step","repeat","velocity_mean","velocity_std")
SCALES={"pitch_mean":12,"pitch_std":8,"density":4,"duration":1,"monophony":.5,"overlap":.5,
        "step":.5,"repeat":.5,"velocity_mean":20,"velocity_std":15}


def _vector(payload: dict, fallback: dict | None=None) -> dict:
    fallback=fallback or {}; scalar=lambda key,sub="mean":float((payload.get(key) or {}).get(sub,fallback.get(key,0)) or 0)
    return {"pitch_mean":scalar("pitch"),"pitch_std":scalar("pitch","std"),
        "density":float(payload.get("density_per_quarter",fallback.get("density",0)) or 0),
        "duration":scalar("duration_quarters"),"monophony":float(payload.get("monophony_ratio",fallback.get("monophony",0)) or 0),
        "overlap":float(payload.get("overlap_ratio",fallback.get("overlap",0)) or 0),
        "step":float(payload.get("step_ratio",fallback.get("step",0)) or 0),
        "repeat":float(payload.get("repeated_note_ratio",fallback.get("repeat",0)) or 0),
        "velocity_mean":scalar("velocity"),"velocity_std":scalar("velocity","std")}


def _weighted(rows: list[dict]) -> dict:
    total=sum(max(1,int(row["note_count"])) for row in rows)
    return {key:sum(row["vector"][key]*max(1,int(row["note_count"])) for row in rows)/max(1,total) for key in VECTOR_KEYS}


def _percentile(values: list[int], fraction: float) -> float:
    if not values:return 0.0
    selected=sorted(values);return float(selected[min(len(selected)-1,round((len(selected)-1)*fraction))])


def _new(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+".tmp");temp.unlink(missing_ok=True)
    db=sqlite3.connect(temp);db.executescript(SCHEMA);return db


def _finish(db: sqlite3.Connection,path: Path) -> None:
    temp=Path(db.execute("PRAGMA database_list").fetchone()[2]);db.commit();db.close();temp.replace(path)


def _mix_rows(archive_path: Path, factory_db: Path, gold_db: Path) -> list[dict]:
    role_maps={}
    for corpus,path in (("factory",factory_db),("gold",gold_db)):
        source=sqlite3.connect(path)
        role_maps[corpus]={(row[0],int(row[1]),int(row[2])):row[3] for row in source.execute(
            "SELECT mf.filename,pf.track_index,pf.channel,pf.role FROM performance_features pf JOIN midi_files mf ON mf.id=pf.file_id")}
        source.close()
    collected=defaultdict(lambda:{"tracks":0,"notes":0,"velocity":[],"cc7":[],"cc11":[],"effective":[]})
    with ZipFile(archive_path) as outer:
        for corpus in ("factory","gold"):
            nested=next(name for name in outer.namelist() if corpus in name.lower() and name.lower().endswith(".zip"))
            with ZipFile(BytesIO(outer.read(nested))) as archive:
                for info in archive.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"):continue
                    midi=parse_midi(archive.read(info));programs={}
                    for ti,events in enumerate(midi.tracks):
                        for event in sorted(events,key=lambda item:(item.tick,item.order)):
                            if event.kind=="program":programs[(ti,int(event.channel or 0))]=int(event.data1 or 0)
                    groups=defaultdict(list)
                    for row in note_rows(midi):groups[(row["track"],row["channel"])].append(row)
                    for (track,channel),notes in groups.items():
                        role=role_maps[corpus].get((info.filename,track,channel),infer_role(channel,programs.get((track,channel),0)))
                        item=collected[(corpus,role)];item["tracks"]+=1;item["notes"]+=len(notes)
                        item["velocity"].extend(row["velocity"] for row in notes)
                        cc7=[int(event.data2 or 0) for event in midi.tracks[track] if event.kind=="control" and int(event.channel or 0)==channel and event.data1==7]
                        cc11=[int(event.data2 or 0) for event in midi.tracks[track] if event.kind=="control" and int(event.channel or 0)==channel and event.data1==11]
                        item["cc7"].extend(cc7);item["cc11"].extend(cc11)
                        level7=median(cc7) if cc7 else 127;level11=median(cc11) if cc11 else 127
                        item["effective"].append(level7*level11/127)
    rows=[]
    for (corpus,role),item in collected.items():
        profile={"corpus":corpus,"role":role,"track_count":item["tracks"],"note_count":item["notes"],
            "velocity_mean":mean(item["velocity"]),"velocity_p95":_percentile(item["velocity"],.95),
            "cc7_median":median(item["cc7"]) if item["cc7"] else 127,"cc7_p95":_percentile(item["cc7"],.95) or 127,
            "cc11_median":median(item["cc11"]) if item["cc11"] else 127,"cc11_p95":_percentile(item["cc11"],.95) or 127,
            "effective_level_p95":_percentile([round(value) for value in item["effective"]],.95)}
        rows.append(profile)
    # Combined policy: Factory owns every safely measurable calibration target.
    # Gold contributes relative performance motion, never the absolute level.
    roles=sorted({row["role"] for row in rows});factory_rows={row["role"]:row for row in rows if row["corpus"]=="factory"};gold_rows={row["role"]:row for row in rows if row["corpus"]=="gold"}
    for role in roles:
        factory=factory_rows.get(role);gold=gold_rows.get(role)
        if not factory and not gold:continue
        # Styles have no dedicated solo/melodic channel. Their accompaniment
        # balance is the safest structural fallback, while Gold melodic is the
        # performance fallback for roles with too little Gold evidence.
        f=factory or factory_rows.get("accompaniment") or gold
        g=gold if gold and gold["track_count"]>=20 else gold_rows.get("melodic") or gold or factory
        cc7=min(116,round(f["cc7_median"]));cc11=round(f["cc11_median"])
        ceiling=127 if role in ("drums","percussion") else min(124,round(f["velocity_p95"] or 124))
        combined={"corpus":"combined","role":role,"track_count":int((factory or {}).get("track_count",0))+int((gold or {}).get("track_count",0)),
            "note_count":int((factory or {}).get("note_count",0))+int((gold or {}).get("note_count",0)),"velocity_mean":f["velocity_mean"],
            "velocity_p95":ceiling,"cc7_median":cc7,"cc7_p95":cc7,
            "cc11_median":cc11,"cc11_p95":min(124,round(f["cc11_p95"])),
            "effective_level_p95":min(112,round(cc7*min(124,f["cc11_p95"])/127)),
            "factory":f,"gold":g,"policy":"factory_first_calibration_gold_relative_expression"}
        rows.append(combined)
    return rows


def build_sound_intelligence_database(factory_path: Path,gold_path: Path,archive_path: Path,output_path: Path) -> dict:
    source=sqlite3.connect(factory_path);source.row_factory=sqlite3.Row;db=_new(output_path)
    db.execute("INSERT INTO build_info VALUES('kind','sound_intelligence')")
    db.execute("INSERT INTO build_info VALUES('training','Factory Styles roles/sounds + Factory/Gold mix; uploaded songs excluded')")
    raw=[]
    query="""SELECT ts.bank_msb,ts.bank_lsb,ts.program,ts.role,ts.note_count,pf.feature_json,
      COALESCE((SELECT p.name FROM instrument_profiles p WHERE p.source='factory' AND p.bank_msb=ts.bank_msb
      AND p.bank_lsb=ts.bank_lsb AND p.program=ts.program AND p.role=ts.role LIMIT 1),'Factory Sound') name
      FROM track_stats ts JOIN performance_features pf ON pf.file_id=ts.file_id AND pf.track_index=ts.track_index
      AND pf.channel=ts.channel WHERE ts.note_count>0"""
    for row in source.execute(query):
        raw.append({"bank_msb":int(row[0] or 0),"bank_lsb":int(row[1] or 0),"program":int(row[2] or 0),
            "role":row[3],"note_count":int(row[4]),"vector":_vector(json.loads(row[5])),"name":row[6]})
    groups=defaultdict(list)
    for row in raw:groups[(row["bank_msb"],row["bank_lsb"],row["program"],row["role"],row["name"])].append(row)
    profiles=[]
    for (msb,lsb,program,role,name),selected in groups.items():
        identity=canonical_identity(program,name,role);profile={"bank_msb":msb,"bank_lsb":lsb,"program":program,"role":role,"name":name,
            "identity":identity,"family":identity_family(identity,program),
            "track_count":len(selected),"note_count":sum(row["note_count"] for row in selected),"vector":_weighted(selected)}
        profiles.append(profile);db.execute("INSERT INTO factory_sound_profiles(bank_msb,bank_lsb,program,role,name,track_count,note_count,profile_json) VALUES(?,?,?,?,?,?,?,?)",
            (msb,lsb,program,role,name,profile["track_count"],profile["note_count"],json.dumps(profile,separators=(',',':'))))
    role_groups=defaultdict(list)
    for row in raw:role_groups[row["role"]].append(row)
    for role,selected in role_groups.items():
        payload={"role":role,"track_count":len(selected),"note_count":sum(row["note_count"] for row in selected),"vector":_weighted(selected)}
        db.execute("INSERT INTO role_models(role,track_count,note_count,profile_json) VALUES(?,?,?,?)",
            (role,payload["track_count"],payload["note_count"],json.dumps(payload,separators=(',',':'))))
    mix=_mix_rows(archive_path,factory_path,gold_path)
    for row in mix:db.execute("""INSERT INTO mix_profiles(corpus,role,track_count,note_count,velocity_mean,velocity_p95,
        cc7_median,cc7_p95,cc11_median,cc11_p95,effective_level_p95,profile_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row[key] for key in ("corpus","role","track_count","note_count","velocity_mean","velocity_p95","cc7_median","cc7_p95","cc11_median","cc11_p95","effective_level_p95"))+(json.dumps(row,separators=(',',':')),))
    rules=[("unknown_only","Factory Sound se automatski dodjeljuje samo adresi koja nije poznata Factory korpusu i nije standardni GM bank 0."),
      ("factory_structure","Factory Styles određuju ulogu, Sound i mix headroom."),
      ("gold_performance","Gold DNA daje samo relativne akcente, timing, gate i fraziranje unutar Factory velocity/volume kalibracije."),
      ("guitar_pitch_safe","Rhythm Guitar Repair ne mijenja akordne pitch note; samo redoslijed žica, timing, velocity i gate."),
      ("song_exclusion","Šest korisničkih song fajlova služe samo Delay/Terca DNA i nisu training izvor ove baze.")]
    db.executemany("INSERT INTO application_rules(rule_key,description) VALUES(?,?)",rules)
    source.close();_finish(db,output_path)
    return {"sound_profiles":len(profiles),"role_models":len(role_groups),"mix_profiles":len(mix),"rules":len(rules)}


def load_sound_intelligence(path: Path) -> dict:
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    result={"sounds":[json.loads(row[0]) for row in db.execute("SELECT profile_json FROM factory_sound_profiles")],
        "roles":[json.loads(row[0]) for row in db.execute("SELECT profile_json FROM role_models")],
        "mix":{row[0]:json.loads(row[1]) for row in db.execute("SELECT role,profile_json FROM mix_profiles WHERE corpus='combined'")}}
    db.close();return result


def _distance(left: dict,right: dict) -> float:
    return math.sqrt(sum(((float(left.get(key,0))-float(right.get(key,0)))/SCALES[key])**2 for key in VECTOR_KEYS))


def analyze_track_assignments(midi: MidiFile,intelligence: dict) -> dict[tuple[int,int],dict]:
    sounds=intelligence.get("sounds",[]);roles=intelligence.get("roles",[])
    for row in sounds:
        if not row.get("identity"):row["identity"]=canonical_identity(row.get("program",0),row.get("name",""),row.get("role",""))
        if not row.get("family"):row["family"]=identity_family(row["identity"],row.get("program",0))
    known=defaultdict(list)
    for row in sounds:known[(row["bank_msb"],row["bank_lsb"],row["program"])].append(row)
    banks=defaultdict(lambda:[0,0]);programs={}
    for ti,events in enumerate(midi.tracks):
        local={channel:[0,0] for channel in range(16)}
        for event in sorted(events,key=lambda item:(item.tick,item.order)):
            channel=int(event.channel or 0)
            if event.kind=="control" and event.data1 in (0,32):local[channel][0 if event.data1==0 else 1]=int(event.data2 or 0)
            elif event.kind=="program":banks[(ti,channel)]=list(local[channel]);programs[(ti,channel)]=int(event.data1 or 0)
    groups=defaultdict(list)
    for row in note_rows(midi):groups[(row["track"],row["channel"])].append(row)
    features={(feature.track,feature.channel):feature for feature in extract_features(midi)};result={}
    for key,notes in groups.items():
        feature=features[key];address=(*banks[key],programs.get(key,0));payload={"pitch":{"mean":feature.pitch.mean,"std":feature.pitch.std},
            "density_per_quarter":feature.density_per_quarter,"duration_quarters":{"mean":feature.duration_quarters.mean},
            "monophony_ratio":feature.monophony_ratio,"overlap_ratio":feature.overlap_ratio,"step_ratio":feature.step_ratio,
            "repeated_note_ratio":feature.repeated_note_ratio,"velocity":{"mean":feature.velocity.mean,"std":feature.velocity.std}}
        vector=_vector(payload);channel=key[1];command_ratio=sum(row["note"] in range(24,48) for row in notes)/max(1,len(notes))
        if channel==9:role,role_conf="drums",1.0
        elif channel==10:role,role_conf="percussion",.98
        elif channel==8 or (vector["pitch_mean"]<52 and vector["monophony"]>=.55):role,role_conf="bass",.92
        elif command_ratio>=.5:role,role_conf="guitar",.98
        elif vector["monophony"]>=.78 and vector["pitch_mean"]>=55:role,role_conf="melodic",.88
        else:
            ranked=sorted((_distance(vector,row["vector"]),row["role"]) for row in roles)
            role=ranked[0][1] if ranked else infer_role(channel,programs.get(key,0));second=ranked[1][0] if len(ranked)>1 else ranked[0][0]+1
            role_conf=max(.55,min(.9,.62+(second-ranked[0][0])/max(1,second)*.35)) if ranked else .55
        exact_rows=known.get(address,[]);exact=min(exact_rows,key=lambda row:_distance(vector,row["vector"])) if exact_rows else None
        unknown=exact is None and address[0]!=0
        allowed=("accompaniment","guitar") if role=="melodic" else (role,)
        candidates=[row for row in sounds if row["role"] in allowed and row["track_count"]>=2]
        ranked=sorted((_distance(vector,row["vector"]),-row["track_count"],row) for row in candidates)
        inferred_identity=(exact or (ranked[0][2] if ranked else {})).get("identity") or canonical_identity(address[2],"",role)
        identity_candidates=[row for row in candidates if row.get("identity")==inferred_identity]
        ranked=sorted((_distance(vector,row["vector"]),-row["track_count"],row) for row in identity_candidates)
        recommendation=ranked[0][2] if ranked else exact
        sound_conf=.0
        if recommendation and ranked:
            second=ranked[1][0] if len(ranked)>1 else ranked[0][0]+1
            sound_conf=max(.55,min(.95,.65+(second-ranked[0][0])/max(1,second)*.3))
        elif exact:sound_conf=1.0
        resolved_role=role if channel in (8,9,10) else exact["role"] if exact else role
        if channel==9:inferred_identity="standard_kit"
        elif channel==10:inferred_identity="percussion_kit"
        result[key]={"track":key[0],"channel":key[1],"source":{"bank_msb":address[0],"bank_lsb":address[1],"program":address[2]},
            "role":resolved_role,"role_confidence":1.0 if exact else role_conf,"known_factory":bool(exact),
            "source_identity":inferred_identity,"source_family":identity_family(inferred_identity,address[2]),
            "unknown_user_sound":unknown,"recommendation":recommendation,"sound_confidence":sound_conf,"vector":vector}
    return result


def soft_limit_velocity(value: int,role: str,mix: dict) -> int:
    model=mix.get(role) or mix.get("melodic") or {};ceiling=int(model.get("velocity_p95",124) or 124)
    if role in ("drums","percussion") or value<=ceiling:return value
    return min(127,ceiling+round((value-ceiling)*.25))


def factory_calibrated_velocity(original: int,gold_proposed: int,role: str,mix: dict,strength: float=.85) -> int:
    """Map Gold's relative accent shape into the Factory mean/P95 envelope."""
    model=mix.get(role) or mix.get("melodic") or {};factory=model.get("factory") or model;gold=model.get("gold") or model
    factory_mean=float(factory.get("velocity_mean",model.get("velocity_mean",original)) or original)
    factory_p95=float(factory.get("velocity_p95",model.get("velocity_p95",124)) or 124)
    gold_mean=float(gold.get("velocity_mean",gold_proposed) or gold_proposed)
    gold_p95=float(gold.get("velocity_p95",127) or 127)
    factory_span=max(8.0,factory_p95-factory_mean);gold_span=max(8.0,gold_p95-gold_mean)
    shaped=factory_mean+(gold_proposed-gold_mean)*(factory_span/gold_span)
    amount=max(0,min(1,float(strength)));value=round(original*(1-amount)+shaped*amount)
    return max(1,min(127,value))


def apply_midi_headroom(midi: MidiFile,role_for,mix: dict,strength: float=.75) -> dict:
    strength=max(0,min(1,float(strength)));groups={(row["track"],row["channel"]) for row in note_rows(midi)}
    track_levels={}
    for track,channel in groups:
        events=midi.tracks[track]
        cc7=[int(event.data2 or 0) for event in events if event.kind=="control" and int(event.channel or 0)==channel and event.data1==7]
        cc11=[int(event.data2 or 0) for event in events if event.kind=="control" and int(event.channel or 0)==channel and event.data1==11]
        track_levels[(track,channel)]={"cc7":round(median(cc7)) if cc7 else 127,"cc11":round(median(cc11)) if cc11 else 127}
    source_center7=round(median([value["cc7"] for value in track_levels.values()])) if track_levels else 127
    source_center11=round(median([value["cc11"] for value in track_levels.values()])) if track_levels else 127
    changed=added=limited=0;details=[]
    for track,channel in sorted(groups):
        role=role_for(track,channel,0);model=mix.get(role) or mix.get("melodic")
        if not model:continue
        events=midi.tracks[track];cc7=[event for event in events if event.kind=="control" and int(event.channel or 0)==channel and event.data1==7]
        cc11=[event for event in events if event.kind=="control" and int(event.channel or 0)==channel and event.data1==11]
        target7=int(model.get("cc7_median",110));target11=int(model.get("cc11_median",105));effective=float(model.get("effective_level_p95",108));current7=track_levels[(track,channel)]["cc7"]
        calibrated_center7=max(0,min(127,target7+(current7-source_center7)))
        new7=round(current7*(1-strength)+calibrated_center7*strength)
        if cc7:
            center=current7
            for event in cc7:
                original=int(event.data2 or 0);desired=max(0,min(127,calibrated_center7+(original-center)))
                event.data2=round(original*(1-strength)+desired*strength);changed+=event.data2!=original
        else:
            events.append(Event(0,-.08,"control",channel,7,new7,0xB0|channel));added+=1
        max11=max(1,min(127,math.floor(effective*127/max(1,new7))))
        current11=track_levels[(track,channel)]["cc11"];calibrated_center11=max(0,min(max11,target11+(current11-source_center11)))
        if cc11:
            center=round(median([int(event.data2 or 0) for event in cc11]))
            for event in cc11:
                original=int(event.data2 or 0);desired=max(0,min(max11,calibrated_center11+(original-center)))
                event.data2=round(original*(1-strength)+desired*strength);limited+=event.data2!=original
        else:
            events.append(Event(0,-.07,"control",channel,11,calibrated_center11,0xB0|channel));added+=1
        details.append({"track":track,"channel":channel,"role":role,"cc7":new7,"cc11_center":calibrated_center11,"cc11_ceiling":max11})
    return {"controller_events_changed":changed+limited,"controller_events_added":added,"tracks":details}


def repair_regular_rhythm_guitars(midi: MidiFile,role_for,strength: float=.65) -> dict:
    strength=max(0,min(1,float(strength)));groups=defaultdict(list)
    for row in note_rows(midi):groups[(row["track"],row["channel"])].append(row)
    repaired=[];notes_changed=gate_changed=0
    for (track,channel),rows in groups.items():
        if role_for(track,channel,rows[0]["start"])!="guitar":continue
        if sum(24<=row["note"]<=47 for row in rows)/max(1,len(rows))>=.5:continue
        rows.sort(key=lambda row:(row["start"],row["note"]));tolerance=max(1,round(.04*midi.division));clusters=[];current=[]
        for row in rows:
            if current and row["start"]-current[0]["start"]>tolerance:
                if len({item["note"] for item in current})>=3:clusters.append(current)
                current=[]
            current.append(row)
        if current and len({item["note"] for item in current})>=3:clusters.append(current)
        chord_notes=sum(len(cluster) for cluster in clusters)
        if len(clusters)<8 or chord_notes/max(1,len(rows))<.35:continue
        robotic_ratio=sum(max(item["start"] for item in cluster)-min(item["start"] for item in cluster)<=1 for cluster in clusters)/len(clusters)
        # A guitar that already contains a deliberate string spread is not
        # "repaired" again.  This prevents double-humanizing good performances.
        if robotic_ratio<.55:continue
        for index,cluster in enumerate(clusters):
            direction="down" if index%2==0 else "up";ordered=sorted(cluster,key=lambda row:row["note"],reverse=direction=="up")
            base=min(row["start"] for row in cluster);spread=max(1,round(.012*midi.division*strength))
            average=mean(row["velocity"] for row in cluster)
            for string,row in enumerate(ordered):
                shift=string*spread;new_start=base+shift;duration=row["off_event"].tick-row["on_event"].tick
                if new_start!=row["on_event"].tick:
                    row["on_event"].tick=new_start;row["off_event"].tick=new_start+duration;notes_changed+=1
                target=max(1,min(127,round(average+3-string*1.25)))
                velocity=round(row["velocity"]*(1-strength*.35)+target*(strength*.35))
                if velocity!=row["velocity"]:row["on_event"].data2=velocity;notes_changed+=1
            if index+1<len(clusters):
                next_start=min(row["start"] for row in clusters[index+1])
                for row in cluster:
                    maximum=max(row["on_event"].tick+1,next_start-max(1,round(.025*midi.division)))
                    if row["off_event"].tick>maximum:row["off_event"].tick=maximum;gate_changed+=1
        repaired.append({"track":track,"channel":channel,"chords":len(clusters),"chord_notes":chord_notes,
            "robotic_chord_ratio_before":robotic_ratio,"repair_reason":"simultaneous chord attacks"})
    return {"tracks":repaired,"notes_changed":notes_changed,"gate_changed":gate_changed,
        "pitch_notes_changed":0,"method":"Factory chord structure + Gold-shaped performance; alternating physical string order"}