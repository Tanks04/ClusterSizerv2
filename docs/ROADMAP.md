# ROADMAP

## v2.0.3 (pravi fix za access violation)

- crash.log je pokazao "Windows fatal exception: access violation" unutar
  app.exec() - pravi native crash, ne Python iznimka. Dva komplementarna
  popravka:
  1. QHeaderView.ResizeMode.ResizeToContents (trajni auto-resize mod)
     zamijenjen s Interactive + jednokratni odgođeni resizeColumnsToContents()
     (MultiSelectTableView.auto_size_columns(), pozvan iz refresh()).
     Trajni ResizeToContents prisiljava Qt da preračuna layout pri svakom
     model resetu, pogotovo rizično pri PRVOM stvarnom prikazu taba koji je
     do tad bio konstruiran ali skriven (Qt odgađa layout skrivenih
     widgeta) - poznato nestabilna kombinacija na Windowsima.
  2. ProjectService.changed rastavljen na servers_changed / storages_changed
     / vms_changed / network_changed - svaka CRUD tablica sad resetira SAMO
     kad se njeni podaci stvarno promijene, umjesto da se svih 5 tablica
     resetira na SVAKU promjenu bilo gdje. Manje nepotrebnih model-reseta =
     manje prilika da se pogodi timing-osjetljiv Qt bug. Dashboard/Summary/
     Reports/naslov prozora i dalje slušaju opći `changed` (trebaju znati o
     bilo kojoj promjeni, ali ne rade beginResetModel na velikim tablicama).

## v2.0.2 (dijagnostika)

- Crash na klik-na-tab bez ikakvog editiranja i dalje prijavljen nakon
  v2.0.1 fixa (koji ostaje ispravan, ali očito nije jedini uzrok). Bez
  radnog PySide6 okruženja za reprodukciju, dodana su dva sloja
  dijagnostike u main.py: faulthandler (hvata prave native segfault-ove
  i piše C+Python stack u crash.log) i globalni sys.excepthook (hvata
  neuhvaćene Python iznimke unutar Qt callbackova, isto u crash.log).
  Sljedeći crash bi trebao ostaviti trag u crash.log pored aplikacije.

## v2.0.1 (bugfix)

- Ispravljen povremeni crash (bez poruke) kod klika na tab dok je bio
  otvoren inline editor ćelije na Servers/Storage/VMs tabu. Uzrok:
  reentrantni model reset (setData -> touch -> changed -> refresh ->
  beginResetModel) dok je Qt još zatvarao editor. touch() sad odgađa
  notify preko QTimer.singleShot(0, ...).

## v2 (gotovo)

- Multi-select posvuda: Ctrl/Shift-klik, Delete tipka na selekciji, desni
  klik (Edit/Copy/Delete) - zajednicka MultiSelectTableView komponenta.
- Batch dodavanje servera (N identicnih odjednom, auto-numerirana imena).
- VM DR-protection: dr_protected flag + zaseban DR footprint (dr_vcpu,
  dr_ram_gb, dr_disk_gb) - DR readiness racuna failover potraznju iz
  DR-protected VM-ova po njihovom DR footprintu, ne iz svih Primary VM-ova.
- Network tab: NetworkSwitch (port inventar po brzini: 1G/10G/25G/40G/
  100G/FC) + Server NIC inventar + NetworkConnection (server<->switch).
  Slobodno/zauzeto po brzini, s upozorenjem na overcommit. Potpuno
  opcionalno - prazan Network tab ne blokira nista drugo.
- "Clear All" po tabu (ne samo File > New za cijeli projekt) - za brzo
  ciscenje krivo uvezenih podataka.
- Strogo tipiziran CSV import - svaki tab prihvaca SAMO svoj format,
  header se validira prije parsiranja (sprjecava npr. VM CSV na Servers
  tabu).
- docs/ABOUT.md - transparentna napomena o ljudsko-AI suradnji.

## v1 (gotovo, prije v2)

- Server / Storage / VM modeli, Primary/DR site.
- Cluster totals (CPU, threads, RAM), oversubscription izracuni s
  podesivim pragovima (Settings), N+1 provjera po lokaciji.
- CRUD + inline editing, CSV import/export, spremanje/ucitavanje projekta
  (.clsz, JSON), tekstualni izvjestaj.

## Namjerno izvan v2 scope-a

- Per-port slot booking na mrezi (npr. "port #3 specificno zauzet") -
  trenutno se prati samo agregatni broj portova po brzini po uredjaju.
  Dovoljno za overcommit upozorenje, ne i za pun cable-management.
- Live monitoring / integracija s vCenter-om, Proxmoxom i sl. - ClusterSizer
  je alat za planiranje, ne za monitoring live infrastrukture.
- Cijena/licenciranje (npr. vSphere core licensing kalkulacije).
- Multi-cluster / multi-DR (trenutno je model Primary + jedan DR site).
- Undo/redo u tablicama.

## Ideje za v3 (nisu potvrdjene, samo zabiljeska)

- Per-port slot booking (ako se pokaze da agregatni brojac nije dovoljan).
- vSphere/Proxmox core-licensing kalkulator kao dodatna stranica.
- Vise od jedne DR lokacije.
- Undo/redo.
