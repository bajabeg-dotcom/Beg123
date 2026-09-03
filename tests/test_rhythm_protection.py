from dataclasses import replace

import pytest

from rxoptimizer.rhythm_protection import (
    ADAPTER_RUN_STATUSES,
    BUILD_TERMINAL_STATUSES,
    ENUM_DOMAINS,
    ENUM_DOMAIN_SHA256,
    FINAL_AUTHORIZATION_STATUSES,
    MODALITY_STATUSES,
    PER_RULE_PROTECTION_STATUSES,
    REQUIRED_PROTECTION_RULES,
    AdapterContract,
    AdapterRegistry,
    AdapterRun,
    AuthorizationDecision,
    CoveragePartition,
    ProtectionGroup,
    ProtectionGroupMembership,
    ProtectionEvidenceRegistry,
    aggregate_protection_status,
    enum_domain_sha256,
    final_analysis_authorization,
    protection_config_sha256,
    sparse_rule_status,
    validate_enum_domains,
)
from rxoptimizer.rhythm_subject_registry import canonical_json
from hashlib import sha256


D = {
    "source": "1" * 64,
    "scope": "2" * 64,
    "universe": "3" * 64,
    "input": "4" * 64,
    "dependency": "5" * 64,
    "result": "6" * 64,
}
SUBJECT_A = "a" * 64
SUBJECT_B = "b" * 64
SUBJECT_C = "c" * 64


def population_digest(*subject_ids):
    return sha256(canonical_json(sorted(subject_ids)).encode("ascii")).hexdigest()


def contract(rule="GUITAR_MODE", adapter_class="CORE_REQUIRED"):
    return AdapterContract(rule, "1", adapter_class, "PREDICATE_V1")


def run(status="COMPLETE", adapter=None, universe_count=None, applicable=2, scanned=2, resolved=2,
        universe_sha256=None, applicable_sha256=None, result_sha256=None):
    adapter = adapter or contract()
    universe_count = applicable if universe_count is None else universe_count
    return AdapterRun(D["source"], adapter, "TRACK_CHANNEL", D["scope"], "UNIVERSE_V1",
        universe_count, universe_sha256 or population_digest(SUBJECT_A, SUBJECT_B), applicable,
        applicable_sha256 or population_digest(SUBJECT_A, SUBJECT_B), scanned, resolved,
        1 if resolved else 0, max(0, resolved - 1), D["input"], D["dependency"],
        result_sha256 or D["result"], status)


def add_run(evidence, value):
    return evidence.add_run(value, subject_universe_ids=[SUBJECT_A, SUBJECT_B],
        applicable_subject_ids=[SUBJECT_A, SUBJECT_B])


def partition(status="COMPLETE", applicable=2, scanned=2, resolved=2, run_id="7" * 64,
        universe_sha256=None, result_sha256=None):
    return CoveragePartition(run_id, "partition-0", D["scope"], applicable, scanned,
        resolved, universe_sha256 or population_digest(SUBJECT_A, SUBJECT_B),
        result_sha256 or D["result"], status)


def allowed(**overrides):
    values = dict(source_quality_status="NORMAL", context_eligibility_status="EXACT_CONTEXT_MATCH",
        core_scan_complete=True, protection_status="PROTECTION_CLEAR",
        factory_model_status="FACTORY_SUFFICIENT", modality_status="ASSESSED_UNIMODAL",
        reference_relationship_status="REFERENCE_SUPPORT")
    values.update(overrides)
    return final_analysis_authorization(**values)


