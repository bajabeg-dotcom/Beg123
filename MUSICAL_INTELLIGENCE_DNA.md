# Korg Pa800 Musical Intelligence — Trill i Layer DNA

Datum izgradnje: 11. august 2026.

## Sigurnosna odluka

Solo→Terca odnosi se analiziraju i uče, ali automatsko generisanje terce ostaje isključeno. Postojeća terca može dobiti samo velocity i već postojeće CC7/CC11 korekcije kada pair prođe strogi recall/precision prag. Delay generation ostaje zasebna mogućnost, ali novi relationship podaci služe za budući phrase/ornament gate.

## Nova baza

`data/musical_intelligence_dna.sqlite3` sadrži:

- `trill_patterns`;
- `trill_occurrences`;
- `trill_features`;
- `trill_context`;
- `trill_harmony`;
- `trill_timing`;
- `trill_velocity`;
- `trill_articulation`;
- `trill_evidence`;
- `trill_confidence`;
- `trill_negative_rules`;
- `layer_relationships`;
- `layer_trill_behavior`;
- `layer_rules`.

Svaka pojava ima source class, SHA-256, fajl, style/section, track, kanal, Bank/Program, tick/order granice i originalni note niz.

## Strogi Trill detector

Detector traži maksimalnu `A-B-A-B...` sekvencu i:

- dvije ili tri note nikada ne proglašava trillerom;
- četiri note čuva samo kao low-confidence kandidat;
- za automatski prihvaćen kandidat zahtijeva najmanje pet nota;
- odvaja exit notu od trill corea;
- blokira simultane chord onsete;
- ne miješa Program Change segmente;
- razlikuje same-note tremolo, scale run, arpeggio i drum roll;
- računa timing, subdivision, acceleration, velocity pattern, phrase position i previous/next context;
- harmoniju označava `UNKNOWN` kada tonalni dokaz nije dovoljan;
- pitch bend, pressure, CC1 i noise note vodi samo kao vremensku korelaciju;
- RX status ostavlja `UNKNOWN` dok Evidence Registry nema potvrđen trigger.

`CONFIRMED` se ne dodjeljuje algoritamski. Detector daje `HIGH_CONFIDENCE`, `MEDIUM_CONFIDENCE`, `LOW_CONFIDENCE` ili `REJECTED`.

## Rezultati punog korpusa

| Izvor | Kandidati | HIGH | MEDIUM | Prihvaćeni HIGH+MEDIUM |
|---|---:|---:|---:|---:|
| Factory RAW | 1.557 | 43 | 279 | 322 |
| Balkan reference RAW | 24.991 | 1.042 | 6.552 | 7.594 |

Low-confidence i rejected kandidati ostaju u bazi radi audita i kasnijeg threshold reviewa. Prihvaćeni događaji daju 271 odvojen pattern profil. Evidence Registry sadrži 7.838 jedinstvenih `TRILL_OCCURRENCE` observations; razlika prema 7.916 prihvaćenih pojava dolazi od SHA-identičnih duplikata u korpusu.

Factory prihvaćeni kandidati:

- 251 diatonskih;
- 33 hromatska;
- 38 sa nedovoljno sigurnim tonalnim kontekstom;
- dominantne podjele: 1/16, 1/16 triplet i 1/32;
- 48 Factory kandidata ima irregular timing i ne dobija izmišljenu subdivision oznaku.

## Solo→Terca/Delay relationship evidence

Šest korisničkih pjesama daju 13 pouzdanih pair zapisa: 11 Delay i dvije postojeće Terca veze. Raniji kandidat u `Devet hiljada metara` je odbačen jer je imao samo 7,6% target precision i predstavljao slučajne terce unutar velikog nepovezanog tracka.

Pouzdane postojeće terce:

- `Danima te cekam`: recall 83,7%, target precision 95,6%, velocity ratio oko 0,824;
- `Dao sam ti dusu`: recall 60,9%, target precision 100%, velocity ratio oko 0,738.

Musical Intelligence baza čuva 0 song-derived source-trill/layer behavior zapisa. Šest pjesama daje samo 13 Delay/Terca track relationship zapisa; iz njih se ne izvlači trill, ornament niti druga izvedbena tehnika.

## Negativna pravila

- bez random trilla;
- bez drum-roll→trill klasifikacije;
- bez same-note tremolo→trill klasifikacije;
- bez scale/arpeggio false positivea;
- bez kopiranja Solo trilla u Tercu ili Delay bez relationship/context dokaza;
- bez generisanja terce;
- bez proglašavanja RX/DNC triggera iz običnog vremenskog preklapanja.

GUI i API izlažu sažetak preko `/api/musical-intelligence`.
