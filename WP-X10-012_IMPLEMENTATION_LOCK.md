# WP-X10-012 — Implementation-Lock Addendum

Datum: 11. august 2026.  
Verzija: 4  
Capability: `ANALYZE_ONLY`  
Status: `READY_FOR_REAUDIT`

## Mixture initialization

Nakon deterministic mean izbora, observation se dodjeljuje komponenti sa najmanjim exact circular distanceom; tie bira niži circular-order indeks. Prazna komponenta daje `INVALID_EMPTY_INITIAL_COMPONENT`; nema reseedinga niti automatskog smanjenja k.

Initial component mass je suma normalized weights hard-assigned članova. `π=m_h/n_eff`. Initial raw scale je weighted mean circular distance, a initial floor weighted median half-tick resolution članova. Obavezni redoslijed: means → hard assignment → mass/π → raw scale → floor → max → component sort → prvi E-step.

Component collapse je nonpositive mass/π, bez final hard membera ili dvije komponente sa istim rational meanom, canonical scale/weightom i posterior vectorom. Candidate postaje `INVALID_COMPONENT_COLLAPSE`; ne pretvara se u niži-k success. Ako svi candidatei collapse, modality je unstable collapse.

## Posterior hard assignment

Posteriori se računaju directed Decimal intervalima. Component je jedinstveni winner samo ako je njegov lower interval veći od upper intervala svih drugih. Overlap daje `POSTERIOR_ASSIGNMENT_TIE`; niži circular-order component služi samo za deterministic bookkeeping, dok modality postaje `UNSTABLE_POSTERIOR_TIE`. Component sufficiency koristi final hard assignment; insufficient component invalidira candidate.

## LOSO matching

Full/fold k mora biti isti. Exhaustive permutation cost je suma circular mean distances. Permutation je validna samo kada njen directed upper cost strogo pobijedi lower cost svih drugih. Overlap daje `UNSTABLE_COMPONENT_MATCH`; nema secondary scale/weight heuristic tie-breaka. k=1 je trivijalno validan. Nakon matcha component i groove-tuple sufficiency moraju ostati validni.

## Zatvoreni enum domeni

Adapter run: `COMPLETE`, `PARTIAL`, `DEPENDENCY_UNAVAILABLE`, `DEFERRED_POST_MODEL`, `NOT_APPLICABLE`, `FAILED_CONTRACT`, `FAILED_RUNTIME`.

Per-rule protection: `CLEAR`, `NOT_APPLICABLE`, `DETECTED`, `AMBIGUOUS`, `EVIDENCE_UNJOINABLE`, `DEPENDENCY_GAP`, `DEFERRED`, `PARTIAL_UNRESOLVED`.

Factory model: `FACTORY_SUFFICIENT`, `FACTORY_INSUFFICIENT`, `FACTORY_UNAVAILABLE`.

Candidate fit: `VALID_CONVERGED`, empty/collapse/insufficient/identifiability/nonfinite/numerical invalid statusi.

Modality: unimodal, multimodal, degenerate exact, insufficient, structure/BIC/match/groove/posterior/collapse unstable, numerical/cycle/nonconvergence review i deferred statusi.

Reference: support, no evidence, insufficient, potential contradiction, uninformative Factory support, deferred unstable Factory i partial post-model.

Protection aggregate: clear, detected, unresolved, external gap, partial, deferred ili contract incomplete.

Final authorization je zatvoren skup svih preserve/review/insufficient/excluded statusa iz truth funkcije plus jedini pozitivni `ANALYZE_ALLOWED`. Build terminal statusi odvajaju source/schema/stable-ID/adapter/numerical/integrity/digest/forbidden-source abort. Unknown enum je hard fail.

## Canonical config

Jedan canonical config/hash uključuje sufficiency, subject/adapter versions, enum-domain hash, weight/density/Decimal/k/init/M-step/posterior/collapse/BIC/LOSO/support/groove/authorization contracts. Hash ulazi u build, adapter runs, modality, reference, authorization i semantic digest. Svaka promjena zahtijeva version bump i fresh build.

## Test lock

Obavezni su testovi za initial ties/empty/π/scale-floor order, zero raw scale, collapse, posterior unique/tie/near-tie, hard-assignment insufficiency, LOSO unique/tie/k1, sve enum vrijednosti i unknown rejection, reachability final statusa, config parity/mismatch, six-song guard, full pytest i novi nezavisni QA nakon schema-v2 integrationa.

## Architect verdict

```text
READY_FOR_REAUDIT
```