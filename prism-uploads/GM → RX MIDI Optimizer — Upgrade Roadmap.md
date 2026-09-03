# GM → RX MIDI Optimizer — Upgrade Roadmap
## Existing Project → Production Intelligence Edition

### GLAVNA DIREKTIVA

**NE KREIRAJ NOVU APLIKACIJU.**

Preuzmi, analiziraj i unaprijedi **postojeći GM → RX MIDI Optimizer** koji već postoji u ovom repositoryju.

Postojeći kod, GUI, SQLite baze, DNA modeli, Factory/Gold korpus, Evidence Registry, testovi, CLI komande i postojeća dokumentacija predstavljaju **FOUNDATION** projekta.

Cilj je:

> **GM → RX MIDI Optimizer → GM → RX Studio / Production Intelligence Edition**

bez gubitka postojećih funkcija i bez resetovanja postojećih baza ili korpusa.

---

# 0. ABSOLUTE PROJECT RULES

Codex mora prvo izvršiti:

1. Detaljan pregled postojećeg repositoryja.
2. Identifikaciju stvarnog entrypointa.
3. Identifikaciju svih postojećih engine/modula.
4. Identifikaciju svih 17 SQLite baza.
5. Pregled postojećih schema.
6. Pregled Factory/Gold korpusa.
7. Pregled svih testova.
8. Pregled `COMPLETION_REPORT.md`.
9. Pregled `CURRENT_ARCHITECTURE_AUDIT.md`.
10. Pregled `RX_EVIDENCE_INVENTORY.md`.
11. Pregled:
   - `DNA_DATABASES.md`
   - `SOLO_INSTRUMENT_DNA.md`
   - `STRUMMING_DNA.md`
   - `SONG_LAYER_DNA.md`
   - `MUSICAL_INTELLIGENCE_DNA.md`
   - `SOUND_INTELLIGENCE_DNA.md`
   - `INSTRUMENT_STRUCTURE_DNA.md`

Prije bilo kakvog većeg koda napraviti:

**BASELINE AUDIT**

koji mora jasno pokazati:

- šta već postoji,
- šta stvarno radi,
- šta je djelimično implementirano,
- šta je samo dokumentacija,
- šta je placeholder,
- šta je hardcoded,
- šta nema dovoljno evidence,
- šta je testirano,
- šta nije testirano,
- šta može biti sigurno unaprijeđeno,
- šta se NE SMIJE dirati.

### CRITICAL RULE

Ne prepisivati postojeću aplikaciju.

Ne praviti paralelni optimizer.

Ne praviti novu bazu podataka ako postojeća baza može biti proširena.

Ne brisati postojeći corpus.

Ne mijenjati značenje postojećih podataka bez migracije.

Ne smanjivati postojeću funkcionalnost.

Svaka nova funkcija mora biti integrisana u postojeću arhitekturu.

---

# PHASE 1 — EXISTING SYSTEM FORENSICS

Analizirati postojeći sistem kao legacy/production software.

Napraviti:

```text
ARCHITECTURE_MAP.md
ENGINE_INVENTORY.md
DATABASE_INVENTORY.md
PIPELINE_MAP.md
FEATURE_MATRIX.md
UPGRADE_GAPS.md
```

Mapirati:

```text
Input MIDI
   ↓
MIDI Parser
   ↓
Track / Role Detection
   ↓
Instrument Identity
   ↓
Factory Intelligence
   ↓
Gold DNA
   ↓
Rhythm DNA
   ↓
Performance DNA
   ↓
Solo DNA
   ↓
Strumming DNA
   ↓
Song Layer DNA
   ↓
RX Intelligence
   ↓
Evidence Gate
   ↓
Optimization Planner
   ↓
Transaction Journal
   ↓
MIDI Export
   ↓
Validation
   ↓
Hardware Test
```

Identifikovati stvarni tok podataka, a ne samo ono što dokumentacija tvrdi.

---

# PHASE 2 — ARCHITECTURE HARDENING

Unaprijediti postojeću arhitekturu bez razbijanja API-ja.

