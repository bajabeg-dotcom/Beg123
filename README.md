# GM → RX MIDI Optimizer

Napredna lokalna beta za spajanje Factory MIDI strukture, beat/role-aware Gold DNA izvedbenog modela i potvrđenog GM→RX bank/program mapiranja.

Završna tehnička provjera i tačan status nalaze se u `COMPLETION_REPORT.md`.

## Pokretanje

```bash
python3 app.py
```

Otvorite `http://127.0.0.1:8765`.

### Windows `.bat` pokretanje

Zbog projektnih pravila batch fajlovi su spremljeni kao `install.bat.tex` i `run.bat.tex`. Na Windows računaru uklonite završni `.tex`, zatim prvo pokrenite `install.bat`, a poslije toga `run.bat`. GUI je ugrađen direktno u Python, pa početna stranica radi i ako `static/` folder nedostaje.

Potreban je Python 3 i NumPy. `install.bat` automatski provjerava/instalira NumPy. Projekt koristi ukupno 17 SQLite baza; detaljna namjena je opisana u `DNA_DATABASES.md`.

## Solo instrumenti

Optimizer ima zaseban Solo DNA sloj za lead/guitar kanale. Analizira fraze, monofoniju, registar, intervale, legato, pitch bend, modulation, expression i aftertouch. U GUI-ju se može uključiti Solo DNA, podesiti jačina i ručno navesti solo MIDI kanale. Potpuna specifikacija je u `SOLO_INSTRUMENT_DNA.md`.

## Pa800 Guitar Mode

Strumming DNA razumije Guitar Mode command note, chord velocity kodove, individualne žice, power chord, mute, RX Noise i Humanize GTR. GUI ima zasebnu Strumming jačinu, Humanize, sigurnu Down/Up varijaciju i Capo audit. Potpuna specifikacija je u `STRUMMING_DNA.md`.

## Novi song MIDI korpus

Šest dodatnih pjesama je strogo zaključano kao Delay/Terca track-identification skup. Ne koristi se za Ornament, Trill, Fill, PowerChord, Noise, Repair ili drugi DNA.

## Song Layer DNA

Optimizer prepoznaje postojeći Delay i terca/harmony track. Delay se optimizuje ili, ako nedostaje, može nastati kao zaseban track. Terca se nikada ne kreira: postojećoj terci koriguju se samo velocity i već postojeći CC7/CC11, bez promjene pitcha, onseta ili trajanja. Trill/ornament procjena koristi isključivo Gold DNA i po defaultu ne izmišlja nove ukrasne note. Detalji su u `SONG_LAYER_DNA.md`.

Strogi Factory/Balkan Trill Extraction, false-positive pravila, potpuni evidence locator i Solo→postojeća Terca/Delay ornament odnosi opisani su u `MUSICAL_INTELLIGENCE_DNA.md`.

Dokazni inventar se generiše naredbom `python3 app.py evidence-inventory`; sažetak i trenutne arhitekturne rupe nalaze se u `RX_EVIDENCE_INVENTORY.md` i `CURRENT_ARCHITECTURE_AUDIT.md`.

## Factory Sound Intelligence i Headroom

Nepoznata User Sound adresa se klasifikuje prema paternu sviranja i, samo uz confidence najmanje 0,75, dobija najbliži dokazani Factory Sound. Factory određuje velocity mean/P95, CC7/CC11 i headroom; Gold daje samo relativne akcente, timing, gate i fraziranje. Regularni robotski guitar akordi mogu se popraviti bez promjene pitch nota. Detalji i mjerene vrijednosti su u `SOUND_INTELLIGENCE_DNA.md`.

## Instrument Identity Lock

Svih 128 GM instrumenata ima eksplicitno pravilo. Sound se smije promijeniti samo u isti identitet: Finger Bass → Finger Bass RX, Picked Bass → Picked Bass RX, Clean Guitar → Clean Guitar RX. Ako identičan RX cilj nije potvrđen, original ostaje. Factory struktura i Gold/Balkan korekcija biraju se po svakom Program Change vremenskom segmentu. Detalji su u `INSTRUMENT_STRUCTURE_DNA.md`.

## Pa800 test agenti

GUI sadrži pet auditabilnih test-agenta. Dugme **Kreiraj test suite** registruje MIDI fajlove iz `output/`, a **Izvezi upute** pravi vodič i manifest u `hardware-tests/`. Automatski agenti provjeravaju fajlove, hash i RX mapiranja. Fizički playback i slušni A/B rezultat moraju se unijeti nakon testa na Pa800; release se do tada prikazuje kao `pending_hardware`.

Ponovno indeksiranje cijele dostavljene arhive:

```bash
python3 app.py import-archive prism-uploads/DNA.zip
```

Samo ponovna izgradnja svih izvedenih DNA baza:

```bash
python3 app.py build-dna
```

Import je idempotentan: SHA-256 duplikati se prepoznaju, a originalni ZIP se ne mijenja. Factory profili koriste stvarni naziv iz MIDI metapodataka kada postoji te MSB/LSB/Program trojku kao pozivni broj.

Opcionalni AI planeri:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.4"
python3 app.py
```

API ključ se čita samo iz environmenta i ne sprema se u bazu ili browser.

## Važno ograničenje

Službeni Pa800 katalog sada sadrži 21 potvrđenu RX/GM adresu i 7 konzervativnih početnih GM→RX pravila s confidence/provenance podacima. Nepokriveni Factory profili ostaju nepromijenjeni i prikazuju se u optimizer izvještaju; dodatna mapiranja mogu se potvrditi u GUI-ju.

Optimizer po defaultu uklanja uređaj-specifični SysEx iz izlaza, normalizuje Gold trajanje u četvrtinkama nezavisno od PPQ-a i štiti RX velocity zone od slučajnog aktiviranja slap/noise/dead artikulacija. Konačni timbar i dalje zavisi od stvarnog Pa800 renderera, pa je za produkciju potreban A/B test na instrumentu.

### Evidence režimi

Default `Strict evidence` režim ne mijenja Program/Bank u RX Sound dok cilj nema `CONFIRMED` primarni manual/PCG/hardware dokaz u Evidence Registryju. `Catalog review` je eksplicitni identity-safe A/B režim za Pa800; report označava sva nepotvrđena mapiranja i takav izvoz nije release-eligible.

RAW snapshot se obnavlja tek poslije punog corpusa komandom `python3 app.py migrate-layout`. Prazan Factory/Gold corpus se ne može proglasiti validnim snapshotom; ako pointer nije prisutan, prvo pokrenuti puni `import-archive` recovery.

### RX Noise Pa800 probe

RX Noise probe se kreira kroz GUI nakon uploada zasebnog MIDI fajla. Svaki testira C7–G9 na četiri velocity nivoa za Clean Guitar RX1–RX6, Finger Bass RX i Picked Bass RX. Šest Delay/Terca referenci blokirano je po SHA-256 sadržaju, čak i kada se preimenuje fajl.

### Single-articulation Factory/Gold probe

```bash
python3 app.py build-articulation-probes
```

Komanda traži stvarne Factory/Gold pojave i pravi jedan testni MIDI po dokazanoj artikulaciji. Svaki fajl aktivira specijalni trigger tačno jednom. Trenutno je generisano 30 proba od 39 kandidata; devet bez evidencea ostaje negenerisano.