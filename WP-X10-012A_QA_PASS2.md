# WP-X10-012A — Independent QA Pass 2

Datum: 11. august 2026.  
Verdict: `RETURN`

Otvoreno:

1. Subject izvan declared universe ne smije implicitno postati `NOT_APPLICABLE`; multi-partition protokol mora agregirati particije umjesto očekivati jednu kopiju run countova.
2. Protection group membership mora pripadati parent run applicable populaciji.
3. Cluster/phrase/component natural key mora biti strogo tipizirani mapping sa canonical fieldovima i stable-ID članovima; alias/non-mapping ulaz je zabranjen.
4. Canonical config mora zaključati subject/adapter/predicate/sufficiency verzije i contract version.
5. Authorization capability mora biti immutable `ANALYZE_ONLY`.

Targeted 57 i full 200 testova prolaze, ali paket nije prihvaćen.

## Verdict

`RETURN`