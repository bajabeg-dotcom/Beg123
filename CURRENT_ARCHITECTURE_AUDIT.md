# Current Architecture Audit — Phase 0

Datum audita: 11. august 2026.

## Šta je odmah zaključano

- Automatsko kreiranje terce je uklonjeno iz enginea.
- Stari API parametar `harmony_create=true` više nema efekta.
- Postojeća terca zadržava pitch, onset i trajanje.
- Na postojećoj terci dozvoljene su samo velocity korekcije i korekcije već postojećih CC7/CC11 događaja.
- Song reference cohort je eksplicitno ograničen na šest korisnički odobrenih fajlova.
- Generisani `*-gold-rx-*.mid` i budući uploadi više ne mogu tiho ući u Delay/Harmony modele.
- Ručno RX mapiranje mora pogoditi stvarnu adresu/naziv iz Pa800 kataloga i proći identity lock.
- Napravljen je SHA-256 inventar svih Factory/Gold MIDI članova.
- Implementiran je `evidence_registry.sqlite3` sa field-level claimovima, locatorima, konfliktima i verification taskovima.
- Multi-Program trackovi se sada rastavljaju na stvarna Bank/Program stanja po Note On vremenu i event orderu.

## P0 stanje nakon Phase 3

### 1. RAW snapshot je obnovljen, runtime tranzicija nije završena

Aktivna generacija `data/generations/335ad9cb42bd41768993/` ima read-only `factory_raw.sqlite3`, `gold_raw.sqlite3` i odvojeni `application_state.sqlite3`, uz semantic hash/count parity. Legacy `factory.sqlite3` se još koristi za dio runtime upita, pa tranzicija nije završena.

Sljedeće: sve read upite prebaciti na atomski `data/database-layout.json` pointer i `connect_raw(..., mode=ro)`; promjenjive write upite prebaciti na application state.

### 2. Evidence Registry runtime gate je implementiran

RX zone i Sound mapiranja prolaze kroz strogi registry gate. `UNKNOWN`, `UNVERIFIED`, `INFERRED` i `CONFLICTED` ne mogu aktivirati RX artikulaciju, mijenjati njen velocity sloj ili u default režimu promijeniti Sound.

Trenutni rezultat je namjerno konzervativan: 0/49 zona i 0/21 Sound ciljeva je prihvaćeno za automatsku generaciju. `catalog_review` postoji samo kao eksplicitni A/B režim i nije release-eligible ako primijeni nepotvrđeno mapiranje.

### 3. Dokumentacija nije lokalno reproducibilna

`reference/pa800/README.md` sadrži službene URL-ove, ali lokalni PDF, hash i page locator ne postoje.

Rješenje: arhivirati dozvoljene službene dokumente, registrirati verziju/OS i vezati svaku tvrdnju za stranicu ili tabelu.

## P1 problemi

- Factory/Gold naziv u trenutnoj dokumentaciji je neprecizan: postojeći Gold ZIP je balkanski referentni korpus, dok budući `GOLD_RULESET` mora biti izvedeno i kurirano znanje.
- RX schema je preuska za trigger composition, PRE/ATTACK/MAIN/TRANSITION/RELEASE/POST sequence, context i negative rules.
- EQ mora ostati odvojen od MIDI velocity/volume modela; bez Pa800 rendera i audio mjerenja nema potvrđenog timbralnog EQ pravila.
- Forum tvrdnje moraju ući kao `forum_hypothesis`, nikad kao `CONFIRMED`.
- Fizički Pa800/PCG/Sound Edit verifikacija ostaje obavezna za Slap switch 87 i detaljne Noise/Slide mape.

## Sljedeća implementacijska faza

1. Dovršiti runtime tranziciju na read-only RAW pointer i application-state write bazu.
2. Materijalizovati Factory statistike kao reproducibilne `observations`, bez promocije u trigger činjenice.
3. Napraviti `RX_UNKNOWN_FIELD_AUDIT` po instrumentu.
4. Nabaviti lokalne primarne PDF/PCG/Sound Edit/hardware locatore i zatvoriti verification taskove.
5. Tek nakon toga graditi instrument labs: bass, guitar, brass/sax/flute, strings, drums/percussion, pads i ostalo.
6. RX Generation ostaje posljednja faza i koristi samo dokazano pravilo sa zadovoljenim context i negative-rule gateom.
