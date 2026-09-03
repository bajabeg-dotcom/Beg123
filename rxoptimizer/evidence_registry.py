"""Field-level RX/DNC evidence registry.

The registry is derived and replaceable.  It never alters source corpora and
never treats a derived database as proof of its own claims.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE registry_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE evidence_sources(
 id INTEGER PRIMARY KEY,source_key TEXT NOT NULL UNIQUE,parent_id INTEGER REFERENCES evidence_sources(id),
 source_type TEXT NOT NULL,classification TEXT NOT NULL,authority TEXT NOT NULL,evidence_status TEXT NOT NULL,
 path TEXT,member_path TEXT,sha256 TEXT,size_bytes INTEGER,immutable INTEGER NOT NULL CHECK(immutable IN(0,1)),
 version TEXT,os_min TEXT,os_max TEXT,metadata_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE evidence_locators(
 id INTEGER PRIMARY KEY,source_id INTEGER NOT NULL REFERENCES evidence_sources(id),locator_type TEXT NOT NULL,
 page INTEGER,section TEXT,table_name TEXT,member_path TEXT,track_index INTEGER,channel INTEGER,
 tick_start INTEGER,tick_end INTEGER,query_hash TEXT,locator_json TEXT NOT NULL DEFAULT '{}',
 CHECK(tick_start IS NULL OR tick_end IS NULL OR tick_end>=tick_start));
CREATE TABLE subjects(
 id INTEGER PRIMARY KEY,subject_key TEXT NOT NULL UNIQUE,subject_type TEXT NOT NULL,canonical_name TEXT NOT NULL,
 instrument_family TEXT,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,metadata_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE claims(
 id INTEGER PRIMARY KEY,claim_key TEXT NOT NULL UNIQUE,subject_id INTEGER NOT NULL REFERENCES subjects(id),
 field_name TEXT NOT NULL,value_json TEXT NOT NULL,value_type TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN('CONFIRMED','HIGH_CONFIDENCE','MEDIUM_CONFIDENCE','LOW_CONFIDENCE',
 'OBSERVED','INFERRED','UNVERIFIED','UNKNOWN','CONFLICTED')),
 confidence REAL CHECK(confidence IS NULL OR(confidence>=0 AND confidence<=1)),assertion_kind TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),created_by TEXT NOT NULL,extractor_version TEXT,
 fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE claim_evidence(
 claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
 locator_id INTEGER NOT NULL REFERENCES evidence_locators(id) ON DELETE CASCADE,
 relation TEXT NOT NULL CHECK(relation IN('SUPPORTS','CONTRADICTS','DERIVES_FROM')),
 weight REAL CHECK(weight IS NULL OR(weight>=0 AND weight<=1)),note TEXT,
 PRIMARY KEY(claim_id,locator_id,relation));
CREATE TABLE observations(
 id INTEGER PRIMARY KEY,observation_key TEXT NOT NULL UNIQUE,subject_id INTEGER REFERENCES subjects(id),
 locator_id INTEGER NOT NULL REFERENCES evidence_locators(id),metric_key TEXT NOT NULL,value_json TEXT NOT NULL,
 unit TEXT,sample_count INTEGER,extractor_name TEXT NOT NULL,extractor_version TEXT NOT NULL,
 parameters_json TEXT NOT NULL DEFAULT '{}',fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE conflicts(
 id INTEGER PRIMARY KEY,subject_id INTEGER NOT NULL REFERENCES subjects(id),field_name TEXT NOT NULL,
 claim_a_id INTEGER NOT NULL REFERENCES claims(id),claim_b_id INTEGER NOT NULL REFERENCES claims(id),
 status TEXT NOT NULL CHECK(status IN('OPEN','RESOLVED','WONT_FIX')),resolution_claim_id INTEGER REFERENCES claims(id),
 notes TEXT,UNIQUE(claim_a_id,claim_b_id));
CREATE TABLE verification_tasks(
 id INTEGER PRIMARY KEY,subject_id INTEGER REFERENCES subjects(id),claim_id INTEGER REFERENCES claims(id),
 task_type TEXT NOT NULL,priority TEXT NOT NULL CHECK(priority IN('P0','P1','P2')),
 required_source_type TEXT NOT NULL,instructions TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN('OPEN','IN_PROGRESS','DONE','BLOCKED')),
 result_locator_id INTEGER REFERENCES evidence_locators(id));
"""