def test_enum_domains_are_closed_ordered_hashed_and_reject_duplicate_unknown_unreachable():
    assert validate_enum_domains(ENUM_DOMAINS, ENUM_DOMAIN_SHA256) == ENUM_DOMAIN_SHA256
    assert enum_domain_sha256(ENUM_DOMAINS) == ENUM_DOMAIN_SHA256
    duplicate = dict(ENUM_DOMAINS); duplicate["adapter_run"] = ADAPTER_RUN_STATUSES + ("COMPLETE",)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_enum_domains(duplicate)
    unknown = dict(ENUM_DOMAINS); unknown["adapter_run"] = ADAPTER_RUN_STATUSES + ("MAYBE",)
    with pytest.raises(ValueError, match="unknown"):
        validate_enum_domains(unknown)
    unreachable = dict(ENUM_DOMAINS); unreachable["adapter_run"] = ADAPTER_RUN_STATUSES[:-1]
    with pytest.raises(ValueError, match="unreachable"):
        validate_enum_domains(unreachable)
    reordered = dict(ENUM_DOMAINS); reordered["adapter_run"] = tuple(reversed(ADAPTER_RUN_STATUSES))
    with pytest.raises(ValueError, match="order"):
        validate_enum_domains(reordered)
    with pytest.raises(ValueError, match="mismatch"):
        validate_enum_domains(ENUM_DOMAINS, "0" * 64)
    invalid_type = dict(ENUM_DOMAINS); invalid_type["adapter_run"] = ADAPTER_RUN_STATUSES[:-1] + (1,)
    with pytest.raises(ValueError, match="string tokens"):
        validate_enum_domains(invalid_type)


def test_config_hash_is_deterministic_and_contract_fields_cannot_be_overridden():
    assert protection_config_sha256({"b": 2, "a": 1}) == protection_config_sha256({"a": 1, "b": 2})
    with pytest.raises(ValueError, match="cannot be overridden"):
        protection_config_sha256({"capability": "WRITE"})


def test_adapter_registry_is_idempotent_conflict_checked_and_complete():
    registry = AdapterRegistry()
    for rule in REQUIRED_PROTECTION_RULES:
        kind = "POST_MODEL_REQUIRED" if rule == "FACTORY_REFERENCE_CONFLICT" else (
            "EXTERNAL_OPTIONAL_FAIL_CLOSED" if rule == "RX_DNC" else "CORE_REQUIRED")
        item = contract(rule, kind)
        registry.register(item); registry.register(item)
    registry.validate_complete()
    with pytest.raises(ValueError, match="Conflicting"):
        registry.register(AdapterContract("GUITAR_MODE", "1", "CORE_REQUIRED", "PREDICATE_V2"))
    incomplete = AdapterRegistry(); incomplete.register(contract())
    with pytest.raises(ValueError, match="incomplete"):
        incomplete.validate_complete()
    bad_hash = replace(contract(), config_sha256="f" * 64)
    with pytest.raises(ValueError, match="config hash mismatch"):
        registry.register(bad_hash)


def test_adapter_class_and_run_status_semantics_fail_closed():
    with pytest.raises(ValueError, match="canonical adapter class"):
        contract("RX_DNC", "CORE_REQUIRED")
    with pytest.raises(ValueError, match="canonical adapter class"):
        contract("CROSS_BAR", "EXTERNAL_OPTIONAL_FAIL_CLOSED")
    with pytest.raises(ValueError, match="post-model"):
        run("DEFERRED_POST_MODEL")
    with pytest.raises(ValueError, match="external optional"):
        run("DEPENDENCY_UNAVAILABLE")
    external = contract("RX_DNC", "EXTERNAL_OPTIONAL_FAIL_CLOSED")
    assert run("DEPENDENCY_UNAVAILABLE", external, applicable=2, scanned=0, resolved=0).run_status == "DEPENDENCY_UNAVAILABLE"
    post = contract("FACTORY_REFERENCE_CONFLICT", "POST_MODEL_REQUIRED")
    assert run("DEFERRED_POST_MODEL", post, applicable=2, scanned=0, resolved=0).run_status == "DEFERRED_POST_MODEL"


def test_failed_runs_are_hard_fail_records_not_sparse_evidence():
    evidence = ProtectionEvidenceRegistry({D["scope"]: D["source"]})
    failed = run("FAILED_RUNTIME", applicable=2, scanned=0, resolved=0)
    with pytest.raises(ValueError, match="build-hard-fail"):
        evidence.add_run(failed, subject_universe_ids=[], applicable_subject_ids=[])


def test_complete_partial_and_not_applicable_count_contracts():
    assert run().run_status == "COMPLETE"
    assert run("PARTIAL", applicable=3, scanned=1, resolved=1).run_status == "PARTIAL"
    assert run("PARTIAL", applicable=3, scanned=3, resolved=2).run_status == "PARTIAL"
    with pytest.raises(ValueError, match="COMPLETE"):
        run("COMPLETE", applicable=3, scanned=2, resolved=2)
    with pytest.raises(ValueError, match="PARTIAL"):
        run("PARTIAL", applicable=2, scanned=2, resolved=2)
    with pytest.raises(ValueError, match="NOT_APPLICABLE"):
        run("NOT_APPLICABLE", applicable=1, scanned=0, resolved=0)


