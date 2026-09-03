# WP-X10-011 — ChatGPT Audit

Datum: 11. august 2026.

Status: `ARCHITECT_CORRECTION_REQUIRED`

Audit je read-only. Capability ostaje `ANALYZE_ONLY`.

## Gapovi

1. Program timeline nije definisan za channel događaje raspoređene kroz više trackova.
2. Početni Program se ne smije predstavljati kao dokazani `(0,0,0)`; potreban je `PROGRAM_DEFAULT_UNSPECIFIED` ili `PROGRAM_UNKNOWN`.
3. Legacy calibration/consensus profili nemaju Program, CV ni tempo dimenzije i ne mogu se retroaktivno označiti kao context-qualified.
4. Legacy role fallback nepoznato pretvara u `melodic`.
5. Nedostajući CV se historijski sprema kao `0`, pa CV0 nije odvojen od UNKNOWN.
6. Section nema potpun `section_no`, style provenance i conflict status.
7. Meter timeline ne bilježi same-tick konflikt i nema segment ID/status.
8. Tempo regime identitet i conflict semantika nisu potpuno definisani.
9. V1 fallback redoslijed i confidence decay nisu izvršivo definisani.
10. Negative corpus nema potpunu Factory/synthetic locator strategiju.
11. Protection baze još nemaju zajednički stable event/note ID join.
12. Semantic digest mora biti kanonski i nezavisan od SQLite rowid/page/timestampa.
13. File ownership ne sadrži novi context-join modul, schema test i negative fixtures.

## Rizici

- Spajanje različitih Program/CV/tempo/section konteksta u lažni Factory consensus.
- Nepoznata role predstavljena kao melodic.
- UNKNOWN CV predstavljen kao CV0.
- Propušten ili proizvoljno primijenjen Program Change iz drugog tracka.
- Tempo/meter konflikt pretvoren u determinističku, ali nedokazivu vrijednost.
- Legacy consensus kontaminacija ako se ponovo koristi bez RAW rebuilda.
- `RARE` trackovi mogu ući u calibration iako zahtijevaju review.
- Registrovano negative pravilo može izgledati implementirano iako detektor ne postoji.
- `MULTIMODAL_UNASSESSED` trenutno ispravno blokira svaki autorizovan anomaly zaključak.

## Kontradikcije

- Architect zahtijeva UNKNOWN role/CV, dok legacy put koristi melodic/CV0 fallback.
- Architect zahtijeva exact Program/CV/tempo consensus, dok postojeći consensus nema te dimenzije.
- `factory_gold_links` trenutno ne uključuje section u match ključ.
- Meter konflikt se trenutno tiho kolabira.
- Nije precizirano kada dependency problem daje red sa UNKNOWN/PRESERVE, a kada hard build failure.

## P0 blockeri

1. Definisati cross-track channel semantiku.
2. Definisati nedokazani početni Program.
3. Zabraniti retroaktivni context-qualified status legacy profila; zahtijevati RAW rebuild/paralelni sloj.
4. Dodati `section_no`, style provenance, `meter_segment_id/status` i tempo regime contract.
5. Definisati v1 fallback politiku.
6. Ispraviti file ownership i nove module/testove.

## Obavezni gateovi

```text
G0 SOURCE
G1 TIMELINE
G2 METADATA
G3 PROTECTION
G4 EXACT CONTEXT
G5 RAW REBUILD CONSENSUS
G6 ANALYZE-ONLY SCHEMA
G7 DETERMINISM
G8 NEGATIVE CORPUS
G9 INDEPENDENT QA
```

## Acceptance korekcije

- Različita cross-track stanja na istom ticku daju `PROGRAM_CONFLICT`; ista se smiju kanonski deduplicirati.
- Bez Program Changea nema potvrđenog `(0,0,0)`.
- Note On prije Program Changea zadržava prethodno stanje i kada Note Off dolazi poslije promjene.
- `section_no`, style provenance, meter segment/status i tempo conflict testovi su obavezni.
- Identical simultaneous tempo događaji nisu konflikt; različiti jesu.
- V1 koristi exact-only context; fallback je isključen dok ne postoji odobrena matrica.
- Legacy role/CV/consensus nikad nije context-qualified.
- Protection flag ima evidence locator ili `PRESERVE_UNTIL_IMPLEMENTED`.
- Semantic digest je nezavisan od rowida i fizičkog SQLite layouta.
- Dva builda daju identične kanonske redove i digest.
- Schema nema repair/proposal/target polja.
- Input MIDI hash ostaje identičan poslije analize.
- Testovi pokrivaju renamed six-song hash, stale dependency hash i negative-corpus completeness.

## Audit verdict

```text
ARCHITECT_CORRECTION_REQUIRED
```

Package se ne predaje Codex Leadu dok Architect addendum ne zatvori šest P0 blockera.
