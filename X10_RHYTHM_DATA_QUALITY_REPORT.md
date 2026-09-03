# X10 Rhythm Repair — Corpus i Data Quality izvještaj

Datum: 11. august 2026.

## Rezultat Phase B

Autoritativni `prism-uploads/DNA.zip` je ponovo uvezen bez parse/import grešaka. Kreiran je aktivni generacijski snapshot:

```text
generation_id = 335ad9cb42bd41768993
```

Oba RAW fajla imaju permission `0444`, a semantic SHA-256 odgovara `data/database-layout.json` pointeru:

- Factory: `8a40bd91181a8d7d509eda400bca802e9ad69689314014f1bfea30801474ff05`
- Gold/reference: `5f4865843164cdc2f4d9ccaadee501c7206294c202f68910d1937c31f4b864c5`

## Corpus

| Corpus | Archive članovi | Jedinstveni fajlovi | Duplikati | Import greške | Trackovi |
|---|---:|---:|---:|---:|---:|
| Factory RAW | 3.211 | 3.187 | 24 | 0 | 29.724 |
| Balkan reference RAW | 182 | 181 | 1 | 0 | 1.883 |

Ukupno je registrovano 3.393 archive člana i 31.607 trackova. Svaki član ima archive member path, SHA-256, veličinu, duplicate rank, RAW database vezu i MIDI validation rezultat.

## MIDI validation

| Corpus | `VALID` | `WARNING_NOTE_PAIR` | `INVALID` |
|---|---:|---:|---:|
| Factory | 2.622 | 589 | 0 |
| Balkan reference | 172 | 10 | 0 |

`WARNING_NOTE_PAIR` znači da section MIDI sadrži unmatched Note On/Off stanje. To nije automatski kvar: Intro/Fill/Ending ili drugi segment može biti izrezan usred trajanja note. Takvi izvori se zato ne brišu i ne “popravljaju”, ali njihovi trackovi ne ulaze automatski u `VALIDATED_DNA` dok se ne analizira section-boundary kontekst.

Factory upozorenja ukupno sadrže 38.482 unmatched Note On i 27.941 unmatched Note Off događaja. Gold/reference upozorenja sadrže 174 unmatched Note Off događaja. Ovo su observations, ne repair naredbe.

## Robust track klasifikacija

Preliminarni data-quality registry koristi median, MAD, IQR i percentile za velocity mean/std, trajanje, density i log note count. Ovo nije finalni X10 timing Calibration Engine i ne proizvodi timing target.

| Corpus | `NORMAL` | `RARE` | `OUTLIER` | `INVALID` |
|---|---:|---:|---:|---:|
| Factory | 25.230 | 4.364 | 130 | 0 |
| Balkan reference | 1.230 | 562 | 91 | 0 |

- Robustnih konteksta: 207.
- Dovoljno uzoraka: 136 konteksta.
- Nedovoljno uzoraka: 71 kontekst.
- Trackova trenutno podobnih za sljedeći validated-DNA review: 26.403.
- Trackova koji traže pregled zbog source warninga, rarity ili outliera: 9.158.
- Trackova iz `WARNING_NOTE_PAIR` izvora: 5.017.

`RARE` nije greška. `OUTLIER` nije automatski greška. Oba statusa služe da rijedak Factory događaj ne postane tiho opšte pravilo.

## Nova baza

`data/rhythm_validation.sqlite3` sadrži:

- `corpus_members` — archive lineage i MIDI validation;
- `calibration_contexts` — robustne distribucije i sample sufficiency;
- `track_quality` — source status, metrics, robust scores, klasifikacija i review gate;
- `quality_summary` — reproducibilni sažetak.

Baza eksplicitno čuva:

```text
repair_capability = NONE_ANALYZE_ONLY
```

Nijedan MIDI događaj nije promijenjen.

## Verifikacija

- 18 prisutnih SQLite baza: `integrity=ok`.
- Foreign-key greške: 0.
- RAW semantic hash parity: prolazi.
- Python compile: prolazi.
- Unit testovi: 87/87 prolazi.

## Sljedeći gate

Phase C ne smije odmah popravljati timing. Sljedeće se implementiraju stable event/note ID, section-boundary note-pair objašnjenje, detaljne role, multi-scale pattern representation i pravi Calibration Engine. Tek Analyze-only anomaly engine smije koristiti te podatke.