def _json(value) -> str:
    return json.dumps(value,ensure_ascii=False,separators=(",",":"))


def _fingerprint(*values) -> str:
    return sha256(_json(values).encode()).hexdigest()


def _source(db,key,source_type,classification,authority,status,path=None,member=None,digest=None,size=None,
            immutable=True,parent=None,metadata=None) -> int:
    parent_id=db.execute("SELECT id FROM evidence_sources WHERE source_key=?",(parent,)).fetchone()[0] if parent else None
    db.execute("""INSERT INTO evidence_sources(source_key,parent_id,source_type,classification,authority,evidence_status,
      path,member_path,sha256,size_bytes,immutable,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
      (key,parent_id,source_type,classification,authority,status,path,member,digest,size,int(immutable),_json(metadata or {})))
    return db.execute("SELECT id FROM evidence_sources WHERE source_key=?",(key,)).fetchone()[0]


def _locator(db,source_id,locator_type,**fields) -> int:
    columns=("page","section","table_name","member_path","track_index","channel","tick_start","tick_end","query_hash")
    db.execute(f"INSERT INTO evidence_locators(source_id,locator_type,{','.join(columns)},locator_json) VALUES(?,?{',?'*len(columns)},?)",
        (source_id,locator_type,*[fields.get(column) for column in columns],_json(fields.get("metadata",{}))))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _subject(db,key,kind,name,family=None,msb=None,lsb=None,program=None,metadata=None) -> int:
    db.execute("INSERT OR IGNORE INTO subjects(subject_key,subject_type,canonical_name,instrument_family,bank_msb,bank_lsb,program,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
        (key,kind,name,family,msb,lsb,program,_json(metadata or {})))
    return db.execute("SELECT id FROM subjects WHERE subject_key=?",(key,)).fetchone()[0]


def _claim(db,key,subject,field,value,status,kind,locator=None,confidence=None,created_by="registry_builder") -> int:
    value_json=_json(value);fingerprint=_fingerprint(subject,field,value_json,status,kind)
    db.execute("""INSERT INTO claims(claim_key,subject_id,field_name,value_json,value_type,status,confidence,
      assertion_kind,created_by,extractor_version,fingerprint) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
      (key,subject,field,value_json,type(value).__name__,status,confidence,kind,created_by,"1",fingerprint))
    claim_id=db.execute("SELECT last_insert_rowid()").fetchone()[0]
    if locator is not None:
        db.execute("INSERT INTO claim_evidence(claim_id,locator_id,relation,weight,note) VALUES(?,?,?,?,?)",
            (claim_id,locator,"DERIVES_FROM",confidence,"Migrated without confidence promotion"))
    return claim_id


