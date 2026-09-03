# X10 Rhythm Repair — Certification Gap i reverse plan

Datum: 11. august 2026.

## Release cilj

Production release znači: minimalan, dokaziv timing repair sa nižim prioritetom od očuvanja validne izvedbe, reproducibilnim bazama, per-event auditom, rollbackom i potvrđenim ljudskim A/B testom.

## Reverse plan

### Faza A — Audit i ugovori

Status: `COMPLETED`.

- architecture/database/data/rhythm/test/safety audit;
- klasifikacija postojećih komponenti;
- Data, Event, Rule, Calibration, Analysis, Repair, Protection, Validation, Audit, Test, UI i Certification ugovori;
- zabrana predstavljanja postojećeg grid-derived optimizera kao X10 repaira.

### Faza B — Reproducibilni corpus i data quality

Status: `COMPLETED_WITH_REVIEW_QUEUE`.

- obnoviti Factory/Gold SQLite iz `prism-uploads/DNA.zip`;
- napraviti aktivni read-only generacijski snapshot;
- prebaciti runtime read upite na layout pointer;
- validirati svaki MIDI/track/event i klasifikovati duplicates/outliers;
- materijalizovati `VALIDATED_FACTORY` i `BALKAN_REFERENCE_RAW` bez kontaminacije.

Exit gate: semantic parity, integrity/FK, source traceability i reproducibilan rebuild.

Rezultat: aktivni snapshot `335ad9cb42bd41768993`, 0 import grešaka, `rhythm_validation.sqlite3`, 26.403 tracka podobna za validated-DNA review i 9.158 review-required trackova. Runtime legacy read tranzicija ostaje zaseban tehnički dug.

### Faza C — Rhythm representation i Calibration Engine

Status: `PARTIAL_ANALYZE_ONLY`.

- stable event/note ID;
- event/subbeat/beat/bar/multi-bar/pattern/section model;
- detaljne role i `UNKNOWN` confidence;
- groove/accent/syncopation fingerprint;
- robust median/MAD/IQR/percentile tolerances;
- sample sufficiency i fallback confidence decay.

Exit gate: nema hardkodiranih repair tolerancija.

Implementirano: stable event/note ID, meter/bar/beat/subbeat/cross-bar kontekst, 77.315 phrase kandidata, 460.263 multi-bar instance i 8.174 lokalna repeated-pattern profila. Preostaje cross-file/context consensus; samo 220 profila trenutno ima opaženu nenultu timing varijaciju.

### Faza D — Analyze-only anomaly engine

Status: `MISSING`.

- klasifikovati validno ponašanje i moguće anomalije;
- dokazati neighbour/cross-bar/musical intent;
- Factory/Gold consensus/conflict;
- bez MIDI mutacije.

Exit gate: negative corpus false-positive prag zadovoljen.

### Faza E — Proposal, simulation i dry run

Status: `MISSING`.

- više kandidata;
- score i modification cost;
- repair budget;
- shadow MIDI before/after;
- groove/pattern/non-target validation;
- explainable report i preview UI.

Exit gate: nijedan proposal se ne commit-a automatski.

### Faza F — Manual commit i rollback

Status: `MISSING`.

- transaction journal;
- accept/reject selected;
- byte-safe original snapshot;
- atomic export i rollback test;
- per-event provenance.

Exit gate: manual repair prolazi integration, regression i rollback suite.

### Faza G — Safe auto repair

Status: `LOCKED`.

- samo high-evidence exact-context pravila;
- najmanji scope i strogi budget;
- cascade protection;
- `PRESERVE` na konflikt/insufficient evidence.

Exit gate: certification corpus false-repair rate ispod unaprijed versioned praga.

### Faza H — Human A/B i certification

Status: `PENDING_HARDWARE_AND_LISTENING`.

- blind Original/Repaired evaluacija na Pa800;
- timing, groove, naturalness, Factory likeness, artifacts;
- calibration feedback kao nova versioned konfiguracija;
- finalni certification report i known limitations.

## Trenutni release blockeri

1. Gold reference corpus nije kuriran/validiran Gold ruleset.
2. Section-boundary `WARNING_NOTE_PAIR` izvori čekaju kontekstualnu klasifikaciju.
3. Nema robust timing Calibration Enginea.
4. Nema event-level anomaly proofa niti pattern/multi-bar modela.
5. Nema candidate simulation, repair budget i transaction rollbacka.
6. Nema negative/adversarial/certification corpusa i KPI-ja.
7. Nema X10 preview/manual review UI-ja.
8. Nema blind human A/B rezultata.

## Procjena preostalog rada

Kompletan production-grade plan nije sigurno završiti jednim velikim skokom. Realna podjela je približno **7–10 fokusiranih sesija**, pod uslovom da se corpus rebuild izvrši bez novih data problema. Hardware/listening potvrda je dodatna van-softverska sesija.

Najkraći siguran redoslijed je B → C → D → E → F → G → H. Preskakanje C ili D direktno krši korisnikovo apsolutno pravilo o false repairu.
