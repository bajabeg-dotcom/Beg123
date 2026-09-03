# Detaljna primjena Solo Instrument DNA

## Cilj

Solo DNA služi da melodijski ili lead instrument dobije prirodniji način sviranja iz Gold DNA materijala, bez promjene same melodije. Ne dodaje nove note, ne transponuje frazu i ne izmišlja artikulacije koje izvorni MIDI nije tražio.

Factory/GM/RX mapiranje određuje **koji zvuk svira**, Gold Performance DNA daje opću dinamiku i timing, a Solo DNA određuje **kako se solo fraza izvodi**.

## Šta sistem analizira

Za svaku MIDI traku i kanal registruje:

- prosječan, minimalan i maksimalan registar tona;
- prosječan interval između nota;
- udio sekundi i malih koraka;
- udio skokova od pet ili više polutonova;
- ponovljene note;
- monofoniju i polifone overlap situacije;
- legato odnos i trajanje nota;
- odmore između nota;
- granice fraza kod odmora od najmanje pola četvrtinke;
- prosječan broj nota po frazi;
- velocity sredinu, raspon i standardnu devijaciju;
- postojeći pitch-bend broj, učestalost i amplitudu;
- CC1 modulation/vibrato;
- CC11 expression;
- channel i polyphonic aftertouch/pressure;
- tempo, metar, instrument program i porodicu instrumenta.

## Automatsko prepoznavanje solo trake

Svaka traka dobija `solo_score` od 0 do 1. Bodovanje koristi stvarne dokaze:

- monofona linija nosi najveću težinu;
- pitch bend, modulation, expression i pressure povećavaju vjerovatnoću;
- lead registar, odvojene fraze i umjerena gustoća povećavaju rezultat;
- guitar trake dobijaju mali dodatak jer Gold DNA sadrži mnogo live guitar-solo materijala;
- bass, drums, percussion i arranger accompaniment nisu automatski solo kandidati.

Automatski prag je `0.62`, uz najmanje osam nota. Korisnik može forsirati kanal unosom MIDI kanala 0–15 u GUI-ju.

## Solo porodice

Modeli se uče odvojeno za:

- piano;
- chromatic/mallet;
- organ;
- guitar solo;
- strings;
- ensemble;
- brass;
- reed/sax/clarinet porodicu;
- pipe/flute;
- synth lead;
- synth pad;
- ethnic solo;
- generički melodic solo fallback.

Model se dodatno bira prema najbližem tempo bucketu i metru.

## Redoslijed obrade

1. MIDI se parsira i validira.
2. Čitaju se CC00, CC32 i Program Change segmenti.
3. Potvrđeni GM/Factory zvuk se mapira na RX gdje postoji sigurna adresa.
4. Gold Performance DNA primjenjuje beat-aware velocity, mikro-timing i gate.
5. Solo classifier bira samo lead/guitar kandidate.
6. Note se dijele u fraze prema stvarnim odmorima.
7. Primjenjuje se blagi frazni luk: početak je jasan, sredina fraze nosi vrhunac, završetak se smiruje.
8. Legato se prilagođava porodičnom modelu, uz overlap najviše `0.03` četvrtinke.
9. Završna nota fraze može biti produžena najviše 5% solo jačine.
10. Postojeći pitch bend se skalira prema Gold modelu, ali najviše između 75% i 125% izvorne amplitude.
11. Ako izvor nema pitch bend, sistem ga ne izmišlja.
12. CC1, CC11 i pressure ostaju vezani za postojeću izvedbenu namjeru.
13. Poslije svake velocity promjene ponovo se primjenjuje RX zone guard.
14. Note-on/off, EOT i ponovljena ista nota prolaze završnu semantičku provjeru.

## RX zaštita

Solo frazni luk ne smije slučajno aktivirati slap, noise, dead, harmonic ili slide oscillator. Promijenjeni velocity ostaje unutar zone iz koje je originalna nota krenula.

Posebno se čuvaju:

- SlapFing/SlapPick granice `53–86`, `87–113` i `114–127`;
- bass radna zona i posebne harmonic/noise zone;
- Clean Guitar RX radna zona `53–93`;
- drum ghost/accent namjera, iako drums nisu solo kandidati.

## GUI kontrole

- **Aktiviraj detaljni Solo DNA**: potpuno uključuje ili isključuje solo sloj.
- **Solo jačina**: 0–100%; preporučeni početak je 65%.
- **Forsirani solo MIDI kanali**: npr. `0,1,4`; koristi se kada automatski classifier ne zna da je neka traka namjerno solo.
- Optimizer izvještaj prikazuje kanal, porodicu, score, broj fraza, broj nota i korišteni model.

## Preporučene postavke

| Solo instrument | Solo jačina | Napomena |
|---|---:|---|
| Sax/reed | 60–75% | Dobro koristi postojeći bend, expression i duže legato fraze. |
| Solo gitara | 55–70% | Čuva postojeći bend; obavezno poslušati RX velocity artikulacije. |
| Synth lead | 60–80% | Dobro reaguje na CC1 i pitch bend ako ih MIDI već ima. |
| Violina/strings solo | 45–65% | Manja jačina čuva prirodne duge note. |
| Flute/pipe | 50–65% | Važne su frazne pauze; ne forsirati overlap. |
| Piano solo | 30–50% | Piano je polifon; automatski classifier je namjerno konzervativan. |
| Harmonika/organ | 40–60% | Koristiti forsirani kanal samo kada je desna ruka stvarno odvojena. |
| Brass/trumpet | 50–70% | Provjeriti napade i kratke note na fizičkom Pa800. |

## Trenutni materijalizovani rezultat

Gold korpus sadrži 1.883 analizirane trake. Solo classifier je pronašao 30 jakih kandidata i izgradio 22 family/tempo/meter modela. Najviše potvrđenih kandidata dolazi iz guitar-solo porodice, zatim synth lead, organ, reed i ostalih melodijskih porodica.

Stvarni test na `TI I JA ZAGRLJENI-LJUBA A UZIVO.MID` pronašao je guitar-solo kanal sa scoreom većim od 0.74, 255 nota i 113 fraza. Solo obrada promijenila je fraznu dinamiku, gate i postojeći bend, dok je izlaz zadržao svih 17.978 note-on i 17.978 note-off događaja bez semantičke greške.

## Ograničenja

- Solo DNA poboljšava MIDI izvedbu, ali ne može simulirati stvarni Pa800 RX multisample renderer.
- Za zvukove bez potvrđene RX adrese ostaje originalni program.
- Aftertouch i bend imaju smisla samo ako ih ciljni Pa800 zvuk koristi.
- Automatski classifier je konzervativan; složeni piano, accordion ili chord-melody kanal može zahtijevati ručni izbor.
- Konačna ocjena timbra, vibrata i RX switch ponašanja zahtijeva fizički Pa800 i slušni A/B test.