# WP-X10-012 — Architect Work-Package Contract

Datum: 11. august 2026.  
Verzija: 1  
Capability: `ANALYZE_ONLY`  
Naziv: Stable-ID Protection Adapters and Multimodal Gate  
Verdict: `READY_FOR_AUDIT`

## Cilj

Izgraditi deterministički protection i multimodal sloj između RAW-derived `rhythm_context_qualified` konteksta i budućeg anomaly/proposal sistema. Paket implementira versioned stable-ID protokol za devet zaštitnih pravila, sparse corpus-scalable storage i Factory-only multimodal procjenu. Ne mijenja MIDI i ne proizvodi target, candidate, proposal ili repair podatke.

## Source granice

```text
Factory NORMAL  → Factory reference, adapter evidence i modality
Factory RARE    → preservation/review only
Factory OUTLIER → review only
Factory INVALID → excluded
Gold/reference  → support/contradiction tek nakon Factory modela
Synthetic       → software contract, nikad Factory/Pa800 evidence
Human evidence  → samo Human Owner provenance
šest songova    → isključivo Delay/Terca relationship
optimizer/repair output → nikad evidence
```

Forbidden SHA se provjerava prije parsiranja, nezavisno od filenamea.

## Dvoprolazni pipeline

```text
RAW + stable IDs
→ exact context
→ pre-consensus structural adapters
→ context-qualified local Factory profiles
→ Factory-only cross-file consensus
→ multimodal assessment
→ Gold/reference support-conflict
→ post-consensus FACTORY_REFERENCE_CONFLICT
→ final analyze authorization
```

Odvojeni statusi su obavezni: `context_eligibility_status`, `model_eligibility_status`, `protection_status` i `analysis_authorization_status`. Protection nikada ne daje repair dozvolu.

## Adapter protokol

Adapter prima immutable source/context snapshot i vraća rule/version/contract, run status, stable subject type/ID, detection/evidence status, source SHA, exact locatore, affected stable note ID-jeve, reason codes, dependency digeste i detalje.

Dozvoljeni detection statusi:

```text
DETECTED
NOT_DETECTED
AMBIGUOUS
EVIDENCE_UNJOINABLE
DEPENDENCY_UNAVAILABLE
DEFERRED_POST_CONSENSUS
```

`NOT_DETECTED` vrijedi samo kada je run `COMPLETE`, puni applicability scope je skeniran i input/coverage digest sačuvan. Odsustvo sparse reda nije clear osim unutar dokazano kompletne coverage granice.

## Devet protection pravila

1. `GUITAR_MODE`: RAW command/chord struktura i exact guitar context. Heuristic identitet ostaje ambiguous; štite se command/chord događaji i onset clusteri.
2. `RX_DNC`: exact Bank/Program + stable locator + `CONFIRMED` manual/PCG/Sound Edit/Pa800 dokaz. Catalog-only, UNKNOWN i konflikt ostaju preserve. Trenutnih 0/49 zona i 0/21 Sound ciljeva ne smije postati clear.
3. `ORNAMENT_TRILL_GRACE`: RAW component stable IDs. HIGH/MEDIUM kandidat je dovoljan za protection, ne za `CONFIRMED`. Grace bez robustnog lokalnog konteksta je ambiguous.
4. `DRUM_FLAM_ROLL_GHOST`: exact drum/percussion scope i lokalna empirical lane/context distribucija. Nema fiksnog low-velocity ili IOI praga.
5. `CROSS_BAR`: note/phrase/component koji prelazi dokazanu bar ili meter granicu. Default/conflict meter nikad nije clear.
6. `SECTION_TRANSITION`: Intro/Fill/Break/Ending i dokazive boundary sekcije. Filename-only section je ambiguous; nema fiksnog tick prozora.
7. `TEMPO_METER_BOUNDARY`: note/cluster/bar pogođen stvarnom promjenom, konfliktom ili unspecified segmentom. Granice koriste segment ID i stvarne tickove.
8. `LOCAL_REPEATED_PATTERN`: exact grid-free rhythm/topology repeat u istom dokazivom scopeu. Approximate repeat nije dokaz.
9. `FACTORY_REFERENCE_CONFLICT`: post-consensus adapter; Factory je autoritet, Gold/reference samo poređenje sa exact contextom nakon modality rezultata.

## Sparse schema

Novi sloj koristi:

- `protection_adapter_runs`: run status, applicability, input/dependency/coverage/run digesti i brojači;
- `protection_groups`: detected/ambiguous grupni dokaz;
- `protection_group_members`: stable subject membership;
- `multimodal_context` i `multimodal_components`;
- `analysis_authorization`: odvojeni context/model/protection/modality/conflict/final statusi.

Clear se ne zapisuje devet puta po noti. `COMPLETE` adapter run + odsustvo membershipa znači dokazani `NOT_DETECTED` samo unutar deklarisane coverage granice. Natural-key kontradikcija je hard fail.