Uvesti/učvrstiti slojeve:

```text
core/
engines/
dna/
evidence/
analysis/
optimization/
midi/
rx/
audio/
hardware/
database/
api/
gui/
validation/
```

Ali:

**ne premještati module samo radi estetike.**

Refactor samo tamo gdje postoji stvarna tehnička korist.

Obavezno:

- type annotations,
- jasni interfaces,
- dependency boundaries,
- deterministic execution,
- structured logging,
- error handling,
- schema versioning,
- migration support,
- testability.

---

# PHASE 3 — MIDI INTELLIGENCE ENGINE

Postojeći parser/optimizer proširiti u ozbiljan MIDI intelligence layer.

Mora razumjeti:

- Format 0 / Format 1,
- PPQ,
- tempo,
- time signature,
- program change,
- bank select,
- CC,
- RPN,
- NRPN,
- pitch bend,
- aftertouch,
- SysEx,
- note overlap,
- note collision,
- velocity,
- gate,
- timing,
- track role.

Uvesti:

### MIDI Event Normalization

Sve interne analize moraju koristiti normalizovani event model.

Originalni event mora ostati dostupan za rollback.

---

# PHASE 4 — ADVANCED ROLE DETECTION

Postojeći beat/role-aware sistem unaprijediti.

Automatski razlikovati:

- Kick
- Snare
- Hi-Hat
- Percussion
- Bass
- Piano
- Guitar
- Strumming Guitar
- Solo Guitar
- Accordion
- Sax
- Clarinet
- Flute
- Strings
- Brass
- Pad
- Delay
- Terca/Harmony
- Melody
- Ornament
- Trill
- Fill
- FX

Koristiti kombinaciju:

```text
MIDI channel
Program
Bank
Register
Pitch distribution
Velocity distribution
Rhythmic density
Onset pattern
Duration
Polyphony
Interval structure
Factory similarity
Gold similarity
```

Svaka klasifikacija mora imati:

```text
role
confidence
evidence
reason
source
```

---

# PHASE 5 — FACTORY DNA 2.0

Postojeći Factory DNA pretvoriti u pravi referentni model.

Factory mora postati:

**authoritative structural reference**

Analizirati:

- groove,
- velocity,
- timing,
- density,
- phrase structure,
- articulation,
- register,
- role,
- section,
- drum patterns,
- bass patterns,
- guitar patterns,
- fills,
- intros,
- endings,
- variations.

Ne koristiti prosjek cijelog Factory korpusa.

Koristiti:

```text
genre
style
role
section
meter
tempo range
instrument
phrase position
```

za izbor referentnog modela.

---

# PHASE 6 — GOLD DNA 2.0

Gold DNA ostaje **performance reference**, a ne structural authority.

Gold smije uticati na:

- timing,
- velocity accents,
- gate,
- phrasing,
- micro-humanization,
- ornament probability,
- expression,
- dynamics.

Gold NE SMIJE automatski mijenjati:

- identitet instrumenta,
- pitch,
- harmoniju,
- postojeću tercu,
- potvrđeni RX mapping.

Uvesti jasnu separaciju:

```text
FACTORY = STRUCTURE
GOLD    = PERFORMANCE
EVIDENCE = AUTHORITY
USER    = FINAL CONTROL
```

---

# PHASE 7 — ADVANCED RHYTHM INTELLIGENCE

Proširiti postojeći Rhythm DNA.

Obavezno podržati:

```text
2/4
3/4
4/4
5/8
6/8
7/8
9/8
10/8
11/8
12/8
13/8
```

Za neparne ritmove ne koristiti generički quantize.

Napraviti beat-group model:

```text
7/8 → 3+2+2
7/8 → 2+2+3

9/8 → 2+2+2+3
9/8 → 3+2+2+2

11/8 → 3+3+2+3
11/8 → 2+2+3+2+2
```

Model mora učiti/čitati stvarnu distribuciju akcenata iz Factory/Gold podataka.

---

# PHASE 8 — PERFORMANCE REALISM ENGINE

Napraviti deterministički humanization engine.