def test_sparse_absence_is_clear_only_inside_matching_complete_coverage():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"], SUBJECT_C: D["source"]}
    evidence = ProtectionEvidenceRegistry(sources)
    complete_run = add_run(evidence, run())
    complete = partition(run_id=complete_run.run_id)
    evidence.add_partition(complete, applicable_subject_ids=[SUBJECT_B, SUBJECT_A],
        scanned_subject_ids=[SUBJECT_A, SUBJECT_B], resolved_subject_ids=[SUBJECT_A, SUBJECT_B])
    assert sparse_rule_status(evidence, SUBJECT_A, "GUITAR_MODE") == "CLEAR"
    assert sparse_rule_status(evidence, SUBJECT_C, "GUITAR_MODE") == "NOT_APPLICABLE"

    partial_evidence = ProtectionEvidenceRegistry(sources)
    partial_run = add_run(partial_evidence, run("PARTIAL", applicable=2, scanned=1, resolved=1))
    partial = partition("PARTIAL", applicable=2, scanned=1, resolved=1, run_id=partial_run.run_id)
    partial_evidence.add_partition(partial, applicable_subject_ids=[SUBJECT_A, SUBJECT_B],
        scanned_subject_ids=[SUBJECT_A], resolved_subject_ids=[SUBJECT_A])
    assert sparse_rule_status(partial_evidence, SUBJECT_A, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"
    assert sparse_rule_status(partial_evidence, SUBJECT_B, "GUITAR_MODE") == "PARTIAL_UNRESOLVED"


def test_multiple_group_memberships_preserve_provenance_and_conservative_status():
    detected = ProtectionGroup("7" * 64, D["source"], "CROSS_BAR", "1", {"bar": 2}, "DETECTED", "8" * 64)
    ambiguous = ProtectionGroup("6" * 64, D["source"], "SECTION_TRANSITION", "1", {"bar": 2}, "AMBIGUOUS", "9" * 64)
    one = ProtectionGroupMembership(detected.group_id, D["scope"])
    two = ProtectionGroupMembership(ambiguous.group_id, D["scope"])
    assert one.membership_id != two.membership_id
    with pytest.raises(ValueError, match="non-clear"):
        ProtectionGroup("7" * 64, D["source"], "CROSS_BAR", "1", {"bar": 2}, "CLEAR", "8" * 64)


def test_sparse_evidence_registry_enforces_references_sources_and_run_natural_keys():
    evidence = ProtectionEvidenceRegistry({D["scope"]: D["source"], SUBJECT_A: D["source"],
        SUBJECT_B: D["source"], SUBJECT_C: "b" * 64})
    adapter_run = add_run(evidence, run())
    part = CoveragePartition(adapter_run.run_id, "p0", D["scope"], 2, 2, 2,
        population_digest(SUBJECT_A, SUBJECT_B), D["result"], "COMPLETE")
    kwargs = {"applicable_subject_ids": [SUBJECT_A, SUBJECT_B],
              "scanned_subject_ids": [SUBJECT_A, SUBJECT_B],
              "resolved_subject_ids": [SUBJECT_A, SUBJECT_B]}
    evidence.add_partition(part, **kwargs); evidence.add_partition(part, **kwargs)
    group = evidence.add_group(ProtectionGroup(
        adapter_run.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 2}, "DETECTED", "8" * 64))
    membership = ProtectionGroupMembership(group.group_id, SUBJECT_A)
    evidence.add_membership(membership); evidence.add_membership(membership)
    # A second group for the same subject is explicitly legal and preserves provenance.
    second = evidence.add_group(ProtectionGroup(
        adapter_run.run_id, D["source"], "GUITAR_MODE", "1", {"bar": 3}, "AMBIGUOUS", "9" * 64))
    evidence.add_membership(ProtectionGroupMembership(second.group_id, SUBJECT_A))
    assert len(evidence.memberships) == 2
    assert sparse_rule_status(evidence, SUBJECT_A, "GUITAR_MODE") == "DETECTED"
    with pytest.raises(ValueError, match="registered group"):
        evidence.add_membership(ProtectionGroupMembership("d" * 64, SUBJECT_A))
    with pytest.raises(ValueError, match="Cross-source"):
        evidence.add_membership(ProtectionGroupMembership(group.group_id, SUBJECT_C))
    with pytest.raises(ValueError, match="registered adapter run"):
        evidence.add_partition(CoveragePartition("d" * 64, "p1", D["scope"], 0, 0, 0,
            population_digest(), D["result"], "COMPLETE"), applicable_subject_ids=[],
            scanned_subject_ids=[], resolved_subject_ids=[])
    contradictory = replace(adapter_run, result_sha256="e" * 64)
    with pytest.raises(ValueError, match="natural key"):
        add_run(evidence, contradictory)


