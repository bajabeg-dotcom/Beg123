from rxoptimizer.midi import Event, MidiFile
from rxoptimizer.rhythm_context_join import build_channel_context, join_note_context
from rxoptimizer.rhythm_negative_corpus import REQUIRED_PROTECTION_RULES


SHA = "1" * 64


def exact_metadata(**overrides):
    value = {"role": "BASS", "role_status": "EXACT", "style_name": "Test",
        "style_status": "EXPLICIT_METADATA", "section": "VARIATION", "section_no": 0,
        "section_status": "EXACT", "cv": 0, "cv_status": "CV_EXACT",
        "role_method": "RAW_TRACK", "role_locator": "Factory/Test.mid#track=0",
        "style_method": "EXPLICIT_METADATA", "style_locator": "Factory/Test.mid#style",
        "section_method": "EXPLICIT_METADATA", "section_locator": "Factory/Test.mid#section",
        "cv_method": "EXPLICIT_METADATA", "cv_locator": "Factory/Test.mid#cv"}
    value.update(overrides); return value


def clear_adapters():
    result = []
    for rule_key, version in REQUIRED_PROTECTION_RULES:
        def clear(rows, _key=rule_key):
            return [{"note_id": row["note_id"], "detection_status": "CLEAR",
                     "evidence_status": "CHECKED", "locator": row["evidence_locator"]} for row in rows]
        clear.rule_key = rule_key; clear.version = version; result.append(clear)
    return result


def note_pair(start=0, end=120, order=0, note=60):
    return [Event(start, order, "note_on", 0, note, 80, 0x90),
            Event(end, order + 1, "note_off", 0, note, 0, 0x80)]


def test_initial_program_and_transport_defaults_are_not_exact():
    midi = MidiFile(1, 480, [note_pair()])
    timelines = build_channel_context(midi, SHA)
    assert timelines["program_segments"][0]["status"] == "PROGRAM_DEFAULT_UNSPECIFIED"
    rows = join_note_context(midi, SHA, exact_metadata(), "NORMAL")
    assert rows[0]["program"] is None
    assert rows[0]["meter_status"] == "METER_DEFAULT_UNSPECIFIED"
    assert rows[0]["tempo_status"] == "TEMPO_DEFAULT_UNSPECIFIED"
    assert rows[0]["eligibility_status"] == "PROTECTED_CONTEXT"


def test_partial_bank_and_exact_program_states():
    partial = MidiFile(1, 480, [[Event(0, 0, "program", 0, 33, status=0xC0), *note_pair(order=1)]])
    assert join_note_context(partial, SHA, exact_metadata(), "NORMAL")[0]["program_status"] == "PROGRAM_PARTIAL_UNSPECIFIED_BANK"
    exact = MidiFile(1, 480, [[Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0), Event(0, 2, "program", 0, 33, status=0xC0),
        Event(0, 3, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
        Event(0, 4, "meta", data1=0x51, raw=(500000).to_bytes(3, "big")), *note_pair(order=5)]])
    row = join_note_context(exact, SHA, exact_metadata(), "NORMAL", clear_adapters())[0]
    assert (row["bank_msb"], row["bank_lsb"], row["program"]) == (10, 2, 33)
    assert row["program_status"] == "PROGRAM_EXACT"
    assert row["section_no"] == 0 and row["cv"] == 0
    assert row["exact_context_key"] is not None
    assert row["eligibility_status"] == "EXACT_CONTEXT_MATCH"


def test_same_track_order_and_note_off_after_program_change():
    midi = MidiFile(1, 480, [[Event(0, 0, "note_on", 0, 60, 80, 0x90),
        Event(0, 1, "program", 0, 40, status=0xC0), Event(120, 2, "note_off", 0, 60, 0, 0x80),
        Event(240, 3, "note_on", 0, 62, 80, 0x90), Event(360, 4, "note_off", 0, 62, 0, 0x80)]])
    rows = join_note_context(midi, SHA, exact_metadata(), "NORMAL")
    assert rows[0]["program"] is None
    assert rows[1]["program"] == 40
    assert rows[0]["note_id"] != rows[1]["note_id"]