## Multimodal gate

Input je samo Factory `NORMAL`, exact-context i cross-file sufficient evidence. Svaki source fajl ima jednaku težinu; Gold/reference nije input modela.

Obavezna dimenzija je circular bar-relative onset phase po event slotu. Deterministički robust mixture selection:

1. stvarne circular faze, bez grid targeta;
2. source-level predstavnici jednake težine;
3. kandidat `k` samo ako svaka komponenta može zadovoljiti cross-file sufficiency;
4. versioned wrapped robust Laplace ili ekvivalentni eksplicitni model;
5. scale floor iz stvarne MIDI phase rezolucije;
6. minimalni BIC, bez ručnog distance/separation praga;
7. tie ili degeneracija daje review;
8. svaka komponenta prolazi distinct-file/bar/source-dominance gate;
9. leave-one-source-out mora zadržati component count i order;
10. initialization, tie-break, circular order i serialization su versioned.

Statusi:

```text
ASSESSED_UNIMODAL
ASSESSED_MULTIMODAL
INSUFFICIENT_MODAL_EVIDENCE
UNSTABLE_MODAL_STRUCTURE
DEGENERATE_EXACT_REFERENCE
NUMERICAL_REVIEW_REQUIRED
```

Samo `ASSESSED_UNIMODAL` prolazi modality dio analyze authorizationa. Multimodal se ne svodi na prosjek.

## Hard fail i preserve

Hard fail: RAW/SHA/source kontaminacija, declared-valid parse failure, stable-ID kontradikcija, core structural adapter crash, konfliktna adapter registracija, nedokazan `NOT_DETECTED`, cross-source subject, nondeterministic modality, schema/FK/digest failure, destructive polje ili source mutacija.

Preserve/review: external dependency gap, nepotvrđen RX/DNC, unjoinable evidence, ambiguous kandidat, RARE/OUTLIER, insufficient/unstable/multimodal Factory distribucija, Factory/reference disagreement ili default/conflict context.

## Performance ugovor

- jedan RAW parse po source/build prolazu;
- adapteri dijele immutable context;
- memory bounded na jedan source plus agregate;
- sparse membership samo za detected/ambiguous/protected subjekte;
- najviše jedan membership po `(source, subject, rule, adapter_version)`;
- Factory modality koristi preagregirane source-level vrijednosti;
- deterministički insert/merge order;
- atomic temp database je rollback granica;
- report navodi parse count, coverage, sparse/dense ratio, peak source notes, modality contexts i semantic digest.

## Ownership prijedlog

Implementer adapter core:

```text
rxoptimizer/rhythm_protection.py
rxoptimizer/rhythm_protection_adapters.py
tests/test_rhythm_protection.py
tests/test_rhythm_protection_adapters.py
```

Implementer multimodal:

```text
rxoptimizer/rhythm_multimodal.py
tests/test_rhythm_multimodal.py
tests/fixtures/x10_multimodal/
```

Lead integration nakon QA:

```text
rxoptimizer/rhythm_negative_corpus.py
rxoptimizer/rhythm_context_join.py
rxoptimizer/rhythm_context_models.py
tests/test_rhythm_context_models.py
tests/test_rhythm_context_schema.py
analysis/agent_work_packages.json
COMPLETION_REPORT.md
SESSION_CHECKPOINT.md
```

Postojeći strumming, trill, calibration i consensus moduli ostaju read-only bez posebnog migration subpackagea.

## Prioriteti

1. Protocol + sparse schema.
2. Cross-bar, section, tempo/meter i local-repeat adapteri.
3. Guitar, ornament i drum adapteri.
4. RX/DNC Evidence Registry adapter.
5. Factory-only robust multimodal gate.
6. Post-consensus Factory/reference conflict.
7. Kontrolisani full-corpus build/status ugovor.

## Acceptance sažetak

Svih devet rule keyjeva mora imati versioned contract; non-clear rezultat exact stable-ID join; `NOT_DETECTED` mora imati complete coverage; nema dense clear redova; structural adapteri koriste stvarne granice/patterne; heuristic instrument/articulation ostaje preserve; RX/DNC ne vjeruje katalogu; šest pjesama i optimizer/repaired output su SHA-zabranjeni; Factory modality je NORMAL/exact/Factory-only, source-balanced, deterministic, grid-free i bez ručnih timing pragova; multimodal/unstable/insufficient blokira authorization; dva builda imaju isti digest; failure čuva staru bazu; SQLite/FK/testovi prolaze; input MIDI je nepromijenjen; nezavisni QA daje `ACCEPT`, `RETURN` ili `BLOCK`.

Human Owner zadržava isključivo pravo potvrde Pa800 evidencea, promotiona hardware rezultata, proposal/repair capabilityja i releasea.

## Architect verdict

```text
READY_FOR_AUDIT
```