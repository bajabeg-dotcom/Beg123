# Pa800 Guitar Mode i Strumming DNA

## Službena Pa800 osnova

Strumming DNA je napravljen prema službenom dokumentu **KORG Pa800 Operating System release 1.60**, u kojem je Guitar Mode uveden za Style Record i Pad Record.

Guitar Mode traka mora imati `Track Type = Gtr`. Tada je `Tension` automatski uključen. Kod programiranja iz vanjskog sequencera MIDI kanal mora odgovarati Style traci, obično Acc1–Acc5.

Za razliku od običnog ACC tracka, najniže dvije oktave ne predstavljaju doslovne tonove akorda, nego Guitar Mode komande. Pa800 zatim gradi stvarne guitar voicinge prema prepoznatom akordu, položaju i Capo parametru.

## C1–B1: strumming komande

| MIDI | Nota | Komanda |
|---:|---|---|
| 24 | C1 | Full Down |
| 25 | C#1 | Full Down Mute |
| 26 | D1 | Full Up |
| 27 | D#1 | Full Up Mute |
| 28 | E1 | Full Down Mute Body |
| 29 | F1 | Full Down Slow |
| 30 | F#1 | Full Down Slow Mute |
| 31 | G1 | Full Up Slow |
| 32 | G#1 | Up Mute 4-Strings |
| 33 | A1 | Down 4-Strings |
| 34 | A#1 | Down Mute 4-Strings |
| 35 | B1 | Up 4-Strings |

## C2–B2: žice, root/fifth i arpeggio

| MIDI | Nota | Komanda |
|---:|---|---|
| 36 | C2 | VI String – low E |
| 37 | C#2 | Recognized Chord Root |
| 38 | D2 | V String – A |
| 39 | D#2 | Recognized Chord Fifth |
| 40 | E2 | IV String – D |
| 41 | F2 | III String – G |
| 42 | F#2 | Mute All Strings |
| 43 | G2 | II String – B |
| 44 | G#2 | Power Chord |
| 45 | A2 | I String – high E |
| 46 | A#2 | Full Down/Up |
| 47 | B2 | Down/Up 4-Strings |

## Chord progression u Intro 1 i Ending 1

U Intro 1 i Ending 1 note `C-1–B-1` kodiraju root akorda, a velocity tačno određuje chord type. Te vrijednosti su semantičke i optimizer ih nikada ne smije normalizovati.

| Velocity | Chord | Velocity | Chord |
|---:|---|---:|---|
| 1 | Major | 2 | Major 6th |
| 3 | Major 7th | 4 | Major 7th flat 5 |
| 5 | Suspended 4th | 6 | Suspended 2nd |
| 7 | Major 7th sus4 | 8 | Minor |
| 9 | Minor 6th | 10 | Minor 7th |
| 11 | Minor 7th flat 5 | 12 | Minor major 7th |
| 13 | Dominant 7th | 14 | 7th flat 5 |
| 15 | 7th sus4 | 16 | Diminished |
| 17 | Diminished major 7th | 18 | Augmented |
| 19 | Augmented 7th | 20 | Augmented major 7th |
| 21 | Major without 3rd | 22 | Major without 3rd and 5th |
| 23 | Flat 5th | 24 | Diminished 7th |

## Ostale mogućnosti Guitar Modea

- `C3–B6`: regularne note za kratke melodijske prolaze, završetke i posebne chord pasaže.
- `C7` i više: RX Noise note, zavisno od odabranog guitar Sounda.
- `Capo 0, I–X`: mijenja položaj i timbar bez promjene chord shapea; neke žice mogu postati nedostupne.
- `Diagram`: prikazuje fingered string, fifth, muted string, barré i capo.
- `Humanize GTR`: utiče na poziciju, velocity i dužinu Guitar track nota.
- `RX Noise`: zasebna glasnoća noise slojeva na Noise/Guitar stranici.
- `Key/Chord`: monitoring referenca u većini CV-ova; chord progression referenca u Intro 1 i Ending 1.
- `Pad Record Guitar Mode`: iste guitar komande mogu se koristiti u Guitar tipu Pad trake.
- NTT Type/Table je nedostupan za Guitar track; Guitar Mode sam računa realne položaje akorda.

