# Pa800 RX Noise Hardware Probe sistem

## Izvorna politika

RX Noise probe engine ne smije koristiti šest Delay/Terca referentnih pjesama. API provjerava SHA-256 sadržaja, pa zabrana vrijedi i ako se jedna od tih pjesama preimenuje.

Probe se stvaraju samo kada korisnik kroz GUI uploaduje drugi MIDI fajl koji je eksplicitno namijenjen hardware testu.

## Šta će probe testirati

Za svaki od osam trenutno evidentiranih kandidata kreira se poseban MIDI:

- Clean Guitar RX1–RX6;
- Finger Bass RX;
- Picked Bass RX.

Svaki probe testira MIDI note 96–127 na velocity 1, 42, 84 i 127. Probe počinju nakon završetka dostavljenog MIDI-ja, na posebnom tracku.

## Trenutni status

- aktivni probe fajlovi: 0;
- hardware rezultati: 0;
- evidence status: `UNVERIFIED`;
- šest Delay/Terca pjesama: strogo zabranjen izvor.

## Potvrđivanje

Nakon Pa800 reprodukcije GUI prima:

- `Probe file ID`;
- `confirmed`, `partial` ili `rejected`;
- potvrđene `nota:velocity` događaje, npr. `96:42`;
- odbačene događaje;
- Pa800 OS/resources i opis zvuka.

Rezultat ne ulazi u produkcijski RX engine prije fizičke potvrde.