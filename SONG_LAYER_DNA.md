# Song Layer DNA — Delay, Terca i Gold Ornament

## Potvrđeni režim

- izlaz je cijeli Song MIDI;
- Delay je poseban MIDI track;
- Terca/harmony se obrađuje samo ako već postoji kao poseban MIDI track;
- postojeći Delay ili Terca track se prvo detektuje i optimizuje;
- novi track se može kreirati samo za Delay kada echo layer ne postoji;
- trileri i ukrasi se uče isključivo iz Gold DNA fajlova.

## Delay DNA

Detekcija traži isti pitch obrazac na drugom track/channel paru sa stabilnim vremenskim offsetom i nižim velocityjem. Model čuva:

- source i echo track/channel;
- offset u četvrtinkama;
- velocity attenuation;
- gate odnos;
- coverage i broj podudarnih nota;
- source/echo program;
- provenance iz konkretnog song fajla.

Ako echo postoji, optimizer mijenja samo njegov velocity i gate prema modelu. Ne kreira drugi echo.

Postojeći echo i terca se identifikuju na originalnom MIDI-ju prije Gold micro-timing transformacije. Završna optimizacija koristi tolerantan note matcher, pa mali nezavisni timing pomaci source i layer tracka ne mogu izazvati lažno kreiranje duplikata.

Ako echo ne postoji:

1. bira glavni monofoni lead/melodic source;
2. traži exact-program phrase model sa najmanje dva izvorna fajla, pet fraza i 75% `FULL` pokrivenosti;
3. segmentira source na `FULL`, `SKIP` ili `PARTIAL` fraze;
4. generiše samo `FULL`; `SKIP` ostavlja praznim, a `PARTIAL` je zaključan dok nema dovoljno dokaza;
5. zahtijeva potpuno slobodan ne-drum MIDI kanal;
6. ako kanal ili evidence nedostaje, vraća `skipped` bez zamjene tracka i bez fallbacka na source kanal;
7. kopira source bank/program inicijalizaciju i dodaje note sa dokazanim offsetom, attenuationom i gateom;
8. sprječava sudar iste pitch note i track dobija naziv `DNA DELAY`.

Model sadrži 220 evidence fraza: 218 `FULL` i dvije `SKIP`. Deset od jedanaest potvrđenih parova koristi offset 0,75 četvrtinke. Globalni model je analitički i ne smije sam generisati Delay.

## Thirds / Terca DNA

Postojeća terca se detektuje kao paralelni track sa istim onsetima i dominantnim razmakom male/velike terce.

Ako postoji, pitch, onset i trajanje se ne mijenjaju. Sistem optimizuje samo velocity i već postojeće CC7/CC11 događaje.

Ako ne postoji:

1. ne bira se source track za generisanje;
2. ne detektuje se tonalitet radi dodavanja nota;
3. ne pravi se `DNA THIRD` track;
4. rezultat ostaje `not_detected`;
5. čak se i stari API zahtjev `harmony_create=true` ignoriše.

Delay može koristiti detektovani source lead. Terca nema creation source niti target-slot logiku.

## Izbor tracka i kanala

Za novu Delay generaciju prihvatljiv je samo potpuno slobodan ne-drum kanal. Prazan track može biti kontejner, ali ne daje pravo na ponovnu upotrebu zauzetog source kanala. Automatska zamjena manje važnog tracka i fallback na source kanal su uklonjeni iz sigurnog režima.

Nikada se automatski ne zamjenjuju:

- drum kanal;
- bass jezgro;
- tempo/meta track;
- jedini lead track;
- jedini chord/accompaniment nosilac.

Zamjena manje važnog tracka je po defaultu isključena u GUI-ju.

## Gold-only Ornament / Trill DNA

Ornament baza se gradi direktno iz `Gold DNA.zip`. Factory Styles i šest novih song fajlova nisu training izvor.

Uči po instrument family i tempu:

- grace note učestalost;
- alternating trill sekvence;
- mordent/neighbor obrasce;
- turn obrasce;
- tremolo ponovljene note;
- pitch-bend učestalost;
- broj ukrasa na 1.000 nota.

Pošto korisnik nije tražio agresivno dodavanje trilera, default režim je:

- detektuj postojeće ukrase;
- koristi Gold model za procjenu;
- ne dodaj nove pitch note;
- prijavi broj postojećih trill sekvenci i `source=gold_only`.

Automatsko generisanje novih trilera može se dodati kao zaseban kasniji režim, poslije slušnog testa.

## GUI kontrole

- Delay DNA on/off;
- kreiranje missing echo tracka;
- Delay strength;
- Terca DNA on/off;
- blokada kreiranja missing terca tracka;
- Terca strength;
- Gold-only Ornament optimizacija;
- dozvola za zamjenu manje važnog tracka.

## Audit

Optimizer izvještaj za svaki song navodi:

- da li je Delay pronađen ili kreiran i da li je postojeća terca detektovana;
- source i target track/channel;
- način izbora slota;
- offset, velocity i gate model;
- broj promijenjenih ili kreiranih Delay nota;
- broj velocity i CC7/CC11 promjena postojeće terce;
- broj postojećih Gold-evaluated trill sekvenci;
- da li je neki track zamijenjen.