# Korg Pa800 — službena dokumentacija i optimizer bilješke

## Službeni Korg dokumenti

- Owner's Manual (English): https://www.korg.com/us/support/download/manual/1/193/2268/
- Advanced Edit, OS 2.0: https://www.korg.com/us/support/download/manual/1/193/1859/
- Easy Start Guide: https://www.korg.com/us/support/download/manual/1/193/2273/
- OS 2.02 Release Notes: https://www.korg.com/us/support/download/manual/1/193/2274/
- OS 2.0 Upgrade Guide: https://www.korg.com/us/support/download/manual/1/193/2532/
- OS 1.60 Upgrade Manual, Guitar Mode pages 5–7: službeni Korg dokument sa C1–B2 command mapom, chord velocity tabelom, Humanize GTR, RX Noise, Capo i Key/Chord pravilima.
- SongBook Editor User Guide: https://www.korg.com/jp/support/download/manual/1/8/2990/
- Kompletna Pa800 download stranica: https://www.korg.com/us/support/download/product/1/193/

Korg dozvoljava jednu kopiju priručnika za ličnu, nekomercijalnu upotrebu. PDF-ovi se preuzimaju sa službenih stranica nakon prihvatanja licence.

## Bitno za MIDI optimizer

- Pa800 prikazuje identitet zvuka kao `CC00.CC32.PC`: Bank Select MSB, Bank Select LSB i Program Change.
- Sve tri vrijednosti u Pa800 priručniku koriste standardni MIDI raspon 0–127.
- Neki sequenceri prikazuju Program kao 1–128; baza čuva 0–127, a GUI pokazuje oba prikaza.
- Bank Select i Program Change za Style Chord Variation trebaju biti na početku varijacije, odnosno tick 0.
- RX zvuk može koristiti do 16 oscilatora, velocity/key zone i posebne drum multisample slojeve.
- Gold DNA Korg SysEx se ne kopira automatski jer može mijenjati uređaj-specifične parametre.
- Guitar Mode command note nisu obični akordi: C1–B2 se moraju analizirati kao strum/string komande, a Intro1/Ending1 velocity 1–24 kao chord type kodovi.

## Provjereni Pa800 RX pozivni brojevi

Vrijednosti su u službenom 0–127 formatu.

| Naziv | CC00 | CC32 | PC |
|---|---:|---:|---:|
| Acous. Bass RX | 121 | 7 | 32 |
| Finger Bass RX | 121 | 13 | 33 |
| Picked Bass RX | 121 | 10 | 34 |
| FunkSlap Bass RX | 121 | 3 | 36 |
| SlapFing Bass RX | 121 | 4 | 36 |
| SlapPick Bass RX | 121 | 5 | 36 |
| Clean Guitar RX1 | 121 | 14 | 28 |
| Clean Guitar RX2 | 121 | 15 | 28 |
| Clean Guitar RX3 | 121 | 16 | 28 |
| Clean Guitar RX4 | 121 | 17 | 28 |
| Clean Guitar RX5 | 121 | 18 | 28 |
| Clean Guitar RX6 | 121 | 20 | 28 |
| Standard Kit RX2 | 120 | 0 | 1 |
| Standard Kit RX3 | 120 | 0 | 2 |
| Ambient Kit RX | 120 | 0 | 3 |
| Pop Std. Kit RX | 120 | 0 | 4 |
| Standard Kit RX1 | 120 | 0 | 5 |
| Jazz Kit RX1 | 120 | 0 | 33 |
| Jazz Kit RX2 | 120 | 0 | 34 |
| Jazz Kit RX3 | 120 | 0 | 35 |

Katalog potvrđuje ciljne Pa800 adrese. Izbor GM izvora za pojedinu RX varijantu ostaje zasebno optimizer pravilo sa provenance/confidence oznakom.