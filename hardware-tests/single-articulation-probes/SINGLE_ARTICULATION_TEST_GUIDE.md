# Korg Pa800 single-articulation test

Svaki MIDI aktivira jednu posebnu artikulaciju tačno jednom. Primjer je uzet iz Factory ili Gold MIDI člana navedenog u manifestu.

1. Učitaj jedan probe MIDI na Pa800.
2. Poslušaj normalnu prethodnu notu ako postoji.
3. Srednja/specijalna nota je jedini artikulacijski trigger koji se testira.
4. Poslušaj normalnu sljedeću notu ako postoji.
5. U GUI unesi Probe ID, `confirmed`, `partial` ili `rejected`, zatim napiši šta se stvarno čulo.
6. Obavezno upiši Pa800 OS i Musical Resources/SET verziju. Bez njih se potvrda odbija.

Naziv artikulacije u fajlu je `OBSERVED_UNVERIFIED_TRIGGER`, ne potvrđena činjenica. Šest Delay/Terca pjesama nije korišteno.
Rezultati se čuvaju atomski u `articulation-results.json`; `confirmed` dobija `pending_evidence_review`, nikad automatski produkcijski status.