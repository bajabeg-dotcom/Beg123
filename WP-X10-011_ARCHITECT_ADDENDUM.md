# WP-X10-011 — Architect Addendum

Datum: 11. august 2026.  
Verzija: 2  
Capability: `ANALYZE_ONLY`  
Verdict: `READY_FOR_REAUDIT`

Ovaj dodatak zamjenjuje neprecizne ili konfliktne dijelove prvobitnog Architect briefa i zatvara P0 zahtjeve iz `WP-X10-011_AUDIT.md`.

## Revidirani cilj i data flow

WP-X10-011 gradi novi, isključivo RAW-derived context-qualified sloj:

```text
RAW MIDI
→ validation gate
→ stable event/note extraction
→ Program/meter/tempo timelines
→ style/section/CV/role evidence
→ note i bar context
→ context-qualified local calibration
→ context-qualified Factory consensus
→ analyze-only observations
```

Legacy `repeated_pattern_calibration`, `consensus_context` i `consensus_event_slot` ostaju historijski slojevi. Ne smiju se naknadnim JOIN-om predstavljati kao da su izvorno trenirani uz Program, CV, tempo ili prošireni section kontekst.

Novi builder proizvodi `rhythm_context_qualified.sqlite3` sa logičkim tabelama za build/source lineage, channel-state events, Program/meter/tempo segmente, note/bar context, local calibration, Factory consensus/evidence, protection observations, negative corpus, summary i semantic digest. Ne mijenja MIDI i ne proizvodi proposal ili repair podatke.

## Cross-track channel-state semantika

- Unutar istog tracka autoritet je `(tick, event.order)`.
- Između različitih trackova na istom ticku ne postoji izmišljeni totalni redoslijed.
- Identični state događaji na istom source/channel/tick/kind/value smiju se deduplicirati uz očuvanje svih evidence lokatora.
- Različite vrijednosti istog state elementa daju `PROGRAM_CONFLICT`.
- Bank Select iz jednog tracka i Program Change iz drugog na istom ticku daju `PROGRAM_CONFLICT/CROSS_TRACK_SAME_TICK_BANK_PROGRAM_ORDER_UNPROVEN`.
- Note On i Program Change u istom tracku poštuju lokalni order. Ako je promjena samo u drugom tracku na istom ticku, note dobija `PROGRAM_SAME_TICK_AMBIGUOUS` i preserve status.
- Konflikt traje do kasnijeg nekonfliktnog Program Changea. Nedokazani Bank nakon toga ostaje parcijalno poznat.
- Program pripadnost note određuje Note On; kasniji Program Change prije Note Off ne mijenja njen identitet.

Početno stanje je `bank_msb=NULL`, `bank_lsb=NULL`, `program=NULL`, `PROGRAM_DEFAULT_UNSPECIFIED`. Nikada se ne pretpostavlja `(0,0,0)` niti GM piano. Program bez dokazanog Banka je `PROGRAM_PARTIAL_UNSPECIFIED_BANK`.

V1 statusi su:

```text
PROGRAM_EXACT
PROGRAM_DEFAULT_UNSPECIFIED
PROGRAM_PARTIAL_UNSPECIFIED_BANK
PROGRAM_UNKNOWN
PROGRAM_CONFLICT
PROGRAM_SAME_TICK_AMBIGUOUS
```

Samo `PROGRAM_EXACT` ulazi u context-qualified calibration i consensus.

## Style, section i CV

Style čuva `style_name`, status, method i evidence locator. Statusi su explicit metadata, filename-derived, conflict i unknown. Filename nije potvrđeni MIDI metadata dokaz.

Section čuva `section`, nullable `section_no`, status, method i locator. Nedostajući broj nije nula. Exact context zahtijeva poznat section i, za numerisane elemente, poznat `section_no`.

CV čuva nullable vrijednost, status, method i locator. `CV_UNKNOWN` nikada nije CV0. Samo eksplicitni CV ili dokazivo `CV_NOT_APPLICABLE` može u exact context.

## Meter i tempo

Svaki meter segment ima stabilni semantic ID, source SHA, tick granice, numerator/denominator, status i locatore. Nedostajući meter može koristiti 4/4 samo kao transportni default `METER_DEFAULT_UNSPECIFIED`, koji nije exact evidence. Različiti same-tick meter događaji daju `METER_CONFLICT`; pogođeni boundary dobija preserve zaštitu.

Tempo identitet koristi integer MPQN (`microseconds_per_quarter`), ne float BPM. `tempo_regime_key` v1 je exact MPQN; nema bucketa ni nearest-tempo fallbacka. Nedostajući tempo je `TEMPO_DEFAULT_UNSPECIFIED`. Različiti same-tick MPQN događaji daju `TEMPO_CONFLICT`. Pattern/bar koji presijeca promjenu ili konflikt dobija `METER_OR_TEMPO_CHANGE_WINDOW` zaštitu.

## Exact-only v1

V1 nema fallback. Rezultat je samo:

```text
EXACT_CONTEXT_MATCH
NO_EXACT_CONTEXT
INSUFFICIENT_EXACT_EVIDENCE
CONTEXT_CONFLICT
PROTECTED_CONTEXT
```

