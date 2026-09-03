"""RAW-derived, mutation-free context attribution for X10 rhythm analysis."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from hashlib import sha256
import json

from .midi import MidiFile
from .rhythm_context import bar_pattern_fingerprints, extract_rhythm_note_context, stable_event_id
from .rhythm_negative_corpus import apply_protection_adapters


ACCEPTED_PROVENANCE_METHODS = {
    "role": {"RAW_TRACK", "RAW_MIDI", "EXPLICIT_METADATA"},
    "style": {"RAW_MIDI", "EXPLICIT_METADATA"},
    "section": {"RAW_TRACK", "RAW_MIDI", "EXPLICIT_METADATA"},
    "cv": {"RAW_TRACK", "RAW_MIDI", "EXPLICIT_METADATA", "CV_NOT_APPLICABLE"},
}


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _stable_id(kind: str, source_sha256: str, value) -> str:
    return sha256(_canonical([kind, source_sha256, value])).hexdigest()


def _locator(source_sha256, track, event):
    return {"source_sha256": source_sha256, "track_index": int(track), "tick": int(event.tick),
            "order": float(event.order), "event_id": stable_event_id(source_sha256, track, event)}


def _state_events(midi, source_sha256):
    grouped = defaultdict(lambda: {"locators": []})
    for track, events in enumerate(midi.tracks):
        for event in events:
            kind = None; value = None
            if event.kind == "control" and event.data1 in (0, 32):
                kind = "bank_msb" if event.data1 == 0 else "bank_lsb"; value = int(event.data2 or 0)
            elif event.kind == "program":
                kind = "program"; value = int(event.data1 or 0)
            if kind is None: continue
            key = (int(event.channel or 0), int(event.tick), kind, value)
            grouped[key]["locators"].append(_locator(source_sha256, track, event))
    result = []
    for (channel, tick, kind, value), item in sorted(grouped.items()):
        semantic = _stable_id("channel-state", source_sha256, [channel, tick, kind, value])
        result.append({"source_sha256": source_sha256, "channel": channel, "tick": tick,
                       "event_kind": kind, "semantic_value": value,
                       "semantic_value_sha256": sha256(_canonical(value)).hexdigest(),
                       "state_event_id": semantic, "evidence_locators": sorted(item["locators"],
                           key=lambda loc: (loc["track_index"], loc["order"], loc["event_id"]))})
    return result


def _program_tick_events(midi, channel):
    grouped = defaultdict(list)
    for track, events in enumerate(midi.tracks):
        for event in events:
            if int(event.channel or 0) != channel: continue
            if event.kind == "program" or (event.kind == "control" and event.data1 in (0, 32)):
                grouped[int(event.tick)].append((track, event))
    return grouped


def _tick_program_conflict(track_events):
    values_by_track = defaultdict(lambda: defaultdict(list)); tracks = defaultdict(set)
    for track, event in track_events:
        kind = "program" if event.kind == "program" else "bank_msb" if event.data1 == 0 else "bank_lsb"
        value = int(event.data1 or 0) if event.kind == "program" else int(event.data2 or 0)
        values_by_track[kind][track].append((float(event.order), value)); tracks[kind].add(track)
    for kind, track_values in values_by_track.items():
        final_values = {sorted(sequence)[-1][1] for sequence in track_values.values()}
        if len(final_values) > 1: return True
    if "program" in tracks and ("bank_msb" in tracks or "bank_lsb" in tracks):
        relevant = [tracks["program"]] + [tracks[kind] for kind in ("bank_msb", "bank_lsb") if kind in tracks]
        if not set.intersection(*map(set, relevant)): return True
    return False


def _authoritative_tick_events(track_events):
    """Choose one proven local order while collapsing identical cross-track duplicates."""
    by_track = defaultdict(list)
    for track, event in track_events: by_track[track].append(event)
    if len(by_track) == 1:
        return sorted(next(iter(by_track.values())), key=lambda event: float(event.order))
    kinds = {"program" if event.kind == "program" else "bank_msb" if event.data1 == 0 else "bank_lsb"
             for _track, event in track_events}
    if len(kinds) > 1:
        candidates = [track for track, events in by_track.items() if kinds.issubset({
            "program" if event.kind == "program" else "bank_msb" if event.data1 == 0 else "bank_lsb" for event in events})]
        if candidates: return sorted(by_track[min(candidates)], key=lambda event: float(event.order))
    selected_track = min(by_track)
    return sorted(by_track[selected_track], key=lambda event: float(event.order))


def _apply_program_events(current, pending, ordered_events):
    program_seen = False
    for event in ordered_events:
        if event.kind == "control" and event.data1 == 0: pending["bank_msb"] = int(event.data2 or 0)
        elif event.kind == "control" and event.data1 == 32: pending["bank_lsb"] = int(event.data2 or 0)
        elif event.kind == "program":
            current.update({"bank_msb": pending["bank_msb"], "bank_lsb": pending["bank_lsb"],
                            "program": int(event.data1 or 0)})
            current["status"] = "PROGRAM_EXACT" if current["bank_msb"] is not None and current["bank_lsb"] is not None else "PROGRAM_PARTIAL_UNSPECIFIED_BANK"
            program_seen = True
    return program_seen


def _program_segments(midi, source_sha256):
    channels = list(range(16))
    output = []
    for channel in channels:
        current = {"bank_msb": None, "bank_lsb": None, "program": None, "status": "PROGRAM_DEFAULT_UNSPECIFIED"}
        pending = {"bank_msb": None, "bank_lsb": None}; starts = [(0, current["status"], dict(current), [])]
        for tick, track_events in sorted(_program_tick_events(midi, channel).items()):
            locators = [_locator(source_sha256, track, event) for track, event in track_events]
            if _tick_program_conflict(track_events):
                current["status"] = "PROGRAM_CONFLICT"; pending = {"bank_msb": None, "bank_lsb": None}
                starts.append((tick, current["status"], dict(current), locators)); continue
            program_seen = _apply_program_events(current, pending, _authoritative_tick_events(track_events))
            if program_seen: starts.append((tick, current["status"], dict(current), locators))
        for index, (tick, status, state_value, locators) in enumerate(starts):
            end = starts[index + 1][0] if index + 1 < len(starts) else None
            payload = [channel, tick, end, status, state_value]
            output.append({"source_sha256": source_sha256, "channel": channel, "start_tick": tick,
                "end_tick": end, "program_segment_id": _stable_id("program-segment", source_sha256, payload),
                "bank_msb": state_value["bank_msb"], "bank_lsb": state_value["bank_lsb"],
                "program": state_value["program"], "status": status,
                "segment_kind": "TIMELINE",
                "evidence_locators": sorted(locators, key=lambda loc: (loc["track_index"], loc["order"], loc["event_id"]))})
    return output


def _global_segments(midi, source_sha256, kind):
    meta_type = 0x58 if kind == "meter" else 0x51
    grouped = defaultdict(lambda: defaultdict(list))
    for track, events in enumerate(midi.tracks):
        for event in events:
            if event.kind != "meta" or event.data1 != meta_type: continue
            if kind == "meter":
                if len(event.raw) < 2: continue
                value = (max(1, int(event.raw[0])), 2 ** int(event.raw[1]))
            else:
                if len(event.raw) != 3: continue
                value = int.from_bytes(event.raw, "big")
            grouped[int(event.tick)][value].append(_locator(source_sha256, track, event))
    starts = []
    if not grouped or min(grouped) > 0:
        default = (4, 4) if kind == "meter" else 500000
        starts.append((0, default, f"{kind.upper()}_DEFAULT_UNSPECIFIED", []))
    for tick, values in sorted(grouped.items()):
        locators = [loc for group in values.values() for loc in group]
        if len(values) > 1:
            starts.append((tick, None, f"{kind.upper()}_CONFLICT", locators))
        else:
            starts.append((tick, next(iter(values)), f"{kind.upper()}_EXACT", locators))
    if not starts:
        starts = [(0, (4, 4) if kind == "meter" else 500000, f"{kind.upper()}_DEFAULT_UNSPECIFIED", [])]
    output = []
    for index, (tick, value, status, locators) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else None
        payload = [tick, end, value, status]
        row = {"source_sha256": source_sha256, "start_tick": tick, "end_tick": end,
               f"{kind}_segment_id": _stable_id(f"{kind}-segment", source_sha256, payload),
               "status": status, "evidence_locators": sorted(locators,
                    key=lambda loc: (loc["track_index"], loc["order"], loc["event_id"]))}
        if kind == "meter":
            row.update({"numerator": value[0] if value else None, "denominator": value[1] if value else None})
        else:
            row.update({"microseconds_per_quarter": value, "tempo_regime_key": str(value) if value is not None else None})
        output.append(row)
    return output


def build_channel_context(midi: MidiFile, source_sha256: str) -> dict:
    """Build deterministic state timelines without imposing cross-track order."""
    if not isinstance(midi, MidiFile) or midi.division <= 0: raise ValueError("Valid PPQ MIDI is required")
    events = _state_events(midi, source_sha256); program_segments = _program_segments(midi, source_sha256)
    known_ids = {row["program_segment_id"] for row in program_segments}
    for track, track_events in enumerate(midi.tracks):
        for event in track_events:
            if event.kind != "note_on" or int(event.data2 or 0) <= 0: continue
            attribution, status = _program_for_note(midi, source_sha256, track, int(event.channel or 0),
                int(event.tick), float(event.order))
            if attribution["program_segment_id"] in known_ids: continue
            known_ids.add(attribution["program_segment_id"])
            locators = list(attribution.get("evidence_locators", [])) + [_locator(source_sha256, track, event)]
            program_segments.append({"source_sha256": source_sha256, "channel": int(event.channel or 0),
                "start_tick": int(event.tick), "end_tick": int(event.tick),
                "program_segment_id": attribution["program_segment_id"], "bank_msb": attribution["bank_msb"],
                "bank_lsb": attribution["bank_lsb"], "program": attribution["program"], "status": status,
                "segment_kind": "NOTE_ON_ATTRIBUTION", "evidence_locators": sorted(locators,
                    key=lambda loc: (loc["track_index"], loc["order"], loc["event_id"]))})
    program_segments.sort(key=lambda row: (row["channel"], row["start_tick"], row["segment_kind"], row["program_segment_id"]))
    return {"channel_state_events": events, "program_segments": program_segments,
            "meter_segments": _global_segments(midi, source_sha256, "meter"),
            "tempo_segments": _global_segments(midi, source_sha256, "tempo")}


def _segment_at(rows, tick, id_key):
    selected = rows[max(0, bisect_right([row["start_tick"] for row in rows], int(tick)) - 1)]
    return selected[id_key], selected


def _program_for_note(midi, source_sha256, track, channel, tick, note_order):
    """Replay every proven state event up to Note On using track-local event order."""
    current = {"bank_msb": None, "bank_lsb": None, "program": None, "status": "PROGRAM_DEFAULT_UNSPECIFIED"}
    pending = {"bank_msb": None, "bank_lsb": None}; locators = []
    for event_tick, track_events in sorted(_program_tick_events(midi, channel).items()):
        if event_tick > int(tick): break
        if event_tick == int(tick):
            remote = [(event_track, event) for event_track, event in track_events if event_track != track]
            if remote:
                payload = [track, channel, tick, float(note_order), "PROGRAM_SAME_TICK_AMBIGUOUS", current]
                value = dict(current); value.update({"program_segment_id": _stable_id("note-program-attribution", source_sha256, payload),
                    "status": "PROGRAM_SAME_TICK_AMBIGUOUS", "evidence_locators": locators + [
                        _locator(source_sha256, event_track, event) for event_track, event in remote]})
                return value, "PROGRAM_SAME_TICK_AMBIGUOUS"
            selected = [(event_track, event) for event_track, event in track_events
                        if event_track == track and float(event.order) < float(note_order)]
            ordered = [event for _event_track, event in sorted(selected, key=lambda item: float(item[1].order))]
            locators.extend(_locator(source_sha256, track, event) for event in ordered)
            _apply_program_events(current, pending, ordered)
            break
        locators.extend(_locator(source_sha256, event_track, event) for event_track, event in track_events)
        if _tick_program_conflict(track_events):
            current["status"] = "PROGRAM_CONFLICT"; pending = {"bank_msb": None, "bank_lsb": None}; continue
        _apply_program_events(current, pending, _authoritative_tick_events(track_events))
    payload = [track, channel, tick, float(note_order), current["status"], current["bank_msb"], current["bank_lsb"], current["program"]]
    value = dict(current); value.update({"program_segment_id": _stable_id("note-program-attribution", source_sha256, payload),
        "evidence_locators": locators})
    return value, current["status"]


def _meta(metadata, key, track, channel, default=None):
    value = metadata.get(key, default)
    if isinstance(value, dict):
        for candidate in ((track, channel), f"{track}:{channel}", str(track), "default"):
            if candidate in value: return value[candidate]
        return default
    return value


def join_note_context(midi: MidiFile, source_sha256: str, metadata, quality_status, protection_adapters=()) -> list[dict]:
    """Join stable notes to exact context; every uncertainty remains preservation data."""
    metadata = dict(metadata or {}); timelines = build_channel_context(midi, source_sha256)
    notes = extract_rhythm_note_context(midi, source_sha256)
    on_orders = {}
    for track, events in enumerate(midi.tracks):
        for event in events:
            if event.kind == "note_on" and int(event.data2 or 0) > 0:
                on_orders[stable_event_id(source_sha256, track, event)] = event.order
    output = []
    for note in notes:
        track = note["track"]; channel = note["channel"]; tick = note["start_tick"]
        program, program_status = _program_for_note(midi, source_sha256, track, channel, tick,
            on_orders.get(note["on_event_id"], -1))
        program_id = program["program_segment_id"]
        meter_id, meter = _segment_at(timelines["meter_segments"], tick, "meter_segment_id")
        tempo_id, tempo = _segment_at(timelines["tempo_segments"], tick, "tempo_segment_id")
        role = _meta(metadata, "role", track, channel, "UNKNOWN")
        role_status = _meta(metadata, "role_status", track, channel, "UNKNOWN")
        style = _meta(metadata, "style_name", track, channel)
        style_status = _meta(metadata, "style_status", track, channel, "UNKNOWN")
        section = _meta(metadata, "section", track, channel)
        section_no = _meta(metadata, "section_no", track, channel)
        section_status = _meta(metadata, "section_status", track, channel, "UNKNOWN")
        cv = _meta(metadata, "cv", track, channel)
        cv_status = _meta(metadata, "cv_status", track, channel, "CV_UNKNOWN")
        quality = _meta({"quality": quality_status}, "quality", track, channel, "INVALID")
        reasons = []
        if quality != "NORMAL": reasons.append(f"QUALITY_{quality}")
        role_method = _meta(metadata, "role_method", track, channel)
        role_locator = _meta(metadata, "role_locator", track, channel)
        style_method = _meta(metadata, "style_method", track, channel)
        style_locator = _meta(metadata, "style_locator", track, channel)
        section_method = _meta(metadata, "section_method", track, channel)
        section_locator = _meta(metadata, "section_locator", track, channel)
        cv_method = _meta(metadata, "cv_method", track, channel)
        cv_locator = _meta(metadata, "cv_locator", track, channel)
        checks = ((program_status, "PROGRAM_EXACT"), (meter["status"], "METER_EXACT"),
                  (tempo["status"], "TEMPO_EXACT"), (role_status, "EXACT"),
                  (style_status, "EXPLICIT_METADATA"), (section_status, "EXACT"))
        for actual, exact in checks:
            if actual != exact: reasons.append(str(actual))
        if cv_status not in {"CV_EXACT", "CV_NOT_APPLICABLE"}: reasons.append(str(cv_status))
        if role == "UNKNOWN": reasons.append("UNKNOWN_ROLE")
        if (role is None or not str(role).strip() or role_method not in ACCEPTED_PROVENANCE_METHODS["role"]
                or not role_locator): reasons.append("ROLE_PROVENANCE_INCOMPLETE")
        if (style is None or not str(style).strip() or style_method not in ACCEPTED_PROVENANCE_METHODS["style"]
                or not style_locator): reasons.append("STYLE_PROVENANCE_INCOMPLETE")
        if (section is None or not str(section).strip() or section_method not in ACCEPTED_PROVENANCE_METHODS["section"]
                or not section_locator): reasons.append("SECTION_PROVENANCE_INCOMPLETE")
        if (cv_method not in ACCEPTED_PROVENANCE_METHODS["cv"] or not cv_locator
                or (cv_status == "CV_EXACT" and cv is None)): reasons.append("CV_PROVENANCE_INCOMPLETE")
        if str(section or "").upper() in {"INTRO", "VARIATION", "FILL", "ENDING"}:
            try: valid_section_no = int(section_no) >= 0 and not isinstance(section_no, bool)
            except (TypeError, ValueError): valid_section_no = False
            if not valid_section_no: reasons.append("SECTION_NO_UNKNOWN")
        exact = not reasons
        exact_key = None
        if exact:
            exact_key = sha256(_canonical([role, program["bank_msb"], program["bank_lsb"], program["program"],
                section, section_no, cv_status, cv, meter["numerator"], meter["denominator"],
                tempo["microseconds_per_quarter"]])).hexdigest()
        row = dict(note)
        row.update({"source_sha256": source_sha256, "program_segment_id": program_id,
            "program_status": program_status, "bank_msb": program["bank_msb"], "bank_lsb": program["bank_lsb"],
            "program": program["program"], "meter_segment_id": meter_id, "meter_status": meter["status"],
            "tempo_segment_id": tempo_id, "tempo_status": tempo["status"],
            "microseconds_per_quarter": tempo["microseconds_per_quarter"], "tempo_regime_key": tempo["tempo_regime_key"],
            "role": role, "role_status": role_status, "role_method": role_method,
            "role_locator": role_locator,
            "style_name": style, "style_status": style_status, "style_method": style_method,
            "style_locator": style_locator,
            "section": section, "section_no": section_no, "section_status": section_status,
            "section_method": section_method, "cv": cv, "cv_status": cv_status,
            "section_locator": section_locator,
            "cv_method": cv_method,
            "cv_locator": cv_locator, "quality_status": quality,
            "exact_context_key": exact_key, "eligibility_status": "EXACT_CONTEXT_MATCH" if exact else "PROTECTED_CONTEXT",
            "preservation_reasons": sorted(set(reasons)), "evidence_locator": {"source_sha256": source_sha256,
                "track_index": track, "on_event_id": note["on_event_id"]}})
        output.append(row)
    patterns = {(row["track"], row["channel"], row["bar"]): row for row in bar_pattern_fingerprints(output)}
    for row in output:
        if row["exact_context_key"] is not None:
            pattern = patterns[(row["track"], row["channel"], row["bar"])]
            row["exact_context_key"] = sha256(_canonical([row["exact_context_key"], pattern["topology_sha256"],
                pattern["onset_cluster_count"]])).hexdigest()
    return apply_protection_adapters(output, protection_adapters)