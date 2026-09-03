# WP-X10-012 — Architect Addendum

Datum: 11. august 2026.  
Verzija: 2  
Capability: `ANALYZE_ONLY`  
Status: `READY_FOR_REAUDIT`

Ovaj dodatak zatvara P0/P1 nalaze iz `WP-X10-012_AUDIT.md` i zamjenjuje neprecizne dijelove prvog briefa.

## S0–S5 stageovi

```text
S0 RAW validation + exact context + stable subject registry
S1 pre-model protection: 8 adaptera bez Factory/reference conflict
S2 model eligibility + Factory profile extraction
S3 Factory consensus + multimodal assessment
S4 post-model Factory/reference conflict
S5 final analyze authorization
```

`DETECTED` protection može ostati Factory evidence, ali blokira kasniju anomaly autorizaciju. `FACTORY_REFERENCE_CONFLICT` nikada nije pre-model dependency.

Odvojeni statusi: context eligibility, model eligibility, protection, Factory model, multimodal, reference relationship i final authorization.

## Stable subject registry

Tipovi: `EVENT`, `NOTE`, `ONSET_CLUSTER`, `BAR`, `PHRASE`, `COMPONENT`, `BOUNDARY`, `TRACK_CHANNEL`, `PROGRAM_SEGMENT`, `EXACT_CONTEXT`.

ID je SHA-256 canonical JSON-a `[contract_version, subject_type, source_sha256, natural_key]`. Natural keys koriste postojeće stable event/note ID-jeve, exact track/channel, meter segment i stvarne bar tick granice, sorted on-event membership za cluster, ordered note membership za phrase/component, te segment ID-jeve za boundary.

`stable_subject_edges` čuva versioned parent-child/many-to-many relacije poput track→event/note, note→on/off, bar→cluster, cluster/phrase/component→note, boundary→bar/note, Program segment→note i context→note. Kontradiktorna natural-key definicija ili zabranjeni ciklus je hard fail.

## Sparse applicability/coverage proof

Svaki adapter run čuva source/rule/version/class, scope type/subject, versioned applicability predicate, subject-universe query/count/digest, applicable/scanned/resolved/protected/ambiguous counts, input/dependency/result digeste i run status.

Scope: source, track/channel, Program segment, bar, phrase, exact context ili consensus context. Determinističke coverage particije koriste stable scope ID, ne runtime chunk broj.

Odsustvo per-subject reda znači `NOT_DETECTED` samo ako subject pripada dokazanoj applicable populaciji, particija je `COMPLETE`, universe/applicability digest odgovara registryju, nema dependency/contract konflikta i subject nije u non-clear grupi. Partial scan zadržava explicit nalaze, ali sve ostalo ostaje preserve.

## RAW re-extraction

Svaki legacy evidence izvor je `REEXTRACTABLE_EXACT`, `UNJOINABLE_PRESERVE` ili `DEPENDENCY_UNAVAILABLE`. Exact je dozvoljen samo ponovnim parsiranjem originalnog RAW-a i direktnim stable-subject joinom. Legacy row ID, filename, approximate tick/pitch/range/name nisu join ključevi.

Guitar, ornament, drum, cross-bar, section, tempo/meter i repeat ponovo se izvlače iz RAW-a. RX event je RAW-derived, ali trigger autoritet dolazi iz version-compatible Evidence Registryja. Factory/reference conflict se gradi novi u S2–S4.

## Adapter ugovori

- `GUITAR_MODE` (`CORE_REQUIRED`): exact Track Type je autoritet. Command range bez toga je ambiguous. Potvrđena/ambiguous traka štiti track scope i exact component membership.
- `RX_DNC` (`EXTERNAL_OPTIONAL_FAIL_CLOSED`): razlikuje confirmed non-RX, confirmed complete/incomplete RX trigger coverage, unknown/User Sound i conflict. Catalog-only nikad nije clear.
- `ORNAMENT_TRILL_GRACE` (`CORE_REQUIRED`): trill je maksimalna ≥4-note strogo alternating two-pitch sekvenca kroz različite onset clustere; grace je kraća note vezana za jedinstveni anchor unutar phrasea bez chord membershipa. Ovo je protection candidate, ne potvrđena ornament tvrdnja.
- `DRUM_FLAM_ROLL_GHOST` (`CORE_REQUIRED`): exact drum/percussion/kit scope; lane je Track/Channel + MIDI note. Flam, roll i ghost koriste susjedstvo/cluster/phrase odnose bez fiksnog velocity ili IOI praga; nedovoljan context je ambiguous.
- `CROSS_BAR` (`CORE_REQUIRED`): exact meter note/phrase/bar membership preko stvarne boundary granice; default/conflict meter je ambiguous.
- `SECTION_TRANSITION` (`CORE_REQUIRED`): sve Intro/Fill/Break/Ending note/bar subjekte i prvi/posljednji stvarni bar exact Variation/section sourcea; filename-only je ambiguous.
- `TEMPO_METER_BOUNDARY` (`CORE_REQUIRED`): stable boundary za change/conflict/unspecified→exact; članovi su note/cluster/bar/phrase koji stvarno dodiruju ili prelaze boundary.
- `LOCAL_REPEATED_PATTERN` (`CORE_REQUIRED`): exact `(track-channel, meter, rhythm hash, topology hash)` sa najmanje dvije bar instance; approximate similarity nije v1.
- `FACTORY_REFERENCE_CONFLICT` (`POST_MODEL_REQUIRED`): samo nakon stable Factory modality i exact reference contexta; nema referencea znači complete not-applicable, nestabilan Factory model znači deferred.

