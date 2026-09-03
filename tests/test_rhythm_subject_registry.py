from dataclasses import replace

import pytest

from rxoptimizer.rhythm_subject_registry import (
    SUBJECT_CONTRACT_VERSION,
    StableSubject,
    StableSubjectEdge,
    StableSubjectRegistry,
    canonical_json,
    stable_subject_id,
)


SOURCE = "1" * 64


def subject(subject_type, **key):
    return StableSubject(subject_type, SOURCE, key)


def test_stable_subject_id_is_canonical_repeatable_and_type_scoped():
    left = stable_subject_id("NOTE", SOURCE, {"track": 2, "members": ["b", "a"]})
    right = stable_subject_id("NOTE", SOURCE, {"members": ["b", "a"], "track": 2})
    assert left == right
    assert left != stable_subject_id("EVENT", SOURCE, {"track": 2, "members": ["b", "a"]})
    assert left != stable_subject_id("NOTE", SOURCE, {"track": 2, "members": ["a", "b"]})
    assert left != stable_subject_id("NOTE", SOURCE, {"track": 2, "members": ["b", "a"]}, "V2")


def test_onset_cluster_membership_is_sorted_but_phrase_and_component_order_is_semantic():
    first = stable_subject_id("ONSET_CLUSTER", SOURCE, {"on_event_ids": ["e2", "e1"], "tick": 10})
    second = stable_subject_id("ONSET_CLUSTER", SOURCE, {"tick": 10, "on_event_ids": ["e1", "e2"]})
    assert first == second
    assert stable_subject_id("PHRASE", SOURCE, {"note_ids": ["n1", "n2"]}) != stable_subject_id(
        "PHRASE", SOURCE, {"note_ids": ["n2", "n1"]})
    assert stable_subject_id("COMPONENT", SOURCE, {"ordered_note_ids": ["n1", "n2"]}) != stable_subject_id(
        "COMPONENT", SOURCE, {"ordered_note_ids": ["n2", "n1"]})
    with pytest.raises(ValueError, match="duplicates"):
        stable_subject_id("ONSET_CLUSTER", SOURCE, {"on_event_ids": ["e1", "e1"]})
    with pytest.raises(ValueError, match="ordered membership"):
        stable_subject_id("PHRASE", SOURCE, {"start_tick": 0, "end_tick": 10})


def test_natural_keys_reject_float_empty_unknown_and_noncanonical_values():
    with pytest.raises(ValueError, match="floats"):
        subject("NOTE", phase=0.5)
    with pytest.raises(ValueError, match="empty"):
        StableSubject("NOTE", SOURCE, {})
    with pytest.raises(ValueError, match="Unknown"):
        StableSubject("UNKNOWN", SOURCE, {"id": 1})
    with pytest.raises(ValueError, match="Unsupported"):
        StableSubject("NOTE", SOURCE, {"set": {1, 2}})
    with pytest.raises(ValueError, match="mapping keys"):
        StableSubject("NOTE", SOURCE, {1: "invalid"})
    with pytest.raises(ValueError, match="lowercase"):
        StableSubject("NOTE", "A" * 64, {"id": 1})


def test_registry_edges_enforce_registered_type_source_and_no_self_cycle():
    registry = StableSubjectRegistry()
    track = registry.add_subject(subject("TRACK_CHANNEL", track=0, channel=1))
    note = registry.add_subject(subject("NOTE", note_id="n1"))
    edge = StableSubjectEdge("TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, note.subject_id, SOURCE)
    assert registry.add_edge(edge) == edge
    assert registry.add_edge(edge) == edge  # idempotent
    with pytest.raises(ValueError, match="requires"):
        registry.add_edge(StableSubjectEdge("NOTE_HAS_ON_EVENT", track.subject_id, note.subject_id, SOURCE))
    with pytest.raises(ValueError, match="self-cycle"):
        StableSubjectEdge("TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, track.subject_id, SOURCE)


def test_edge_contract_version_must_match_both_endpoints():
    registry = StableSubjectRegistry()
    track = registry.add_subject(StableSubject("TRACK_CHANNEL", SOURCE, {"track": 0}, "V2"))
    note = registry.add_subject(StableSubject("NOTE", SOURCE, {"note": 60}, "V2"))
    with pytest.raises(ValueError, match="contract versions"):
        registry.add_edge(StableSubjectEdge(
            "TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, note.subject_id, SOURCE,
            contract_version=SUBJECT_CONTRACT_VERSION))


def test_registry_rejects_cross_source_and_missing_endpoints():
    registry = StableSubjectRegistry()
    track = registry.add_subject(subject("TRACK_CHANNEL", track=0, channel=1))
    other = StableSubject("NOTE", "2" * 64, {"note_id": "n2"})
    registry.add_subject(other)
    with pytest.raises(ValueError, match="Cross-source"):
        registry.add_edge(StableSubjectEdge(
            "TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, other.subject_id, SOURCE))
    missing = "3" * 64
    with pytest.raises(ValueError, match="endpoints"):
        registry.add_edge(StableSubjectEdge(
            "TRACK_CHANNEL_CONTAINS_NOTE", track.subject_id, missing, SOURCE))


def test_multiple_memberships_are_preserved_and_digest_is_insert_order_independent():
    def build(reverse=False):
        registry = StableSubjectRegistry()
        phrase = subject("PHRASE", track=0, note_ids=["n1", "n2"])
        component = subject("COMPONENT", kind="TRILL", note_ids=["n1", "n2"])
        note = subject("NOTE", note_id="n1")
        items = [phrase, component, note]
        registry.extend_subjects(reversed(items) if reverse else items)
        edges = [
            StableSubjectEdge("PHRASE_CONTAINS_NOTE", phrase.subject_id, note.subject_id, SOURCE),
            StableSubjectEdge("COMPONENT_CONTAINS_NOTE", component.subject_id, note.subject_id, SOURCE),
        ]
        for edge in reversed(edges) if reverse else edges:
            registry.add_edge(edge)
        return registry
    first, second = build(), build(True)
    assert len(first.edges) == 2
    assert first.semantic_digest() == second.semantic_digest()


def test_subject_record_and_canonical_json_do_not_depend_on_python_identity():
    first = subject("BAR", meter_segment_id="m1", start_tick=0, end_tick=1920)
    second = subject("BAR", end_tick=1920, start_tick=0, meter_segment_id="m1")
    assert first == second
    assert first.subject_id == second.subject_id
    assert canonical_json(first.semantic_record) == canonical_json(second.semantic_record)
    assert first.contract_version == SUBJECT_CONTRACT_VERSION