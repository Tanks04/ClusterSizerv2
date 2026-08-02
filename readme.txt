# ClusterSizer v2

Desktop GUI alat (PySide6/Qt) za sysadmine: sastavljanje HW-a za cluster
resurse, pregled opterecenja (oversubscription), DR sizing i mrezna
dokumentacija (switch portovi, server<->switch veze).

O nastanku ovog projekta (ljudsko-AI suradnja): vidi docs/ABOUT.md

## Pokretanje

    pip install -r requirements.txt
    python main.py

## Sto radi

- Servers: unos servera (site Primary/DR, sockets, cores, threads, RAM,
  GHz, NIC inventar). Batch dodavanje - jedan dijalog moze napraviti N
  identicnih servera odjednom (cesta situacija u clusteru). Ukupni
  CPU/RAM/NIC racuna se odmah. Vrijednosti se mogu mijenjati direktno u
  tablici (dvoklik na celiju).
- Storage: storage sustavi po lokaciji (Primary/DR), raw/usable kapacitet,
  RAID/EC overhead racuna se automatski.
- VMs: virtualke po lokaciji, unos rucno ili CSV import. Svaki VM moze biti
  oznacen kao "DR Protected" sa SVOJIM DR footprintom (vcpu/ram/disk) - jer
  DR replike cesto nisu 1:1 s produkcijom. DR izracun koristi bas taj
  footprint, ne prepostavlja da se sve replicira isto.
- Network: switchevi (port inventar po brzini: 1G/10G/25G/40G/100G/FC) i
  veze server<->switch. Servers imaju svoj NIC inventar, pa Network tab
  pokazuje slobodno/zauzeto po brzini i upozorava (⚠) ako je neka brzina
  precrpljena. Potpuno opcionalno - prazan Network tab ne utjece ni na sto
  drugo u alatu.
- Summary: Primary vs DR jedno pored drugog - fizicki kapacitet, potraznja,
  oversubscription (obojeno OK/Warning/Critical), N+1 provjera, i DR
  Readiness (racuna failover potraznju iz DR-protected VM-ova, ne iz svih
  VM-ova na Primary lokaciji).
- Reports: citljivi tekstualni izvjestaj + export, export svih podataka
  kao CSV bundle.
- Settings: pragovi upozorenja (CPU/RAM/Storage oversubscription).
- Multi-select posvuda: Ctrl/Shift-klik za selekciju vise redaka, Delete
  tipka brise sve selektirano, desni klik nudi Edit/Copy/Delete. Copy
  kopira sve postavke odabranog retka (servera, VM-a, switcha, veze).
- Svaki tab ima "Clear All" gumb - ako se nesto krivo uveze (npr. CSV
  pogresnog tipa), lako se pocisti bez da se dira ostatak projekta.
  File > New cisti citav projekt.
- File menu: New / Open / Save / Save As (.clsz = JSON), Import/Export CSV.

## Vazno: CSV import je strogo tipiziran

Svaki tab (Servers/Storage/VMs/Switches/Connections) ima SVOJ CSV format.
Import provjerava da header sadrzi tocno ocekivane kolone za taj tip -
ako pokusas uvesti npr. VMs CSV na Servers tabu, dobijes jasnu gresku
umjesto da se tiho naprave krivi redovi. Vidi examples/ za tocan format
svakog tipa.

## CSV format

Vidi examples/*.csv - isti header koriste Import i Export gumbi na svakoj
stranici. connections_example.csv referencira servere/switcheve PO IMENU
(mora se poklapati s imenima iz servers_example.csv / switches_example.csv).

## Status

Funkcionalan v2. Vidi docs/ROADMAP.md za povijest i ono sto namjerno NIJE
u v2 (npr. per-port slot booking na mrezi - trenutno se prati samo
agregatni broj portova po brzini, ne pojedinacni port ID).