Programming/schema/stable-ID greška bilo kojeg adaptera je hard fail. Missing external RX evidence je row-level preserve. Missing local core dependency je hard fail. Semantic uncertainty je preserve.

## Schema v2

V1 ostaje immutable. V2 je puni RAW rebuild, bez `ALTER`, legacy-ID migracije ili nasljeđivanja v1 digesta.

Obavezne tabele: stable subjects/edges, adapter registry/runs/partitions, protection groups/members, context/model eligibility, Factory local profiles/consensus slots, multimodal context/components, reference relationships, final authorization i semantic digest.

Implementer dobija nove subject/protection/multimodal/reference module i testove. Lead nakon QA integriše v2 u postojeće context module i schema tests. Digest v2 pokriva sve nove semantic tabele.

## `X10_WRAPPED_LAPLACE_BIC_V1`

Input je exact reduced rational circular phase `x=tick_in_bar/bar_ticks` za Factory NORMAL exact context/slot.

Exact-repeat pre-gate: ako su svi reduced rational zapisi isti, status je `DEGENERATE_EXACT_REFERENCE`, `k=1`, bez fita i bez izmišljene tolerancije.

Equal-source hierarchical weights čuvaju sve bar observations, ali svaki source ima jednaku ukupnu težinu. Za source sa `n_s` observationa koristi se `q=1/n_s`, zatim normalizacija na effective sample size `n_eff`; isti `n_eff` ide u BIC.

Circular distance je `min(|x-μ|,1-|x-μ|)`. Wrapped Laplace density je:

```text
exp(-d/b) / [2b(1-exp(-1/(2b)))]
```

Mixture ima `π>0`, sumu težina 1, `μ∈[0,1)` i scale floor kao weighted median half-tick phase rezolucije članova komponente.

`k_max=min(unique rational phases, floor(bar observations / existing B_min))`. Svaka komponenta mora sama proći postojeći `F_min`, `B_min` i dominant-source gate. `p_k=3k-1`; `BIC=-2L+p ln(n_eff)`. Strict minimalni finite BIC pobjeđuje; binary64 tie daje unstable.

Inicijalizacija je deterministic farthest-first iz observed rational phases. EM koristi canonical source/bar order, responsibility-weighted circular absolute-deviation observed mean, weighted mean distance scale, canonical component sort, max 1024 iteracije i cycle digest. NaN, cycle ili non-convergence daje numerical review.

Leave-one-source-out zahtijeva najmanje `F_min+1` sources, isti selected `k` i exhaustive circular component matching uz deterministic tie-break. Promjena `k`, ambiguous matching ili insufficient fold daje unstable.

Per-slot modality se spaja u context status. Multimodal slotovi moraju dati stabilne cross-slot groove-mode signature tupleove koji sami prolaze sufficiency i leave-one-source-out. Stabilni multimodal context i dalje ostaje preserve dok nema mode-assignment repair ugovora.

## Factory/reference metric

Reference ne refituje Factory model. Svaka sufficient Factory komponenta dobija najkraći circular empirical support arc svih hard-assigned rational phases, proširen samo stvarnom half-tick rezolucijom članova. Reference je support ako je unutar unije arcova; potential contradiction tek ako reference sama prolazi sufficiency i ima observation izvan svih arcova. Insufficient reference ostaje insufficient, a unstable Factory model deferred. Degenerate Factory support dopušta samo resolution-equivalent identičnu fazu.

## Authorization precedence

Hard failure abortuje build. INVALID se isključuje; RARE/OUTLIER, non-exact context ili incomplete core scan se čuvaju. Factory NORMAL exact/core-complete može biti model evidence. Detected/ambiguous protection, RX evidence gap, insufficient Factory consensus, zero variance, unresolved modality, stable multimodality, deferred reference gate ili potential contradiction daju odgovarajući preserve/review status. `ANALYZE_ALLOWED` postoji samo kada su svi adapteri clear/non-applicable, Factory je sufficient unimodal, a reference je support ili insufficient/not-applicable. Svaki izlaz ostaje bez repair/mutation capabilityja.

## Disk-backed corpus build

Zabranjeno je `list(source_records)`, držanje corpusa u RAM-u, dense 9×note clear rows i ponovno parsiranje po adapteru. Atomic temp SQLite spool čuva manifest, subjects, adapter rezultate, profile i multimodal podatke. Source se parsira jednom, adapteri dijele isti immutable source, merge order je canonical SHA/type/ID, modality čita indexed context/slot/source observations.

Complexity je linearna ili indexed po sourceu; memory je najveći source + aktivni context. Report mora sadržati source/parse count, subject counts, adapter/partition/non-clear/membership counts, dense-equivalent i sparse ratio, peak source size, modality fit metrike, spool/final bytes i semantic digest. Acceptance zahtijeva `parse_count==source_count`, bez dense storagea i deterministički report/digest.

## Acceptance

S0–S5, registry/edges, sparse coverage/partial semantics, RAW re-extraction klasifikacija, svih devet zatvorenih adaptera, registry class crash policy, schema-v2 full rebuild, complete wrapped-Laplace/BIC/LOSO/groove coherence, Factory/reference support metric, authorization truth-table testovi, six-song/optimizer guards, Factory-only fit, disk-backed single-parse build, sparse report, no mutation/destructive fields, atomic rollback, digest/FK/integrity i targeted/adversarial/full pytest moraju proći prije nezavisnog QA verdicta.

## Architect verdict

```text
READY_FOR_REAUDIT
```