# Factory Sound Intelligence, Headroom i Guitar Repair DNA

## Autoritet podataka

- šest korisničkih Song MIDI fajlova koristi se samo za Delay i Terca DNA;
- Factory Styles određuju instrument ulogu, izbor Factory Sounda, chord/strum strukturu i MIDI mix prostor;
- Gold DNA određuje samo relativne akcente, micro-timing, gate i fraziranje unutar Factory kalibracije;
- nijedan Song fajl nije training izvor za Sound Intelligence, headroom ili guitar repair.

## Šta je ustanovljeno

| Uloga | Factory velocity mean / P95 | Gold velocity mean / P95 | Factory CC7 medijan | Gold CC7 medijan | Factory / Gold CC11 medijan |
|---|---:|---:|---:|---:|---:|
| Bass | 100,66 / 126 | 117,38 / 127 | 110 | 115 | 106 / 95 |
| Guitar | 80,45 / 120 | 96,43 / 127 | 110 | 100 | 100 / 95 |
| Drums | 88,73 / 127 | 97,11 / 127 | 110 | 127 | 115 / 118 |
| Accompaniment | 88,66 / 121 | premalo direktnih Gold uzoraka; koristi se Gold melodic fallback | 110 | — | 100 / melodic 102 |
| Gold melodic | — | 101,77 / 127 | Factory accompaniment fallback 110 | 100 | Factory 100 / Gold 102 |

Gold je osjetno jači u velocityju i često ide do 127. Factory ne pravi audio mastering headroom u MIDI fajlu, ali dosljedno ostavlja kontrolni prostor: CC7 je uglavnom oko 110, a CC11 je raspoređen po ulozi. Zato optimizer ne kopira Gold Volume niti njegov apsolutni velocity centar. Factory drži velocity mean/P95, balans i plafon; Gold daje samo relativni akcent, timing, gate i frazni oblik unutar tog prostora.

## Nepoznati User Sounds

`sound_intelligence_dna.sqlite3` sadrži 603 Factory Sound profila i pet Factory role modela. Za nepoznatu bank/program adresu optimizer analizira:

- registar i pitch raspon;
- monofoniju, overlap i chord gustoću;
- trajanje i density;
- intervale, step/repeat odnos;
- velocity mean/std;
- Guitar Mode command odnos;
- tvrde kanalne zaštite za bass, drums i percussion.

Zatim bira najbliži dokazani Factory Sound. Standardni GM bank 0 se ne proglašava User Soundom. Poznata Factory adresa se nikad ne prepisuje ovom logikom. Automatska zamjena zahtijeva confidence najmanje 0,75; slabije preporuke se samo prijavljuju u audit izvještaju.

## MIDI headroom

Headroom sloj radi tri stvari:

1. Gold relativni velocity oblik se preslikava u Factory mean/P95 omotač po ulozi.
2. Završni soft limiter ponovo provjerava Solo, Strumming i Guitar Repair izlaz, bez uništavanja drum i RX velocity slojeva.
3. CC7 se centrira prema Factory role centru, najčešće 110, uz očuvanje postojeće automatizacije.
4. CC11 se centrira prema Factory medijanu i ograničava kada kombinacija CC7 × CC11 prelazi Factory effective-level plafon.

Ovo je MIDI kontrolni headroom. Stvarni audio peak, LUFS, EQ i kompresija ne mogu se izmjeriti bez rendera stvarnog Pa800 izlaza.

## Rhythm Guitar Repair

Za Standard MIDI File najbolji izbor nije pretvaranje običnih akorda u Style Guitar Mode komande. Guitar Mode je Style/Pad sistem, dok Song MIDI mora ostati prenosiv i odmah svirljiv.

Zato repair koristi hibrid:

- Factory daje dokaz da je track guitar i daje chord/strum strukturu;
- Gold je već primijenio velocity, timing i gate karakter;
- repair se aktivira samo na dokazanoj guitar traci sa najmanje osam chord napada i najmanje 55% potpuno simultanih, robotskih akorda;
- akordne pitch note se ne mijenjaju;
- žice dobijaju mali fizički vremenski razmak;
- down/up redoslijed se izmjenjuje;
- velocity dobija blagi string accent;
- gate se završava prije sljedećeg akorda;
- već humanizovana gitara se ne obrađuje drugi put.

Pa800 Guitar Mode trackovi i dalje koriste zasebni Strumming DNA sa službenim command notama, RX Noise i Humanize GTR pravilima.

## Verifikacija

- 603 Factory Sound profila;
- 16 Factory/Gold/combined mix profila;
- Factory regresija: 3.211/3.211 fajlova, 0 grešaka i 0 pogoršanih note-on/off slučajeva;
- poznati Factory Soundovi zamijenjeni Sound Intelligence logikom: 0;
- dokazano robotske Factory guitar trake popravljene: 1.714;
- Factory mean/P95 velocity kalibracija: 1.345.808 nota;
- završni Factory plafon nakon kasnijih Solo/Strumming/Guitar slojeva: 2.011 nota;
- Gold audit: 182 fajla, 0 grešaka i 0 pogoršanja;
- 540 nepoznatih Gold track/adresa analizirano, 51 prelazi automatski confidence prag 0,75;
- svaki guitar repair prijavljuje `pitch_notes_changed: 0`.