Bez randomizacije po defaultu.

Modelirati:

- velocity curve,
- onset deviation,
- gate variation,
- accent,
- anticipation,
- release,
- phrase breathing,
- dynamic contour.

Koristiti robustnu statistiku:

```text
median
MAD
IQR
robust z-score
percentiles
```

Humanization mora biti:

```text
role-aware
beat-aware
phrase-aware
instrument-aware
style-aware
section-aware
```

---

# PHASE 9 — BALKAN SOLO DNA 2.0

Postojeći Solo DNA proširiti.

### Accordion

Prepoznati:

- attack,
- sustain,
- release,
- bellows-like dynamics,
- repeated-note articulation,
- trill,
- grace notes,
- 32nd-note ornaments.

CC11 model mora biti izveden iz Gold/Factory podataka gdje evidence postoji.

### Sax / Clarinet / Flute

Modelirati:

- scoop,
- grace note,
- legato,
- breath-like phrasing,
- pitch bend,
- modulation,
- velocity contour.

Pitch bend se nikada ne smije koristiti ako bi prešao sigurnu granicu instrumenta.

---

# PHASE 10 — RX/DNC INTELLIGENCE 2.0

Postojeći RX engine unaprijediti u artikulation decision engine.

Modelirati:

```text
base sound
articulation
trigger
velocity zone
note range
CC
pitch bend
RX switch
noise
dead note
slap
legato
```

Svaka RX odluka mora imati:

```text
candidate
confidence
evidence
risk
reason
```

---

# PHASE 11 — GM → RX MAPPING ENGINE 2.0

Postojećih 21 potvrđenih adresa i 7 konzervativnih pravila ne smiju se rušiti.

Napraviti mapping pipeline:

```text
GM identity
↓
Program Change
↓
Bank MSB
↓
Bank LSB
↓
Factory identity
↓
RX candidate
↓
Evidence lookup
↓
Confidence
↓
Strict Evidence Gate
↓
Decision
```

Tri rezultata:

```text
CONFIRMED
REVIEW
UNCHANGED
```

Nikada:

```text
GUESS
```

u Strict modu.

---

# PHASE 12 — EVIDENCE ENGINE 2.0

Evidence Registry pretvoriti u centralni authority layer.

Svaka tvrdnja mora imati:

```text
claim_id
source
source_type
locator
hash
confidence
status
created_at
verified_at
hardware_result
```

Status:

```text
UNVERIFIED
CANDIDATE
REVIEW
CONFIRMED
REJECTED
SUPERSEDED
```

Hardware dokaz ima veću težinu od statističkog nagađanja.

---

# PHASE 13 — AI INTELLIGENCE LAYER

OpenAI koristiti kao **planner/advisor**, ne kao nekontrolisani generator MIDI izmjena.

AI smije:

- analizirati report,
- objasniti problem,
- predložiti popravku,
- rangirati opcije,
- predložiti A/B probe,
- analizirati evidence,
- generisati test plan,
- objasniti konflikt.

AI NE SMIJE direktno mijenjati MIDI bez determinističkog enginea.

Arhitektura:

```text
AI
 ↓
Recommendation
 ↓
Deterministic Validator
 ↓
Evidence Gate
 ↓
Optimizer
 ↓
Transaction Journal
```

API ključ:

```text
OPENAI_API_KEY
```

nikada ne spremati u:

- SQLite,
- MIDI,
- browser storage,
- log,
- report.

---

# PHASE 14 — OPENAI API INTEGRATION

Ako je OpenAI API već integrisan, provjeriti ga i unaprijediti.

Ako nije:

napraviti minimalni adapter:

```text
openai_adapter.py
```

sa:

```text
analyze_midi_report()
explain_optimization()
generate_test_plan()
analyze_conflict()
suggest_mapping_review()
```

Model mora biti configurable kroz environment:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

Nikada hardcode API key.

---

# PHASE 15 — OPTIMIZATION PLANNER

Optimizer više ne smije biti samo skup pravila.

Napraviti:

```text
ANALYZE
↓
DIAGNOSE
↓
PLAN
↓
SIMULATE
↓
VALIDATE
↓
APPLY
↓
AUDIT
```

Svaka promjena mora imati:

```text
before
after
reason
confidence
evidence
risk
cost
```

Uvesti repair budget.

Primjer:

```text
LOW
MEDIUM
HIGH
```

Ako je rizik veći od dozvoljenog budžeta:

```text
DO NOT APPLY
```

---

# PHASE 16 — TRANSACTION / ROLLBACK ENGINE

Postojeći Journal unaprijediti.

Svaki event modification:

```text
transaction_id
file_hash
track
event_id
old_value
new_value
reason
engine
confidence
evidence
timestamp
```

Mora biti moguće:

```text
rollback transaction
rollback file
rollback optimization stage
```

Original nikada ne smije biti uništen.

---

# PHASE 17 — MULTI-STAGE OPTIMIZATION

Uvesti profile:

### SAFE

Samo:

- očigledne MIDI greške,
- collision,
- clipping,
- invalid events,
- potvrđeni mapping.

### BALANCED

SAFE +

- groove,
- velocity,
- phrasing,
- performance DNA.

### PROFESSIONAL

BALANCED +

- RX,
- solo,
- strumming,
- song layer,
- spatial mix.

### EXPERIMENTAL

Sve prethodno +

AI recommendations,

ali svaki rizični zahvat mora biti označen.

---

# PHASE 18 — A/B ENGINE

Za svaku ozbiljniju promjenu generisati:

```text
ORIGINAL.mid
VERSION_A.mid
VERSION_B.mid
REPORT.txt
CHECKLIST.txt
MANIFEST.json
```

Mora postojati mogućnost poređenja:

```text
pitch
timing
velocity
duration
CC
program
bank
SysEx
RX triggers
```

---

# PHASE 19 — AUTOMATIC MIDI QUALITY CONTROL

Nakon svake optimizacije automatski provjeriti:

- MIDI validity,
- event ordering,
- note pairing,
- overlap,
- stuck notes,
- velocity,
- tempo,
- time signature,
- Program Change,
- Bank Select,
- RPN,
- NRPN,
- SysEx,
- PPQ,
- track count,
- channel integrity.

Ako QC padne:

```text
EXPORT BLOCKED
```

---

# PHASE 20 — PA800 COMPATIBILITY ENGINE

Napraviti poseban validator za Pa800.

Provjeravati:

- GM compatibility,
- RX bank/program,
- velocity zones,
- pitch bend range,
- CC usage,
- SysEx safety,
- channel allocation,
- drum channel,
- Guitar Mode,
- articulation triggers.

Output:

```text
PA800 SAFE
PA800 REVIEW
PA800 UNSAFE
```

---

# PHASE 21 — MASTER MIX INTELLIGENCE

Postojeći Sound Intelligence unaprijediti.

Modelirati:

```text
CC7
CC11
CC91
CC93
velocity
headroom
role
register
density
```

Ali ne koristiti univerzalne hardcoded vrijednosti gdje Factory evidence postoji.

Prioritet:

```text
Factory evidence
↓
Gold relative behaviour
↓
safe fallback
```

---

# PHASE 22 — GUI / STUDIO INTERFACE

Postojeći GUI pretvoriti u pravi Studio workflow.

Glavni paneli:

```text
1. PROJECT
2. MIDI ANALYZER
3. FACTORY DNA
4. GOLD DNA
5. RX / DNC
6. SOLO LAB
7. STRUMMING LAB
8. SONG LAYER
9. EVIDENCE
10. OPTIMIZER
11. A/B LAB
12. HARDWARE TEST
13. JOURNAL
14. AI ASSISTANT
15. REPORTS
```

Ne praviti GUI samo radi izgleda.

Svaki panel mora biti vezan za stvarni engine.

---

# PHASE 23 — AUTONOMOUS ANALYSIS MODE

Dodati:

## AUTO ANALYZE

User ubaci MIDI.

System automatski:

```text
detect
↓
classify
↓
analyze
↓
compare Factory
↓
compare Gold
↓
check RX
↓
check evidence
↓
detect anomalies
↓
generate repair plan
↓
calculate confidence
```

Ali **ne primjenjuje rizične promjene bez dozvole**.

---

# PHASE 24 — AUTO OPTIMIZE MODE

Opcionalno:

```text
AUTO OPTIMIZE
```

Radi samo promjene koje zadovoljavaju:

```text
confidence >= configured threshold
AND
evidence policy allows
AND
risk <= budget
AND
QC passes
```

Sve ostalo ide u:

```text
REVIEW QUEUE
```

---

# PHASE 25 — REVIEW QUEUE

Napraviti centralnu listu:

```text
Issue
Confidence
Evidence
Risk
Suggested Action
A/B Test
Apply
Reject
Ignore
```

User mora moći ručno potvrditi odluke.

---

# PHASE 26 — HARDWARE LEARNING LOOP

Postojeći Pa800 test sistem proširiti:

```text
Generate Probe
↓
Play on Pa800
↓
User Rating
↓
A/B Result
↓
Evidence Registry
↓
Model Calibration
↓
Future Optimization
```

Hardverski rezultat ne smije direktno prepisivati Factory podatke.

Mora biti zaseban evidence layer.

---

# PHASE 27 — CONFLICT RESOLUTION

Automatski otkrivati konflikte:

```text
RX threshold A = 87
RX threshold B = 94
```

System mora:

1. pronaći izvore,
2. procijeniti kvalitet dokaza,
3. napraviti A/B probe,
4. čekati hardware result,
5. označiti winner,
6. sačuvati stari rule kao historical evidence.

Nikada tiho prepisati konflikt.

---

# PHASE 28 — DATABASE ENGINEERING

Postojećih 17 baza optimizovati.

Provjeriti:

- schema consistency,
- foreign keys,
- indexes,
- duplicate records,
- orphan records,
- migrations,
- integrity,
- WAL,
- transaction safety,
- backup,
- restore.

Dodati:

```text
schema_version
corpus_version
build_id
source_hash
created_at
```

Ne raditi destruktivnu migraciju.

---

# PHASE 29 — CORPUS PIPELINE

Import mora ostati idempotentan.

Dodati:

```text
SHA-256
source classification
Factory/Gold classification
duplicate detection
corpus manifest
build checkpoint
resume
```

Batch mora moći nastaviti nakon prekida.

---

# PHASE 30 — REGRESSION TESTING

Postojećih 150 testova ne smije biti smanjeno.

Cilj:

```text
existing tests PASS
+
new tests
+
integration tests
+
database tests
+
MIDI golden tests
+
evidence tests
+
API tests
+
GUI smoke tests
```

Napraviti regression corpus.

Za poznate MIDI fajlove čuvati expected fingerprints.

---

# PHASE 31 — DETERMINISM TEST

Isti input mora dati isti output.

Pokrenuti:

```text
same MIDI
same DB
same config
same model
```

više puta.

Rezultat mora biti identičan:

```text
SHA-256(output_A)
==
SHA-256(output_B)
```

osim ako je eksplicitno uključen nondeterministic/experimental način.

---

# PHASE 32 — PERFORMANCE

Optimizovati za velike korpuse.

Podržati:

```text
batch processing
checkpoint
incremental indexing
SQLite indexes
lazy loading
cache
parallel read analysis
```

Ne koristiti nepotrebno RAM za kompletan corpus.

---

# PHASE 33 — REPORTING

Svaki optimization job mora napraviti:

```text
optimization_report.json
optimization_report.txt
evidence_report.json
change_manifest.json
quality_report.json
```

Report mora sadržavati:

```text
input hash
output hash
database versions
rules used
DNA models used
changes
unchanged tracks
warnings
confidence
evidence
QC
Pa800 compatibility
```

---

# PHASE 34 — SECURITY / API

OpenAI integration mora imati:

- environment-only secrets,
- timeout,
- retry,
- rate limit handling,
- structured errors,
- no secret logging,
- offline fallback.