def test_same_tick_program_replay_never_uses_later_bank_state():
    program_then_bank = MidiFile(1, 480, [[Event(0, 0, "program", 0, 40, status=0xC0),
        Event(0, 1, "control", 0, 0, 10, 0xB0), Event(0, 2, "control", 0, 32, 2, 0xB0),
        *note_pair(order=3)]])
    row = join_note_context(program_then_bank, SHA, exact_metadata(), "NORMAL")[0]
    assert row["program"] == 40 and row["bank_msb"] is None and row["bank_lsb"] is None
    assert row["program_status"] == "PROGRAM_PARTIAL_UNSPECIFIED_BANK"
    bank_then_note_then_program = MidiFile(1, 480, [[Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0), Event(0, 2, "note_on", 0, 60, 80, 0x90),
        Event(0, 3, "program", 0, 40, status=0xC0), Event(120, 4, "note_off", 0, 60, 0, 0x80)]])
    row = join_note_context(bank_then_note_then_program, SHA, exact_metadata(), "NORMAL")[0]
    assert row["program"] is None and row["program_status"] == "PROGRAM_DEFAULT_UNSPECIFIED"


def test_same_tick_bank_then_program_then_note_is_exact_attribution():
    midi = MidiFile(1, 480, [[Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0), Event(0, 2, "program", 0, 40, status=0xC0),
        *note_pair(order=3)]])
    row = join_note_context(midi, SHA, exact_metadata(), "NORMAL")[0]
    assert (row["bank_msb"], row["bank_lsb"], row["program"]) == (10, 2, 40)
    assert row["program_status"] == "PROGRAM_EXACT"


def test_prior_tick_program_replay_preserves_bank_order_semantics():
    program_then_bank = MidiFile(1, 480, [[Event(0, 0, "program", 0, 40, status=0xC0),
        Event(0, 1, "control", 0, 0, 10, 0xB0), Event(0, 2, "control", 0, 32, 2, 0xB0),
        *note_pair(start=120, end=240, order=3)]])
    row = join_note_context(program_then_bank, SHA, exact_metadata(), "NORMAL")[0]
    assert row["program_status"] == "PROGRAM_PARTIAL_UNSPECIFIED_BANK"
    assert row["bank_msb"] is None and row["bank_lsb"] is None
    bank_then_program = MidiFile(1, 480, [[Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "control", 0, 32, 2, 0xB0), Event(0, 2, "program", 0, 40, status=0xC0),
        *note_pair(start=120, end=240, order=3)]])
    row = join_note_context(bank_then_program, SHA, exact_metadata(), "NORMAL")[0]
    assert (row["bank_msb"], row["bank_lsb"], row["program"]) == (10, 2, 40)


def test_multiple_same_track_programs_at_same_tick_follow_each_note_order():
    midi = MidiFile(1, 480, [[Event(0, 0, "program", 0, 10, status=0xC0),
        Event(0, 1, "note_on", 0, 60, 80, 0x90), Event(0, 2, "program", 0, 11, status=0xC0),
        Event(0, 3, "note_on", 0, 62, 80, 0x90), Event(120, 4, "note_off", 0, 60, 0, 0x80),
        Event(120, 5, "note_off", 0, 62, 0, 0x80)]])
    rows = join_note_context(midi, SHA, exact_metadata(), "NORMAL")
    assert [row["program"] for row in rows] == [10, 11]
    assert all(row["program_status"] == "PROGRAM_PARTIAL_UNSPECIFIED_BANK" for row in rows)
    segments = [row for row in build_channel_context(midi, SHA)["program_segments"]
                if row["channel"] == 0 and row["status"] != "PROGRAM_DEFAULT_UNSPECIFIED"]
    assert segments[-1]["program"] == 11
    assert all(row["status"] != "PROGRAM_CONFLICT" for row in segments)


def test_cross_track_identical_deduplicates_and_conflict_preserves():
    identical = MidiFile(1, 480, [[Event(0, 0, "program", 0, 9, status=0xC0)],
        [Event(0, 0, "program", 0, 9, status=0xC0)]])
    events = build_channel_context(identical, SHA)["channel_state_events"]
    assert len([row for row in events if row["event_kind"] == "program"]) == 1
    assert len(events[0]["evidence_locators"]) == 2
    conflict = MidiFile(1, 480, [[Event(0, 0, "program", 0, 9, status=0xC0)],
        [Event(0, 0, "program", 0, 10, status=0xC0), *note_pair(order=1)]])
    rows = join_note_context(conflict, SHA, exact_metadata(), "NORMAL")
    assert rows[0]["program_status"] == "PROGRAM_SAME_TICK_AMBIGUOUS"
    assert rows[0]["eligibility_status"] == "PROTECTED_CONTEXT"


