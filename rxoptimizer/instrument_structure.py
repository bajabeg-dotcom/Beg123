"""Per-instrument Factory Style structure and Gold/Balkan correction DNA."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

from .features import GoldDNAModel,track_feature_from_dict
from .instrument_identity import (
    GM_PROGRAM_NAMES,canonical_identity,gm_family,gm_identity,identities_compatible,identity_family,
)


SCHEMA="""
CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE gm_instrument_catalog(program INTEGER PRIMARY KEY,name TEXT,family TEXT,identity TEXT,role_hint TEXT);
CREATE TABLE factory_instrument_structures(id INTEGER PRIMARY KEY,bank_msb INTEGER,bank_lsb INTEGER,program INTEGER,
 identity TEXT,family TEXT,role TEXT,name TEXT,section TEXT,cv INTEGER,meter_num INTEGER,meter_den INTEGER,
 track_count INTEGER,note_count INTEGER,model_hash TEXT,structure_json TEXT,
 UNIQUE(bank_msb,bank_lsb,program,role,section,cv,meter_num,meter_den));
CREATE TABLE factory_identity_models(id INTEGER PRIMARY KEY,identity TEXT,role TEXT,meter_num INTEGER,meter_den INTEGER,
 track_count INTEGER,note_count INTEGER,model_hash TEXT,model_json TEXT,UNIQUE(identity,role,meter_num,meter_den));
CREATE TABLE gold_instrument_corrections(id INTEGER PRIMARY KEY,identity TEXT,family TEXT,role TEXT,tempo_bucket INTEGER,
 meter_num INTEGER,meter_den INTEGER,track_count INTEGER,note_count INTEGER,model_hash TEXT,model_json TEXT,
 UNIQUE(identity,role,tempo_bucket,meter_num,meter_den));
CREATE TABLE identity_conversion_rules(id INTEGER PRIMARY KEY,source_program INTEGER,source_identity TEXT,target_name TEXT,
 target_bank_msb INTEGER,target_bank_lsb INTEGER,target_program INTEGER,target_identity TEXT,mode TEXT,allowed INTEGER,reason TEXT,
 UNIQUE(source_program,source_identity,target_bank_msb,target_bank_lsb,target_program,mode));
