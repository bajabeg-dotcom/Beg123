# WP-X10-011 — Codex Lead Technical Plan

Datum: 11. august 2026.  
Ulazni gate: `AUDIT_REVIEWED`  
Capability: `ANALYZE_ONLY`  
Lead verdict: `LEAD_READY`

## Scope ove implementacije

Prvi Implementer paket gradi samostalnu, mutation-free jezgru za:

1. deterministički Program/Bank, meter i tempo timeline;
2. exact note-context join preko stable event/note ID-a;
3. context-qualified SQLite schema, atomic builder i semantic digest;
4. odvojeni declarative negative-corpus manifest i fail-closed protection statuse.

Ovaj paket ne integrira GUI/API, ne mijenja postojeći optimizer, ne mijenja legacy calibration/consensus i ne pokreće auto-repair. Lead integration u `app.py` i `dna_databases.py` dolazi samo poslije QA `ACCEPT`.

## Fajl ownership

Implementer smije kreirati/mijenjati samo:

```text
rxoptimizer/rhythm_context_join.py
rxoptimizer/rhythm_context_models.py
rxoptimizer/rhythm_negative_corpus.py
tests/test_rhythm_context_join.py
tests/test_rhythm_context_models.py
tests/test_rhythm_context_schema.py
tests/test_rhythm_negative_corpus.py
tests/fixtures/x10_negative/manifest.json
tests/fixtures/x10_negative/*.json
```

Implementer ne smije mijenjati postojeće `rhythm_context.py`, `rhythm_calibration.py`, `rhythm_consensus.py`, `midi.py`, `database.py`, `app.py`, `dna_databases.py` niti governance/report dokumente.

QA je read-only. Lead jedini mijenja integration i registry fajlove.

## Modul A — `rhythm_context_join.py`

Javni interfejs:

```python
build_channel_context(midi, source_sha256) -> dict
join_note_context(midi, source_sha256, metadata, quality_status, protection_adapters=()) -> list[dict]
```

Obavezni rezultati:

- `channel_state_events`, `program_segments`, `meter_segments`, `tempo_segments`;
- stable semantic segment IDs;
- exact evidence locator lista za deduplicirane događaje;
- Program statusi iz Architect addenduma;
- meter/tempo exact/default/conflict statusi;
- note-level `program_segment_id`, `meter_segment_id`, `tempo_segment_id` i statusi;
- section/style/CV/role vrijednost, method, status i locator;
- row-level `eligibility_status` i `preservation_reasons`.

Cross-track isti tick se grupiše semantički; track indeks nije tie-breaker. Program conflict traje do kasnijeg nekonfliktnog Program Changea. Note On attribution koristi same-track order ili raniji globalno dokazani state.

## Modul B — `rhythm_context_models.py`

Javni interfejs:

```python
build_context_qualified_database(source_records, output_path, config=None) -> dict
canonical_semantic_rows(database_path) -> list[str]
semantic_digest(database_path) -> str
assert_analyze_only_schema(database_path) -> None
```

Builder ulaz je iterable RAW source recorda sa bytes/hash/corpus/member/metadata/quality. Ne prima legacy calibration/consensus database kao model input.

Builder redoslijed gateova:

```text
G0 source/hash/forbidden source
G1 parse + stable identity
G2 Program/meter/tempo timelines
G3 metadata provenance
G4 NORMAL-only model eligibility
G5 stable-ID protection
G6 exact context
G7 Factory-only consensus authority
G8 negative manifest contract
G9 analyze-only schema audit
G10 semantic digest
G11 SQLite integrity/FK + atomic replace
```

V1 može materijalizovati note/bar context i exact eligibility, ali ne mora izgraditi statistički consensus ako minimum cross-file corpus nije prisutan u ciljanim testovima. Ako postoji consensus tabela, samo Factory `NORMAL` exact rows mogu u nju; reference ostaje odvojena evidence klasa.

## Modul C — `rhythm_negative_corpus.py`

Javni interfejs:

```python
load_negative_manifest(path) -> dict
validate_negative_manifest(manifest, forbidden_sha256=()) -> dict
apply_protection_adapters(note_context, adapters) -> list[dict]
```

Manifest source klase:

```text
FACTORY_NEGATIVE_OBSERVATION
REFERENCE_NEGATIVE_OBSERVATION
SYNTHETIC_GUARD_FIXTURE
HUMAN_VALIDATED_NEGATIVE
```

Synthetic fixtures su declarative JSON i ne smiju tvrditi Factory/Pa800 evidence. Adapter rezultat mora sadržati stable note/event ID; ambiguous/unavailable/unjoinable znači preserve.

## Natural keys

```text
source_context:
  source_sha256

channel_state_events:
  source_sha256, channel, tick, event_kind, semantic_value_sha256

program_segments:
  source_sha256, channel, start_tick, program_segment_id

meter_segments:
  source_sha256, start_tick, meter_segment_id

tempo_segments:
  source_sha256, start_tick, tempo_segment_id

note_context:
  source_sha256, note_id

bar_context:
  source_sha256, track_index, channel, bar_index, topology_sha256

local_context_calibration:
  corpus, exact_context_key, source_sha256, local_profile_key

context_consensus:
  corpus, exact_context_key

context_consensus_evidence:
  consensus_key, source_sha256, local_profile_key

protection_observations:
  source_sha256, stable_subject_id, rule_key, adapter_version

negative_corpus_cases:
  source_class, case_id

semantic_digest:
  digest_algorithm, schema_version
```

Natural-key collision sa različitim semantic sadržajem je hard fail.

## Hard-fail granica

Hard fail: missing/stale dependency, source SHA mismatch, forbidden six-song/repaired/optimizer evidence, unsupported schema, parse failure za declared-valid source, contradictory natural-key duplicate, invalid/incomplete negative manifest, forbidden schema field, source mutation, digest failure, SQLite integrity/FK failure.

Row-level preserve: Program/role/CV/style/section/meter/tempo ambiguity, RARE/OUTLIER, insufficient exact evidence, adapter unavailable/unjoinable, unresolved multimodality ili Factory/reference contradiction.

## Targeted test matrix

Minimalno testirati:

- unspecified initial Program, partial bank i exact Program;
- same-track Note On prije/poslije Program Changea;
- Note Off nakon Program Changea ne mijenja note identity;
- identical naspram conflicting cross-track same-tick Program/Bank;
- cross-track same-tick Note On ambiguity;
- identical naspram conflicting meter i tempo događaja;
- default meter/tempo nisu exact;
- CV0 nije CV UNKNOWN; `section_no=0` nije missing;
- unknown role nije melodic;
- NORMAL-only eligibility, RARE/OUTLIER preserve;
- exact-only/no fallback;
- stable-ID adapter failure preserve;
- odvojene negative source klase i forbidden SHA nakon renamea;
- legacy calibration/consensus nisu builder input;
- forbidden schema/API field audit;
- input bytes/hash bez promjene i nula MIDI outputa;
- two-build semantic digest parity;
- namjerni build failure čuva prethodnu bazu;
- SQLite integrity/FK;
- puni pytest bez warninga.

## QA acceptance

QA vraća:

- `ACCEPT` samo ako scope/ownership, targeted tests, full regression, analyze-only schema, determinism i atomicity prolaze;
- `RETURN` za ispravljive implementacijske ili testne nedostatke;
- `BLOCK` za ugovornu/sigurnosnu kontradikciju ili nedostajuću Human odluku.

QA tehnički verdict nije Pa800 dokaz niti release.

## Lead verdict

```text
LEAD_READY
```