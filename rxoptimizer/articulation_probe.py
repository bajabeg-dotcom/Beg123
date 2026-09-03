"""Factory/Gold evidence-based single-articulation Pa800 hardware probes."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
from zipfile import ZipFile

from .midi import Event, MidiFile, encode_midi, note_rows, parse_midi, validate_midi


SCHEMA="""
CREATE TABLE probe_build(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE articulation_candidates(
 id INTEGER PRIMARY KEY,profile_name TEXT NOT NULL,oscillator INTEGER NOT NULL,
 articulation TEXT NOT NULL,bank_msb INTEGER NOT NULL,bank_lsb INTEGER NOT NULL,
 program INTEGER NOT NULL,velocity_min INTEGER,velocity_max INTEGER,key_min INTEGER,key_max INTEGER,
 evidence_status TEXT NOT NULL,UNIQUE(profile_name,oscillator));
CREATE TABLE articulation_evidence(
 candidate_id INTEGER PRIMARY KEY REFERENCES articulation_candidates(id),occurrence_count INTEGER NOT NULL,
 file_count INTEGER NOT NULL,factory_count INTEGER NOT NULL,gold_count INTEGER NOT NULL,
 best_source_class TEXT,best_member TEXT,best_sha256 TEXT,best_example_json TEXT,
 examples_json TEXT NOT NULL);
CREATE TABLE articulation_probe_files(
 id INTEGER PRIMARY KEY,candidate_id INTEGER NOT NULL REFERENCES articulation_candidates(id),
 output_name TEXT NOT NULL UNIQUE,output_sha256 TEXT NOT NULL,trigger_count INTEGER NOT NULL,
 context_note_count INTEGER NOT NULL,result_status TEXT NOT NULL DEFAULT 'pending_hardware');
CREATE TABLE articulation_probe_results(
 id INTEGER PRIMARY KEY,probe_file_id INTEGER NOT NULL REFERENCES articulation_probe_files(id),
 status TEXT NOT NULL CHECK(status IN('confirmed','partial','rejected')),
 heard_articulation TEXT NOT NULL DEFAULT '',comments TEXT NOT NULL DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def _atomic_json(path:Path,payload:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");temporary.replace(path)


def initialize_confirmation_files(manifest_path:Path,results_path:Path)->dict:
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if not results_path.exists():
        _atomic_json(results_path,{"schema_version":1,"policy":"physical_pa800_only","history":[],"latest":{}})
    csv_path=manifest_path.parent/"SINGLE_ARTICULATION_CONFIRMATION.csv"
    lines=["probe_file_id,profile,expected_articulation,source_member,status,heard_articulation,pa800_os,resources_version,comments"]
    for row in manifest.get("files",[]):
        values=[row["probe_file_id"],row["profile"],row["articulation"],row["source"]["member"],"pending_hardware","","","",""]
        lines.append(",".join('"'+str(value).replace('"','""')+'"' for value in values))
    csv_path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"results":str(results_path),"csv":str(csv_path),"files":len(manifest.get("files",[]))}


def _new(path:Path):
    temp=path.with_suffix(path.suffix+".tmp");temp.unlink(missing_ok=True);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(temp);db.row_factory=sqlite3.Row;db.executescript(SCHEMA);return db,temp


def _slug(value:str)->str:
    return re.sub(r"[^A-Za-z0-9._-]+","_",value).strip("._")[:90] or "probe"


def _candidates(factory_db:Path):
    db=sqlite3.connect(factory_db);db.row_factory=sqlite3.Row
    rows=[dict(row) for row in db.execute("""SELECT rz.*,vc.bank_msb,vc.bank_lsb,vc.program,vc.category
      FROM rx_zones rz JOIN pa800_voice_catalog vc ON vc.name=rz.profile_name
      WHERE lower(rz.articulation) NOT LIKE 'radni%'
      ORDER BY rz.profile_name,rz.oscillator""")]
    working=defaultdict(list)
    for row in db.execute("SELECT * FROM rx_zones WHERE lower(articulation) LIKE 'radni%'"):
        working[row["profile_name"]].append(dict(row))
    db.close();return rows,working


def _timelines(midi):
    result={}
    for ti,events in enumerate(midi.tracks):
        pending={channel:[0,0] for channel in range(16)};active={channel:(0,0,0) for channel in range(16)}
        timelines={channel:[((-1,-1),active[channel])] for channel in range(16)}
        for event in sorted(events,key=lambda item:(item.tick,item.order)):
            if event.channel is None:continue
            channel=int(event.channel)
            if event.kind=="control" and event.data1 in (0,32):pending[channel][0 if event.data1==0 else 1]=int(event.data2 or 0)
            elif event.kind=="program":
                active[channel]=(pending[channel][0],pending[channel][1],int(event.data1 or 0))
                timelines[channel].append(((int(event.tick),float(event.order)),active[channel]))
        for channel,items in timelines.items():result[(ti,channel)]=items
    return result


def _address(items,tick,order):
    keys=[item[0] for item in items];index=bisect_right(keys,(int(tick),float(order)))-1
    return items[max(0,index)][1]


def _inside(row,zone):
    return ((zone.get("key_min") is None or int(zone["key_min"])<=row["note"]<=int(zone.get("key_max",127))) and
        (zone.get("velocity_min") is None or int(zone["velocity_min"])<=row["velocity"]<=int(zone.get("velocity_max",127))))


def _source_meta(midi):
    tempo_raw=None
    for track in midi.tracks:
        for event in track:
            if event.kind=="meta" and event.data1==0x51 and len(event.raw)==3:tempo_raw=event.raw;break
        if tempo_raw:break
    return tempo_raw


def _probe_midi(candidate,example):
    division=int(example["division"]);channel=9 if candidate["category"]=="drums" else 0
    events=[Event(0,0,"meta",data1=3,raw=f"SINGLE ARTICULATION {candidate['profile_name']} {candidate['articulation']}".encode()),
        Event(0,1,"meta",data1=1,raw=b"UNVERIFIED FACTORY/GOLD OBSERVATION")]
    if example.get("tempo_raw"):events.append(Event(0,2,"meta",data1=0x51,raw=bytes.fromhex(example["tempo_raw"])))
    events += [Event(0,3,"control",channel,0,int(candidate["bank_msb"]),0xB0|channel),
        Event(0,4,"control",channel,32,int(candidate["bank_lsb"]),0xB0|channel),
        Event(0,5,"program",channel,int(candidate["program"]),None,0xC0|channel)]
    tick=division;context_count=0
    for label in ("previous","current","next"):
        row=example.get(label)
        if not row:continue
        duration=max(1,round(max(.125,min(1.5,float(row["duration_quarters"])))*division))
        events.append(Event(tick,10+len(events)*2,"note_on",channel,int(row["note"]),int(row["velocity"]),0x90|channel))
        events.append(Event(tick+duration,11+len(events)*2,"note_off",channel,int(row["note"]),0,0x80|channel))
        if label!="current":context_count+=1
        tick+=max(division,duration+max(1,division//8))
    return MidiFile(1,division,[events]),context_count


def build_single_articulation_probes(archive_path:Path,factory_db:Path,output_dir:Path,database_path:Path)->dict:
    candidates,working=_candidates(factory_db);by_address=defaultdict(list)
    for index,row in enumerate(candidates):row["candidate_index"]=index;by_address[(row["bank_msb"],row["bank_lsb"],row["program"])].append(row)
    stats={index:{"count":0,"files":set(),"factory":0,"gold":0,"examples":[]} for index in range(len(candidates))}
    with ZipFile(archive_path) as outer:
        for nested in outer.namelist():
            if not nested.lower().endswith(".zip"):continue
            source_class="factory_raw" if "factory" in nested.lower() else "gold_raw" if "gold" in nested.lower() else None
            if not source_class:continue
            with ZipFile(BytesIO(outer.read(nested))) as archive:
                for info in archive.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in (".mid",".midi"):continue
                    data=archive.read(info);midi=parse_midi(data);timelines=_timelines(midi);tempo=_source_meta(midi)
                    grouped=defaultdict(list)
                    for row in note_rows(midi):
                        row["address"]=_address(timelines[(row["track"],row["channel"])],row["start"],row["on_event"].order)
                        grouped[(row["track"],row["channel"])].append(row)
                    for group in grouped.values():
                        group.sort(key=lambda item:(item["start"],item["on_event"].order))
                        for position,row in enumerate(group):
                            matched=by_address.get(row["address"],())
                            for candidate in matched:
                                if not _inside(row,candidate):continue
                                state=stats[candidate["candidate_index"]];state["count"]+=1;state["files"].add(info.filename)
                                state["factory" if source_class=="factory_raw" else "gold"]+=1
                                normal=working.get(candidate["profile_name"],())
                                def context(offset):
                                    idx=position+offset
                                    if not 0<=idx<len(group):return None
                                    value=group[idx]
                                    if value["address"]!=row["address"] or not any(_inside(value,zone) for zone in normal):return None
                                    return {"note":value["note"],"velocity":value["velocity"],"duration_quarters":value["duration"]/midi.division}
                                example={"source_class":source_class,"member":info.filename,"sha256":sha256(data).hexdigest(),
                                    "division":midi.division,"tempo_raw":tempo.hex() if tempo else None,"track":row["track"],"channel":row["channel"],
                                    "tick":row["start"],"current":{"note":row["note"],"velocity":row["velocity"],"duration_quarters":row["duration"]/midi.division},
                                    "previous":context(-1),"next":context(1)}
                                score=(100 if source_class=="factory_raw" else 50)+10*int(example["previous"] is not None)+10*int(example["next"] is not None)
                                example["score"]=score;state["examples"].append(example);state["examples"]=sorted(state["examples"],key=lambda item:(-item["score"],item["member"],item["tick"]))[:20]
    db,temp=_new(database_path);output_dir.mkdir(parents=True,exist_ok=True);files=[]
    db.executemany("INSERT INTO probe_build VALUES(?,?)",(("source_policy","factory_gold_only"),("six_song_usage","forbidden"),("trigger_count_per_file","1")))
    for index,candidate in enumerate(candidates):
        cursor=db.execute("INSERT INTO articulation_candidates(profile_name,oscillator,articulation,bank_msb,bank_lsb,program,velocity_min,velocity_max,key_min,key_max,evidence_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (candidate["profile_name"],candidate["oscillator"],candidate["articulation"],candidate["bank_msb"],candidate["bank_lsb"],candidate["program"],candidate["velocity_min"],candidate["velocity_max"],candidate["key_min"],candidate["key_max"],"OBSERVED_UNVERIFIED_TRIGGER"))
        candidate_id=cursor.lastrowid;state=stats[index];best=state["examples"][0] if state["examples"] else None
        db.execute("INSERT INTO articulation_evidence VALUES(?,?,?,?,?,?,?,?,?,?)",(candidate_id,state["count"],len(state["files"]),state["factory"],state["gold"],
            best.get("source_class") if best else None,best.get("member") if best else None,best.get("sha256") if best else None,
            json.dumps(best,separators=(',',':')) if best else None,json.dumps(state["examples"],separators=(',',':'))))
        if not best:continue
        probe,context_count=_probe_midi(candidate,best);encoded=encode_midi(probe);validation=validate_midi(parse_midi(encoded))
        if not validation["valid"]:raise ValueError(f"Invalid articulation probe: {candidate['profile_name']} {candidate['articulation']}")
        digest=sha256(encoded).hexdigest();name=f"{_slug(candidate['profile_name'])}__{_slug(candidate['articulation'])}__{digest[:10]}.mid"
        target=output_dir/name;temporary=target.with_suffix(".mid.tmp");temporary.write_bytes(encoded);temporary.replace(target)
        probe_id=db.execute("INSERT INTO articulation_probe_files(candidate_id,output_name,output_sha256,trigger_count,context_note_count) VALUES(?,?,?,?,?)",
            (candidate_id,name,digest,1,context_count)).lastrowid
        files.append({"probe_file_id":probe_id,"output":name,"profile":candidate["profile_name"],"articulation":candidate["articulation"],
            "address":[candidate["bank_msb"],candidate["bank_lsb"],candidate["program"]],"trigger":best["current"],
            "context":{"previous":best["previous"],"next":best["next"]},"source":{key:best[key] for key in ("source_class","member","sha256","track","channel","tick")},
            "occurrence_count":state["count"],"file_count":len(state["files"]),"evidence_status":"OBSERVED_UNVERIFIED_TRIGGER"})
    manifest={"policy":"factory_gold_only_single_trigger","files":files,"candidates":len(candidates),"files_created":len(files)}
    (output_dir/"single-articulation-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (output_dir/"SINGLE_ARTICULATION_TEST_GUIDE.md").write_text("""# Korg Pa800 single-articulation test

Svaki MIDI aktivira jednu posebnu artikulaciju tačno jednom. Primjer je uzet iz Factory ili Gold MIDI člana navedenog u manifestu.

1. Učitaj jedan probe MIDI na Pa800.
2. Poslušaj normalnu prethodnu notu ako postoji.
3. Srednja/specijalna nota je jedini artikulacijski trigger koji se testira.
4. Poslušaj normalnu sljedeću notu ako postoji.
5. U GUI unesi Probe ID, `confirmed`, `partial` ili `rejected`, zatim napiši šta se stvarno čulo.
6. Obavezno upiši Pa800 OS i Musical Resources/SET verziju. Bez njih se potvrda odbija.

Naziv artikulacije u fajlu je `OBSERVED_UNVERIFIED_TRIGGER`, ne potvrđena činjenica. Šest Delay/Terca pjesama nije korišteno.
Rezultati se čuvaju atomski u `articulation-results.json`; `confirmed` dobija `pending_evidence_review`, nikad automatski produkcijski status.
""",encoding="utf-8")
    initialize_confirmation_files(output_dir/"single-articulation-manifest.json",output_dir/"articulation-results.json")
    db.commit();db.close();temp.replace(database_path)
    return {"candidates":len(candidates),"with_evidence":sum(bool(stats[i]["examples"]) for i in stats),"files_created":len(files),"output_dir":str(output_dir)}


def articulation_probe_status(path:Path)->dict:
    if not path.exists():return {"status":"not_built","files":0,"results":{}}
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    files=db.execute("SELECT COUNT(*) FROM articulation_probe_files").fetchone()[0]
    candidates=db.execute("SELECT COUNT(*) FROM articulation_candidates").fetchone()[0]
    results=dict(db.execute("SELECT result_status,COUNT(*) FROM articulation_probe_files GROUP BY result_status").fetchall())
    db.close();return {"status":"ready" if files else "no_evidence","candidates":candidates,"files":files,"results":results}


def record_articulation_probe_result(path:Path,probe_file_id:int,status:str,heard_articulation:str="",comments:str="")->dict:
    if status not in ("confirmed","partial","rejected"):raise ValueError("status mora biti confirmed, partial ili rejected")
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    row=db.execute("SELECT * FROM articulation_probe_files WHERE id=?",(int(probe_file_id),)).fetchone()
    if row is None:db.close();raise ValueError("Nepoznat articulation probe_file_id")
    db.execute("INSERT INTO articulation_probe_results(probe_file_id,status,heard_articulation,comments) VALUES(?,?,?,?)",
        (int(probe_file_id),status,heard_articulation,comments))
    db.execute("UPDATE articulation_probe_files SET result_status=? WHERE id=?",(status,int(probe_file_id)))
    db.commit();result=dict(db.execute("SELECT * FROM articulation_probe_files WHERE id=?",(int(probe_file_id),)).fetchone());db.close();return result


def file_articulation_probe_status(manifest_path:Path,results_path:Path)->dict:
    if not manifest_path.exists():return {"status":"not_built","files":0,"results":{}}
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    payload=json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {"latest":{},"history":[]}
    counts=defaultdict(int)
    for row in manifest.get("files",[]):counts[payload.get("latest",{}).get(str(row["probe_file_id"]),{}).get("status","pending_hardware")]+=1
    return {"status":"ready","files":len(manifest.get("files",[])),"results":dict(counts),
        "history_count":len(payload.get("history",[])),"storage":"atomic_json"}


def record_file_articulation_result(manifest_path:Path,results_path:Path,probe_file_id:int,status:str,
                                    heard_articulation:str,comments:str,pa800_os:str,
                                    resources_version:str,tested_at:str="",audio_chain:str="")->dict:
    if status not in ("confirmed","partial","rejected"):raise ValueError("status mora biti confirmed, partial ili rejected")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"));probe=next((row for row in manifest.get("files",[]) if int(row["probe_file_id"])==int(probe_file_id)),None)
    if probe is None:raise ValueError("Nepoznat articulation probe_file_id")
    if not pa800_os.strip() or not resources_version.strip():raise ValueError("Pa800 OS i Musical Resources verzija su obavezni")
    if status in ("confirmed","partial") and not heard_articulation.strip():raise ValueError("Upiši šta se stvarno čulo")
    payload=json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {"schema_version":1,"policy":"physical_pa800_only","history":[],"latest":{}}
    probe_path=manifest_path.parent/probe["output"]
    record={"probe_file_id":int(probe_file_id),"status":status,"expected_articulation":probe["articulation"],
        "heard_articulation":heard_articulation.strip(),"comments":comments.strip(),"pa800_os":pa800_os.strip(),
        "resources_version":resources_version.strip(),"tested_at":tested_at.strip() or datetime.now(timezone.utc).isoformat(),"audio_chain":audio_chain.strip(),
        "source":probe["source"],"probe_sha256":sha256(probe_path.read_bytes()).hexdigest() if probe_path.exists() else None,
        "promotion_status":"pending_evidence_review" if status=="confirmed" else "not_eligible"}
    payload.setdefault("history",[]).append(record);payload.setdefault("latest",{})[str(probe_file_id)]=record;_atomic_json(results_path,payload)
    return record


def build_articulation_promotion_queue(manifest_path:Path,results_path:Path,queue_path:Path)->dict:
    if not manifest_path.exists():raise ValueError("Nedostaje single-articulation manifest")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"));results=json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {"latest":{}}
    by_id={str(row["probe_file_id"]):row for row in manifest.get("files",[])};ready=[];contradictions=[]
    for probe_id,result in sorted(results.get("latest",{}).items(),key=lambda item:int(item[0])):
        probe=by_id.get(str(probe_id))
        if not probe:continue
        base={"queue_id":sha256(f"{probe_id}:{result.get('tested_at','')}:{result.get('status','')}".encode()).hexdigest()[:20],
            "probe_file_id":int(probe_id),"profile":probe["profile"],"expected_articulation":probe["articulation"],
            "heard_articulation":result.get("heard_articulation",""),"hardware":{"device":"Korg Pa800","os":result.get("pa800_os"),
            "resources_version":result.get("resources_version"),"audio_chain":result.get("audio_chain"),"tested_at":result.get("tested_at")},
            "factory_gold_observation":{"source":probe["source"],"trigger":probe["trigger"],"context":probe["context"],
            "occurrence_count":probe["occurrence_count"],"file_count":probe["file_count"]},"comments":result.get("comments","")}
        if result.get("status")=="confirmed":
            base.update({"review_status":"READY_FOR_EVIDENCE_REVIEW","proposed_evidence_status":"HARDWARE_OBSERVED",
                "automatic_runtime_promotion":False});ready.append(base)
        elif result.get("status")=="rejected":
            base.update({"review_status":"CONTRADICTION_REVIEW","proposed_evidence_status":"HARDWARE_CONTRADICTION",
                "automatic_runtime_promotion":False});contradictions.append(base)
    queue={"schema_version":1,"policy":"human_review_before_registry_or_runtime","ready":ready,
        "contradictions":contradictions,"ready_count":len(ready),"contradiction_count":len(contradictions)}
    _atomic_json(queue_path,queue);return queue


def articulation_promotion_queue_status(queue_path:Path)->dict:
    if not queue_path.exists():return {"status":"not_built","ready_count":0,"contradiction_count":0}
    queue=json.loads(queue_path.read_text(encoding="utf-8"));return {"status":"pending_review" if queue.get("ready_count") or queue.get("contradiction_count") else "empty",
        "ready_count":queue.get("ready_count",0),"contradiction_count":queue.get("contradiction_count",0),"automatic_runtime_promotion":False}