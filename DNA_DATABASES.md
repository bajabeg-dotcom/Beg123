# DNA baze podataka

Projekt koristi dvije corpus radne baze, četrnaest izvedenih/evidence baza i tri trajne hardversko-testne SQLite baze: ukupno 19 SQLite baza. Izvorni `DNA.zip` ostaje nepromijenjen i SHA-256 evidentiran. Phase 3 dodatno može napraviti atomske generacijske snapshotove sa read-only RAW bazama i odvojenim application stateom.

## Sirovi korpusi

### `data/factory.sqlite3`

Radni inventar Factory Styles materijala: MIDI fajlovi, instrument profili, section/CV podaci, track statistike, segmentni feature zapisi, Pa800 katalog i aktivna mapiranja. Autoritativni RAW dokaz je originalni ZIP/member SHA-256 inventar.

### `data/gold_dna.sqlite3`

Autoritativni inventar Gold DNA pjesama: MIDI fajlovi, role profili, tempo/metar i sirovi performance feature zapisi.

### `data/generations/<generation-id>/`

- `factory_raw.sqlite3` i `gold_raw.sqlite3` sadrže samo RAW corpus tabele i otvaraju se read-only;
- `application_state.sqlite3` sadrži katalog, RX zone, mappings, planove, run audit i import greške;
- `data/database-layout.json` je atomski pointer na aktivnu generaciju;
- semantic SHA-256 potvrđuje da snapshot nije izgubio nijedan RAW red;
- builder odbija napraviti snapshot ako je Factory ili Gold corpus prazan.

## Izvedene DNA baze

### `data/rhythm_dna.sqlite3`

- 29.724 Factory rhythm track potpisa;
- style, Intro/Variation/Fill/Break/Ending i section broj;
- CV, role, tempo i metar;
- density i puni 16-step signature JSON;
- 356 agregiranih section/role/CV profila.

### `data/performance_dna.sqlite3`

- 1.883 Gold performance trake;
- tempo bucket i metar;
- velocity/timing po 16-step poziciji;
- swing, gate, density, CC1 i CC11;
- 85 modela: globalni i role/tempo/meter kohorte.

Optimizer ovu bazu koristi direktno za izbor najbližeg Gold modela.

### `data/voice_dna.sqlite3`

- 21 potvrđena Pa800 adresa;
- 87 aktivnih Factory/GM→RX mapa;
- confidence i provenance;
- 49 RX artikulacijskih zona;
- 9 drum profila;
- snapshot pokrivenosti profila, traka i nota.

### `data/rx_dna.sqlite3`

- 20 kataloških RX zvukova;
- 49 radnih oscillator/switch pravila koja se dodatno klasifikuju u Evidence Registryju;
- 79 Factory→RX mapping/evidence zapisa;
- 23 Factory RX behavior profila;
- 262 section/CV usage profila;
- 5 drum layer pravila.

Optimizer ovu bazu učitava kroz Evidence Registry gate. `UNKNOWN`, `UNVERIFIED`, `INFERRED` i `CONFLICTED` pravila ne mogu automatski aktivirati artikulaciju ili mijenjati RX velocity sloj. Trenutni strict status je 0/49 prihvaćenih zone pravila.

### `data/solo_dna.sqlite3`

- 1.883 Gold trake sa detaljnim solo feature zapisima;
- 30 automatski potvrđenih solo kandidata;
- 22 modela po instrument family, tempu i metru;
- monofonija, registar, intervali, fraze, odmor, legato i overlap;
- pitch bend, CC1, CC11 i pressure statistike;
- 8 pravila za očuvanje melodije, RX zona, bend namjere i sigurnog gate-a.

### `data/strumming_dna.sqlite3`

- 1.196 dokazano Guitar Mode/strumming trackova;
- 19.052 C1–B2 command događaja;
- 73 section/tempo/meter modela;
- 65 profila konkretnih guitar Soundova;
- 24 službene strum/string/arpeggio komande;
- 24 Intro1/Ending1 chord velocity tipa;
- down/up, mute, slow, four-string, RX Noise i transition statistike;
- 12 pravila iz službenog Pa800 Guitar Mode priručnika.

### `data/delay_dna.sqlite3`

- 11 potvrđenih echo parova iz šest song MIDI fajlova;
- 10 globalnih/programskih modela;
- stabilni offset, velocity attenuation, gate i coverage;
- dominantni offset 0,75 četvrtinke;
- 220 phrase occurrence zapisa: 218 `FULL` i dvije `SKIP` fraze;
- 10 phrase modela sa source-file/sample pragovima i generation odlukom;
- `PARTIAL` generacija je isključena dok nema dovoljno čistog dokaza;
- Delay uvijek ostaje zaseban track i zaseban, slobodan MIDI kanal.

### `data/harmony_dna.sqlite3`

- dvije pouzdane terca/harmony veze;
- tri globalna/programska modela;
- smjer gore/dolje, odnos male i velike terce, velocity, gate i coverage;
- terca se nikada ne kreira;
- postojeći harmony pitch, onset i trajanje se ne prepisuju;
- optimizuju se samo velocity i već postojeći CC7/CC11 događaji.

### `data/ornament_dna.sqlite3`