@pytest.mark.parametrize(("rule_status", "aggregate"), [
    ("DETECTED", "PROTECTED_DETECTED"),
    ("AMBIGUOUS", "PROTECTION_UNRESOLVED"),
    ("EVIDENCE_UNJOINABLE", "PROTECTION_UNRESOLVED"),
    ("DEPENDENCY_GAP", "EXTERNAL_EVIDENCE_GAP"),
    ("PARTIAL_UNRESOLVED", "PROTECTION_SCAN_PARTIAL"),
    ("DEFERRED", "PROTECTION_DEFERRED"),
])
def test_protection_aggregate_precedence(rule_status, aggregate):
    statuses = {rule: "CLEAR" for rule in REQUIRED_PROTECTION_RULES}
    statuses[REQUIRED_PROTECTION_RULES[-1]] = rule_status
    assert aggregate_protection_status(statuses) == aggregate


def test_protection_aggregate_requires_all_nine_clear_or_not_applicable():
    statuses = {rule: ("NOT_APPLICABLE" if index % 2 else "CLEAR")
                for index, rule in enumerate(REQUIRED_PROTECTION_RULES)}
    assert aggregate_protection_status(statuses) == "PROTECTION_CLEAR"
    missing = dict(statuses); missing.pop(REQUIRED_PROTECTION_RULES[-1])
    with pytest.raises(ValueError, match="missing"):
        aggregate_protection_status(missing)
    unknown = dict(statuses); unknown["UNKNOWN_RULE"] = "CLEAR"
    with pytest.raises(ValueError, match="unknown"):
        aggregate_protection_status(unknown)
    with pytest.raises(TypeError, match="rule-keyed"):
        aggregate_protection_status(["CLEAR"] * 9)
    duplicate_pairs = list(statuses.items()) + [(REQUIRED_PROTECTION_RULES[0], "CLEAR")]
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate_protection_status(duplicate_pairs)


def test_run_scope_partition_and_group_semantic_linkage_are_strict():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"]}
    missing_scope = ProtectionEvidenceRegistry({SUBJECT_A: D["source"]})
    with pytest.raises(ValueError, match="scope subject is not registered"):
        add_run(missing_scope, run())
    wrong_source = ProtectionEvidenceRegistry({D["scope"]: "f" * 64})
    with pytest.raises(ValueError, match="another source"):
        add_run(wrong_source, run())

    evidence = ProtectionEvidenceRegistry(sources)
    parent = add_run(evidence, run())
    valid = partition(run_id=parent.run_id)
    population = dict(applicable_subject_ids=[SUBJECT_A, SUBJECT_B],
        scanned_subject_ids=[SUBJECT_A, SUBJECT_B], resolved_subject_ids=[SUBJECT_A, SUBJECT_B])
    evidence.add_partition(valid, **population)
    conflicting = replace(valid, result_sha256="e" * 64)
    with pytest.raises(ValueError, match="natural key"):
        evidence.add_partition(conflicting, **population)
    mismatch = replace(valid, partition_key="other", applicable_count=1, scanned_count=1,
        resolved_count=1, applicable_universe_sha256=population_digest(SUBJECT_A))
    with pytest.raises(ValueError, match="parent run"):
        evidence.add_partition(mismatch, applicable_subject_ids=[SUBJECT_A],
            scanned_subject_ids=[SUBJECT_A], resolved_subject_ids=[SUBJECT_A])
    with pytest.raises(ValueError, match="population counts"):
        another = replace(valid, partition_key="third")
        evidence.add_partition(another, applicable_subject_ids=[SUBJECT_A],
            scanned_subject_ids=[SUBJECT_A], resolved_subject_ids=[SUBJECT_A])

    wrong_rule = ProtectionGroup(parent.run_id, D["source"], "CROSS_BAR", "1",
        {"bar": 2}, "DETECTED", "8" * 64)
    with pytest.raises(ValueError, match="contract does not match"):
        evidence.add_group(wrong_rule)
    missing_run = ProtectionGroup("f" * 64, D["source"], "GUITAR_MODE", "1",
        {"bar": 2}, "DETECTED", "8" * 64)
    with pytest.raises(ValueError, match="registered adapter run"):
        evidence.add_group(missing_run)


