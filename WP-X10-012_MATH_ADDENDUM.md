# WP-X10-012 — Final Mathematical and Adapter Addendum

Datum: 11. august 2026.  
Verzija: 3  
Capability: `ANALYZE_ONLY`  
Status: `READY_FOR_REAUDIT`

Ovaj dodatak zaključava preostale matematičke, numerical, grace/drum i authorization ugovore.

## Versioned sufficiency

`X10_SUFFICIENCY_V1`: minimum 3 distinct Factory files, 9 bar observations, dominant-source share ≤0.5 i najmanje 4 files za leave-one-source-out. Canonical config/hash se upisuje u sve stageove; mismatch je hard fail.

## Weight, likelihood i BIC

Za source `s` sa `n_s` observationa: raw weight `a_sj=1/n_s`; ukupna raw masa `A=S`. Kish `n_eff=(Σa)^2/Σa²=S²/Σ_s(1/n_s)`. Normalized likelihood weight je `w_i=a_i*n_eff/A`, pa `Σw=n_eff` i svaki source ima jednaku masu. Ovaj postupak je invariantan na množenje svih raw težina istom pozitivnom konstantom.

`L_k=Σ_i w_i log f_k(x_i)`, `p_k=3k-1`, `BIC_k=-2L_k+p_k ln(n_eff)`. Candidate je invalid ako `n_eff<=p_k`.

## Numerical representation

Reduced rational phase je semantic autoritet za unique/exact/tie/digest. Semantic odluke koriste Decimal precision 50, `ROUND_HALF_EVEN`; finalni likelihood/BIC intervali se računaju precision 60 sa directed floor/ceiling roundingom. Binary64 je samo report/UI vrijednost.

Candidate A je dokazivo bolji samo ako je njegov BIC upper bound manji od lower bounda svakog drugog kandidata. Overlap najboljih intervala daje `UNSTABLE_BIC_NEAR_TIE`; nema epsilon praga.

## Wrapped Laplace EM

Circular distance je `min(|x-μ|,1-|x-μ|)`. Wrapped Laplace density je `exp(-d/b)/[2b(1-exp(-1/(2b)))]`; means su samo observed rational phases.

Exact rational repeat daje `DEGENERATE_EXACT_REFERENCE`, `k=1`, bez fita/tolerancije i bez authorizationa.

`k_max` je minimum unique phases, `floor(B/9)` i najvećeg k sa `3k-1<n_eff`. Svaka component mora imati ≥3 files, ≥9 hard-assigned bars i dominance ≤0.5.

Initialization je deterministic weighted circular-medoid pa farthest-first, sa smallest-rational tie-breakom. E-step je standard responsibility. M-step bira observed rational phase koja minimizira responsibility-weighted circular absolute deviation; overlapping directed objective interval bira najmanju rational phase. Raw scale je responsibility-weighted mean distance. Floor je responsibility-weighted median stvarne half-tick phase resolution; update order je responsibilities → mean → raw scale → floor → max → mixture weight → canonical component order.

Canonical parameter tuple određuje convergence. Ponovljen non-adjacent digest je numerical cycle; max 1024 iteracije je computational safety limit. NaN, invalid denominator, cycle ili nonconvergence daju review status.

Leave-one-source-out zahtijeva 4 files, isti k, sufficient components i exhaustive permutation matching. Permutation je validna samo ako njen directed cost interval strogo pobjeđuje ostale; overlap daje unstable match.

## Groove coherence

Slotovi su stable-key sortirani. Groove tuple je ordered component-ID tuple po source/bar instanceu; unimodal slot koristi 0. Nedostajući slot je incomplete. Tuple groups moraju proći iste file/bar/dominance i LOSO gateove. Stabilno više tuple modova daje assessed multimodal, ali i dalje preserve; nestabilni tupleovi daju unstable groove structure. Multiple group membership je dozvoljen i evidence se ne gubi.

## Konzervativni grace/drum v1

Grace: samo exact Human-validated RAW stable component može biti detected. Bez toga svaki applicable melodic/guitar/solo Track/Channel dobija `AMBIGUOUS_GRACE_CLASSIFIER_UNAVAILABLE`; nema duration/percentile/interval heuristike i nema analyze authorizationa.

Drum: repeated same-lane structural component ili Human-validated RAW component može biti protection detection, ali flam/roll/ghost se ne proglašava potvrđenim. Ostali exact drum/percussion scope dobija `AMBIGUOUS_DRUM_ARTICULATION_CLASSIFIER_UNAVAILABLE`; nema velocity/IOI/channel-only clear pravila.

## Factory/reference support

Factory component support arc je complement najvećeg exact circular gap-a; tie bira najmanji canonical start. Arc se proširuje samo stvarnom half-tick rezolucijom članova. Full-circle arc je uninformative. Reference je supported ako njena resolution proširena phase dodiruje neki Factory arc. Potential contradiction zahtijeva stable Factory model, sufficient reference i observation izvan svih arcova; reference ne refituje Factory model.

## Status i authorization

Status domeni su eksplicitni za source quality, context, adapter runs, per-rule protection, Factory model, modality i reference relationship. Unknown enum je contract hard fail.

Protection precedence: runtime/contract failure abort; detected → protected; ambiguous/unjoinable → unresolved; external gap → preserve; partial → partial preserve; deferred → deferred preserve; svi complete clear/non-applicable → clear; druga kombinacija je contract incomplete.

Authorization precedence:

1. hard source/schema/ID/integrity/adapter failure → build abort;
2. INVALID → excluded;
3. RARE/OUTLIER → preserve quality;
4. unproven/conflict context → preserve context;
5. partial core scan → preserve;
6. detected/unresolved/external-gap/partial/deferred protection → odgovarajući preserve/review;
7. insufficient Factory → insufficient evidence;
8. degenerate exact → zero-variance review;
9. insufficient/unstable/numerical/deferred modality → preserve;
10. stable multimodal → preserve multimodal;
11. partial/deferred/uninformative reference gate → preserve;
12. potential contradiction → review conflict;
13. samo Factory sufficient + assessed unimodal + protection clear + reference support/no-reference/insufficient-reference → `ANALYZE_ALLOWED`.

Svaki izlaz, uključujući `ANALYZE_ALLOWED`, ima proposal/repair false i mutation `NONE`.

## Exception razdvajanje

Programming/runtime exception i invalid output/schema/natural key su hard fail. Missing external RX evidence je dependency gap/preserve. Muzička nejasnoća je ambiguous/preserve. Insufficient statistics je review/preserve. Exception se nikad ne maskira kao musical ambiguity.

## QA/integration

Schema-v2 integration u WP-011 fajlove zahtijeva novi nezavisni QA; WP-011 ACCEPT se ne prenosi. Testovi moraju pokriti weight invariance, rational/mixed PPQ, wrap, exact repeats, intra-source bimodality, BIC interval ties, cycles/nonconvergence, grace/drum fail-closed, exhaustive authorization, sparse partial coverage, contamination, spool determinism, full pytest i atomic rollback.

## Architect verdict

```text
READY_FOR_REAUDIT
```