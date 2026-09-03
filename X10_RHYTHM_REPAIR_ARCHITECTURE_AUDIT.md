# X10 Rhythm Repair — Architecture Audit

Datum audita: 11. august 2026.

## Izvršni zaključak

Repository sadrži dobru osnovu za čitanje/pisanje MIDI-ja, Factory/Gold feature extraction, section/CV profile, determinističke transformacije i evidence/audit zaštitu. Međutim, **X10 Rhythm Repair engine još ne postoji kao zaseban dokazni sistem**.

Postojeći `optimizer.py` je transformacijski optimizer. Ne smije se preimenovati ili tretirati kao X10 repair zato što trenutno:

- računa timing cilj preko najbliže 1/16 mreže;
- koristi fiksni maksimalni pomak od ±0,08 četvrtinke;
- primjenjuje promjene po širokoj ulozi bez event-level anomaly proofa;
- nema simulaciju više kandidata, repair budget, explicit rollback ni before/after groove gate.

Prema apsolutnom X10 pravilu, početni runtime režim budućeg sistema mora biti `ANALYZE_ONLY`. `SAFE_AUTO_REPAIR` se može uključiti tek nakon kalibracije, negativnih testova i certification gatea.

## Status fizičkih podataka

- Autoritativni corpus izvor je `prism-uploads/DNA.zip`.
- Evidencijski inventar navodi 3.211 Factory članova / 3.187 jedinstvenih SHA-256 i 182 balkanska referentna člana / 181 jedinstveni SHA-256.
- Nakon početnog audita corpus je obnovljen i aktivni snapshot je `335ad9cb42bd41768993`.
- `factory_raw.sqlite3` i `gold_raw.sqlite3` su read-only (`0444`) i prolaze semantic hash parity.
- Šest korisničkih song MIDI fajlova ostaje strogo ograničeno na identifikaciju postojećih Delay/Terca odnosa i nije Rhythm Repair evidence.

Trenutni workspace je ponovo reproducibilan iz `DNA.zip`; novi data-quality rezultat je u `X10_RHYTHM_DATA_QUALITY_REPORT.md`.

## Architecture audit matrica

| Područje | Status | Dokaz | X10 procjena |
|---|---|---|---|
| Standard MIDI parser/writer | `IMPLEMENTED` | `rxoptimizer/midi.py` | Dobra osnova; podržava event order i EOT normalizaciju. |
| Osnovna MIDI semantička validacija | `PARTIAL` | `validate_midi()` | Provjerava vrijednosti i note-on/off balans, ali ne puni X10 non-target/event-identity ugovor. |
| RAW source hash inventar | `IMPLEMENTED` | `analysis/evidence_inventory.json` | Dobar lineage temelj. |
| Read-only generacijski RAW layout | `PARTIAL` | `rxoptimizer/database_layout.py` | Dizajn i test postoje; aktivni veliki snapshot trenutno nije prisutan. |
| Program/Bank vremenski segmenti | `IMPLEMENTED` | `instrument_segments`, test istog tick ordera | Važno za pravilnu instrument/role analizu. |
| Factory rhythm feature extraction | `PARTIAL` | `features.py`, `rhythm_dna.sqlite3` builder | Ima velocity/timing/gate/density/swing, ali je 16-step/4-4 centričan. |
| Gold performance model | `PARTIAL` | `GoldDNAModel` | Determinističan, ali postojeći Gold corpus je `balkan_reference_raw`, ne validirani Gold ruleset. |
| Section/CV/meter modeli | `PARTIAL` | `dna_databases.py` | Postoje section/role/CV grupe; nema pune pattern/bar/multi-bar hijerarhije. |
| Role classification | `PARTIAL` | `infer_role()`, sound intelligence | Uloge su preširoke; nema KICK/SNARE/HIHAT/PAD/FILL/FX event-level klasifikacije i potpunog `UNKNOWN` gatea. |
| Pattern fingerprint | `PARTIAL` | track feature/signature hash | Potpisuje agregat trake; nema stabilan pattern instance model sa ponavljanjem i cross-bar kontekstom. |
| Groove signature | `MISSING` | — | Nema zaseban timing/velocity/density/accent/syncopation before/after ugovor. |
| Robust calibration | `MISSING` | — | Nema median/MAD/IQR/percentile tolerance modela po kontekstu. |
| Outlier governance | `MISSING` | — | Nema `NORMAL/RARE/OUTLIER/INVALID` klasifikaciju prije DNA promocije. |
| Event-level anomaly proof | `MISSING` | — | Postojeći optimizer transformiše; ne dokazuje da je događaj greška. |
| Musical-intent protection | `PARTIAL` | RX, Guitar Mode i ornament zaštite | Nema jedinstven gate za syncopation, pickup, anticipation, fill i cross-bar frazu. |
| Candidate generation/ranking | `MISSING` | — | Nema Factory/Gold/local/neighbour kandidata i determinističkog scorea. |
| Before/after simulation | `MISSING` | — | Nema shadow MIDI evaluacije prije commit-a. |
| Repair transaction i rollback | `PARTIAL` | `deepcopy` i atomski DB builderi | Original se često kopira, ali nema eksplicitni session snapshot/proposal/commit/rollback protokol. |
| Repair budget | `MISSING` | — | Nema max events/percent/delta/pattern/section budžeta. |
| Per-note repair provenance | `MISSING` | — | Run report postoji, ali ne stabilni event ID + original/target/rule/evidence zapis za svaku notu. |
| Rule registry/version conflict | `MISSING` | — | Pravila su raspoređena kroz module i hardkodirane pragove. |
| Evidence Registry | `IMPLEMENTED` | `evidence_registry.py` | Dobar fail-closed RX temelj; mora se proširiti na rhythm claims/calibration. |
| Dry run/preview UI | `MISSING` | — | GUI nema event proposal listu sa accept/reject/rollback. |
| Determinism | `PARTIAL` | deterministični modeli i testovi | Nema corpus-level X10 identical-output certification testa. |
| Negative/adversarial corpus | `MISSING` | — | Nema dokaz da validni groove, pickup, fill i syncopation ostaju netaknuti. |
| False/missed repair KPI | `MISSING` | — | Najvažniji sigurnosni KPI-jevi nisu izračunati. |
| Blind human A/B | `MISSING` | hardware gate postoji | Nema Rhythm Repair A/B protokola i rezultata. |
| Certification | `MISSING` | — | Release gate nije X10 Rhythm certification gate. |