Zabranjeni su role/family/section/CV/Program fallback, nearest tempo, general Factory i Gold fallback.

Exact key uključuje role, exact Bank/Program, section i `section_no`, CV status/value, meter, exact MPQN, topology SHA i onset-cluster count. Style je obavezna provenance/coverage dimenzija, ali nije identity ključ cross-file consensusa; builder izvještava distinct styles i dominant-style share.

## Data-quality i negative corpus

Track politika:

```text
NORMAL  → calibration i Factory consensus
RARE    → observation/review i preservation evidence
OUTLIER → review only
INVALID → potpuno isključen
```

Negative izvori ostaju odvojeni kao Factory observation, reference observation, synthetic guard fixture i Human-validated negative. Synthetic fixture testira software contract, ne Korg ponašanje. Šest Delay/Terca pjesama, optimizer output i repaired output su zabranjeni; rename se blokira SHA-256 pravilom. Human Owner jedini promovira Pa800/listening dokaz.

## Stable-ID protection adapteri

Svaki adapter vraća observation ID, source SHA, stable note/event ID, rule key, detection/evidence status, locator i verziju. `AMBIGUOUS`, `ADAPTER_UNAVAILABLE` i `EVIDENCE_UNJOINABLE` uvijek znače preserve. Legacy evidence se povezuje samo exact locatorom nakon ponovnog parsiranja RAW sourcea; nema približnog tick/pitch/name/index spajanja.

Adapteri pokrivaju Guitar Mode, RX/DNC, trill/grace/ornament, drum flam/roll/ghost, cross-bar, section transition, tempo/meter boundary, local repeated pattern i Factory/reference conflict.

## Semantic digest i determinism

SQLite file hash nije semantic digest. Digest se računa kao SHA-256 nad kanonskim UTF-8 JSON Lines zapisima semantic tabela. Isključeni su rowid, autoincrement, insertion order, timestamps, page layout, apsolutne putanje, file size i privremena imena. Ključevi i redovi se sortiraju po versioned natural keys; `NULL` ostaje JSON `null`, integer ostaje integer, binary se predstavlja SHA-256 digestom, a locator normalizovanim POSIX member pathom.

Dva builda sa istim sourceom, konfiguracijom i verzijama moraju dati identične kanonske redove i semantic digest; byte-identičan SQLite nije zahtjev.

## Hard-fail i row-level preserve

Build hard-failuje i čuva prethodnu validnu bazu ako nedostaje obavezna dependency, SHA/schema ne odgovara, validni source se ne može parsirati, u evidence uđe zabranjeni source/output, natural key ima kontradiktorne duplikate, negative manifest/kategorije nisu validne, digest/integrity/FK ne prolazi, schema sadrži repair/proposal polja ili source bude mutiran.

Program/role/CV/style/section/meter/tempo ambiguity, RARE/OUTLIER, optional adapter gap, insufficient exact sample, neprocijenjena multimodalnost ili Factory/reference kontradikcija ostaju row-level `UNKNOWN`, `PRESERVE`, `PRESERVE_UNTIL_IMPLEMENTED` ili `REVIEW_REQUIRED`; ne ruše cijeli build i ne ulaze u calibration/consensus.

## Analyze-only zabrane

Novi schema i API ne smiju sadržati `target_*`, `candidate_*`, `proposal_*`, `repair_*`, apply, commit ili mutation polja. Metadata mora navesti `capability=ANALYZE_ONLY` i `mutation_capability=NONE`. Input MIDI SHA mora ostati nepromijenjen.

## File ownership

- Architect: `WP-X10-011_ARCHITECT.md`, ovaj addendum.
- Audit: `WP-X10-011_AUDIT.md`, `WP-X10-011_REAUDIT.md`; read-only.
- Lead integration: registry, completion/checkpoint, `rxoptimizer/dna_databases.py`, `app.py`.
- Implementer extraction: `rxoptimizer/rhythm_context_join.py`, `tests/test_rhythm_context_join.py`.
- Implementer model/builder: `rxoptimizer/rhythm_context_models.py`, `tests/test_rhythm_context_models.py`, `tests/test_rhythm_context_schema.py`.
- Implementer negative/protection: `rxoptimizer/rhythm_negative_corpus.py`, `tests/test_rhythm_negative_corpus.py`, declarative `tests/fixtures/x10_negative/` JSON fixtures.
- QA je read-only.
- Existing context/calibration/consensus/database moduli nisu u Implementer ownershipu bez nove Lead odluke.

## Acceptance gate

Acceptance zahtijeva: RAW rebuild; no legacy enrichment; exact Program attribution sa conflict/ambiguity testovima; explicit role/style/section/section_no/CV/meter/tempo provenance; NORMAL-only consensus; exact-only lookup; Factory-only consensus authority; odvojeni reference support/contradiction; stable-ID protections; odvojene negative source klase; šest-song SHA guard; schema/API bez proposal/repair polja; bez MIDI outputa/mutacije; deterministički semantic digest; atomic rollback; SQLite integrity/FK; svi pytest testovi bez warninga; nezavisni QA verdict `ACCEPT`, `RETURN` ili `BLOCK`.

## Architect verdict

```text
READY_FOR_REAUDIT
```