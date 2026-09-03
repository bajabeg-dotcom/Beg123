# WP-X10-011 — Architect Brief

Datum: 11. august 2026.

Status: `ARCHITECT_READY`

Capability: `ANALYZE_ONLY`

## Cilj

Svakom analiziranom `note_id`, onset clusteru, baru i consensus rezultatu pridružiti dokaziv kontekst:

```text
ROLE + ROLE_CONFIDENCE
BANK/PROGRAM SEGMENT
SECTION + SECTION_CONFIDENCE
CV + CV_STATUS
METER SEGMENT
TEMPO SEGMENT
PROTECTION FLAGS
SOURCE LINEAGE
```

Sistem smije klasifikovati i objasniti observation/review rezultate, ali ne smije proizvoditi target tick, proposal ili MIDI izmjenu.

## Scope

1. Bank/Program atribucija prema stanju aktivnom na Note On `(tick, order)`.
2. Role klasifikacija sa metodom/confidence statusom ili `UNKNOWN`.
3. Razdvajanje eksplicitnog CV0 od nepoznatog CV-a.
4. Section vrijednost, provenance, metoda i confidence.
5. Tempo timeline, tempo pri Note On događaju i boundary/conflict zaštita.
6. Join sa stable event/note ID, calibration profilima i Factory consensusom.
7. Versioned negative corpus i protection observations.
8. Factory autoritet; Gold/reference samo support/contradiction.
9. Fail-closed rezultat sa `repair_allowed=false`.
10. Reproducibilan atomski builder, semantic digest i testovi.

Preporučeni izvedeni sloj: `rhythm_context_join.sqlite3`.

Minimalne tabele:

```text
context_build_info
source_context
program_segments
tempo_segments
note_context
bar_context
protection_observations
negative_corpus_cases
context_join_summary
```

## Non-goals

- Nema repaira, quantizea, humanizacije, proposal sloja ni target ticka.
- Nema izmjene performance optimizera niti automatskog Sound mapiranja.
- Nema potvrđivanja RX/DNC triggera bez hardware dokaza.
- Nema korištenja šest song fajlova izvan Delay/Terca identifikacije.
- Nema učenja iz optimizer outputa.
- Gold/reference nije Factory autoritet.
- Nema UI Accept/Reject niti auto-repair.
- Heuristika se ne predstavlja kao potvrđena role/section/CV činjenica.

## Dependencies i fail-closed pravila

- stable event/note identity;
- `rhythm_validation`, `rhythm_calibration`, `rhythm_consensus`;
- RAW Factory i Gold/reference ili reproducibilan `DNA.zip` build;
- exact Program segment semantika;
- source SHA-256 inventory i šest-song SHA exclusion.

Ako dependency/hash ne odgovara, RAW nedostaje ili protection evidence nije spojiv, build/analysis daje `PRESERVE`, `UNKNOWN` ili prekid — nikad tihi fallback.

## Context contract

Svaka nota mora imati najmanje:

```text
note_id, on_event_id, source_sha256, member_path,
track, channel, start_tick, on_event_order,
bank_msb, bank_lsb, program, program_segment_id, program_status,
role, role_confidence, role_method,
section, section_confidence, section_method,
cv, cv_status, cv_method,
tempo_bpm, tempo_segment_id, tempo_status,
meter_num, meter_den, bar, beat,
protection_flags, context_version
```

## Program contract

- Bank Select ostaje pending do sljedećeg Program Changea.
- Note On koristi stanje aktivno na tačnom `(tick, order)`.
- Program Change poslije Note On na istom ticku ne mijenja tu notu.
- Multi-program track ostaje segmentiran.
- Dominantni track program nije note-level fallback.
- Nedokaziva adresa daje `PROGRAM_UNKNOWN`.

## Role contract

Dozvoljene evidence kategorije:

```text
CONFIRMED_METADATA
HIGH_CHANNEL_OR_EXACT_RULE
MEDIUM_PROGRAM_FAMILY
LOW_HEURISTIC
UNKNOWN
```

`melodic` nije default za nepoznato. Low/Unknown aktivira `UNKNOWN_OR_LOW_ROLE`. Numerički confidence mora biti versioned derivacija kategorije, ne lažna empirijska vjerovatnoća.

## Section/CV contract