def build_evidence_registry(inventory_path: Path,factory_path: Path,output_path: Path) -> dict:
    inventory=json.loads(inventory_path.read_text(encoding="utf-8"))
    temp=output_path.with_suffix(output_path.suffix+".tmp");temp.unlink(missing_ok=True);output_path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(temp);db.row_factory=sqlite3.Row;db.executescript(SCHEMA)
    inventory_hash=sha256(inventory_path.read_bytes()).hexdigest()
    db.executemany("INSERT INTO registry_meta VALUES(?,?)",(("schema_version","1"),("builder_version","1"),("inventory_sha256",inventory_hash)))

    source_ids={}
    for row in inventory.get("source_records",[]):
        key=row["path"]
        source_ids[key]=_source(db,key,row["classification"],row["classification"],row["authority"],row["evidence_status"],
            path=row["path"],digest=row["sha256"],size=row["size"],immutable=row["immutable"])
    container=next((row["path"] for row in inventory.get("source_records",[]) if row["classification"]=="source_container"),None)
    for archive in inventory.get("nested_archives",[]):
        key=archive["path"]
        source_ids[key]=_source(db,key,"nested_archive",archive["classification"],archive["authority"],archive["evidence_status"],
            path=key,digest=archive["sha256"],size=archive["size"],parent=container)
        for member in archive["members"]:
            member_key=f"{key}::{member['path']}"
            member_id=_source(db,member_key,"midi_member",archive["classification"],archive["authority"],member["evidence_status"],
                path=key,member=member["path"],digest=member["sha256"],size=member["size"],parent=key,
                metadata={"crc32":member["crc32"]})
            _locator(db,member_id,"MIDI_MEMBER",member_path=member["path"])

    factory=sqlite3.connect(factory_path);factory.row_factory=sqlite3.Row
    manual_key=next((key for key in source_ids if key.endswith("reference/pa800/README.md")),None)
    manual_locator=_locator(db,source_ids[manual_key],"INDEX_ONLY") if manual_key else None
    oscillator_key=next((key for key in source_ids if key.endswith("prism-uploads/Oscilatori.txt")),None)
    oscillator_locator=_locator(db,source_ids[oscillator_key],"USER_NOTE") if oscillator_key else None

    for row in factory.execute("SELECT * FROM pa800_voice_catalog ORDER BY id"):
        key=f"sound:{row['bank_msb']}:{row['bank_lsb']}:{row['program']}:{row['name']}"
        subject=_subject(db,key,"RX_SOUND",row["name"],row["category"],row["bank_msb"],row["bank_lsb"],row["program"])
        for field in ("name","category","bank_msb","bank_lsb","program","is_rx"):
            _claim(db,f"{key}:{field}",subject,field,row[field],"UNVERIFIED","CATALOG_ENTRY",manual_locator)
        unknown=_claim(db,f"{key}:trigger_type",subject,"trigger_type",None,"UNKNOWN","MISSING_FIELD")
        db.execute("INSERT INTO verification_tasks(subject_id,claim_id,task_type,priority,required_source_type,instructions,status) VALUES(?,?,?,?,?,?,?)",
            (subject,unknown,"RX_TRIGGER_VERIFY","P0","LOCAL_PRIMARY_MANUAL_OR_HARDWARE","Utvrditi trigger i precizan locator bez inferencije","OPEN"))

    switch_claims={}
    for row in factory.execute("SELECT * FROM rx_zones ORDER BY profile_name,oscillator"):
        key=f"zone:{row['profile_name']}:{row['oscillator']}"
        subject=_subject(db,key,"RX_ARTICULATION_ZONE",f"{row['profile_name']} oscillator {row['oscillator']}",row["profile_name"])
        for field in ("articulation","velocity_min","velocity_max","key_min","key_max","switch_value","notes"):
            if row[field] is None:continue
            status="INFERRED" if row["profile_name"] in ("SlapFing Bass RX","SlapPick Bass RX") and field=="switch_value" else "UNVERIFIED"
            claim=_claim(db,f"{key}:{field}",subject,field,row[field],status,"USER_OBSERVATION",oscillator_locator)
            if field=="switch_value":switch_claims[(row["profile_name"],row["oscillator"])]=(subject,claim)
        db.execute("INSERT INTO verification_tasks(subject_id,task_type,priority,required_source_type,instructions,status) VALUES(?,?,?,?,?,?)",
            (subject,"ZONE_VERIFY","P0","PCG_SOUND_EDIT_OR_HARDWARE","Potvrditi velocity/key/switch zonu na konkretnom Pa800 Soundu","OPEN"))

    for name in ("SlapFing Bass RX","SlapPick Bass RX"):
        pair=switch_claims.get((name,2))
        if not pair:continue
        subject,claim_87=pair
        claim_94=_claim(db,f"zone:{name}:2:switch_value:historical94",subject,"switch_value",94,"LOW_CONFIDENCE",
            "HISTORICAL_USER_OBSERVATION",oscillator_locator,confidence=.2)
        db.execute("UPDATE claims SET status='CONFLICTED' WHERE id IN(?,?)",(claim_87,claim_94))
        db.execute("INSERT INTO conflicts(subject_id,field_name,claim_a_id,claim_b_id,status,notes) VALUES(?,?,?,?,?,?)",
            (subject,"switch_value",claim_87,claim_94,"OPEN","87 je statistički podržana radna korekcija; 94 je raniji zapis. Potreban PCG/Sound Edit/hardware dokaz."))

    factory.close()
    missing_evidence=db.execute("""SELECT COUNT(*) FROM claims c WHERE c.active=1 AND c.status!='UNKNOWN'
      AND NOT EXISTS(SELECT 1 FROM claim_evidence ce WHERE ce.claim_id=c.id)""").fetchone()[0]
    unknown_without_task=db.execute("""SELECT COUNT(*) FROM claims c WHERE c.status='UNKNOWN'
      AND NOT EXISTS(SELECT 1 FROM verification_tasks v WHERE v.claim_id=c.id AND v.status='OPEN')""").fetchone()[0]
    if missing_evidence or unknown_without_task:
        db.close();temp.unlink(missing_ok=True)
        raise ValueError(f"Evidence audit failed: missing_evidence={missing_evidence}, unknown_without_task={unknown_without_task}")
    integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys=db.execute("PRAGMA foreign_key_check").fetchall()
    counts={table:db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in
        ("evidence_sources","evidence_locators","subjects","claims","claim_evidence","observations","conflicts","verification_tasks")}
    db.commit();db.close()
    if integrity!="ok" or foreign_keys:
        temp.unlink(missing_ok=True);raise ValueError("Evidence registry integrity failure")
    temp.replace(output_path)
    return {**counts,"integrity":integrity,"foreign_key_errors":len(foreign_keys),"inventory_sha256":inventory_hash}


