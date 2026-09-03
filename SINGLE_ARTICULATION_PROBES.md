# Factory/Gold Single-Articulation Pa800 probe

## Princip

Jedan probe fajl aktivira jednu posebnu artikulaciju tačno jednom. Trigger nije izmišljen: uzima se iz stvarnog Factory MIDI događaja ili, ako Factory nema primjer, iz Gold MIDI događaja iste Bank/Program adrese.

Normalna prethodna i sljedeća nota dodaju se samo kada su u radnoj zoni istog Sounda. Tako test ne aktivira više posebnih artikulacija.

Šest Delay/Terca referentnih pjesama nije dio ovog procesa.

## Rezultat analize

- posebni kandidati: 39;
- kandidati sa stvarnim Factory/Gold događajem: 30;
- generisani probe MIDI fajlovi: 30;
- specijalni triggeri po fajlu: 1;
- najbolji izvor za svih 30: `factory_raw`;
- kandidati bez dokaza: 9, zato nisu generisani.

## Pokrivene grupe

- Clean Guitar RX1–RX4: Slap/Slide, Dead/Mute, Harm/Ghost i Noise gdje postoji dokaz;
- Finger Bass RX: Harm, Stop, Gliss i Noise;
- Picked Bass RX: Harm, Stop, Gliss i Noise;
- SlapFing/SlapPick Bass RX: Slap/Harmonic;
- Pop Std. Kit RX: pet note/layer grupa.

Clean Guitar RX5/RX6 i Clean Guitar RX2 Harm/Ghost nemaju dovoljan Factory/Gold MIDI događaj za odgovarajuće zone i nisu izmišljeni.

## Evidence

Za svaki probe manifest čuva:

- izvorni Factory/Gold član;
- SHA-256 izvora;
- track, kanal i tick;
- Bank MSB, LSB i Program;
- tačnu trigger notu, velocity i trajanje;
- normalni prethodni/sljedeći kontekst;
- occurrence i file count.

Status ostaje `OBSERVED_UNVERIFIED_TRIGGER` dok korisnik ne potvrdi zvuk na fizičkom Pa800.

## Fajlovi

- MIDI probe: `hardware-tests/single-articulation-probes/`;
- manifest: `hardware-tests/single-articulation-probes/single-articulation-manifest.json`;
- vodič: `hardware-tests/single-articulation-probes/SINGLE_ARTICULATION_TEST_GUIDE.md`;
- baza rezultata: `data/articulation_probe.sqlite3`.
- kompletan paket: `hardware-tests/SINGLE_ARTICULATION_PROBES_PA800.zip`.
- trajni rezultati: `hardware-tests/single-articulation-probes/articulation-results.json`;
- ručni worksheet: `hardware-tests/single-articulation-probes/SINGLE_ARTICULATION_CONFIRMATION.csv`.

ZIP SHA-256: `761ad97bba82c96e6d56cdbd33e43808905a45ebc534b0dad520a4b7074f2cbd`.

Za `confirmed`/`partial` rezultat obavezni su Pa800 OS, Musical Resources verzija i opis stvarno čute artikulacije. Potvrda se sprema atomski u JSON i dobija status `pending_evidence_review`; ne ulazi automatski u produkcijski engine.

`evidence-promotion-queue.json` se gradi samo iz posljednjeg rezultata svakog Probe ID-a. `confirmed` ide u `READY_FOR_EVIDENCE_REVIEW`, `rejected` u `CONTRADICTION_REVIEW`, a automatska runtime promocija je uvijek isključena.

## Ponovna gradnja

```bash
python3 app.py build-articulation-probes
```