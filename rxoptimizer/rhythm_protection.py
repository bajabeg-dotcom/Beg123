"""Sparse protection protocol and final ANALYZE_ONLY authorization for X10."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Iterable, Mapping

from .rhythm_subject_registry import (
    EDGE_TYPES,
    SUBJECT_TYPES,
    canonical_json,
)


PROTECTION_CONTRACT_VERSION = "X10_PROTECTION_V1"
REQUIRED_PROTECTION_RULES = (
    "GUITAR_MODE",
    "RX_DNC",
    "ORNAMENT_TRILL_GRACE",
    "DRUM_FLAM_ROLL_GHOST",
    "CROSS_BAR",
    "SECTION_TRANSITION",
    "TEMPO_METER_BOUNDARY",
    "LOCAL_REPEATED_PATTERN",
    "FACTORY_REFERENCE_CONFLICT",
)
CANONICAL_ADAPTER_CLASSES: Mapping[str, str] = {
    **{rule: "CORE_REQUIRED" for rule in REQUIRED_PROTECTION_RULES
       if rule not in {"RX_DNC", "FACTORY_REFERENCE_CONFLICT"}},
    "RX_DNC": "EXTERNAL_OPTIONAL_FAIL_CLOSED",
    "FACTORY_REFERENCE_CONFLICT": "POST_MODEL_REQUIRED",
}
ADAPTER_CLASSES = ("CORE_REQUIRED", "EXTERNAL_OPTIONAL_FAIL_CLOSED", "POST_MODEL_REQUIRED")
ADAPTER_RUN_STATUSES = (
    "COMPLETE", "PARTIAL", "DEPENDENCY_UNAVAILABLE", "DEFERRED_POST_MODEL",
    "NOT_APPLICABLE", "FAILED_CONTRACT", "FAILED_RUNTIME",
)
PER_RULE_PROTECTION_STATUSES = (
    "CLEAR", "NOT_APPLICABLE", "DETECTED", "AMBIGUOUS", "EVIDENCE_UNJOINABLE",
    "DEPENDENCY_GAP", "DEFERRED", "PARTIAL_UNRESOLVED",
)
FACTORY_MODEL_STATUSES = ("FACTORY_SUFFICIENT", "FACTORY_INSUFFICIENT", "FACTORY_UNAVAILABLE")
CANDIDATE_FIT_STATUSES = (
    "VALID_CONVERGED", "INVALID_EMPTY_INITIAL_COMPONENT", "INVALID_COMPONENT_COLLAPSE",
    "INVALID_COMPONENT_INSUFFICIENT", "INVALID_IDENTIFIABILITY",
    "INVALID_NONFINITE_LIKELIHOOD", "INVALID_NUMERICAL_CONSTRAINT",
)
MODALITY_STATUSES = (
    "ASSESSED_UNIMODAL", "ASSESSED_MULTIMODAL", "DEGENERATE_EXACT_REFERENCE",
    "INSUFFICIENT_MODAL_EVIDENCE", "UNSTABLE_MODAL_STRUCTURE", "UNSTABLE_BIC_NEAR_TIE",
    "UNSTABLE_COMPONENT_MATCH", "UNSTABLE_GROOVE_MODE_STRUCTURE", "UNSTABLE_POSTERIOR_TIE",
    "UNSTABLE_COMPONENT_COLLAPSE", "NUMERICAL_REVIEW_REQUIRED",
    "NUMERICAL_CYCLE_REVIEW_REQUIRED", "NUMERICAL_NONCONVERGENCE_REVIEW_REQUIRED", "DEFERRED",
)
REFERENCE_RELATIONSHIP_STATUSES = (
    "REFERENCE_SUPPORT", "NO_REFERENCE_EVIDENCE", "INSUFFICIENT_REFERENCE_EVIDENCE",
    "POTENTIAL_CONTRADICTION", "FACTORY_SUPPORT_UNINFORMATIVE",
    "DEFERRED_FACTORY_MODEL_UNSTABLE", "POST_MODEL_PARTIAL",
)
PROTECTION_AGGREGATE_STATUSES = (
    "PROTECTION_CLEAR", "PROTECTED_DETECTED", "PROTECTION_UNRESOLVED",
    "EXTERNAL_EVIDENCE_GAP", "PROTECTION_SCAN_PARTIAL", "PROTECTION_DEFERRED",
    "PROTECTION_CONTRACT_INCOMPLETE",
)
FINAL_AUTHORIZATION_STATUSES = (
    "EXCLUDED_INVALID_SOURCE", "PRESERVE_SOURCE_QUALITY", "PRESERVE_CONTEXT_UNPROVEN",
    "PRESERVE_CORE_SCAN_PARTIAL", "PROTECTED_DETECTED", "PRESERVE_PROTECTION_UNRESOLVED",
    "PRESERVE_EXTERNAL_EVIDENCE_GAP", "PRESERVE_PROTECTION_SCAN_PARTIAL",
    "PRESERVE_PROTECTION_DEFERRED", "PRESERVE_PROTECTION_CONTRACT_INCOMPLETE",
    "INSUFFICIENT_FACTORY_EVIDENCE", "ZERO_VARIANCE_REVIEW", "PRESERVE_MODALITY_INSUFFICIENT",
    "PRESERVE_MODALITY_UNSTABLE", "PRESERVE_MODALITY_DEFERRED", "PRESERVE_MULTIMODAL_CONTEXT",
    "PRESERVE_REFERENCE_GATE_PARTIAL", "PRESERVE_REFERENCE_GATE_DEFERRED",
    "REVIEW_FACTORY_REFERENCE_CONFLICT", "PRESERVE_FACTORY_SUPPORT_UNINFORMATIVE", "ANALYZE_ALLOWED",
)
BUILD_TERMINAL_STATUSES = (
    "BUILD_COMPLETE", "BUILD_ABORT_SOURCE_CONTRACT", "BUILD_ABORT_SCHEMA_CONTRACT",
    "BUILD_ABORT_STABLE_ID_CONTRACT", "BUILD_ABORT_ADAPTER_CONTRACT",
    "BUILD_ABORT_ADAPTER_RUNTIME", "BUILD_ABORT_NUMERICAL_CONTRACT", "BUILD_ABORT_INTEGRITY",
    "BUILD_ABORT_DIGEST", "BUILD_ABORT_FORBIDDEN_SOURCE",
)
SOURCE_QUALITY_STATUSES = ("NORMAL", "RARE", "OUTLIER", "INVALID")
CONTEXT_ELIGIBILITY_STATUSES = ("EXACT_CONTEXT_MATCH", "CONTEXT_UNPROVEN", "CONTEXT_CONFLICT")
PARTITION_STATUSES = ("COMPLETE", "PARTIAL")

ENUM_DOMAINS: Mapping[str, tuple[str, ...]] = {
    "subject_type": SUBJECT_TYPES,
    "edge_type": EDGE_TYPES,
    "protection_rule": REQUIRED_PROTECTION_RULES,
    "adapter_class": ADAPTER_CLASSES,
    "adapter_run": ADAPTER_RUN_STATUSES,
    "per_rule_protection": PER_RULE_PROTECTION_STATUSES,
    "factory_model": FACTORY_MODEL_STATUSES,
    "candidate_fit": CANDIDATE_FIT_STATUSES,
    "modality": MODALITY_STATUSES,
    "reference_relationship": REFERENCE_RELATIONSHIP_STATUSES,
    "protection_aggregate": PROTECTION_AGGREGATE_STATUSES,
    "final_authorization": FINAL_AUTHORIZATION_STATUSES,
    "build_terminal": BUILD_TERMINAL_STATUSES,
    "source_quality": SOURCE_QUALITY_STATUSES,
    "context_eligibility": CONTEXT_ELIGIBILITY_STATUSES,
    "partition": PARTITION_STATUSES,
}


def _domain_payload(domains: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
    return {name: list(values) for name, values in sorted(domains.items())}


def enum_domain_sha256(domains: Mapping[str, Iterable[str]] = ENUM_DOMAINS) -> str:
    return sha256(canonical_json(_domain_payload(domains)).encode("ascii")).hexdigest()


ENUM_DOMAIN_SHA256 = enum_domain_sha256()


def validate_enum_domains(
    domains: Mapping[str, Iterable[str]],
    expected_sha256: str | None = None,
) -> str:
    if set(domains) != set(ENUM_DOMAINS):
        unknown = sorted(set(domains) - set(ENUM_DOMAINS))
        unreachable = sorted(set(ENUM_DOMAINS) - set(domains))
        raise ValueError(f"Enum domain keys differ; unknown={unknown}, unreachable={unreachable}")
    for name, canonical in ENUM_DOMAINS.items():
        values = tuple(domains[name])
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError(f"Enum domain {name} requires non-empty string tokens")
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate enum token in {name}")
        unknown = sorted(set(values) - set(canonical))
        unreachable = sorted(set(canonical) - set(values))
        if unknown or unreachable:
            raise ValueError(f"Enum domain {name} differs; unknown={unknown}, unreachable={unreachable}")
        if values != canonical:
            raise ValueError(f"Enum domain {name} canonical order mismatch")
    digest = enum_domain_sha256(domains)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("enum_domain_sha256 mismatch")
    return digest


def canonical_protection_config(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = {
        "contract_version": PROTECTION_CONTRACT_VERSION,
        "capability": "ANALYZE_ONLY",
        "mutation_capability": "NONE",
        "enum_domain_sha256": ENUM_DOMAIN_SHA256,
        "subject_types": list(SUBJECT_TYPES),
        "edge_types": list(EDGE_TYPES),
        "protection_rules": list(REQUIRED_PROTECTION_RULES),
        "adapter_classes_by_rule": dict(CANONICAL_ADAPTER_CLASSES),
    }
    if extra:
        for key, value in extra.items():
            if key in config and config[key] != value:
                raise ValueError(f"Canonical config field cannot be overridden: {key}")
            config[key] = value
    return config


def protection_config_sha256(extra: Mapping[str, Any] | None = None) -> str:
    return sha256(canonical_json(canonical_protection_config(extra)).encode("ascii")).hexdigest()


def _require_token(value: str, domain: Iterable[str], label: str) -> str:
    if value not in domain:
        raise ValueError(f"Unknown {label}: {value}")
    return value


def _require_digest(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True)
class AdapterContract:
    rule_key: str
    adapter_version: str
    adapter_class: str
    applicability_predicate_version: str
    contract_version: str = PROTECTION_CONTRACT_VERSION
    config_sha256: str = field(default_factory=protection_config_sha256)

    def __post_init__(self) -> None:
        _require_token(self.rule_key, REQUIRED_PROTECTION_RULES, "protection rule")
        _require_token(self.adapter_class, ADAPTER_CLASSES, "adapter class")
        if not self.adapter_version or not self.applicability_predicate_version:
            raise ValueError("Adapter and applicability versions are required")
        _require_digest(self.config_sha256, "config_sha256")
        expected_class = CANONICAL_ADAPTER_CLASSES[self.rule_key]
        if self.adapter_class != expected_class:
            raise ValueError(f"{self.rule_key} must use canonical adapter class {expected_class}")


class AdapterRegistry:
    def __init__(self, expected_config_sha256: str | None = None) -> None:
        # A caller building a full canonical config passes its complete hash.
        expected_config_sha256 = expected_config_sha256 or protection_config_sha256()
        _require_digest(expected_config_sha256, "expected_config_sha256")
        self.expected_config_sha256 = expected_config_sha256
        self._contracts: dict[tuple[str, str], AdapterContract] = {}

    def register(self, contract: AdapterContract) -> AdapterContract:
        if contract.config_sha256 != self.expected_config_sha256:
            raise ValueError("Adapter config hash mismatch")
        key = (contract.rule_key, contract.adapter_version)
        previous = self._contracts.get(key)
        if previous is not None and previous != contract:
            raise ValueError("Conflicting adapter registration")
        self._contracts[key] = contract
        return contract

    @property
    def contracts(self) -> tuple[AdapterContract, ...]:
        return tuple(self._contracts[key] for key in sorted(self._contracts))

    def validate_complete(self) -> None:
        rules = [contract.rule_key for contract in self.contracts]
        missing = sorted(set(REQUIRED_PROTECTION_RULES) - set(rules))
        duplicated = sorted(rule for rule in set(rules) if rules.count(rule) > 1)
        if missing or duplicated:
            raise ValueError(f"Adapter registry incomplete; missing={missing}, duplicate_versions={duplicated}")


@dataclass(frozen=True)
class AdapterRun:
    source_sha256: str
    contract: AdapterContract
    scope_type: str
    scope_subject_id: str
    subject_universe_query_version: str
    subject_universe_count: int
    subject_universe_sha256: str
    applicable_count: int
    applicable_universe_sha256: str
    scanned_count: int
    resolved_count: int
    protected_count: int
    ambiguous_count: int
    input_sha256: str
    dependency_sha256: str
    result_sha256: str
    run_status: str
    run_id: str = field(init=False)

    def __post_init__(self) -> None:
        for label, digest in (("source_sha256", self.source_sha256),
                              ("scope_subject_id", self.scope_subject_id),
                              ("subject_universe_sha256", self.subject_universe_sha256),
                              ("applicable_universe_sha256", self.applicable_universe_sha256),
                              ("input_sha256", self.input_sha256),
                              ("dependency_sha256", self.dependency_sha256),
                              ("result_sha256", self.result_sha256)):
            _require_digest(digest, label)
        _require_token(self.run_status, ADAPTER_RUN_STATUSES, "adapter run status")
        if self.scope_type not in SUBJECT_TYPES:
            raise ValueError("Adapter scope_type must be a stable subject type")
        counts = (self.subject_universe_count, self.applicable_count, self.scanned_count,
                  self.resolved_count, self.protected_count, self.ambiguous_count)
        if any(not isinstance(value, int) or value < 0 for value in counts):
            raise ValueError("Adapter run counts must be nonnegative integers")
        if not (self.applicable_count <= self.subject_universe_count and
                self.scanned_count <= self.applicable_count and
                self.resolved_count <= self.scanned_count and
                self.protected_count + self.ambiguous_count <= self.resolved_count):
            raise ValueError("Adapter run counts are inconsistent")
        if self.run_status == "COMPLETE" and not (
                self.scanned_count == self.applicable_count == self.resolved_count):
            raise ValueError("COMPLETE adapter run requires full applicable scan and resolution")
        if self.run_status == "PARTIAL" and (
                self.scanned_count == self.applicable_count == self.resolved_count):
            raise ValueError("PARTIAL adapter run must leave applicable subjects unscanned or unresolved")
        if self.run_status == "NOT_APPLICABLE" and any(counts[1:]):
            raise ValueError("NOT_APPLICABLE adapter run must have zero applicable/result counts")
        if self.run_status == "DEPENDENCY_UNAVAILABLE" and self.contract.adapter_class != "EXTERNAL_OPTIONAL_FAIL_CLOSED":
            raise ValueError("Only external optional adapters may preserve a dependency gap")
        if self.run_status == "DEFERRED_POST_MODEL" and self.contract.adapter_class != "POST_MODEL_REQUIRED":
            raise ValueError("Only post-model adapter may be deferred post-model")
        payload = [PROTECTION_CONTRACT_VERSION, self.source_sha256, self.contract.rule_key,
                   self.contract.adapter_version, self.scope_type, self.scope_subject_id,
                   self.subject_universe_sha256, self.applicable_universe_sha256,
                   self.input_sha256, self.dependency_sha256, self.result_sha256]
        object.__setattr__(self, "run_id", sha256(canonical_json(payload).encode("ascii")).hexdigest())


@dataclass(frozen=True)
class CoveragePartition:
    run_id: str
    partition_key: str
    stable_scope_id: str
    applicable_count: int
    scanned_count: int
    resolved_count: int
    applicable_universe_sha256: str
    result_sha256: str
    status: str
    partition_id: str = field(init=False)

    def __post_init__(self) -> None:
        for label, digest in (("run_id", self.run_id), ("stable_scope_id", self.stable_scope_id),
                              ("applicable_universe_sha256", self.applicable_universe_sha256),
                              ("result_sha256", self.result_sha256)):
            _require_digest(digest, label)
        _require_token(self.status, PARTITION_STATUSES, "partition status")
        if not self.partition_key:
            raise ValueError("partition_key is required")
        if any(not isinstance(value, int) or value < 0 for value in
               (self.applicable_count, self.scanned_count, self.resolved_count)):
            raise ValueError("Coverage counts must be nonnegative integers")
        if not self.resolved_count <= self.scanned_count <= self.applicable_count:
            raise ValueError("Coverage partition counts are inconsistent")
        if self.status == "COMPLETE" and not (
                self.applicable_count == self.scanned_count == self.resolved_count):
            raise ValueError("COMPLETE coverage partition requires complete resolution")
        if self.status == "PARTIAL" and (
                self.scanned_count == self.applicable_count == self.resolved_count):
            raise ValueError("PARTIAL coverage partition must leave applicable subjects unscanned or unresolved")
        payload = [self.run_id, self.partition_key, self.stable_scope_id,
                   self.applicable_universe_sha256, self.result_sha256]
        object.__setattr__(self, "partition_id", sha256(canonical_json(payload).encode("ascii")).hexdigest())


@dataclass(frozen=True)
class ProtectionGroup:
    run_id: str
    source_sha256: str
    rule_key: str
    adapter_version: str
    group_natural_key: Any
    per_rule_status: str
    evidence_sha256: str
    group_id: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest(self.run_id, "run_id")
        _require_digest(self.source_sha256, "source_sha256")
        _require_token(self.rule_key, REQUIRED_PROTECTION_RULES, "protection rule")
        _require_token(self.per_rule_status, PER_RULE_PROTECTION_STATUSES, "per-rule protection status")
        _require_digest(self.evidence_sha256, "evidence_sha256")
        if self.per_rule_status in {"CLEAR", "NOT_APPLICABLE"}:
            raise ValueError("Sparse groups may only store non-clear evidence")
        payload = [PROTECTION_CONTRACT_VERSION, self.run_id, self.source_sha256, self.rule_key,
                   self.adapter_version, self.group_natural_key]
        object.__setattr__(self, "group_id", sha256(canonical_json(payload).encode("ascii")).hexdigest())


@dataclass(frozen=True)
class ProtectionGroupMembership:
    group_id: str
    stable_subject_id: str
    membership_role: str = "AFFECTED_SUBJECT"
    membership_id: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest(self.group_id, "group_id")
        _require_digest(self.stable_subject_id, "stable_subject_id")
        if not self.membership_role:
            raise ValueError("membership_role is required")
        payload = [self.group_id, self.stable_subject_id, self.membership_role]
        object.__setattr__(self, "membership_id", sha256(canonical_json(payload).encode("ascii")).hexdigest())


class ProtectionEvidenceRegistry:
    """Natural-key and referential validator for sparse protocol records."""

    def __init__(self, subject_sources: Mapping[str, str] | None = None) -> None:
        self.subject_sources = dict(subject_sources or {})
        for subject_id, source_sha256 in self.subject_sources.items():
            _require_digest(subject_id, "subject_id")
            _require_digest(source_sha256, "subject source_sha256")
        self.runs: dict[str, AdapterRun] = {}
        self.partitions: dict[str, CoveragePartition] = {}
        self.groups: dict[str, ProtectionGroup] = {}
        self.memberships: dict[str, ProtectionGroupMembership] = {}
        self._run_natural_keys: dict[tuple[str, str, str, str, str], str] = {}
        self._run_subject_universe: dict[str, frozenset[str]] = {}
        self._run_applicable_universe: dict[str, frozenset[str]] = {}
        self._partition_natural_keys: dict[tuple[str, str, str], str] = {}
        self._partition_applicable: dict[str, frozenset[str]] = {}
        self._partition_scanned: dict[str, frozenset[str]] = {}
        self._partition_resolved: dict[str, frozenset[str]] = {}

    @staticmethod
    def _insert_unique(target: dict[str, Any], key: str, value: Any, label: str) -> None:
        previous = target.get(key)
        if previous is not None and previous != value:
            raise ValueError(f"Contradictory {label} ID")
        target[key] = value

    def add_run(
        self,
        run: AdapterRun,
        *,
        subject_universe_ids: Iterable[str],
        applicable_subject_ids: Iterable[str],
    ) -> AdapterRun:
        scope_source = self.subject_sources.get(run.scope_subject_id)
        if scope_source is None:
            raise ValueError("Adapter run scope subject is not registered")
        if scope_source != run.source_sha256:
            raise ValueError("Adapter run scope subject belongs to another source")
        if run.run_status in {"FAILED_CONTRACT", "FAILED_RUNTIME"}:
            raise ValueError("Failed adapter run is a build-hard-fail, not evidence")
        universe = tuple(sorted(subject_universe_ids))
        applicable = tuple(sorted(applicable_subject_ids))
        if len(universe) != len(set(universe)) or len(applicable) != len(set(applicable)):
            raise ValueError("Adapter run populations cannot contain duplicate subject IDs")
        for subject_id in (*universe, *applicable):
            _require_digest(subject_id, "adapter run population subject_id")
            if self.subject_sources.get(subject_id) != run.source_sha256:
                raise ValueError("Adapter run population subject is unregistered or belongs to another source")
        if not set(applicable).issubset(universe):
            raise ValueError("Adapter applicable population must be inside subject universe")
        if len(universe) != run.subject_universe_count or len(applicable) != run.applicable_count:
            raise ValueError("Adapter run population counts do not match run")
        universe_digest = sha256(canonical_json(list(universe)).encode("ascii")).hexdigest()
        applicable_digest = sha256(canonical_json(list(applicable)).encode("ascii")).hexdigest()
        if universe_digest != run.subject_universe_sha256:
            raise ValueError("Adapter run subject universe digest mismatch")
        if applicable_digest != run.applicable_universe_sha256:
            raise ValueError("Adapter run applicable universe digest mismatch")
        natural = (run.source_sha256, run.contract.rule_key, run.contract.adapter_version,
                   run.scope_type, run.scope_subject_id)
        previous_id = self._run_natural_keys.get(natural)
        if previous_id is not None and previous_id != run.run_id:
            raise ValueError("Contradictory adapter run natural key")
        self._insert_unique(self.runs, run.run_id, run, "adapter run")
        previous_universe = self._run_subject_universe.get(run.run_id)
        previous_applicable = self._run_applicable_universe.get(run.run_id)
        if previous_universe is not None and previous_universe != frozenset(universe):
            raise ValueError("Contradictory adapter run subject universe")
        if previous_applicable is not None and previous_applicable != frozenset(applicable):
            raise ValueError("Contradictory adapter run applicable universe")
        self._run_natural_keys[natural] = run.run_id
        self._run_subject_universe[run.run_id] = frozenset(universe)
        self._run_applicable_universe[run.run_id] = frozenset(applicable)
        return run

    def add_partition(
        self,
        partition: CoveragePartition,
        *,
        applicable_subject_ids: Iterable[str],
        scanned_subject_ids: Iterable[str],
        resolved_subject_ids: Iterable[str],
    ) -> CoveragePartition:
        run = self.runs.get(partition.run_id)
        if run is None:
            raise ValueError("Coverage partition requires a registered adapter run")
        if run.run_status not in {"COMPLETE", "PARTIAL"}:
            raise ValueError("Coverage partition requires COMPLETE or PARTIAL parent run")
        natural = (partition.run_id, partition.partition_key, partition.stable_scope_id)
        previous_id = self._partition_natural_keys.get(natural)
        if previous_id is not None and previous_id != partition.partition_id:
            raise ValueError("Contradictory coverage partition natural key")
        if partition.stable_scope_id != run.scope_subject_id:
            raise ValueError("Coverage partition scope does not match parent run")
        if (partition.applicable_count != run.applicable_count or
                partition.scanned_count != run.scanned_count or
                partition.resolved_count != run.resolved_count or
                partition.applicable_universe_sha256 != run.applicable_universe_sha256 or
                partition.result_sha256 != run.result_sha256):
            raise ValueError("Coverage partition semantics do not match parent run")
        applicable = tuple(sorted(applicable_subject_ids))
        scanned = tuple(sorted(scanned_subject_ids))
        resolved = tuple(sorted(resolved_subject_ids))
        if (len(applicable) != len(set(applicable)) or len(scanned) != len(set(scanned)) or
                len(resolved) != len(set(resolved))):
            raise ValueError("Coverage populations cannot contain duplicate subject IDs")
        for subject_id in (*applicable, *scanned, *resolved):
            _require_digest(subject_id, "coverage subject_id")
            if self.subject_sources.get(subject_id) != run.source_sha256:
                raise ValueError("Coverage subject is unregistered or belongs to another source")
        if not set(scanned).issubset(applicable):
            raise ValueError("Scanned coverage subjects must be applicable")
        if not set(resolved).issubset(scanned):
            raise ValueError("Resolved coverage subjects must be scanned")
        if (len(applicable) != partition.applicable_count or len(scanned) != partition.scanned_count or
                len(resolved) != partition.resolved_count):
            raise ValueError("Coverage population counts do not match partition")
        population_digest = sha256(canonical_json(list(applicable)).encode("ascii")).hexdigest()
        if population_digest != partition.applicable_universe_sha256:
            raise ValueError("Coverage applicable universe digest mismatch")
        self._insert_unique(self.partitions, partition.partition_id, partition, "coverage partition")
        previous_applicable = self._partition_applicable.get(partition.partition_id)
        previous_scanned = self._partition_scanned.get(partition.partition_id)
        previous_resolved = self._partition_resolved.get(partition.partition_id)
        if previous_applicable is not None and previous_applicable != frozenset(applicable):
            raise ValueError("Contradictory coverage applicable population")
        if previous_scanned is not None and previous_scanned != frozenset(scanned):
            raise ValueError("Contradictory coverage scanned population")
        if previous_resolved is not None and previous_resolved != frozenset(resolved):
            raise ValueError("Contradictory coverage resolved population")
        self._partition_natural_keys[natural] = partition.partition_id
        self._partition_applicable[partition.partition_id] = frozenset(applicable)
        self._partition_scanned[partition.partition_id] = frozenset(scanned)
        self._partition_resolved[partition.partition_id] = frozenset(resolved)
        return partition

    def add_group(self, group: ProtectionGroup) -> ProtectionGroup:
        run = self.runs.get(group.run_id)
        if run is None:
            raise ValueError("Protection group requires a registered adapter run")
        if (group.source_sha256 != run.source_sha256 or
                group.rule_key != run.contract.rule_key or
                group.adapter_version != run.contract.adapter_version):
            raise ValueError("Protection group contract does not match parent run")
        if group.per_rule_status == "DETECTED" and run.protected_count == 0:
            raise ValueError("Detected group contradicts parent run protected count")
        if group.per_rule_status in {"AMBIGUOUS", "EVIDENCE_UNJOINABLE"} and run.ambiguous_count == 0:
            raise ValueError("Ambiguous group contradicts parent run ambiguous count")
        expected_run_status = {
            "DEPENDENCY_GAP": "DEPENDENCY_UNAVAILABLE",
            "DEFERRED": "DEFERRED_POST_MODEL",
            "PARTIAL_UNRESOLVED": "PARTIAL",
        }.get(group.per_rule_status)
        if expected_run_status is not None and run.run_status != expected_run_status:
            raise ValueError("Protection group status contradicts parent run status")
        self._insert_unique(self.groups, group.group_id, group, "protection group")
        return group

    def add_membership(self, membership: ProtectionGroupMembership) -> ProtectionGroupMembership:
        group = self.groups.get(membership.group_id)
        if group is None:
            raise ValueError("Protection membership requires a registered group")
        if self.subject_sources:
            source = self.subject_sources.get(membership.stable_subject_id)
            if source is None:
                raise ValueError("Protection membership subject is not registered")
            if source != group.source_sha256:
                raise ValueError("Cross-source protection membership is forbidden")
        self._insert_unique(self.memberships, membership.membership_id, membership,
                            "protection membership")
        return membership

    def resolve_subject_rule(self, stable_subject_id: str, rule_key: str) -> str:
        _require_token(rule_key, REQUIRED_PROTECTION_RULES, "protection rule")
        source = self.subject_sources.get(stable_subject_id)
        if source is None:
            raise ValueError("Protection subject is not registered")
        statuses = []
        for membership in self.memberships.values():
            if membership.stable_subject_id != stable_subject_id:
                continue
            group = self.groups[membership.group_id]
            if group.rule_key == rule_key:
                statuses.append(group.per_rule_status)
        if statuses:
            precedence = ("DETECTED", "AMBIGUOUS", "EVIDENCE_UNJOINABLE", "DEPENDENCY_GAP",
                          "PARTIAL_UNRESOLVED", "DEFERRED")
            return next(status for status in precedence if status in statuses)
        matching_runs = [run for run in self.runs.values()
                         if run.source_sha256 == source and run.contract.rule_key == rule_key]
        if len(matching_runs) != 1:
            return "PARTIAL_UNRESOLVED"
        run = matching_runs[0]
        if run.run_status == "NOT_APPLICABLE":
            return "NOT_APPLICABLE"
        if run.run_status == "DEPENDENCY_UNAVAILABLE":
            return "DEPENDENCY_GAP"
        if run.run_status == "DEFERRED_POST_MODEL":
            return "DEFERRED"
        if run.run_status != "COMPLETE":
            return "PARTIAL_UNRESOLVED"
        partitions = [partition for partition in self.partitions.values() if partition.run_id == run.run_id]
        if len(partitions) != 1:
            return "PARTIAL_UNRESOLVED"
        partition = partitions[0]
        applicable = self._partition_applicable[partition.partition_id]
        resolved = self._partition_resolved[partition.partition_id]
        if stable_subject_id not in applicable:
            return "NOT_APPLICABLE"
        if partition.status == "COMPLETE" and stable_subject_id in resolved:
            return "CLEAR"
        return "PARTIAL_UNRESOLVED"


def sparse_rule_status(
    registry: ProtectionEvidenceRegistry,
    stable_subject_id: str,
    rule_key: str,
) -> str:
    """Resolve sparse absence only from registered coverage populations."""
    if not isinstance(registry, ProtectionEvidenceRegistry):
        raise TypeError("registry must be ProtectionEvidenceRegistry")
    return registry.resolve_subject_rule(stable_subject_id, rule_key)


def aggregate_protection_status(per_rule_statuses: Mapping[str, str] | Iterable[tuple[str, str]]) -> str:
    if isinstance(per_rule_statuses, Mapping):
        items = tuple(per_rule_statuses.items())
    else:
        try:
            items = tuple(per_rule_statuses)
        except TypeError as exc:
            raise TypeError("per_rule_statuses must contain rule-keyed results") from exc
        if any(not isinstance(item, (tuple, list)) or len(item) != 2 for item in items):
            raise TypeError("per_rule_statuses must contain rule-keyed results")
    keys = tuple(item[0] for item in items)
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate protection rule result")
    results = dict(items)
    unknown = sorted(set(keys) - set(REQUIRED_PROTECTION_RULES))
    missing = sorted(set(REQUIRED_PROTECTION_RULES) - set(keys))
    if unknown or missing or len(keys) != len(REQUIRED_PROTECTION_RULES):
        raise ValueError(f"Protection rule results incomplete; unknown={unknown}, missing={missing}")
    statuses = tuple(results[rule] for rule in REQUIRED_PROTECTION_RULES)
    for status in statuses:
        _require_token(status, PER_RULE_PROTECTION_STATUSES, "per-rule protection status")
    if "DETECTED" in statuses:
        return "PROTECTED_DETECTED"
    if "AMBIGUOUS" in statuses or "EVIDENCE_UNJOINABLE" in statuses:
        return "PROTECTION_UNRESOLVED"
    if "DEPENDENCY_GAP" in statuses:
        return "EXTERNAL_EVIDENCE_GAP"
    if "PARTIAL_UNRESOLVED" in statuses:
        return "PROTECTION_SCAN_PARTIAL"
    if "DEFERRED" in statuses:
        return "PROTECTION_DEFERRED"
    if all(status in {"CLEAR", "NOT_APPLICABLE"} for status in statuses):
        return "PROTECTION_CLEAR"
    return "PROTECTION_CONTRACT_INCOMPLETE"


@dataclass(frozen=True)
class AuthorizationDecision:
    authorization_status: str
    analysis_allowed: bool
    proposal_allowed: bool = False
    repair_allowed: bool = False
    mutation_capability: str = "NONE"
    capability: str = "ANALYZE_ONLY"

    def __post_init__(self) -> None:
        _require_token(self.authorization_status, FINAL_AUTHORIZATION_STATUSES, "final authorization status")
        expected = self.authorization_status == "ANALYZE_ALLOWED"
        if self.analysis_allowed != expected:
            raise ValueError("analysis_allowed must exactly match ANALYZE_ALLOWED")
        if self.proposal_allowed or self.repair_allowed or self.mutation_capability != "NONE":
            raise ValueError("X10 protection authorization is ANALYZE_ONLY")


_UNSTABLE_MODALITY = {
    "UNSTABLE_MODAL_STRUCTURE", "UNSTABLE_BIC_NEAR_TIE", "UNSTABLE_COMPONENT_MATCH",
    "UNSTABLE_GROOVE_MODE_STRUCTURE", "UNSTABLE_POSTERIOR_TIE", "UNSTABLE_COMPONENT_COLLAPSE",
    "NUMERICAL_REVIEW_REQUIRED", "NUMERICAL_CYCLE_REVIEW_REQUIRED",
    "NUMERICAL_NONCONVERGENCE_REVIEW_REQUIRED",
}


def final_analysis_authorization(
    *,
    source_quality_status: str,
    context_eligibility_status: str,
    core_scan_complete: bool,
    protection_status: str,
    factory_model_status: str,
    modality_status: str,
    reference_relationship_status: str,
) -> AuthorizationDecision:
    """Exhaustive fail-closed S5 truth function from the locked precedence."""
    _require_token(source_quality_status, SOURCE_QUALITY_STATUSES, "source quality status")
    _require_token(context_eligibility_status, CONTEXT_ELIGIBILITY_STATUSES, "context status")
    _require_token(protection_status, PROTECTION_AGGREGATE_STATUSES, "protection aggregate")
    _require_token(factory_model_status, FACTORY_MODEL_STATUSES, "Factory model status")
    _require_token(modality_status, MODALITY_STATUSES, "modality status")
    _require_token(reference_relationship_status, REFERENCE_RELATIONSHIP_STATUSES, "reference status")
    if not isinstance(core_scan_complete, bool):
        raise ValueError("core_scan_complete must be bool")

    if source_quality_status == "INVALID": status = "EXCLUDED_INVALID_SOURCE"
    elif source_quality_status in {"RARE", "OUTLIER"}: status = "PRESERVE_SOURCE_QUALITY"
    elif context_eligibility_status != "EXACT_CONTEXT_MATCH": status = "PRESERVE_CONTEXT_UNPROVEN"
    elif not core_scan_complete: status = "PRESERVE_CORE_SCAN_PARTIAL"
    elif protection_status == "PROTECTED_DETECTED": status = "PROTECTED_DETECTED"
    elif protection_status == "PROTECTION_UNRESOLVED": status = "PRESERVE_PROTECTION_UNRESOLVED"
    elif protection_status == "EXTERNAL_EVIDENCE_GAP": status = "PRESERVE_EXTERNAL_EVIDENCE_GAP"
    elif protection_status == "PROTECTION_SCAN_PARTIAL": status = "PRESERVE_PROTECTION_SCAN_PARTIAL"
    elif protection_status == "PROTECTION_DEFERRED": status = "PRESERVE_PROTECTION_DEFERRED"
    elif protection_status == "PROTECTION_CONTRACT_INCOMPLETE": status = "PRESERVE_PROTECTION_CONTRACT_INCOMPLETE"
    elif factory_model_status != "FACTORY_SUFFICIENT": status = "INSUFFICIENT_FACTORY_EVIDENCE"
    elif modality_status == "DEGENERATE_EXACT_REFERENCE": status = "ZERO_VARIANCE_REVIEW"
    elif modality_status == "INSUFFICIENT_MODAL_EVIDENCE": status = "PRESERVE_MODALITY_INSUFFICIENT"
    elif modality_status in _UNSTABLE_MODALITY: status = "PRESERVE_MODALITY_UNSTABLE"
    elif modality_status == "DEFERRED": status = "PRESERVE_MODALITY_DEFERRED"
    elif modality_status == "ASSESSED_MULTIMODAL": status = "PRESERVE_MULTIMODAL_CONTEXT"
    elif reference_relationship_status == "POST_MODEL_PARTIAL": status = "PRESERVE_REFERENCE_GATE_PARTIAL"
    elif reference_relationship_status == "DEFERRED_FACTORY_MODEL_UNSTABLE": status = "PRESERVE_REFERENCE_GATE_DEFERRED"
    elif reference_relationship_status == "POTENTIAL_CONTRADICTION": status = "REVIEW_FACTORY_REFERENCE_CONFLICT"
    elif reference_relationship_status == "FACTORY_SUPPORT_UNINFORMATIVE": status = "PRESERVE_FACTORY_SUPPORT_UNINFORMATIVE"
    elif modality_status == "ASSESSED_UNIMODAL" and reference_relationship_status in {
            "REFERENCE_SUPPORT", "NO_REFERENCE_EVIDENCE", "INSUFFICIENT_REFERENCE_EVIDENCE"}:
        status = "ANALYZE_ALLOWED"
    else:
        # Closed enums can still form a semantically unreachable combination.
        status = "PRESERVE_PROTECTION_CONTRACT_INCOMPLETE"
    return AuthorizationDecision(status, status == "ANALYZE_ALLOWED")