CREATE TABLE application_rules(id INTEGER PRIMARY KEY,rule_key TEXT UNIQUE,description TEXT);
"""


def _new(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+".tmp");temp.unlink(missing_ok=True)
    db=sqlite3.connect(temp);db.executescript(SCHEMA);return db


def _finish(db: sqlite3.Connection,path: Path) -> None:
    temp=Path(db.execute("pragma database_list").fetchone()[2]);db.commit();db.close();temp.replace(path)


def _name_query(source: str, alias: str="ts") -> str:
    return f"""COALESCE((SELECT p.name FROM instrument_profiles p WHERE p.source='{source}'
      AND p.bank_msb={alias}.bank_msb AND p.bank_lsb={alias}.bank_lsb AND p.program={alias}.program
      AND p.role={alias}.role LIMIT 1),'')"""


def build_instrument_structure_database(factory_path: Path,gold_path: Path,output_path: Path) -> dict:
    db=_new(output_path);db.execute("INSERT INTO build_info VALUES('kind','instrument_structure')")
    db.execute("INSERT INTO build_info VALUES('policy','Factory full structure; Gold Balkan correction; strict instrument identity lock')")
    for program,name in enumerate(GM_PROGRAM_NAMES):
        family=gm_family(program);role="bass" if family=="bass" else "guitar" if family=="guitar" else "melodic"
        db.execute("INSERT INTO gm_instrument_catalog VALUES(?,?,?,?,?)",(program,name,family,canonical_identity(program,name,role),role))

    factory=sqlite3.connect(factory_path);factory.row_factory=sqlite3.Row
    rows=factory.execute(f"""SELECT s.bank_msb,s.bank_lsb,s.program,s.role,
      COALESCE(NULLIF(s.name,''),{_name_query('factory','s')}) name,mf.section,COALESCE(pf.cv,0),
      mf.meter_num,mf.meter_den,s.note_count,s.feature_json
      FROM instrument_segments s JOIN midi_files mf ON mf.id=s.file_id
      LEFT JOIN performance_features pf ON pf.file_id=s.file_id AND pf.track_index=s.track_index
      AND pf.channel=s.channel WHERE s.note_count>0""").fetchall()
    groups=defaultdict(list)
    for row in rows:
        # Address/role/section is the durable identity of a Factory structure.
        # Track names can be aliases for the same address and must not create
        # duplicate UNIQUE rows.
        key=(row[0],row[1],row[2],row[3],row[5],row[6],row[7],row[8])
        groups[key].append((int(row[9]),track_feature_from_dict(json.loads(row[10])),row[4]))
    identity_groups=defaultdict(list)
    for key,selected in groups.items():
        chosen_name=max(selected,key=lambda item:item[0])[2]
        identity=canonical_identity(key[2],chosen_name,key[3]);family=identity_family(identity,key[2])
        model=GoldDNAModel.fit([feature for _,feature,_ in selected]);payload={"identity":identity,"family":family,"role":key[3],
            "section":key[4],"cv":key[5],"meter":f"{key[6]}/{key[7]}","aliases":sorted({name for _,_,name in selected}),
            "model":model.to_dict()}
        encoded=json.dumps(payload,separators=(',',':'));db.execute("""INSERT INTO factory_instrument_structures(
          bank_msb,bank_lsb,program,identity,family,role,name,section,cv,meter_num,meter_den,track_count,note_count,model_hash,structure_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(key[0],key[1],key[2],identity,family,key[3],chosen_name,
          key[4],key[5],key[6],key[7],len(selected),sum(count for count,_,_ in selected),hashlib.sha256(encoded.encode()).hexdigest(),encoded))
        identity_groups[(identity,key[3],key[6],key[7])].extend((count,feature) for count,feature,_ in selected)
    for key,selected in identity_groups.items():
        model=GoldDNAModel.fit([feature for _,feature in selected]);payload={"identity":key[0],"role":key[1],
            "meter_num":key[2],"meter_den":key[3],"model":model.to_dict(),"provenance":"Factory Styles full structure"}
        encoded=json.dumps(payload,separators=(',',':'));db.execute("""INSERT INTO factory_identity_models(identity,role,meter_num,
          meter_den,track_count,note_count,model_hash,model_json) VALUES(?,?,?,?,?,?,?,?)""",
          (*key,len(selected),sum(count for count,_ in selected),hashlib.sha256(encoded.encode()).hexdigest(),encoded))

    gold=sqlite3.connect(gold_path);gold.row_factory=sqlite3.Row
    rows=gold.execute(f"""SELECT s.program,s.role,COALESCE(NULLIF(s.name,''),{_name_query('gold','s')}) name,
      mf.tempo_bpm,mf.meter_num,mf.meter_den,s.note_count,s.feature_json
      FROM instrument_segments s JOIN midi_files mf ON mf.id=s.file_id WHERE s.note_count>0""").fetchall()
    corrections=defaultdict(list)
    for row in rows:
        identity=canonical_identity(row[0],row[2],row[1]);bucket=round(float(row[3] or 0)/20)*20 if row[3] else 0
        corrections[(identity,identity_family(identity,row[0]),row[1],bucket,row[4],row[5])].append((int(row[6]),track_feature_from_dict(json.loads(row[7]))))
    for key,selected in corrections.items():
        model=GoldDNAModel.fit([feature for _,feature in selected]);payload={"identity":key[0],"family":key[1],"role":key[2],
            "tempo_bucket":key[3],"meter_num":key[4],"meter_den":key[5],"model":model.to_dict(),"provenance":"Gold DNA Balkan corpus"}
        encoded=json.dumps(payload,separators=(',',':'));db.execute("""INSERT INTO gold_instrument_corrections(identity,family,role,
          tempo_bucket,meter_num,meter_den,track_count,note_count,model_hash,model_json) VALUES(?,?,?,?,?,?,?,?,?,?)""",
          (*key,len(selected),sum(count for count,_ in selected),hashlib.sha256(encoded.encode()).hexdigest(),encoded))

    # Every GM identity is explicitly defined. Absence of an exact RX identity means preserve.
    catalog=[dict(row) for row in factory.execute("SELECT name,bank_msb,bank_lsb,program,category FROM pa800_voice_catalog WHERE is_rx=1")]
    for program,name in enumerate(GM_PROGRAM_NAMES):
        role_hint="bass" if gm_family(program)=="bass" else "guitar" if gm_family(program)=="guitar" else "melodic"
        identity=canonical_identity(program,name,role_hint);db.execute("""INSERT INTO identity_conversion_rules(source_program,source_identity,target_name,
          target_bank_msb,target_bank_lsb,target_program,target_identity,mode,allowed,reason) VALUES(?,?,?,?,?,?,?,?,?,?)""",
          (program,identity,"",-1,-1,-1,identity,"preserve",1,"Nema potvrđenog identičnog RX cilja; sačuvaj original"))
        for target in catalog:
            role="drums" if target["category"]=="drums" else target["category"]
            target_identity=canonical_identity(target["program"],target["name"],role)
            if identity==target_identity:
                db.execute("""INSERT OR IGNORE INTO identity_conversion_rules(source_program,source_identity,target_name,
                  target_bank_msb,target_bank_lsb,target_program,target_identity,mode,allowed,reason) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (program,identity,target["name"],target["bank_msb"],target["bank_lsb"],target["program"],
                   target_identity,"rx_identity",1,"Isti kanonski instrument identitet"))
    # Drum channel uses kit identity, independent of melodic GM program naming.
    for target in catalog:
        if target["category"]=="drums" and canonical_identity(target["program"],target["name"],"drums")=="standard_kit":
            db.execute("""INSERT OR IGNORE INTO identity_conversion_rules(source_program,source_identity,target_name,target_bank_msb,
              target_bank_lsb,target_program,target_identity,mode,allowed,reason) VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (0,"standard_kit",target["name"],target["bank_msb"],target["bank_lsb"],target["program"],"standard_kit","rx_identity",1,"Standard drum kit identitet"))
    rules=(("identity_lock","Sound se smije promijeniti samo u isti kanonski instrument identitet."),
      ("preserve_without_rx","Ako nema identičnog potvrđenog RX cilja, originalni Sound ostaje."),
      ("factory_full_structure","Factory model čuva 16-step velocity/timing, gate, density, section, CV i meter po instrumentu."),
      ("gold_same_identity","Gold korekcija se prvo traži za isti instrument identitet i isti metar/tempo."),
      ("gold_fallback","Ako nema Gold modela istog identiteta, koristi se role model bez promjene Sounda."))
    db.executemany("INSERT INTO application_rules(rule_key,description) VALUES(?,?)",rules)
    conversion_count=db.execute("SELECT COUNT(*) FROM identity_conversion_rules").fetchone()[0]
    factory.close();gold.close();_finish(db,output_path)
    return {"gm_instruments":128,"factory_structures":len(groups),"factory_identity_models":len(identity_groups),
        "gold_corrections":len(corrections),"conversion_rules":conversion_count,"rules":len(rules)}


