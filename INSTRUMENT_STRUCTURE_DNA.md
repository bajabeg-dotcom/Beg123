# Instrument Identity Lock i Full Factory Style DNA

## Glavno pravilo

Sound se može promijeniti samo u isti kanonski instrument identitet.

- Finger Bass GM/Factory → Finger Bass RX;
- Picked Bass → Picked Bass RX;
- Acoustic Bass → Acous. Bass RX;
- Clean Electric Guitar → Clean Guitar RX;
- Standard Kit → Standard Kit RX;
- Alto Sax ne može postati Clarinet;
- Fretless Bass ne može postati Finger Bass;
- instrument bez potvrđenog identičnog RX cilja ostaje originalan.

Isti Program Change broj nije dovoljan dokaz. Identitet koristi Bank MSB/LSB, Program, naziv, ulogu i vremenski segment. Drum kit i melodic Sound mogu dijeliti PC broj, ali nisu isti instrument.

## Svih 128 GM identiteta

`instrument_structure_dna.sqlite3` sadrži kompletan GM katalog 0–127. Svaki program ima naziv, kanonski identitet, porodicu, role hint i eksplicitno preserve pravilo. RX adresa je dozvoljena samo kada njen identitet odgovara izvornom instrumentu.

Trenutno postoje 142 conversion pravila: 128 obaveznih preserve pravila i 14 identity-safe RX opcija za Standard Kit, Clean Guitar, Acoustic/Finger/Picked Bass i potvrđene slap varijante.

## Full Factory struktura po instrumentu

Iz Factory Styles izgrađena je 6.301 struktura i 194 runtime identity modela. Struktura se razdvaja po:

- CC00/CC32/PC adresi;
- instrument identitetu i ulozi;
- Intro, Variation, Fill, Break i Ending sekciji;
- CV oznaci i metru;
- 16-step velocity i timing potpisu;
- gate-u, densityju, swingu, CC1 i CC11 ponašanju.

Optimizer prvo bira Factory model istog identiteta i metra. Njegov velocity po beat poziciji je glavni kalibracijski cilj.

## Gold/Balkan korekcija

Gold DNA daje 356 korekcijskih modela za 71 instrument identitet. Redoslijed primjene je:

1. detektuj svaki Program Change vremenski segment;
2. zaključaj instrument identitet;
3. učitaj Factory strukturu istog identiteta;
4. učitaj Gold model istog identiteta, tempa i metra kada postoji;
5. Factory određuje velocity mean/std/P95 i beat poziciju;
6. Gold daje samo relativni akcent, timing, gate i fraziranje;
7. Sound se mijenja samo ako RX cilj ima isti identitet;
8. u suprotnom mapping se odbija i original ostaje.

Ako nema Gold modela istog instrumenta, koristi se role-performance fallback bez promjene Sounda.

## Program Change vremenska linija

Identitet se ne određuje jednom za cijeli track. Svaki Program Change segment ima vlastiti identitet. Track zato može prvo koristiti Finger Bass, zatim Picked Bass, a svaki dio dobija samo svoju korekciju i svoj dozvoljeni RX cilj.

## Verifikacija

- 128 GM identiteta;
- 98 Factory identiteta;
- 71 Gold identitet;
- 6.301 Factory section/CV struktura;
- 194 Factory runtime identity modela;
- 376 Gold/Balkan identity korekcija;
- 142 conversion pravila;
- 80 aktivnih identity-safe mapiranja;
- cross-family mapiranja u aktivnoj bazi: 0;
- Factory regresija: 3.211 fajlova, 0 grešaka i 0 pogoršanja;
- Factory instrument-model primjene: 17.634;
- Gold korekcije istog identiteta: 6.210;
- jedan stvarni konflikt (`Standard 16 Beat_Fill1`) ispravno je blokiran: drum-kit segment nije pretvoren u Finger Bass RX.