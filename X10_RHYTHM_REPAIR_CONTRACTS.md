# X10 Rhythm Repair — obavezni ugovori prije implementacije

Datum: 11. august 2026.

## 1. Data Contract

Slojevi se fizički i logički razdvajaju:

```text
RAW_FACTORY
VALIDATED_FACTORY
FACTORY_DNA
BALKAN_REFERENCE_RAW
GOLD_CANDIDATE
VALIDATED_GOLD_DNA
CALIBRATED_MODEL
USER_INPUT
REPAIR_SESSION_SNAPSHOT
REPAIR_PROPOSALS
REPAIRED_OUTPUT
```

Obavezno za svaki source/model zapis:

- immutable source SHA-256 i member path;
- corpus class i validation status;
- style/section/CV/track/channel/Bank/Program;
- parser, extractor, schema i rules version;
- sample count i evidence locator;
- `NORMAL`, `RARE`, `OUTLIER` ili `INVALID` status;
- zabrana da optimizer/repair output automatski postane DNA.

## 2. Event Identity Contract

Svaki MIDI događaj dobija stabilni identitet izveden iz:

```text
input_sha256 + track + original_order + event_kind + channel + original_tick
```

Note par dobija poseban `note_id` koji povezuje Note On i Note Off. Repair smije promijeniti samo odobrena polja istog identiteta. Track, channel, pitch i unrelated događaji ostaju identični osim ako poseban versioned rule izričito dozvoli drugačije.

## 3. Rule Contract

Jedinstveni Rule Registry mora sadržati:

- `rule_id`, version, status i owner;
- priority, specificity i scope;
- role/section/pattern/meter/tempo preconditions;
- required evidence i minimum samples;
- protected/negative conditions;
- dozvoljenu akciju i maksimalni delta;
- validation funkciju;
- conflict resolution;
- provenance i test IDs.

Konflikt se rješava redom: safety → specificity → evidence confidence → rule priority. Neriješen konflikt daje `REVIEW_REQUIRED`, nikad repair.

## 4. Calibration Contract

Tolerancije se ne hardkodiraju. Za svaki dovoljno specifičan kontekst računaju se:

- median i MAD;
- IQR i relevantni percentili;
- distribution density;
- sample/file/style coverage;
- tempo/PPQ-normalizovana granica;
- minimum meaningful repair delta;
- maximum allowed repair delta;
- confidence i fallback distance.

Fallback hijerarhija:

```text
EXACT_PATTERN
→ ROLE + SECTION + CV + METER + TEMPO
→ STYLE_FAMILY
→ VALIDATED_FACTORY_DNA
→ VALIDATED_GOLD_DNA
→ NO_EVIDENCE
```

Svaki fallback smanjuje confidence. `NO_EVIDENCE` znači `NO_REPAIR`.

## 5. Analysis Contract

Prije prijedloga repaira sistem mora proizvesti:

- role sa confidence ili `UNKNOWN`;
- section i boundary confidence;
- bar/beat/subbeat i multi-bar kontekst;
- pattern instance/fingerprint;
- neighbour i cross-bar odnose;
- syncopation, anticipation, pickup, fill i articulation zaštite;
- Factory/Gold distance, tolerance, samples i conflicts;
- anomaly class ili `FACTORY_VALID/GOLD_VALID/WITHIN_TOLERANCE`.

Grid je dozvoljen samo kao koordinatni opis. Nije dokaz da je event pogrešan.

## 6. Repair Contract

Početni režim je `ANALYZE_ONLY`. Kada se kasnije omogući repair, tok je:

```text
SNAPSHOT → ANALYZE → PROPOSE → SIMULATE → VALIDATE → COMMIT/REJECT
```

Svaki proposal mora imati:

- stable event/note ID;
- original i candidate vrijednost;
- najmanji scope;
- Factory, Gold, local-pattern i neighbour dokaz;
- confidence i conflicts;
- modification cost;
- repair budget impact;
- očekivano poboljšanje;
- potpuno objašnjenje.

Nema pozitivnog poboljšanja ili postoji dilema: `REJECT/PRESERVE`.

## 7. Protection Contract

Automatski su zaštićeni:

- `UNKNOWN` role;
- šest Delay/Terca referentnih pjesama kao training evidence;
- RX/DNC/articulation-sensitive događaji bez potvrđenog pravila;
- Guitar Mode command/chord kodovi;
- ornaments, grace notes i trill core;
- validna syncopation/anticipation/pickup/fill/cross-bar fraza;
- SysEx i svi non-target kontroleri;
- pitch, velocity i duration kada repair cilja samo timing.

Protection violation blokira session i zahtijeva rollback.

## 8. Validation Contract

Candidate se prihvata samo ako:

- MIDI ostaje validan;
- non-target semantic hash/parity prolazi;
- Factory/Gold reference similarity se poboljšava;
- groove i pattern score se ne pogoršavaju;
- syncopation i musical intent ostaju očuvani;
- scope i budget nisu prekoračeni;
- nema novog overlap/unmatched/duplicate problema;
- svaki edit ima provenance.

Validation failure daje rollback cijele transakcije.

## 9. Audit/Rollback Contract

Session čuva input/output hash, sve version lockove, konfiguraciju, proposals, rejectione, conflicts, simulation metrics i final status. Original se nikada ne prepisuje. Rollback mora biti moguć bez ponovnog računanja i mora vratiti byte-identičan session snapshot.

## 10. Test Contract

Obavezni corpus slojevi:

- `GOLDEN`: validirani poznati repair primjeri;
- `NEGATIVE`: validni Factory microtiming, groove, syncopation, guitar/bass anticipation, fill i pickup;
- `EDGE`: empty/one-note/dense/sparse/tempo change/triplet/cross-bar;
- `ADVERSARIAL`: pogrešan role/section/pattern, DB conflict, corrupted model i budget overflow;
- `CORRUPTION`: kontrolisani single-event, beat, subbeat, bar i pattern kvarovi;
- `CERTIFICATION`: immutable, versioned i odvojen od treninga.

Najvažniji KPI je `false_repair_rate`. Certification prag mora biti definisan prije uključivanja automatskog repaira. Sigurnost ima prednost nad recallom.

## 11. UI Contract

GUI mora prikazati `Before`, `After`, role/section/pattern, Factory/Gold match, tolerance, confidence, razlog, conflicts i validation rezultat. Korisnik mora imati `Analyze`, `Dry Run`, `Preview`, `Accept selected`, `Reject`, `Rollback` i `Export Report`.

## 12. Certification Contract

`CERTIFIED` je dozvoljen tek nakon database, calibration, determinism, integrity, protection, groove, pattern, regression, adversarial, rollback, dry-run, audit i human blind A/B prolaza.

Dok to nije ispunjeno:

```text
AUTO_REPAIR = DISABLED
CERTIFICATION = NOT_READY
```

## 13. Agent Governance Contract

Svaki X10 work package mora proći formalni tok:

```text
Human Goal → ChatGPT Architect → ChatGPT Audit → Codex Lead
→ Codex Implementer → Codex Lead Integration → Codex QA
→ Human Owner
```

Codex QA mora biti nezavisan od Implementera i vraća isključivo `ACCEPT`, `RETURN` ili `BLOCK`. Tehnički `ACCEPT` ne predstavlja Pa800 dokaz niti release; te odluke pripadaju Human Owneru. Detalji su u `X10_AGENT_OPERATING_MODEL.md`.
