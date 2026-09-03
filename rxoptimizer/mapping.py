"""Conservative Factory/GM to Pa800 RX mapping recommendations.

The recommendation engine deliberately separates *recognising a source* from
*verifying a target*.  A recommendation is emitted only when its target exists
in the supplied Pa800 catalog; consequently this module never manufactures a
Bank Select or Program Change address.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import re
from typing import Iterable, Mapping, Sequence
from .instrument_identity import canonical_identity,identities_compatible


MappingRow = Mapping[str, object]


def _integer(row: MappingRow, key: str, default: int = 0) -> int:
    value = row.get(key, default)
    return default if value is None else int(value)


def _text(row: MappingRow, key: str) -> str:
    value = row.get(key, "")
    return "" if value is None else str(value)


def _normal_name(value: str) -> str:
    value = value.casefold().replace("acous.", "acoustic").replace("guit.", "guitar")
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _source_key(row: MappingRow) -> tuple[int, int, int, str]:
    return (
        _integer(row, "source_bank_msb", _integer(row, "bank_msb")),
        _integer(row, "source_bank_lsb", _integer(row, "bank_lsb")),
        _integer(row, "source_program", _integer(row, "program")),
        _text(row, "role") or "melodic",
    )


def _catalog_indexes(catalog: Iterable[MappingRow]):
    usable = [row for row in catalog if _integer(row, "is_rx", 1)]
    by_address = {
        (_integer(row, "bank_msb"), _integer(row, "bank_lsb"), _integer(row, "program")): row
        for row in usable
    }
    by_name = {_normal_name(_text(row, "name")): row for row in usable if _text(row, "name")}
    return by_address, by_name


def _target(by_name: Mapping[str, MappingRow], *names: str):
    for name in names:
        row = by_name.get(_normal_name(name))
        if row is not None:
            return row
    return None


def _family_candidate(profile: MappingRow, by_name: Mapping[str, MappingRow]):
    """Return (catalog row, confidence, rule) for a safe family match."""
    role = _text(profile, "role").casefold() or "melodic"
    program = _integer(profile, "program")
    name = _normal_name(_text(profile, "name"))
    is_bass = role == "bass" or "bass" in name
    is_guitar = role == "guitar" or "guitar" in name
    is_drums = role in ("drums", "percussion") or "kit" in name or "drum" in name

    # Name-qualified rules precede generic GM program-family rules.  This is
    # important for Pa800 program 36, shared by three different slap RX sounds.
    if is_bass:
        if "slapfing" in name or "slap fing" in name:
            return _target(by_name, "SlapFing Bass RX"), .99, "name:slap-finger"
        if "slappick" in name or "slap pick" in name:
            return _target(by_name, "SlapPick Bass RX"), .99, "name:slap-pick"
        if "funk" in name and "slap" in name:
            return _target(by_name, "FunkSlap Bass RX"), .98, "name:funk-slap"
        if "picked bass" in name or "pick bass" in name:
            return _target(by_name, "Picked Bass RX"), .97, "name:picked-bass"
        if "finger bass" in name:
            return _target(by_name, "Finger Bass RX"), .97, "name:finger-bass"
        if "acoustic bass" in name or "acous bass" in name:
            return _target(by_name, "Acous. Bass RX"), .97, "name:acoustic-bass"
        gm_bass = {
            32: ("Acous. Bass RX", .98, "gm-family:acoustic-bass"),
            33: ("Finger Bass RX", .99, "gm-family:finger-bass"),
            34: ("Picked Bass RX", .99, "gm-family:picked-bass"),
            36: ("FunkSlap Bass RX", .96, "gm-family:slap-bass-1"),
            37: ("SlapPick Bass RX", .92, "gm-family:slap-bass-2"),
        }
        if program in gm_bass:
            target_name, confidence, rule = gm_bass[program]
            return _target(by_name, target_name), confidence, rule

    if is_guitar and (program == 27 or "clean" in name):
        return _target(by_name, "Clean Guitar RX1"), .96 if program == 27 else .93, "family:clean-guitar"

    if is_drums:
        if "jazz" in name or (program == 32 and _integer(profile, "bank_msb") == 0):
            return _target(by_name, "Jazz Kit RX1"), .93, "family:jazz-kit"
        if program == 0 and _integer(profile, "bank_msb") == 0:
            return _target(by_name, "Standard Kit RX2"), .95, "gm-family:standard-kit"

    return None, 0.0, ""


def recommend_profile(profile: MappingRow, catalog: Iterable[MappingRow]):
    """Recommend one verified RX target for an instrument profile, or ``None``.

    Returned dictionaries can be passed directly to ``optimizer.optimize``.
    Program numbers use MIDI's native 0--127 representation.
    """
    by_address, by_name = _catalog_indexes(catalog)
    address = (
        _integer(profile, "bank_msb"),
        _integer(profile, "bank_lsb"),
        _integer(profile, "program"),
    )
    source_name = _normal_name(_text(profile, "name"))

    if address in by_address:
        target = by_address[address]
        confidence, method = 1.0, "known-rx-identity"
        provenance = "Exact CC00/CC32/PC identity in supplied Pa800 RX catalog"
    elif source_name and source_name in by_name:
        target = by_name[source_name]
        confidence, method = .99, "catalog-name-identity"
        provenance = "Exact normalized sound name in supplied Pa800 RX catalog"
    else:
        target, confidence, method = _family_candidate(profile, by_name)
        if target is None:
            return None
        provenance = (
            f"Conservative {method} recommendation; target address verified by "
            "supplied Pa800 RX catalog"
        )

    same_address=address==(_integer(target,"bank_msb"),_integer(target,"bank_lsb"),_integer(target,"program"))
    if not identities_compatible(address[2],_text(profile,"name"),_integer(target,"program"),_text(target,"name"),
                                 _text(profile,"role"),same_address=same_address):
        return None

    return {
        "source_bank_msb": address[0],
        "source_bank_lsb": address[1],
        "source_program": address[2],
        "role": _text(profile, "role") or "melodic",
        "source_name": _text(profile, "name"),
        "rx_name": _text(target, "name"),
        "target_bank_msb": _integer(target, "bank_msb"),
        "target_bank_lsb": _integer(target, "bank_lsb"),
        "target_program": _integer(target, "program"),
        "confidence": confidence,
        "provenance": provenance,
        "recommendation_method": method,
        "source_identity":canonical_identity(address[2],_text(profile,"name"),_text(profile,"role")),
        "target_identity":canonical_identity(_integer(target,"program"),_text(target,"name"),_text(profile,"role")),
        "identity_locked":1,
        "is_default": 1,
    }


def recommend_mappings(
    profiles: Iterable[MappingRow], catalog: Iterable[MappingRow], min_confidence: float = 0.0
) -> list[dict]:
    """Recommend and deduplicate mappings, retaining the strongest evidence."""
    catalog = list(catalog)
    strongest: dict[tuple[int, int, int, str], dict] = {}
    for profile in profiles:
        recommendation = recommend_profile(profile, catalog)
        if recommendation is None or recommendation["confidence"] < min_confidence:
            continue
        key = _source_key(recommendation)
        current = strongest.get(key)
        if current is None or recommendation["confidence"] > current["confidence"]:
            strongest[key] = recommendation
    return sorted(strongest.values(), key=_source_key)


def apply_recommendations(
    existing: Iterable[MappingRow],
    recommendations: Iterable[MappingRow],
    min_confidence: float = .90,
    replace_lower_confidence: bool = False,
) -> tuple[list[dict], dict]:
    """Merge recommendations without overwriting user/existing rows by default.

    ``replace_lower_confidence`` is opt-in and still replaces only a row whose
    recorded confidence is lower.  The returned list remains directly usable
    by the optimizer and the report makes every merge decision auditable.
    """
    merged = {_source_key(row): dict(row) for row in existing}
    report = {"added": 0, "replaced": 0, "kept_existing": 0, "below_threshold": 0}
    for row in recommendations:
        candidate = dict(row)
        if float(candidate.get("confidence", 0)) < min_confidence:
            report["below_threshold"] += 1
            continue
        key = _source_key(candidate)
        current = merged.get(key)
        if current is None:
            merged[key] = candidate
            report["added"] += 1
        elif replace_lower_confidence and float(candidate.get("confidence", 0)) > float(current.get("confidence", 0)):
            merged[key] = candidate
            report["replaced"] += 1
        else:
            report["kept_existing"] += 1
    return sorted(merged.values(), key=_source_key), report


def coverage_report(profiles: Iterable[MappingRow], recommendations: Iterable[MappingRow]) -> dict:
    """Return unique-profile coverage with role and evidence-method breakdowns."""
    unique_profiles = {_source_key(row): row for row in profiles}
    recommended = {_source_key(row): row for row in recommendations}
    by_role = defaultdict(lambda: {"total": 0, "mapped": 0, "unmapped": 0})
    methods = Counter()
    for key in unique_profiles:
        role = key[3]
        by_role[role]["total"] += 1
        if key in recommended:
            by_role[role]["mapped"] += 1
            methods[_text(recommended[key], "recommendation_method") or "unspecified"] += 1
        else:
            by_role[role]["unmapped"] += 1
    total = len(unique_profiles)
    mapped = sum(key in recommended for key in unique_profiles)
    return {
        "profiles_total": total,
        "profiles_mapped": mapped,
        "profiles_unmapped": total - mapped,
        "coverage_percent": round(100 * mapped / total, 2) if total else 0.0,
        "by_role": dict(sorted(by_role.items())),
        "by_method": dict(sorted(methods.items())),
    }


def catalog_rows(connection) -> list[dict]:
    """Read the verified RX catalog from an existing project SQLite connection."""
    return [dict(row) for row in connection.execute(
        "SELECT name,category,bank_msb,bank_lsb,program,is_rx,source FROM pa800_voice_catalog"
    )]


def factory_profile_rows(connection) -> list[dict]:
    """Read Factory profiles from an existing project SQLite connection."""
    return [dict(row) for row in connection.execute(
        "SELECT bank_msb,bank_lsb,program,role,name,source FROM instrument_profiles WHERE source='factory'"
    )]