# X10 Rhythm Context — stable identity i multi-scale osnova

Datum: 11. august 2026.

## Implementirano

`rxoptimizer/rhythm_context.py` uvodi mutation-free analitički sloj:

- stabilni `event_id` iz source SHA-256, tracka, originalnog ordera, vrste događaja, kanala, ticka i payload-a;
- stabilni `note_id` koji povezuje tačan Note On i Note Off;
- meter timeline sa promjenama mjere;
- bar, beat, subbeat fraction i tick-in-bar poziciju;
- duration u tickovima i četvrtinkama;
- `cross_bar` oznaku;
- previous/next note relacije po track/channel toku;
- exact bar pattern fingerprint bez quantize ili nearest-grid operacije.

## Važno ograničenje

Exact fingerprint trenutno dokazuje samo identičan event raspored. On nije još groove-similarity model i ne smije se koristiti kao repair target.

```text
repair_capability = NONE
purpose = ANALYSIS_IDENTITY_AND_CONTEXT
```

## Testovi

- isti originalni događaj daje isti ID;
- promjena ticka mijenja ID;
- 3/4 meter i cross-bar nota su pravilno označeni;
- neighbour veze su stabilne;
- dva identična takta daju isti fingerprint bez grid snappinga.

Phrase/multi-bar instance i lokalna Calibration baza su sada materijalizovane. Sljedeće: cross-file/context consensus i analyze-only anomaly engine; fingerprint ostaje dokaz strukture, ne automatski repair cilj.
