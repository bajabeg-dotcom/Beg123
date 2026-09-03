# WP-X10-012 — Independent Architecture Audit

Datum: 11. august 2026.  
Capability: `ANALYZE_ONLY`  
Verdict: `ARCHITECT_CORRECTION_REQUIRED`

## P0 nalazi

1. Post-consensus `FACTORY_REFERENCE_CONFLICT` stvara kružnu zavisnost sa WP-011 obaveznim adapterima. Pre-model, model eligibility, post-model conflict i final authorization moraju biti odvojeni stageovi.
2. Nije definisan zajednički stable subject registry za event, note, onset cluster, bar, phrase, component i boundary subjekte, natural keys i parent-child veze.
3. Sparse `NOT_DETECTED` coverage nije operativno dokaziva bez scope tipa, applicability predicatea, subject-universe digesta/counta i partial-scan pravila.
4. Legacy strumming/trill/RX evidence nije stable-ID joinable. Potrebna je RAW re-extraction klasifikacija `REEXTRACTABLE_EXACT`, `UNJOINABLE_PRESERVE` ili `DEPENDENCY_UNAVAILABLE`; približan tick/pitch/name/range join je zabranjen.
5. Drum, section-transition i local-repeat adapteri nemaju zatvoren algoritamski ulaz/applicability/membership/coverage ugovor.
6. Circular mixture/BIC nije matematički kompletan: density, `k`, parameter count, `n`, fit, constraints, tie, convergence, assignment, matching i runtime lock nedostaju. Dozvoljena tvrdnja je samo da nema ručnog timing-distance/separation praga.
7. Source balancing je kontradiktoran očuvanju intra-source modova; mora se izabrati source representative ili hijerarhijski/equal-source weighted likelihood.
8. Circular 0/1 boundary, mixed PPQ scale floor, diskretna phase, exact-repeat pre-gate, per-slot status i groove-mode coherence nisu definisani.
9. WP-011/WP-012 statusi, dense/sparse schema i semantic digest nisu kompatibilni. Potreban je eksplicitni schema-v2/migration ownership prije implementacije.

## P1 nalazi

- Guitar note range nije dokaz Guitar Modea.
- RX/DNC mora razlikovati exact non-applicable Sound od applicable evidence gap/ambiguous zone/confirmed detection.
- Jedan membership po subject/rule može izgubiti više grupnih provenance veza.
- Factory/reference circular conflict metric nije definisan.
- Multimodal full-corpus fit treba disk-backed deterministic spool i complexity/report ugovor.
- Adapter registry mora razlikovati `CORE_REQUIRED` i `EXTERNAL_OPTIONAL` crash ponašanje.
- Potrebna je potpuna authorization truth table.

## Obavezne korekcije

Architect mora razdvojiti stageove, definisati subject registry i coverage dokaz, zatvoriti svih devet adapter ugovora, propisati RAW re-extraction/migration, dati kompletan circular model, razriješiti source weighting, definisati exact-repeat/PPQ/circular semantiku, dodijeliti schema-v2 ownership i objaviti authorization truth table i corpus-scale acceptance.

## Gate verdict

```text
ARCHITECT_CORRECTION_REQUIRED
```