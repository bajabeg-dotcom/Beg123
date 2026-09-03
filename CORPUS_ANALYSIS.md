# Analiza MIDI korpusa

| Korpus | Jedinstveni fajlovi | Profili | Trake | Glavna namjena |
|---|---:|---:|---:|---|
| Factory Styles | 3.187 | 607 | 29.724 | sekcije, ritam, patch inventar |
| Gold DNA | 181 | 291 | 1.883 | live dinamika, gate, gustoća |

Factory arhiva sadrži 248 stilskih foldera. Segmenti su raspoređeni na Variation 1–4, Intro 1–3, Fill 1–2, Break i Ending 1–3. Pronađena su 24 duplikata. Gold DNA ima jedan duplikat.

## Ponderirane izvedbene karakteristike

| Korpus / uloga | Note | Velocity mean | Velocity std | Trajanje u četvrtinkama | Note po četvrtinki |
|---|---:|---:|---:|---:|---:|
| Factory melodic | 1.065.352 | 85.12 | 13.47 | 3.937 | 4.28 |
| Gold melodic | 1.862.650 | 101.01 | 5.97 | 0.409 | 4.69 |
| Factory drums | 322.657 | 88.75 | 21.27 | 4.493 | 4.89 |
| Gold drums | 401.077 | 97.01 | 19.89 | 0.200 | 6.27 |

Zaključak: Gold DNA je dinamički jači, komprimiraniji u melodic dijelu, kraći u gate-u i nešto gušći. Factory trajanja su neuobičajeno duga jer style segmenti često koriste arranger-held note i specifične note-off obrasce; zato optimizer ne kopira Gold vrijednosti direktno nego ograničava omjer promjene.

## Važni pozivni brojevi viđeni u materijalu

Factory koristi Korg Pa-series banke MSB 120/121. Među najčešćima su melodic `120/0/65`, `121/3/1`, `120/0/67`, te drum kitovi `120/0/6`, `120/0/35` i `120/0/34` (Program prikazan 1–128).

Gold DNA često koristi melodic `121/19/22`, `121/5/49`, `121/13/26`, `121/15/22` i `121/15/26`, te drum kitove `120/0/1`, `120/0/2` i `120/0/5`.

Ovi brojevi su automatski registrirani kao identiteti izvornog instrumenta. Oni nisu automatski proglašeni RX brojevima; stvarno RX odredište mora se potvrditi za konkretan uređaj.

## Potvrda iz službenog Korg Pa800 priručnika

Pa800 identitet zvuka prikazuje kao `CC00.CC32.PC`, odnosno Bank Select MSB, Bank Select LSB i Program Change. Priručnik koristi MIDI vrijednosti 0–127; GUI dodatno pokazuje 1–128 radi kompatibilnosti sa sequencerima koji Program prikazuju u tom formatu.

U zaseban `pa800_voice_catalog` unesena je 21 službeno potvrđena adresa: šest RX bass zvukova, šest Clean Guitar RX zvukova i devet GM/RX drum kitova. Primjeri su Finger Bass RX `121/13/33`, Clean Guitar RX1 `121/14/28` i Pop Std. Kit RX `120/0/4`. Katalog potvrđuje ciljnu adresu, ali GM→RX izbor ostaje zasebno pravilo kako se muzička namjena ne bi pogrešno pretpostavila.

Optimizer počinje sa sedam konzervativnih GM pravila, a zatim recommendation engine iz Factory profila generiše samo one dodatne source tuple čiji cilj postoji u potvrđenom Pa800 katalogu. Ostali profili ostaju netaknuti i prijavljuju se kao `unmapped`. Gold SysEx se stavlja u karantin, a trajanje se poredi u četvrtinkama kako različiti PPQ formati Factory (192) i Gold (uglavnom 384) ne bi dali pogrešan gate.

## Napredna ekspanzija

Nakon identity-safe recommendation prolaza postoji 79 aktivnih mapa. One pokrivaju 79/607 jedinstvenih profila, 8.048/29.724 Factory traka i 376.601/1.388.009 nota. Gold/Balkan referentna baza sadrži 1.883 feature zapisa sa 16-step velocity/timing histogramima, swingom, gate-om, densityjem i CC1/CC11 statistikama. Puni test svih 3.211 Factory segmenata završio je bez parse/export greške i bez pogoršanja izvorne note-on/off semantike.