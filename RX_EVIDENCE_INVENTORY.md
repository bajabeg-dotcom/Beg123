# RX/DNC Evidence Inventory

Datum inventara: 11. august 2026.

## Zaključak

Projekt sada ima mašinski provjerljiv inventar u `analysis/evidence_inventory.json`. Factory i referentni korpus su odvojeni, svaki MIDI član ima SHA-256, a izvorni fajlovi su označeni kao read-only dokaz.

| Izvor | Klasifikacija | MIDI članovi | Jedinstveni SHA-256 | Status |
|---|---|---:|---:|---|
| Split Factory Styles.zip | `factory_raw` | 3.211 | 3.187 | direktni sirovi dokaz |
| Gold DNA.zip | `balkan_reference_raw` | 182 | 181 | direktni referentni dokaz |
| Šest odobrenih song MIDI-ja | `song_layer_reference` | 6 | 6 | samo Delay/postojeća terca |
| `Oscilatori.txt` | `user_observation` | — | — | `UNVERIFIED` |
| `reference/pa800/README.md` | `manual_link_index` | — | — | nije primarni dokument |

## Kritična praznina

U workspaceu nema lokalnih službenih Korg PDF-ova, Sound List, PCG, SET ili STY fajlova. Postoje samo URL-ovi i raniji sažeci. Zato nijedna tvrdnja ne smije dobiti `CONFIRMED` samo zato što dokumentacija navodi naziv priručnika; potreban je lokalni dokument sa SHA-256 i preciznim page/section locatorom ili fizički Pa800 test.

## Stroga klasifikacija

- `FACTORY_RAW`: ne mijenja se i ne uči iz optimizer izlaza.
- `BALKAN_REFERENCE_RAW`: postojeći Gold MIDI primjeri; nisu Korg Factory autoritet.
- `GOLD_RULESET`: izvedena pravila, statistika, granice i negativna pravila; nije folder popravljenih MIDI-ja.
- `SONG_LAYER_REFERENCE`: šest korisničkih fajlova služe samo za Delay i detekciju/optimizaciju postojeće terce.
- `USER_OBSERVATION`: korisnička opažanja iz Sound Edita; ostaju `UNVERIFIED` dok ih ne potvrdi drugi izvor.
- `OPTIMIZER_OUTPUT`: nikada nije trening dokaz.

## Trenutni evidence status

Relativno dobro dokumentovano, ali traži lokalni PDF snapshot:

- format `CC00.CC32.PC`;
- 21 Pa800 katalog adresa;
- Guitar Mode command/chord tabele;
- postojanje RX Noise, Humanize GTR i Capo funkcija.

Još uvijek `OBSERVED`, `INFERRED` ili `UNVERIFIED`:

- bass/guitar oscillator i velocity zone iz `Oscilatori.txt`;
- Slap switch 87;
- Clean Guitar C7–C9 noise podrasponi;
- Pop Std. Kit RX layer switch vrijednosti;
- pojedinačni triggeri, key-switch, overlap, pitch curve, release behavior i CC/aftertouch pravila po Soundu.

## Implementirana Evidence Registry schema

1. `evidence_sources`: izvor, vrsta, verzija, OS raspon, SHA-256 i autoritet.
2. `evidence_locators`: PDF stranica/sekcija ili MIDI član, track, kanal i tick raspon.
3. `subjects`: RX Sound, artikulacija, trigger, event sequence ili pravilo.
4. `claims`: field-level tvrdnja, vrijednost, status i confidence.
5. `claim_evidence`: `SUPPORTS`, `CONTRADICTS` ili `DERIVES_FROM` veza.
6. `observations`: reproducibilna MIDI/statistička mjerenja i verzija extractora.
7. `conflicts`: suprotne tvrdnje i status rješenja.
8. `verification_tasks`: konkretan manual, PCG ili hardware test potreban za potvrdu.

Registry je materijalizovan u `data/evidence_registry.sqlite3`. Postojeće RX zone nisu promovirane: Slap 87/94 konflikt je otvoren, a kataloški Sound triggeri ostaju `UNKNOWN` sa obaveznim verification taskom.

## Runtime primjena

- strict Evidence Gate propušta samo `CONFIRMED` primarni dokaz za generaciju i Sound zamjenu;
- transformacija postojećeg događaja zahtijeva najmanje `HIGH_CONFIDENCE`/`CONFIRMED` primarni dokaz bez otvorenog konflikta;
- trenutni rezultat je 0/49 prihvaćenih RX zona i 0/21 prihvaćenih RX Sound ciljeva;
- zato default optimizer čuva originalni Sound i originalni RX velocity kada bi odluka zavisila od nepotvrđenog pravila;
- `catalog_review` dopušta identity-safe mapiranje isključivo za označen A/B test i takav run nije release-eligible.
