# ClusterSizer

**Desktop alat za sysadmine: sastavljanje HW-a za cluster, pregled
opterećenja i DR sizing — bez ručnog zbrajanja u Excelu po treći put.**

## O aplikaciji

ClusterSizer pomaže kod planiranja infrastrukture za virtualizacijski
cluster. Upišeš servere (broj, socketi, jezgre, RAM), storage (Primary i
DR), i virtualke — alat odmah izračuna ukupne resurse, oversubscription
(CPU/RAM/storage), izdrži li cluster ispad jednog hosta (N+1), i ima li DR
lokacija stvarno dovoljno kapaciteta za failover.

Zamišljen je za onaj trenutak kad sastavljaš ponudu ili plan za novi
cluster i moraš odgovoriti na pitanja tipa: "koliko RAM-a mi realno treba",
"hoće li ovih 5 servera izdržati ako jedan padne", "ima li DR dovoljno
snage da preuzme produkciju, i to za VM-ove koji se STVARNO repliciraju,
ne za sve". Uz to vodi i mrežnu stranu — koji switch ima slobodnih 25G
portova, i kako je koji server fizički povezan — jer se to inače prvo
zaboravi, a zadnje otkrije.

Nije monitoring alat (ne gleda što cluster stvarno radi live), nego alat
za **planiranje prije nego što se HW naruči ili raspiše**.

## Značajke

- **Servers** — site (Primary/DR), socketi/jezgre/threadovi/RAM/GHz, NIC
  inventar. Batch dodavanje N identičnih servera odjednom. Inline editing
  direktno u tablici.
- **Storage** — Primary/DR, raw/usable kapacitet, RAID/EC overhead se
  računa automatski.
- **VMs** — svaki VM može biti označen kao *DR Protected* sa svojim
  vlastitim DR footprintom (vcpu/ram/disk) — jer DR replike često nisu 1:1
  s produkcijom, i DR izračun to poštuje.
- **Network** — switchevi (port inventar po brzini: 1G/10G/25G/40G/100G/FC)
  i veze server↔switch, sa slobodno/zauzeto pregledom po brzini.
  Potpuno opcionalno.
- **Summary** — Primary vs DR jedno pored drugog: kapacitet, potražnja,
  oversubscription (OK/Warning/Critical), N+1 provjera, DR Readiness.
- **Reports** — čitljivi tekstualni izvještaj + CSV export svih podataka.
- Multi-select posvuda (Ctrl/Shift-klik, Delete, desni klik → Edit/Copy/
  Delete), strogo tipizirani CSV import (svaki tab prima samo svoj format),
  "Clear All" po tabu, spremanje/učitavanje projekta (`.clsz`, JSON).

## Pokretanje

```bash
pip install -r requirements.txt
python main.py
```

Primjeri CSV-a za sve tipove (servers/storage/vms/switches/connections) su
u `examples/`.

## Status i povijest promjena

Vidi [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Zahvala

Ovaj alat je nastao u suradnji s Claude-om (Anthropic) — od prve ideje do
zadnjeg bugfixa.

Iako je i kod i app besplatan, a kao i ideja ponuđen besplatno, ako smatrate da 
Vam se sviđa, možete uplatiti koji EUR za pivu i whisky autoru programa <3