- 939 Gold melodic/guitar traka;
- 46 family/tempo modela;
- 19.675 trill kandidata i 526.962 grace kandidata;
- grace, trill, neighbor/mordent, tremolo i pitch-bend učestalost;
- strogi `Gold DNA only` provenance, bez Factory i song training izvora;
- default režim procjenjuje postojeće ukrase i ne dodaje nove note.

### `data/sound_intelligence_dna.sqlite3`

- 603 Factory Sound profila sa stvarnim bank/program adresama;
- pet Factory role modela;
- 16 Factory, Gold i kombinovanih mix/headroom profila;
- prepoznavanje nepoznatog User Sounda iz registra, monofonije, chord/density i izvedbenog paterna;
- confidence-gated izbor najboljeg Factory Sounda;
- Factory CC7/CC11 headroom i Gold velocity/performance politika;
- sigurnosna pravila za regularni Song rhythm-guitar repair.

### `data/instrument_structure_dna.sqlite3`

- svih 128 GM instrument identiteta;
- 6.301 Factory section/CV struktura;
- 194 Factory runtime modela po instrument identitetu i metru;
- 376 Gold/Balkan korekcija istog identiteta;
- 142 preserve/RX conversion pravila;
- Program Change vremenska identity linija;
- stroga zabrana cross-instrument Sound zamjene.

Korpus radne baze dodatno sadrže kanonsku tabelu `instrument_segments`: 29.936 Factory i 2.602 Gold segmenta. Time se 142 Factory i 102 Gold track/channel para sa više Program Change stanja više ne pripisuju posljednjem Soundu.

### `data/evidence_registry.sqlite3`

- 3.405 evidence izvora, uključujući svaki MIDI član i njegov SHA-256;
- 70 RX Sound/articulation subjekata;
- 488 field-level claimova i 467 preciznih evidence veza;
- 70 otvorenih verification zadataka;
- dva otvorena konflikta za Slap oscillator-2 switch 87 naspram ranijeg zapisa 94;
- `UNKNOWN`, `UNVERIFIED`, `INFERRED` i `CONFLICTED` se ne predstavljaju kao potvrđene činjenice;
- integrity `ok` i nula foreign-key grešaka.

### `data/musical_intelligence_dna.sqlite3`

- 1.557 Factory i 24.991 Balkan-reference trill kandidata;
- 322 Factory i 7.594 reference HIGH/MEDIUM kandidata;
- 271 evidence-traceable pattern profil;
- kompletan timing, velocity, harmony, phrase, articulation-cooccurrence i confidence zapis;
- 13 Solo→layer odnosa: 11 Delay i dvije postojeće Terca veze;
- 0 song-derived source-trill/layer behavior zapisa; šest pjesama daje samo Delay/Terca track veze;
- stroga false-positive i negative-rule tabela;
- Terca generation je eksplicitno `disabled`.

### `data/optimizer_dna.sqlite3`

- verzije Factory i Gold korpusa;
- SHA-256 sirovih baza;
- hash i metapodaci svih Performance DNA modela;
- optimizer run konfiguracije, izvještaji i source/output SHA-256.

### `data/hardware_test_dna.sqlite3`

- pet test-agenta i njihove izvršne mogućnosti;
- Pa800 test suiteovi i kritični MIDI caseovi;
- Hardware Playback i Listening Review rezultati;
- ocjene timinga, RX artikulacije i bubnjeva od 1 do 5;
- release gate koji ostaje `pending_hardware` bez fizičkog testa.

Ova baza se namjerno ne briše pri `build-dna`, kako ručno prikupljeni dokazi ne bi bili izgubljeni.

### `data/rx_noise_probe.sqlite3`

- probe engine za zasebno uploadovane MIDI fajlove i osam RX Noise Sound profila;
- šest Delay/Terca pjesama je blokirano SHA-256 pravilom i ne može postati probe izvor;
- note 96–127 kroz velocity 1/42/84/127;
- trenutno 0 probe fajlova; budući fajlovi imaju `pending_hardware`, `confirmed`, `partial` ili `rejected` rezultat;
- potvrđene i odbačene note, komentar i Pa800 konfiguracija;
- probe podaci ne ulaze u produkcijski RX engine prije fizičke potvrde.

### `data/articulation_probe.sqlite3`

- 39 posebnih RX/artikulacijskih kandidata bez radnih/normalnih zona;
- 30 kandidata sa stvarno opaženim Factory/Gold MIDI događajem;
- 30 single-shot MIDI proba, svaka sa tačno jednim posebnim triggerom;
- source member, SHA-256, track, kanal, tick, Bank/Program, nota, velocity i trajanje;
- prethodni/sljedeći kontekst samo iz radne zone istog Sounda;
- devet kandidata bez evidencea nije generisano;
- šest Delay/Terca pjesama je potpuno isključeno.

## Ponovna izgradnja

Puni import i gradnja svih baza:

```bash
python3 app.py import-archive prism-uploads/DNA.zip
```

Samo ponovna izgradnja svih izvedenih DNA baza:

```bash
python3 app.py build-dna
```

Builder koristi privremeni SQLite fajl i atomski ga zamjenjuje tek nakon uspješne gradnje. Ponovljeno pokretanje daje potpuno obnovljene, nekumulirane izvedene baze.