Ako API nije dostupan:

**Optimizer mora normalno raditi bez AI-ja.**

AI je dodatni intelligence layer, nikako core dependency.

---

# PHASE 35 — DOCUMENTATION

Ažurirati dokumentaciju prema stvarnom kodu.

Napraviti:

```text
README.md
ARCHITECTURE.md
DNA_DATABASES.md
API.md
CLI.md
EVIDENCE.md
AI.md
HARDWARE_TESTING.md
TROUBLESHOOTING.md
UPGRADE_NOTES.md
```

Dokumentacija ne smije tvrditi da nešto postoji ako kod to ne implementira.

---

# PHASE 36 — RELEASE CERTIFICATION

Na kraju napraviti:

```text
FULL SYSTEM AUDIT
```

Provjeriti:

### CORE

- MIDI parser
- optimizer
- exporter

### DNA

- Factory
- Gold
- Rhythm
- Performance
- Solo
- Strumming
- Song Layer
- Musical Intelligence

### RX

- mapping
- articulation
- evidence

### SAFETY

- rollback
- journal
- deterministic mode
- QC

### AI

- API
- fallback
- security

### HARDWARE

- Pa800 tests
- probe generation
- evidence promotion

### DATABASE

- integrity
- migration
- backup
- restore

### GUI

- all panels
- upload
- optimization
- reports
- hardware workflow

---

# PHASE 37 — FINAL QUALITY GATE

Release se može označiti:

## PRODUCTION READY

samo ako:

```text
All existing tests PASS
AND
All new tests PASS
AND
Database integrity PASS
AND
Determinism PASS
AND
MIDI QC PASS
AND
Evidence policy PASS
AND
No destructive migration
AND
Rollback PASS
AND
AI security PASS
```

Hardverski dio mora imati poseban status:

```text
CODE VERIFIED
HARDWARE VERIFIED
```

Nikada ne označavati Pa800 ponašanje kao potvrđeno ako fizički test nije izvršen.

---

# FINAL ARCHITECTURE

Konačni sistem treba evoluirati u:

```text
                    GM MIDI
                       │
                       ▼
              ┌─────────────────┐
              │ MIDI Intelligence│
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      FACTORY        GOLD        EVIDENCE
       DNA           DNA          REGISTRY
          │            │            │
          └────────────┼────────────┘
                       ▼
              ┌─────────────────┐
              │ Musical Analysis │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ Optimization     │
              │ Planner          │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ RX/DNC Engine    │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ Deterministic    │
              │ MIDI Optimizer   │
              └────────┬────────┘
                       ▼
                 MIDI OUTPUT
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        QC          A/B LAB      JOURNAL
          │
          ▼
      PA800 TEST
          │
          ▼
    HARDWARE EVIDENCE
          │
          ▼
    MODEL CALIBRATION
```

---

# CODEx COORDINATOR EXECUTION MODEL

Coordinator treba voditi **jedan upgrade cilj**, ne novi projekat.

Ako postoje 2–3 stvarno nezavisne velike vertikale, dozvoljeno je paralelno ih rasporediti:

### VERTICAL A
**Core + MIDI + Optimization Engine**

### VERTICAL B
**DNA + RX + Evidence Intelligence**

### VERTICAL C
**GUI + AI + Hardware/Test/Reporting**

Svaka vertikala mora imati:

```text
investigation
implementation
focused tests
documentation
```

Ne praviti task samo za sitne promjene.

Svi rade nad **istim postojećim checkoutom**.

Prije svake veće izmjene provjeriti active claims i izbjeći stvarni hunk collision.

---

# NAJVAŽNIJE

Ovaj roadmap nije zahtjev za novu aplikaciju.

To je:

> **FULL UPGRADE / EVOLUTION ROADMAP postojećeg GM → RX MIDI Optimizer projekta.**

Codex mora prvo razumjeti šta već postoji i tek onda nadograditi ono što nedostaje.

**Preserve → Audit → Harden → Extend → Integrate → Validate → Certify.**

Ne:

**Delete → Rewrite → Rebuild.**