def test_run_universe_and_applicable_population_have_separate_proven_digests():
    sources = {D["scope"]: D["source"], SUBJECT_A: D["source"], SUBJECT_B: D["source"],
        SUBJECT_C: D["source"]}
    evidence = ProtectionEvidenceRegistry(sources)
    value = run(universe_count=3, universe_sha256=population_digest(SUBJECT_A, SUBJECT_B, SUBJECT_C),
        applicable=2, applicable_sha256=population_digest(SUBJECT_A, SUBJECT_B))
    stored = evidence.add_run(value, subject_universe_ids=[SUBJECT_C, SUBJECT_A, SUBJECT_B],
        applicable_subject_ids=[SUBJECT_B, SUBJECT_A])
    assert stored.subject_universe_sha256 != stored.applicable_universe_sha256
    bad = ProtectionEvidenceRegistry(sources)
    with pytest.raises(ValueError, match="applicable universe digest mismatch"):
        bad.add_run(replace(value, applicable_universe_sha256="e" * 64),
            subject_universe_ids=[SUBJECT_A, SUBJECT_B, SUBJECT_C],
            applicable_subject_ids=[SUBJECT_A, SUBJECT_B])
    with pytest.raises(ValueError, match="inside subject universe"):
        ProtectionEvidenceRegistry(sources).add_run(value,
            subject_universe_ids=[SUBJECT_A, SUBJECT_C, D["scope"]],
            applicable_subject_ids=[SUBJECT_A, SUBJECT_B])


@pytest.mark.parametrize("rule", [
    "GUITAR_MODE", "ORNAMENT_TRILL_GRACE", "DRUM_FLAM_ROLL_GHOST", "CROSS_BAR",
    "SECTION_TRANSITION", "TEMPO_METER_BOUNDARY", "LOCAL_REPEATED_PATTERN",
])
def test_seven_structural_rules_are_canonically_core_required(rule):
    assert contract(rule, "CORE_REQUIRED").adapter_class == "CORE_REQUIRED"
    with pytest.raises(ValueError, match="canonical adapter class"):
        contract(rule, "POST_MODEL_REQUIRED")


@pytest.mark.parametrize(("overrides", "expected"), [
    ({"source_quality_status": "INVALID"}, "EXCLUDED_INVALID_SOURCE"),
    ({"source_quality_status": "RARE"}, "PRESERVE_SOURCE_QUALITY"),
    ({"context_eligibility_status": "CONTEXT_CONFLICT"}, "PRESERVE_CONTEXT_UNPROVEN"),
    ({"core_scan_complete": False}, "PRESERVE_CORE_SCAN_PARTIAL"),
    ({"protection_status": "PROTECTED_DETECTED"}, "PROTECTED_DETECTED"),
    ({"protection_status": "PROTECTION_UNRESOLVED"}, "PRESERVE_PROTECTION_UNRESOLVED"),
    ({"protection_status": "EXTERNAL_EVIDENCE_GAP"}, "PRESERVE_EXTERNAL_EVIDENCE_GAP"),
    ({"protection_status": "PROTECTION_SCAN_PARTIAL"}, "PRESERVE_PROTECTION_SCAN_PARTIAL"),
    ({"protection_status": "PROTECTION_DEFERRED"}, "PRESERVE_PROTECTION_DEFERRED"),
    ({"protection_status": "PROTECTION_CONTRACT_INCOMPLETE"}, "PRESERVE_PROTECTION_CONTRACT_INCOMPLETE"),
    ({"factory_model_status": "FACTORY_INSUFFICIENT"}, "INSUFFICIENT_FACTORY_EVIDENCE"),
    ({"modality_status": "DEGENERATE_EXACT_REFERENCE"}, "ZERO_VARIANCE_REVIEW"),
    ({"modality_status": "INSUFFICIENT_MODAL_EVIDENCE"}, "PRESERVE_MODALITY_INSUFFICIENT"),
    ({"modality_status": "UNSTABLE_BIC_NEAR_TIE"}, "PRESERVE_MODALITY_UNSTABLE"),
    ({"modality_status": "DEFERRED"}, "PRESERVE_MODALITY_DEFERRED"),
    ({"modality_status": "ASSESSED_MULTIMODAL"}, "PRESERVE_MULTIMODAL_CONTEXT"),
    ({"reference_relationship_status": "POST_MODEL_PARTIAL"}, "PRESERVE_REFERENCE_GATE_PARTIAL"),
    ({"reference_relationship_status": "DEFERRED_FACTORY_MODEL_UNSTABLE"}, "PRESERVE_REFERENCE_GATE_DEFERRED"),
    ({"reference_relationship_status": "POTENTIAL_CONTRADICTION"}, "REVIEW_FACTORY_REFERENCE_CONFLICT"),
    ({"reference_relationship_status": "FACTORY_SUPPORT_UNINFORMATIVE"}, "PRESERVE_FACTORY_SUPPORT_UNINFORMATIVE"),
    ({}, "ANALYZE_ALLOWED"),
])
def test_final_authorization_status_reachability(overrides, expected):
    decision = allowed(**overrides)
    assert decision.authorization_status == expected
    assert decision.analysis_allowed is (expected == "ANALYZE_ALLOWED")
    assert not decision.proposal_allowed and not decision.repair_allowed
    assert decision.mutation_capability == "NONE" and decision.capability == "ANALYZE_ONLY"