## Database audit

### Postojeća vrijednost

- RAW tabele čuvaju `midi_files`, `instrument_profiles`, `track_stats`, `performance_features` i `instrument_segments`.
- Derived builderi su atomski i čuvaju source database SHA-256.
- Evidence Registry ima field-level claims, locatore, observations, konflikte i verification taskove.
- Optimizer run audit čuva source/output SHA-256, konfiguraciju i izvještaj.

### Nedostaci za X10

Potrebne su nove versioned tabele ili zasebna baza za:

- corpus validation i outlier status;
- stabilne event identitete;
- bar/beat/subbeat/multi-bar/pattern instance;
- calibration distributions i sufficiency;
- rhythm rules i konflikte;
- anomaly observations;
- repair sessions, proposals, simulations, decisions i rollback;
- groove/pattern before-after metrike;
- per-event provenance;
- certification corpus i release rezultate.

Corpus/database audit više nije blokiran: aktivni RAW snapshot, derived baze i `rhythm_validation.sqlite3` prolaze integrity provjeru. Runtime tranzicija svih legacy read upita na pointer i dalje nije završena.

## Rhythm engine audit

### Dobro i ponovno upotrebljivo

- Timing se normalizuje u četvrtinkama i nezavisan je od PPQ-a u feature modelu.
- Model je role-aware i position-aware.
- Transformacije su determinističke.
- Postoje zaštite za RX velocity zone, Guitar Mode chord kodove, SysEx i ponovljene note.
- Program Change se prati po vremenskim segmentima.

### `INCORRECT/UNSAFE` ako bi se koristilo kao X10 repair

1. `features.extract_features()` mjeri odstupanje prema najbližoj 1/16 mreži i uvijek koristi 16 pozicija jednog 4/4 takta.
2. `optimizer.optimize()` ponovo konstruiše `grid_tick` i pomjera notu prema grid + mean offset cilju.
3. Timing limit ±0,08, gate clamp 0,67–1,50 i drugi pragovi nisu rezultat Calibration Enginea.
4. Deterministički pseudo-jitter u Strumming sloju je humanization transformacija; ne smije biti dio Rhythm Repair dokazivanja.
5. Regular rhythm-guitar repair koristi “robotski simultani akord” heuristiku i direktno mijenja onset/gate bez pune X10 simulacije i Factory/Gold consensus gatea.
6. Globalna obrada po ulozi može promijeniti validan event i nema minimal-scope anomaly contract.

Ovi moduli se ne brišu. Moraju dobiti jasnu oznaku `PERFORMANCE_TRANSFORM`, dok novi X10 engine radi odvojeno i defaultno samo analizira.

## Test audit

`python3 -m unittest discover -s tests -v` je 11. augusta 2026. završio sa **79/79 prolaznih testova**.

Pokriveno je:

- MIDI parse/encode i osnovna semantika;
- Bank/Program segmenti i mapping zaštite;
- Factory/Gold feature extraction;
- RX evidence fail-closed ponašanje;
- Guitar Mode, solo, Delay/Terca granice i trill false positives;
- DB layout i atomski builderi;
- hardware test gateovi.

Nije pokriveno:

- X10 anomaly proof;
- robust calibration i sample sufficiency;
- repair candidate simulation/ranking;
- validni syncopation/pickup/fill/cross-bar negative corpus;
- intentional microtiming preservation na corpus nivou;
- repair budget i cascade protection;
- rollback nakon djelimičnog failurea;
- per-event provenance;
- false-repair i missed-repair KPI;
- certification determinism/performance corpus;
- blind human A/B.

## Sigurnosna odluka

Dok nedostaju calibration, negative corpus i simulation gate:

```text
X10_RUNTIME_MODE = ANALYZE_ONLY
AUTO_REPAIR = DISABLED
CERTIFICATION_STATUS = NOT_READY
```

Postojeći optimizer može ostati dostupan kao eksplicitni performance transform, ali njegovi rezultati nisu X10 repair evidence niti Gold training data.
