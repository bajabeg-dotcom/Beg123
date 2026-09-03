# X10 Rhythm Consensus i Analyze-only Anomaly Engine

Datum: 11. august 2026.

## Implementirano

`rxoptimizer/rhythm_consensus.py` uvodi fail-closed cross-file sloj:

- Factory i Gold/reference ostaju odvojeni;
- svaki source fajl ima jedan ravnopravan glas, bez pseudo-replikacije stotina taktova iz jednog fajla;
- zahtijevaju se najmanje tri različita fajla i devet ukupnih bar primjera;
- dominantni pojedinačni izvor ne smije preći versioned konfiguracijski prag;
- podržan je samo exact role/section/meter/onset-topology kontekst;
- Factory može dobiti `FACTORY_CONSENSUS`;
- Gold/reference može dobiti samo `REFERENCE_CONSENSUS_CANDIDATE`;
- Gold/reference nikada sam ne autorizuje anomaly niti repair;
- Factory/Gold veza ostaje `SUPPORT_REVIEW` ili `POTENTIAL_CONTRADICTION`.

## Ispravka visokog rizika

Topology identitet sada uključuje:

- onset-cluster veličine;
- relativne inter-onset intervale kao racionalni dio takta;
- cluster/voice pripadnost;
- pitch odnos i trajanje kao PPQ-nezavisni racionalni odnos.

Time se straight i syncopated pattern više ne mogu spojiti samo zato što imaju iste note i trajanja. Kalibracija i anomaly analiza koriste onset-cluster alignment, a ne slijepo note-index uparivanje akorda.

## Consensus schema

Predviđena `rhythm_consensus.sqlite3` baza sadrži:

- `consensus_context`;
- `consensus_event_slot`;
- `consensus_evidence`;
- `factory_gold_links`;
- `negative_rules`;
- versioned build/config hash i summary.

Builder je atomski i odbija nedostajuću calibration bazu.

## Negative rules

Registrovano je 12 početnih pravila. Direktno se trenutno detektuju:

- `CROSS_BAR_PROTECTED`;
- `SECTION_SENSITIVE`;
- `LOCAL_REPEAT_SUPPORTS_ORIGINAL`;
- `MULTIMODAL_UNASSESSED`.

Ostali nedovršeni gateovi imaju akciju `PRESERVE_UNTIL_IMPLEMENTED`, uključujući role confidence, meter/tempo transition, Guitar Mode/RX/DNC, ornaments, drum flam/roll/ghost, onset ambiguity i Factory/Gold conflict.

## Anomaly izlaz

Engine može vratiti:

- `NO_EXACT_FACTORY_CONSENSUS`;
- `OBSERVED_WITHIN_EMPIRICAL_RANGE`;
- `OUTSIDE_EXACT_REFERENCE_REVIEW`;
- `ANOMALY_CANDIDATE_REVIEW`;
- `PROTECTED_OBSERVATION`;
- `PROTECTED_REVIEW`.

Svaki rezultat obavezno sadrži:

```text
repair_allowed = false
```

Ne generiše se target tick i MIDI se ne mijenja.

## Verifikacija

- pytest collection problem za `test_agent_status` je uklonjen bez API renamea;
- nezavisni test agent: 91 passed, 0 failed/errors, 0 warninga;
- onset topology, onset-cluster alignment, insufficient-file gate, local-repeat protection i fail-closed anomaly ponašanje imaju testove.

## Fizička materializacija

Velike SQLite baze u ovom workspace okruženju nisu trajne između svih sesija. Posljednji puni corpus/calibration build je verificirao generaciju `335ad9cb42bd41768993`, ali trenutni pointer je uklonjen kada su njegovi target fajlovi nestali. Time se sprečava lažni aktivni status.

Za novi puni build:

```bash
python3 app.py import-archive prism-uploads/DNA.zip
```

Import pipeline sada redom gradi RAW snapshot, validation, calibration i consensus bazu.