## Šta Strumming DNA uči iz Factory Styles

Za svaku dokazanu Guitar Mode traku čuva:

- Style i sekciju: Intro, Variation, Fill, Break ili Ending;
- CV/track/channel i instrument profil;
- tempo bucket i metar;
- odnos down/up poteza;
- mute, slow i four-string omjere;
- pojedinačne string/arpeggio komande;
- chord root i chord type događaje;
- RX Noise raspored;
- velocity po svih 16 pozicija 4/4 mreže;
- mikro-timing po 16-step poziciji;
- stroke transition statistiku;
- density, velocity prosjek i standardnu devijaciju;
- zasebne modele za svaki guitar Sound.

Detekcija zahtijeva dokaz instrumenta: guitar naziv, guitar program bez instrument metapodatka ili gotovo čistu Guitar Mode command traku. Piano, kit, drums, bass, organ, brass, sax, synth i pad profili eksplicitno se odbacuju.

## Primjena u optimizeru

1. Prepozna Guitar Mode traku prije Gold transformacije.
2. Izdvoji command note `C1–B2` i RX Noise note iz običnog melodic/ACC procesa.
3. Potpuno zaštiti chord progression velocity `1–24`.
4. Izabere najbliži section/tempo/meter Strumming model.
5. Primijeni Factory velocity profil prema 16-step poziciji.
6. Primijeni deterministički Humanize GTR na timing, velocity i gate.
7. Timing je ograničen na najviše ±0.025 četvrtinke.
8. Gate varijacija je ograničena približno na ±10% Humanize jačine.
9. Down/Up komanda se može zamijeniti samo odgovarajućim parom iste porodice:
   open ostaje open, mute ostaje mute, slow ostaje slow, four-string ostaje four-string.
10. Alternacija se koristi samo kada je potvrđena Factory transition modelom.
11. String, root, fifth, mute-all, power-chord i arpeggio identiteti ostaju sačuvani.
12. RX Noise pitch se ne mijenja; dozvoljena je samo blaga dinamika i timing.
13. Regularne note `C3–B6` i dalje mogu koristiti Gold Performance DNA.
14. CC11 na Guitar Mode traci ostaje originalan, jer Pa800 manual upozorava da Expression događaji mogu mijenjati glasnoću tracka.
15. Izlaz prolazi note-on/off, MIDI range i End-of-Track validaciju.

## GUI kontrole

- **Aktiviraj Pa800 Strumming DNA**
- **Strumming jačina**: preporuka 55–75%
- **Humanize GTR**: preporuka 25–55%
- **Sigurna Down/Up varijacija**
- **Capo 0–10**: bilježi namjeravanu Pa800 Capo poziciju u optimizer audit izvještaj

Capo je Style Guitar Mode parametar i običan SMF ga ne može potpuno prenijeti. Zato ga aplikacija bilježi i prikazuje testeru, ali ne izmišlja neprovjeren SysEx.

## Materijalizovani Factory rezultat

- 1.196 dokazano Guitar Mode/strumming trackova;
- 19.052 Guitar Mode command događaja;
- 73 section/tempo/meter modela;
- 65 guitar Sound profila;
- 24 službene command note;
- 24 službena chord velocity tipa;
- 12 Guitar Mode sigurnosnih pravila.

## Važna ograničenja

- SMF može sadržati Guitar Mode command note, ali Style parametri poput Track Type, Capo, Key/Chord i Noise level moraju biti potvrđeni nakon importa na Pa800.
- Nije sigurno proglašavati običnu nisku notu Guitar Mode komandom bez guitar dokaza.
- RX Noise rezultat zavisi od konkretnog Pa800 Sounda.
- Konačni chord voicing, capo položaj, muted strings i Humanize GTR zvuk moraju se provjeriti na fizičkom Pa800.

## Regresijska provjera

Provjereno je svih 613 Factory fajlova koji sadrže Strumming DNA evidenciju. Svih 1.196 Guitar Mode trackova je ponovo prepoznato, bez parse/export greške, bez pogoršanja note-on/off semantike i bez ijedne promjene chord root/velocity koda u Intro 1 ili Ending 1.