def test_all_unstable_and_numerical_modality_tokens_reach_unstable_preserve():
    for status in MODALITY_STATUSES:
        if status.startswith("UNSTABLE_") or status.startswith("NUMERICAL_"):
            assert allowed(modality_status=status).authorization_status == "PRESERVE_MODALITY_UNSTABLE"


def test_every_final_authorization_status_is_reachable_and_unknown_input_hard_fails():
    reached = {allowed().authorization_status}
    cases = [
        dict(source_quality_status="INVALID"), dict(source_quality_status="OUTLIER"),
        dict(context_eligibility_status="CONTEXT_UNPROVEN"), dict(core_scan_complete=False),
        *[dict(protection_status=status) for status in (
            "PROTECTED_DETECTED", "PROTECTION_UNRESOLVED", "EXTERNAL_EVIDENCE_GAP",
            "PROTECTION_SCAN_PARTIAL", "PROTECTION_DEFERRED", "PROTECTION_CONTRACT_INCOMPLETE")],
        dict(factory_model_status="FACTORY_UNAVAILABLE"), dict(modality_status="DEGENERATE_EXACT_REFERENCE"),
        dict(modality_status="INSUFFICIENT_MODAL_EVIDENCE"), dict(modality_status="UNSTABLE_MODAL_STRUCTURE"),
        dict(modality_status="DEFERRED"), dict(modality_status="ASSESSED_MULTIMODAL"),
        dict(reference_relationship_status="POST_MODEL_PARTIAL"),
        dict(reference_relationship_status="DEFERRED_FACTORY_MODEL_UNSTABLE"),
        dict(reference_relationship_status="POTENTIAL_CONTRADICTION"),
        dict(reference_relationship_status="FACTORY_SUPPORT_UNINFORMATIVE"),
    ]
    reached.update(allowed(**case).authorization_status for case in cases)
    assert reached == set(FINAL_AUTHORIZATION_STATUSES)
    with pytest.raises(ValueError, match="Unknown source"):
        allowed(source_quality_status="MAYBE")
    with pytest.raises(ValueError, match="bool"):
        allowed(core_scan_complete=1)
    with pytest.raises(ValueError, match="exactly match"):
        AuthorizationDecision("ANALYZE_ALLOWED", False)


def test_declared_enum_appendix_tokens_remain_reachable_in_domains():
    assert set(BUILD_TERMINAL_STATUSES) == set(ENUM_DOMAINS["build_terminal"])
    assert set(PER_RULE_PROTECTION_STATUSES) == set(ENUM_DOMAINS["per_rule_protection"])
    assert set(FINAL_AUTHORIZATION_STATUSES) == set(ENUM_DOMAINS["final_authorization"])