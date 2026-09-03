# Slap Bass RX — provjera velocity praga

## Zaključak

Radna korekcija za interni low/high multisample switch kod `SlapFing Bass RX` i `SlapPick Bass RX` je **87**, umjesto ranije upisanih 94. Ovo nije promjena glavnih RX zona: radni oscilator i dalje obuhvata velocity 53–113, dok posebni Slap/Harmonic oscilator ostaje 114–127.

Prag 87 je trenutno označen kao kombinacija korisničkog znanja i statističke potvrde iz Factory Styles materijala. Za konačnu potvrdu treba otvoriti originalni zvuk na Pa800 u Sound Edit modu ili analizirati službeni PCG/Musical Resources sadržaj.

## Factory Styles analiza

Analiza je urađena preko svih 3.211 Factory MIDI segmenata koristeći NumPy i ugrađeni MIDI parser.

| Profil | Trake | Note | 53–86 | 87–113 | 114–127 | Najčešće velocity vrijednosti |
|---|---:|---:|---:|---:|---:|---|
| SlapFing Bass RX | 214 | 5.185 | 1.249 | 3.538 | 132 | 92, 91, 80, 93, 90, 110, 87 |
| SlapPick Bass RX | 21 | 859 | 374 | 386 | 76 | 111, 72, 115, 104, 74, 68, 108 |

`SlapPick Bass RX` naročito pokazuje dvije jasne grupe oko 72 i 111, što podržava interni switch približno na 87. `SlapFing Bass RX` ima najveću koncentraciju oko 87–93.

## Promjena u optimizeru

Kod Slap RX bass profila Gold velocity transformacija više ne smije slučajno prebaciti notu preko praga 87:

- original 53–86 ostaje u 53–86;
- original 87–113 ostaje u 87–113;
- original 114–127 ostaje u 114–127.

Time se čuva namjera Factory patterna, a Gold DNA utiče na dinamiku samo unutar odgovarajućeg artikulacijskog sloja.