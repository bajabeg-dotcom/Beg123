# X10 Rhythm Calibration — phrase, multi-bar i repeated-pattern audit

Datum: 11. august 2026.

## Status

Implementirana je prva grid-free Calibration faza. Ona ne popravlja MIDI i ne proizvodi automatski timing target.

```text
mode = ANALYZE_ONLY
repair_capability = false
```

## Izvor

- aktivni RAW snapshot: `335ad9cb42bd41768993`;
- Factory trackovi prihvaćeni iz data-quality gatea: 24.705;
- Gold/reference trackovi prihvaćeni iz data-quality gatea: 1.698;
- šest Delay/Terca pjesama nije korišteno;
- warning, outlier i neodobreni source trackovi nisu tiho uključeni.

## Phrase kandidati

Kreirano je 77.315 heuristic phrase kandidata:

- `REST_AT_LEAST_ONE_BEAT`: 36.424;
- `EMPTY_BAR`: 14.488;
- `END_OF_TRACK_CHANNEL`: 26.403.

Phrase granice su eksplicitno `HEURISTIC_CANDIDATE`, ne potvrđena muzička činjenica.

## Multi-bar obrasci

- ukupno 460.263 multi-bar instance;
- 255.786 prozora od dva takta;
- 204.477 prozora od četiri takta;
- 124.488 instanci pripada sekvenci koja se ponavlja više puta.

Fingerprint koristi stvarne tick odnose. Ne koristi nearest-grid, quantize ili random jitter.

## Repeated-pattern Calibration

Pronađena su 8.174 lokalna ponovljena topology profila:

- Factory: 2.417 profila iz 9.923 ponovljena takta;
- Gold/reference: 5.757 profila iz 77.819 ponovljenih taktova;
- najmanje ponavljanja po profilu: 3;
- najviše ponavljanja: Factory 9, Gold/reference 205.

Ključna podjela:

- `EXACT_REPEAT_REFERENCE`: 7.954;
- `ROBUST_VARIATION_PROFILE`: 220.

Exact repeat dokazuje strukturu, ali ne dokazuje toleranciju. Samo 220 profila ima opaženu nenultu MAD/IQR timing varijaciju. Čak ni oni još nemaju repair dozvolu; prvo moraju proći cross-file/context consensus i negative corpus validaciju.

## Instrument/role pokrivenost profila

Factory:

- percussion 653;
- drums 565;
- bass 429;
- guitar 406;
- accompaniment 364.

Gold/reference:

- melodic 2.011;
- guitar 1.858;
- bass 1.056;
- drums 832.

## Nova baza

`data/rhythm_calibration.sqlite3` sadrži:

- `phrase_candidates`;
- `multi_bar_patterns`;
- `repeated_pattern_calibration`;
- `build_info` i `build_summary` sa source hashovima i `ANALYZE_ONLY` lockom.

## Sigurnosni zaključak

Ova faza može odgovoriti:

> Koji pattern se ponavlja, koliko puta, gdje su njegove stvarne faze i kolika je opažena robusna varijacija?

Još ne smije odgovoriti:

> Pomjeri ovu notu na novi tick.

Sljedeći gate je cross-file Factory consensus po role/section/meter/tempo/pattern kontekstu, uz negative-rule zaštitu syncopationa, pickup-a, fill-a, Guitar Modea, ornamenata i RX/DNC događaja.
