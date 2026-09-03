# WP-X10-012 — Codex Lead Technical Plan

Datum: 11. august 2026.  
Ulazni gate: `AUDIT_REVIEWED`  
Capability: `ANALYZE_ONLY`  
Verdict: `LEAD_READY`

## Podjela

### WP-012A — Subject Registry i Sparse Protocol

Ownership:

```text
rxoptimizer/rhythm_subject_registry.py
rxoptimizer/rhythm_protection.py
tests/test_rhythm_subject_registry.py
tests/test_rhythm_protection.py
```

Implementira canonical subject ID-jeve/edges, enum/config hash, adapter registry/run/coverage/group/membership modele, partial semantics, protection aggregation i authorization truth funkciju. Bez SQLite v2 integrationa.

### WP-012B — Structural Adapters

Ownership:

```text
rxoptimizer/rhythm_protection_adapters.py
tests/test_rhythm_protection_adapters.py
```

Implementira Guitar, RX fail-closed join interface, trill structural protection, grace/drum ambiguous v1, cross-bar, section, tempo/meter i local-repeat adaptere. Factory/reference adapter ostaje post-model interface/deferred.

### WP-012C — Multimodal i Reference

Ownership:

```text
rxoptimizer/rhythm_multimodal.py
rxoptimizer/rhythm_reference_conflict.py
tests/test_rhythm_multimodal.py
tests/test_rhythm_reference_conflict.py
tests/fixtures/x10_multimodal/
```

Implementira `X10_WRAPPED_LAPLACE_BIC_V1`, Decimal interval odluke, initialization/collapse/posterior/LOSO/groove coherence i Factory/reference support arcs.

### WP-012D — Schema-v2 Integration

Lead nakon module-level QA mijenja:

```text
rxoptimizer/rhythm_context_join.py
rxoptimizer/rhythm_context_models.py
rxoptimizer/rhythm_negative_corpus.py
tests/test_rhythm_context_models.py
tests/test_rhythm_context_schema.py
```

V2 je puni RAW rebuild sa disk-backed spoolom; v1 ostaje immutable. Ovaj integration dobija poseban novi QA.

## Gateovi

1. 012A targeted tests + full regression.
2. 012A independent QA.
3. 012B targeted/adversarial tests + QA.
4. 012C mathematical/property tests + QA.
5. 012D integration/corpus-spool tests + fresh QA.

Implementeri ne dijele fajlove. QA je read-only. Šest song SHA, optimizer i repaired output ostaju zabranjeni. Nijedan paket ne proizvodi MIDI, target, proposal ili repair podatke.

## Lead verdict

```text
LEAD_READY
```