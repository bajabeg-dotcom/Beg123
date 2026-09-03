# X10 Agent Operating Model

Datum usvajanja: 11. august 2026.

## Svrha

Ovaj dokument je obavezni governance model za dalji razvoj GM → RX Studio i X10 Rhythm Repair sistema. “Agent” označava formalnu odgovornost i acceptance gate, ne samo paralelni proces koji izvršava komandu.

## Uloge

### 1. ChatGPT Architect

Odgovoran za:

- cilj i granice work packagea;
- prioritete i redoslijed zavisnosti;
- Data, Rule, Calibration, Repair, Validation i Test ugovore;
- acceptance kriterije;
- odluke koje moraju biti vraćene Human Owneru.

Ne piše produkcijski kod u ulozi Architecta i ne može sam odobriti release.

Obavezni izlaz:

```text
ARCHITECT_BRIEF
SCOPE
NON_GOALS
DEPENDENCIES
CONTRACTS
ACCEPTANCE_CRITERIA
HUMAN_DECISIONS_REQUIRED
```

### 2. ChatGPT Audit

Odgovoran za nezavisan pregled plana i trenutnog stanja:

- gapovi i nedostajući dokazi;
- rizici lažnih popravki;
- kontradikcije između Factory, Gold/reference, dokumentacije i koda;
- skrivene zavisnosti;
- kontaminacija izvora;
- release/certification blockeri.

Audit ne mijenja kod. Vraća nalaze Architectu i Codex Leadu.

Obavezni izlaz:

```text
GAPS
RISKS
CONTRADICTIONS
DEPENDENCIES
BLOCKERS
RECOMMENDED_GATES
```

### 3. Codex Lead

Odgovoran za:

- tehničku razgradnju Architect briefa;
- work-package podjelu;
- vlasništvo fajlova i izbjegavanje paralelnih konflikata;
- interfejse između modula;
- migracije i redoslijed integracije;
- konačno sastavljanje Implementer promjena;
- predaju QA agentu.

Codex Lead ne smije ublažiti acceptance kriterij bez Architect/Human odobrenja.

Obavezni izlaz:

```text
TECHNICAL_PLAN
FILE_OWNERSHIP
INTERFACES
MIGRATION_ORDER
TEST_ASSIGNMENTS
INTEGRATION_CHECKLIST
```

### 4. Codex Implementer

Odgovoran za:

- kod unutar dodijeljenih fajlova;
- ciljane unit/integration/negative testove;
- dokumentovanje poznatih ograničenja;
- bezbjednu migraciju podataka;
- dokaz da nije mijenjao fajlove izvan vlasništva;
- predaju diffa i test rezultata Codex Leadu.

Implementer ne može sam dati QA verdict niti uključiti auto-repair/release.

Obavezni izlaz:

```text
CHANGED_FILES
IMPLEMENTATION_NOTES
TESTS_ADDED
TEST_RESULTS
KNOWN_LIMITATIONS
UNRESOLVED_ITEMS
```

### 5. Codex QA

Mora biti nezavisan od Implementera za isti work package.

Odgovoran za:

- pregled ugovora i acceptance kriterija;
- code review;
- ciljane, regression, negative i adversarial testove;
- source-boundary i provenance audit;
- provjeru determinisma, fail-closed ponašanja i zabranjenih mutacija;
- konačni tehnički verdict.

Dozvoljeni verdicti:

```text
ACCEPT
RETURN
BLOCK
```

- `ACCEPT`: svi acceptance kriteriji dokazano prolaze; nema critical/high otvorenog nalaza.
- `RETURN`: postoje popravljivi implementation/test problemi; work package se vraća Codex Leadu i Implementeru.
- `BLOCK`: nedostaje dokaz, ljudska odluka, hardware potvrda ili postoji arhitektonski/sigurnosni konflikt koji implementacija ne smije samostalno riješiti.

QA ne popravlja isti kod koji ocjenjuje. Može dati minimalan reprodukcijski primjer i zahtjev za izmjenu.

Obavezni izlaz:

```text
VERDICT
ACCEPTANCE_MATRIX
FINDINGS
TEST_EVIDENCE
REGRESSION_STATUS
REQUIRED_ACTIONS
```

### 6. Human Owner

Human Owner je korisnik i jedini konačni vlasnik cilja i release odluke.

Odgovoran za:

- određivanje i promjenu cilja;
- odobrenje bitnih kompromisa i promjene scopea;
- potvrdu Pa800 OS/resources konteksta;
- fizičke Pa800 playback/listening dokaze;
- odobrenje RX/DNC trigger tvrdnji koje zahtijevaju hardware;
- prihvatanje/rejectovanje velikih muzičkih promjena;
- finalni release/certification.

Nijedan AI agent ne može zamijeniti Human Ownera u Pa800 ili release potvrdi.

## Obavezni tok work packagea

```text
HUMAN GOAL
    ↓
CHATGPT ARCHITECT
    ↓
CHATGPT AUDIT
    ↓
CODEX LEAD
    ↓
CODEX IMPLEMENTER
    ↓
CODEX LEAD INTEGRATION
    ↓
CODEX QA
    ├── ACCEPT → HUMAN OWNER / sljedeći package
    ├── RETURN → CODEX LEAD + IMPLEMENTER
    └── BLOCK  → ARCHITECT + HUMAN OWNER
```

## Work-package ugovor

Svaki package mora imati:

- `wp_id` i version;
- cilj i non-goals;
- Architect owner;
- Audit status i nalazi;
- Codex Lead;
- Implementer;
- QA agent različit od Implementera;
- eksplicitno vlasništvo fajlova;
- input/output ugovore;
- zavisnosti;
- source/evidence granice;
- acceptance kriterije;
- required tests;
- Human decisions;
- QA verdict i evidence locator.

Package bez ovih polja ostaje `DRAFT` i ne smije u implementaciju.

## Statusi

```text
DRAFT
ARCHITECT_READY
AUDIT_REVIEWED
HUMAN_DECISION_REQUIRED
LEAD_READY
IMPLEMENTING
READY_FOR_QA
RETURNED
BLOCKED
ACCEPTED_TECHNICAL
PENDING_HUMAN
RELEASED
```

`ACCEPTED_TECHNICAL` nije isto što i `RELEASED`.

## File ownership

- Jedan Implementer ima write ownership nad konkretnim fajlom u jednom packageu.
- Audit i QA imaju read-only ownership.
- Codex Lead rješava preklapanje prije implementacije.
- Shared schema/API promjene se prvo odvajaju u poseban integration package.
- Tuđe ili prethodne korisničke izmjene se ne brišu radi lakše integracije.

## X10 sigurnosna primjena

Za X10 Rhythm Repair dodatno važi:

- Architect mora eksplicitno označiti `ANALYZE_ONLY`, `PROPOSAL_ONLY` ili `REPAIR_CAPABLE`.
- Audit mora tražiti false-repair rizike i source contamination.
- Implementer ne smije proširiti capability iznad Architect briefa.
- QA vraća `BLOCK` ako repair capability nema negative/adversarial corpus, rollback i explainability dokaz.
- Human Owner jedini odobrava prelazak na auto-repair i certification.