- Section čuva vrijednost, metodu i confidence.
- CV čuva vrijednost i status odvojeno.
- Nedostajući CV je `NULL/UNKNOWN`, nikad implicitni CV0.
- CV0 postoji samo uz eksplicitan dokaz.
- Intro/Fill/Break/Ending ostaju `SECTION_SENSITIVE`.

## Tempo contract

Tempo događaji se sortiraju po `tick → track → event order`. Nota dobija tempo aktivan na Note On događaju.

Statusi:

```text
TEMPO_EXACT
TEMPO_DEFAULT_UNSPECIFIED
TEMPO_BOUNDARY
TEMPO_CONFLICT
```

Tempo/meter boundary aktivira preserve gate; nema proizvoljnog okolnog prozora u ovoj fazi.

## Consensus join contract

Exact ključ:

```text
role + section + CV status/value + meter + program identity
+ tempo regime + topology + onset-cluster count
```

Lookup rezultat:

```text
EXACT_CONTEXT_MATCH
EXPLICIT_FALLBACK_MATCH
INSUFFICIENT_CONTEXT_EVIDENCE
CONTEXT_CONFLICT
```

Fallback je uvijek objašnjen, navodi uklonjene dimenzije i confidence decay. Gold/reference ne autorizuje Factory consensus.

## Negative corpus contract

Svaki case ima:

```text
case_id, category, source_class, source/synthetic locator,
expected_protection, expected_status, evidence_status,
human_validation_status, rules_version
```

Obavezne kategorije: syncopation, pickup/anticipation, section transition, cross-bar, local repeat, tempo/meter transition, Guitar Mode, RX/DNC, trill/grace/ornament, drum flam/roll/ghost, ambiguous onset cluster, Factory/Gold conflict, unknown role/program/CV i zero-variance consensus.

Nedokazan detektor daje `PRESERVE_UNTIL_IMPLEMENTED`.

## Prioriteti

1. `WP-X10-011A` P0 — Context schema i timelines.
2. `WP-X10-011B` P0 — Role, Section i CV evidence.
3. `WP-X10-011C` P1 — Consensus context join.
4. `WP-X10-011D` P1 — Negative corpus i protection registry.
5. `WP-X10-011E` P2 — Analyze-only integration.
6. `WP-X10-011F` P2 — Regression, adversarial i QA handoff.

## Acceptance kriteriji

1. Stabilan `note_id` za svaku analiziranu notu.
2. Exact Program segment prati same-tick event order.
3. Pending CC0/32 bez Program Changea ne mijenja instrument.
4. Multi-program track nema dominantni note-level fallback.
5. Role ima method/confidence ili `UNKNOWN`.
6. Nepoznata role nije implicitni melodic.
7. Nepoznati CV nije CV0.
8. Section provenance/confidence je eksplicitan.
9. Note dobija aktivni tempo na Note On.
10. Tempo/meter boundary i conflict aktiviraju preserve.
11. Consensus ne gubi Program/CV/tempo bez evidentiranog fallbacka.
12. Factory je jedini `FACTORY_CONSENSUS` autoritet.
13. Gold/reference samo support/contradiction.
14. Svaka negative kategorija ima case i očekivani preserve rezultat.
15. Nedostajući detektor znači `PRESERVE_UNTIL_IMPLEMENTED`.
16. Šest song fajlova blokirano je SHA pravilom.
17. Optimizer output nije evidence.
18. Svaki anomaly rezultat ima `repair_allowed=false`.
19. Nema target/candidate tick polja.
20. Builder je atomski i fail-closed na dependency/hash grešku.
21. Isti input daje isti semantic digest.
22. SQLite integrity/FK prolazi.
23. Postojeći i novi pytest testovi prolaze bez warninga.
24. Codex QA je nezavisan i izdaje samo `ACCEPT`, `RETURN` ili `BLOCK`.

## Human decisions required

Za `ANALYZE_ONLY` implementaciju nije potrebna nova odluka ako se primijeni najkonzervativnija politika.

Prije proposal/repair faze Human Owner mora odlučiti o obaveznom Program/CV kontekstu, dozvoljenim role-confidence kategorijama, ljudski potvrđenim negative primjerima, Pa800 OS/resources kontekstu, false-repair pragu i svakom prelasku na `PROPOSAL_ONLY` ili `REPAIR_CAPABLE`.