def load_instrument_structure(path: Path) -> dict:
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    result={"factory_models":[json.loads(row[0]) for row in db.execute("SELECT model_json FROM factory_identity_models")],
        "corrections":[json.loads(row[0]) for row in db.execute("SELECT model_json FROM gold_instrument_corrections")],
        "rules":[dict(row) for row in db.execute("SELECT * FROM identity_conversion_rules WHERE allowed=1")]}
    db.close();return result


def choose_factory_model(data: dict,identity: str,role: str,meter_num: int,meter_den: int):
    selected=next((row for row in data.get("factory_models",[]) if row["identity"]==identity and row["role"]==role
        and int(row["meter_num"] or 4)==meter_num and int(row["meter_den"] or 4)==meter_den),None)
    if not selected:return None
    return GoldDNAModel.from_dict(selected["model"]),{"identity":identity,"meter":f"{meter_num}/{meter_den}","provenance":selected["provenance"]}


def choose_identity_model(data: dict,identity: str,role: str,tempo_bpm: float | None,meter_num: int,meter_den: int):
    bucket=round(float(tempo_bpm or 0)/20)*20 if tempo_bpm else 0
    candidates=[row for row in data.get("corrections",[]) if row["identity"]==identity and row["role"]==role
        and int(row["meter_num"] or 4)==meter_num and int(row["meter_den"] or 4)==meter_den]
    if not candidates:return None
    selected=min(candidates,key=lambda row:abs(int(row.get("tempo_bucket") or 0)-bucket))
    return GoldDNAModel.from_dict(selected["model"]),{"identity":identity,"scope":f'{selected["tempo_bucket"]}:{meter_num}/{meter_den}',"provenance":selected["provenance"]}