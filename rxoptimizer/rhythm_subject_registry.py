"""Canonical stable subjects for the X10 ANALYZE_ONLY pipeline.

This module deliberately has no SQLite or MIDI mutation responsibility.  It
defines the portable identity contract used by protection adapters and later
schema-v2 materialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping


SUBJECT_CONTRACT_VERSION = "X10_STABLE_SUBJECT_V1"
SUBJECT_TYPES = (
    "EVENT",
    "NOTE",
    "ONSET_CLUSTER",
    "BAR",
    "PHRASE",
    "COMPONENT",
    "BOUNDARY",
    "TRACK_CHANNEL",
    "PROGRAM_SEGMENT",
    "EXACT_CONTEXT",
)

# Direction is containment/evidence-owner -> contained/evidence-member.
EDGE_TYPE_DOMAINS: Mapping[str, tuple[str, str]] = {
    "TRACK_CHANNEL_CONTAINS_EVENT": ("TRACK_CHANNEL", "EVENT"),
    "TRACK_CHANNEL_CONTAINS_NOTE": ("TRACK_CHANNEL", "NOTE"),
    "NOTE_HAS_ON_EVENT": ("NOTE", "EVENT"),
    "NOTE_HAS_OFF_EVENT": ("NOTE", "EVENT"),
    "BAR_CONTAINS_ONSET_CLUSTER": ("BAR", "ONSET_CLUSTER"),
    "ONSET_CLUSTER_CONTAINS_NOTE": ("ONSET_CLUSTER", "NOTE"),
    "PHRASE_CONTAINS_NOTE": ("PHRASE", "NOTE"),
    "COMPONENT_CONTAINS_NOTE": ("COMPONENT", "NOTE"),
    "BOUNDARY_TOUCHES_BAR": ("BOUNDARY", "BAR"),
    "BOUNDARY_TOUCHES_NOTE": ("BOUNDARY", "NOTE"),
    "PROGRAM_SEGMENT_CONTAINS_NOTE": ("PROGRAM_SEGMENT", "NOTE"),
    "EXACT_CONTEXT_CONTAINS_NOTE": ("EXACT_CONTEXT", "NOTE"),
}
EDGE_TYPES = tuple(EDGE_TYPE_DOMAINS)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _validate_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _canonicalize(value: Any) -> Any:
    """Return a JSON-safe deterministic value and reject ambiguous keys."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        raise ValueError("Stable natural keys cannot contain floats")
    if isinstance(value, Mapping):
        result = {}
        if any(not isinstance(key, str) or not key for key in value):
            raise ValueError("Stable natural-key mapping keys must be non-empty strings")
        for key in sorted(value):
            result[key] = _canonicalize(value[key])
        return result
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    raise ValueError(f"Unsupported stable natural-key value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(_canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalize_subject_natural_key(subject_type: str, natural_key: Any) -> Any:
    normalized = _canonicalize(natural_key)
    if subject_type == "ONSET_CLUSTER" and isinstance(normalized, dict):
        membership_keys = [key for key in ("on_event_ids", "members", "note_ids") if key in normalized]
        if len(membership_keys) != 1:
            raise ValueError("ONSET_CLUSTER natural key requires exactly one membership list")
        key = membership_keys[0]
        members = normalized[key]
        if not isinstance(members, list) or not members:
            raise ValueError("ONSET_CLUSTER membership must be a non-empty list")
        if len(members) != len({canonical_json(member) for member in members}):
            raise ValueError("ONSET_CLUSTER membership cannot contain duplicates")
        normalized[key] = sorted(members, key=canonical_json)
    if subject_type in {"PHRASE", "COMPONENT"} and isinstance(normalized, dict):
        membership_keys = [key for key in ("ordered_note_ids", "note_ids", "members") if key in normalized]
        if len(membership_keys) != 1:
            raise ValueError(f"{subject_type} natural key requires exactly one ordered membership list")
        members = normalized[membership_keys[0]]
        if not isinstance(members, list) or not members:
            raise ValueError(f"{subject_type} membership must be a non-empty ordered list")
        if len(members) != len({canonical_json(member) for member in members}):
            raise ValueError(f"{subject_type} membership cannot contain duplicates")
    return normalized


def stable_subject_id(
    subject_type: str,
    source_sha256: str,
    natural_key: Any,
    contract_version: str = SUBJECT_CONTRACT_VERSION,
) -> str:
    if subject_type not in SUBJECT_TYPES:
        raise ValueError(f"Unknown stable subject type: {subject_type}")
    _validate_sha256(source_sha256, "source_sha256")
    if not isinstance(contract_version, str) or not contract_version:
        raise ValueError("contract_version is required")
    normalized = _normalize_subject_natural_key(subject_type, natural_key)
    if normalized in ({}, []):
        raise ValueError("Stable subject natural_key cannot be empty")
    payload = [contract_version, subject_type, source_sha256, normalized]
    return sha256(canonical_json(payload).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class StableSubject:
    subject_type: str
    source_sha256: str
    natural_key: Any
    contract_version: str = SUBJECT_CONTRACT_VERSION
    subject_id: str = field(init=False)

    def __post_init__(self) -> None:
        normalized = _normalize_subject_natural_key(self.subject_type, self.natural_key)
        object.__setattr__(self, "natural_key", normalized)
        object.__setattr__(self, "subject_id", stable_subject_id(
            self.subject_type, self.source_sha256, normalized, self.contract_version))

    @property
    def semantic_record(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "subject_type": self.subject_type,
            "source_sha256": self.source_sha256,
            "natural_key": self.natural_key,
            "subject_id": self.subject_id,
        }


@dataclass(frozen=True)
class StableSubjectEdge:
    edge_type: str
    parent_subject_id: str
    child_subject_id: str
    source_sha256: str
    contract_version: str = SUBJECT_CONTRACT_VERSION
    edge_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.edge_type not in EDGE_TYPE_DOMAINS:
            raise ValueError(f"Unknown stable edge type: {self.edge_type}")
        _validate_sha256(self.parent_subject_id, "parent_subject_id")
        _validate_sha256(self.child_subject_id, "child_subject_id")
        _validate_sha256(self.source_sha256, "source_sha256")
        if self.parent_subject_id == self.child_subject_id:
            raise ValueError("Stable subject self-cycle is forbidden")
        payload = [self.contract_version, self.edge_type, self.source_sha256,
                   self.parent_subject_id, self.child_subject_id]
        object.__setattr__(self, "edge_id", sha256(canonical_json(payload).encode("ascii")).hexdigest())


class StableSubjectRegistry:
    """In-memory validator used before a disk-backed schema-v2 merge."""

    def __init__(self) -> None:
        self._subjects: dict[str, StableSubject] = {}
        self._natural_keys: dict[tuple[str, str, str, str], str] = {}
        self._edges: dict[str, StableSubjectEdge] = {}

    @property
    def subjects(self) -> tuple[StableSubject, ...]:
        return tuple(self._subjects[key] for key in sorted(self._subjects))

    @property
    def edges(self) -> tuple[StableSubjectEdge, ...]:
        return tuple(self._edges[key] for key in sorted(self._edges))

    def add_subject(self, subject: StableSubject) -> StableSubject:
        if not isinstance(subject, StableSubject):
            raise TypeError("subject must be StableSubject")
        natural = (subject.contract_version, subject.subject_type, subject.source_sha256,
                   canonical_json(subject.natural_key))
        previous_id = self._natural_keys.get(natural)
        if previous_id is not None and previous_id != subject.subject_id:
            raise ValueError("Contradictory stable subject natural key")
        previous = self._subjects.get(subject.subject_id)
        if previous is not None and previous.semantic_record != subject.semantic_record:
            raise ValueError("Contradictory stable subject ID")
        self._subjects[subject.subject_id] = subject
        self._natural_keys[natural] = subject.subject_id
        return subject

    def add_edge(self, edge: StableSubjectEdge) -> StableSubjectEdge:
        if not isinstance(edge, StableSubjectEdge):
            raise TypeError("edge must be StableSubjectEdge")
        parent = self._subjects.get(edge.parent_subject_id)
        child = self._subjects.get(edge.child_subject_id)
        if parent is None or child is None:
            raise ValueError("Stable edge endpoints must already be registered")
        if parent.source_sha256 != child.source_sha256 or parent.source_sha256 != edge.source_sha256:
            raise ValueError("Cross-source stable subject edges are forbidden")
        if not (parent.contract_version == child.contract_version == edge.contract_version):
            raise ValueError("Stable edge and endpoint contract versions must match")
        expected = EDGE_TYPE_DOMAINS[edge.edge_type]
        if (parent.subject_type, child.subject_type) != expected:
            raise ValueError(f"Edge {edge.edge_type} requires {expected[0]} -> {expected[1]}")
        previous = self._edges.get(edge.edge_id)
        if previous is not None and previous != edge:
            raise ValueError("Contradictory stable edge ID")
        self._edges[edge.edge_id] = edge
        try:
            self._assert_acyclic()
        except Exception:
            if previous is None:
                self._edges.pop(edge.edge_id, None)
            raise
        return edge

    def extend_subjects(self, subjects: Iterable[StableSubject]) -> None:
        for subject in subjects:
            self.add_subject(subject)

    def _assert_acyclic(self) -> None:
        adjacency: dict[str, list[str]] = {}
        for edge in self._edges.values():
            adjacency.setdefault(edge.parent_subject_id, []).append(edge.child_subject_id)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("Forbidden stable subject edge cycle")
            if node in visited:
                return
            visiting.add(node)
            for child in sorted(adjacency.get(node, ())):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(self._subjects):
            visit(node)

    def semantic_digest(self) -> str:
        payload = {
            "contract_version": SUBJECT_CONTRACT_VERSION,
            "subjects": [subject.semantic_record for subject in self.subjects],
            "edges": [{
                "contract_version": edge.contract_version,
                "edge_type": edge.edge_type,
                "source_sha256": edge.source_sha256,
                "parent_subject_id": edge.parent_subject_id,
                "child_subject_id": edge.child_subject_id,
                "edge_id": edge.edge_id,
            } for edge in self.edges],
        }
        return sha256(canonical_json(payload).encode("ascii")).hexdigest()