def load_runtime_evidence_policy(path: Path) -> dict:
    """Return a fail-closed policy snapshot for runtime RX decisions."""
    empty={"policy_version":"1","mode":"strict","fail_closed":True,"fail_closed_reason":"missing_registry",
        "registry_sha256":None,"inventory_sha256":None,"registry_integrity":"missing","zones":{},"sounds":{},
        "rules_admitted_transform":0,"rules_admitted_generation":0,"blocked_conflicts":0,
        "blocked_by_status":{},"blocked_by_authority":0,"unknown_claims":0}
    if not path.exists():return empty
    try:
        db=sqlite3.connect(path);db.row_factory=sqlite3.Row
        integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok":
            db.close();return {**empty,"fail_closed_reason":"registry_integrity","registry_integrity":integrity}
        result={**empty,"fail_closed":False,"fail_closed_reason":None,"registry_integrity":integrity,
            "registry_sha256":sha256(path.read_bytes()).hexdigest()}
        meta=dict(db.execute("SELECT key,value FROM registry_meta").fetchall());result["inventory_sha256"]=meta.get("inventory_sha256")
        conflict_subjects={row[0] for row in db.execute("SELECT subject_id FROM conflicts WHERE status IN('OPEN','WONT_FIX')")}
        allowed_primary={"hardware_verified","local_primary_manual","factory_raw"}
        blocked=Counter();zones={};sounds={}
        for subject in db.execute("SELECT * FROM subjects WHERE subject_type IN('RX_ARTICULATION_ZONE','RX_SOUND')"):
            claims=list(db.execute("SELECT * FROM claims WHERE subject_id=? AND active=1",(subject["id"],)))
            statuses={row["field_name"]:row["status"] for row in claims}
            authorities=set()
            for claim in claims:
                authorities.update(row[0] for row in db.execute("""SELECT es.classification FROM claim_evidence ce
                    JOIN evidence_locators el ON el.id=ce.locator_id JOIN evidence_sources es ON es.id=el.source_id
                    WHERE ce.claim_id=?""",(claim["id"],)))
            conflicted=subject["id"] in conflict_subjects or "CONFLICTED" in statuses.values()
            transform_status=bool(claims) and all(status in ("CONFIRMED","HIGH_CONFIDENCE") for status in statuses.values())
            generation_status=bool(claims) and all(status=="CONFIRMED" for status in statuses.values())
            authority_ok=bool(authorities&allowed_primary)
            transform_allowed=transform_status and authority_ok and not conflicted
            generation_allowed=generation_status and authority_ok and not conflicted
            if conflicted:result["blocked_conflicts"]+=1
            for status in statuses.values():
                if status not in ("CONFIRMED","HIGH_CONFIDENCE"):blocked[status]+=1
            if (transform_status or generation_status) and not authority_ok:result["blocked_by_authority"]+=1
            result["unknown_claims"]+=sum(status=="UNKNOWN" for status in statuses.values())
            payload={"subject_key":subject["subject_key"],"statuses":statuses,"authorities":sorted(authorities),
                "transform_existing_allowed":transform_allowed,"generate_articulation_allowed":generation_allowed,
                "safety_only":not transform_allowed,"conflicted":conflicted}
            if subject["subject_type"]=="RX_ARTICULATION_ZONE":zones[subject["subject_key"]]=payload
            else:sounds[subject["subject_key"]]=payload
            result["rules_admitted_transform"]+=int(transform_allowed)
            result["rules_admitted_generation"]+=int(generation_allowed)
        result["zones"]=zones;result["sounds"]=sounds;result["blocked_by_status"]=dict(blocked)
        db.close();return result
    except (sqlite3.Error,OSError,ValueError) as error:
        return {**empty,"fail_closed_reason":f"registry_error:{type(error).__name__}","registry_integrity":"error"}
