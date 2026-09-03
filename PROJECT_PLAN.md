# Plan projekta: Factory Rhythm × Gold DNA Performance × RX Sounds

> Status: napredna lokalna beta je završena 11. augusta 2026. Više nije skelet; produkcijska potvrda zahtijeva zvučnu A/B kalibraciju na fizičkom Pa800.

## Nalaz iz dostavljenog materijala

- `prism-uploads/DNA.zip` sadrži 3.211 Factory MIDI segmenata (3.187 jedinstvenih) u 248 stilskih grupa i 182 Gold DNA fajla (181 jedinstven).
- Factory je SMF format 1 na 192 PPQ i već je podijeljen na Intro 1–3, Variation 1–4, Fill 1–2, Break i Ending 1–3. To ga čini boljom osnovom za **strukturu i ritmiku**.
- Gold DNA je uglavnom SMF format 0 na 384 PPQ i sadrži kompletne live izvedbe. To ga čini boljim izvorom za **velocity, gate/trajanje, gustoću i način sviranja**.
- U analizi je Gold melodic prosjek velocityja 101.01 prema Factory 85.12, a Gold drums 97.01 prema Factory 88.75. Gold note su kraće i malo gušće.
- `prism-uploads/Oscilatori.txt` daje RX velocity/key zone, ali ne daje RX Bank MSB, Bank LSB i Program brojeve. Ti brojevi se ne smiju izmišljati.

## Agent operating model

Projekt koristi šest formalnih uloga:

1. `ChatGPT Architect`: plan, prioriteti, work-package ugovori i acceptance kriteriji.
2. `ChatGPT Audit`: gapovi, rizici, kontradikcije i zavisnosti.
3. `Codex Lead`: tehnička podjela zadataka, vlasništvo fajlova i integracija.
4. `Codex Implementer`: kod i ciljani testovi unutar dodijeljenih fajlova.
5. `Codex QA`: nezavisni pregled i verdict `ACCEPT`, `RETURN` ili `BLOCK`.
6. `Human Owner`: cilj, bitne odluke, Pa800 dokazi i release.

Detaljni tok, izlazni ugovori i zabrana spajanja Implementer/QA odgovornosti nalaze se u `X10_AGENT_OPERATING_MODEL.md`.

## Implementirane faze

1. `data/factory.sqlite3`: 3.187 fajlova, 607 automatski registriranih role-aware profila i 29.724 track statistike.
2. `data/gold_dna.sqlite3`: 181 fajl, 291 profil i 1.883 track statistike.
3. Seed od 49 RX oscilator/drum zona iz `Oscilatori.txt`.
4. Lokalni ChatGPT/Codex planner i opcionalni OpenAI Responses API adapter.
5. HTML GUI za import, plan, pregled RX zona, GM→RX mapiranje, optimizer i download.
6. Dependency-free SMF parser/writer, SysEx karantin, RX velocity zaštita i round-trip testovi.
7. Službeni Pa800 katalog od 21 adrese i 7 početnih GM→RX mapa sa confidence/provenance oznakama.

## Sljedeća obavezna kalibracija

Sljedeća faza je proširiti pokrivenost Factory 120/121 profila prema službenom Pa800 katalogu i napraviti A/B test najmanje 10 stilova na stvarnom instrumentu. Trenutni MVP koristi role-aware profile (bass, guitar, accompaniment, percussion, drums i melodic), podesivu Gold jačinu te ograničava promjenu trajanja na 0.67–1.50 puta.