def test_cross_track_bank_program_order_and_global_meta_conflicts():
    midi = MidiFile(1, 480, [[Event(0, 0, "control", 0, 0, 10, 0xB0),
        Event(0, 1, "meta", data1=0x58, raw=bytes((4, 2, 24, 8))),
        Event(0, 2, "meta", data1=0x51, raw=(500000).to_bytes(3, "big"))],
        [Event(0, 0, "program", 0, 9, status=0xC0),
         Event(0, 1, "meta", data1=0x58, raw=bytes((3, 2, 24, 8))),
         Event(0, 2, "meta", data1=0x51, raw=(600000).to_bytes(3, "big")), *note_pair(order=3)]])
    timelines = build_channel_context(midi, SHA)
    assert any(row["status"] == "PROGRAM_CONFLICT" for row in timelines["program_segments"] if row["channel"] == 0 and row["start_tick"] == 0)
    assert timelines["meter_segments"][0]["status"] == "METER_CONFLICT"
    assert timelines["tempo_segments"][0]["status"] == "TEMPO_CONFLICT"


def test_partial_cross_track_bank_program_combination_is_conflict():
    midi = MidiFile(1, 480, [[Event(0, 0, "control", 0, 0, 10, 0xB0)],
        [Event(0, 0, "control", 0, 32, 2, 0xB0), Event(0, 1, "program", 0, 40, status=0xC0),
         *note_pair(order=2)]])
    timelines = build_channel_context(midi, SHA)
    assert any(row["status"] == "PROGRAM_CONFLICT" for row in timelines["program_segments"] if row["channel"] == 0)
    assert join_note_context(midi, SHA, exact_metadata(), "NORMAL")[0]["program_status"] == "PROGRAM_SAME_TICK_AMBIGUOUS"


def test_unknown_role_and_non_normal_quality_preserve_without_fallback():
    midi = MidiFile(1, 480, [note_pair()])
    row = join_note_context(midi, SHA, exact_metadata(role="UNKNOWN", role_status="UNKNOWN"), "RARE")[0]
    assert "UNKNOWN_ROLE" in row["preservation_reasons"]
    assert "QUALITY_RARE" in row["preservation_reasons"]
    assert row["exact_context_key"] is None


def test_numbered_section_without_number_is_not_exact():
    midi = MidiFile(1, 480, [note_pair()])
    row = join_note_context(midi, SHA, exact_metadata(section_no=None), "NORMAL")[0]
    assert "SECTION_NO_UNKNOWN" in row["preservation_reasons"]


def test_missing_metadata_value_method_or_locator_blocks_exact_eligibility():
    midi = MidiFile(1, 480, [note_pair()])
    cases = ({"role_method": None}, {"role_method": "HEURISTIC_GUESS"}, {"role": ""},
             {"style_locator": None}, {"section": None},
             {"section_no": -1}, {"cv": None}, {"cv_method": None})
    for override in cases:
        row = join_note_context(midi, SHA, exact_metadata(**override), "NORMAL", clear_adapters())[0]
        assert row["eligibility_status"] == "PROTECTED_CONTEXT"
        assert any("PROVENANCE_INCOMPLETE" in reason or reason == "SECTION_NO_UNKNOWN"
                   for reason in row["preservation_reasons"])


def test_absent_required_adapters_are_explicit_fail_closed_observations():
    midi = MidiFile(1, 480, [note_pair()])
    row = join_note_context(midi, SHA, exact_metadata(), "NORMAL")[0]
    required = {key for key, _version in REQUIRED_PROTECTION_RULES}
    unavailable = {item["rule_key"] for item in row["protection_observations"]
                   if item["detection_status"] == "ADAPTER_UNAVAILABLE"}
    assert unavailable == required
    assert row["eligibility_status"] == "PROTECTED_CONTEXT"
    assert any(reason.startswith("PRESERVE_UNTIL_IMPLEMENTED:") for reason in row["preservation_reasons"])