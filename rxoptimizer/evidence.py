"""Build a reproducible, read-only evidence inventory.

The inventory records what entered the project; it does not interpret MIDI or
promote observations to facts.  That separation prevents optimized output and
user notes from contaminating Factory/Gold evidence.
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile


MIDI_SUFFIXES = {".mid", ".midi"}


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _record(path: Path, classification: str, authority: str, evidence_status: str,
            immutable: bool = True) -> dict:
    data = path.read_bytes()
    return {
        "path": path.as_posix(),
        "classification": classification,
        "authority": authority,
        "evidence_status": evidence_status,
        "immutable": immutable,
        "size": len(data),
        "sha256": _digest(data),
    }


def _nested_zip_inventory(outer_path: Path) -> list[dict]:
    result = []
    with ZipFile(outer_path) as outer:
        for outer_info in outer.infolist():
            if outer_info.is_dir() or not outer_info.filename.lower().endswith(".zip"):
                continue
            archive_data = outer.read(outer_info)
            name_lower = outer_info.filename.lower()
            classification = "factory_raw" if "factory" in name_lower else "balkan_reference_raw"
            archive = {
                "path": f"{outer_path.as_posix()}::{outer_info.filename}",
                "classification": classification,
                "authority": "factory_style" if classification == "factory_raw" else "reference_corpus",
                "evidence_status": "DIRECT_RAW",
                "immutable": True,
                "size": len(archive_data),
                "sha256": _digest(archive_data),
                "members": [],
            }
            with ZipFile(BytesIO(archive_data)) as nested:
                for info in nested.infolist():
                    if info.is_dir() or Path(info.filename).suffix.lower() not in MIDI_SUFFIXES:
                        continue
                    data = nested.read(info)
                    archive["members"].append({
                        "path": info.filename,
                        "size": len(data),
                        "crc32": f"{info.CRC:08x}",
                        "sha256": _digest(data),
                        "evidence_status": "DIRECT_RAW",
                    })
            archive["midi_count"] = len(archive["members"])
            archive["unique_sha256_count"] = len({item["sha256"] for item in archive["members"]})
            result.append(archive)
    return result


def build_evidence_inventory(root: Path = Path("."), output: Path | None = None) -> dict:
    """Inventory local evidence without modifying any source artifact."""
    uploads = root / "prism-uploads"
    archive_path = uploads / "DNA.zip"
    records = []
    if archive_path.exists():
        records.append(_record(archive_path, "source_container", "mixed_raw_container", "DIRECT_RAW"))
    for path in sorted(uploads.glob("*.mid")):
        records.append(_record(path, "song_layer_reference", "user_supplied_song", "DIRECT_RAW"))
    notes = uploads / "Oscilatori.txt"
    if notes.exists():
        records.append(_record(notes, "user_observation", "user_report", "UNVERIFIED", immutable=True))
    manual_index = root / "reference" / "pa800" / "README.md"
    if manual_index.exists():
        records.append(_record(manual_index, "manual_link_index", "index_only", "NOT_PRIMARY_DOCUMENT"))

    nested = _nested_zip_inventory(archive_path) if archive_path.exists() else []
    inventory = {
        "schema_version": 1,
        "rules": {
            "factory_raw_read_only": True,
            "optimized_output_is_evidence": False,
            "gold_rules_are_not_raw_midi": True,
            "unknown_is_not_inferred": True,
            "user_observation_requires_confirmation": True,
        },
        "source_records": records,
        "nested_archives": nested,
        "summary": {
            "source_records": len(records),
            "factory_midi": sum(item["midi_count"] for item in nested if item["classification"] == "factory_raw"),
            "factory_unique_midi": sum(item["unique_sha256_count"] for item in nested if item["classification"] == "factory_raw"),
            "reference_midi": sum(item["midi_count"] for item in nested if item["classification"] == "balkan_reference_raw"),
            "reference_unique_midi": sum(item["unique_sha256_count"] for item in nested if item["classification"] == "balkan_reference_raw"),
            "local_primary_manual_pdfs": 0,
        },
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(output)
    return inventory
