# ClusterSizer 2.4.2

**A desktop tool for sysadmins: sizing HW for a cluster, tracking load, and
DR sizing — without manually adding it all up in Excel for the third time.**

## About

ClusterSizer helps with planning infrastructure for a virtualization
cluster. Enter your servers (count, sockets, cores, RAM), storage (Primary
and DR), and VMs — the tool immediately calculates total resources,
oversubscription (CPU/RAM/storage), whether the cluster survives losing
one host (N+1), and whether the DR site actually has enough capacity for
failover.

It's built for that moment when you're putting together a quote or plan
for a new cluster and need to answer questions like: "how much RAM do I
actually need", "will these 5 servers hold up if one goes down", "does DR
have enough capacity to take over production, and specifically for the
VMs that ACTUALLY replicate, not all of them". It also covers the
network side — which switch has free 25G ports, and how each server is
physically connected — since that's usually the first thing forgotten and
the last thing discovered.

It's not a monitoring tool (it doesn't look at what the cluster is
actually doing live), but a tool for **planning before the HW is ordered
or the tender is written**.


## Features

- **Servers** — site (Primary/DR), sockets/cores/threads/RAM/GHz, NIC
  inventory (incl. direct-attach SAS), and a Hyperthreading toggle that
  actually affects CPU oversubscription math (HT-adjusted per server, not
  a flat multiplier). Batch-add N identical servers at once. Inline
  editing directly in the table.
- **Storage** — Primary/DR, you enter both raw and usable capacity and
  the RAID/EC overhead percentage is shown for information (not derived
  automatically), plus a connectivity port inventory
  (1G/10G/25G/40G/100G/FC/SAS) with a live free/used column.
- **VMs** — every VM can be flagged as *DR Protected* with its own DR
  footprint (vcpu/ram/disk) — since DR replicas are often not a 1:1 match
  with production, and the DR calculation respects that. Each VM also
  gets a Workload Profile (CPU Intensive/Balanced/Memory Intensive/
  Storage Intensive/Light) for the **Cluster Preparation** wizard — the
  reverse question from the rest of the app: not "do these VMs fit the
  servers I have" but "how many servers should I buy for these VMs".
  Accounts for growth, HA (N+1/N+2), memory reserve, and reuses each
  VM's DR protection for a separate DR host AND storage estimate. Turns
  straight
  into real Server AND Storage rows via one button, sized for the same
  demand (with a RAID/EC overhead assumption you can adjust).
- **Network** — switches (port inventory by speed: 1G/10G/25G/40G/100G/
  FC/SAS) and connections between any two of {Server, Switch, Storage} -
  including direct-attach storage links with no switch in between (e.g.
  FC/SAS HBAs wired straight to an array) - with a free/used overview by
  speed. Fully optional.
- **Summary** — the landing tab: a quick top-line card row (servers,
  cores, RAM, storage, VMs, DR readiness), then Primary vs DR side by
  side in detail: capacity, demand, oversubscription (OK/Warning/
  Critical), N+1 check, DR Readiness.
- **Settings** — recommended oversubscription presets by hypervisor
  vendor (VMware, Hyper-V, Proxmox/KVM, Citrix Hypervisor), or set your
  own thresholds manually.
- **Reports** — readable text report, a color-coded PDF export (built
  with Qt's own printing support, no extra libraries), and CSV export of
  all data.
- **Compare** — load two saved scenarios side by side (or snapshot the
  current project into either slot) under the same thresholds - a
  highlighted table plus a quick at-a-glance delta card row. "Save
  Scenario Copy As..." branches off a what-if without touching your
  active project.
- **Smart Import** — import VM inventory from VMware/Nutanix/Proxmox/
  RVTools exports (CSV/XLSX/JSON) via column mapping, with reusable
  saved profiles.
- Undo/Redo (Ctrl+Z / Ctrl+Y) for Add/Delete/Duplicate/Import/Clear All.
- Multi-select everywhere (Ctrl/Shift-click, Delete, right-click → Edit/
  Copy/Delete), strictly-typed CSV import (each tab only accepts its own
  format), a "Clear All" button per tab, project save/load (`.clsz`, JSON).

## Running it

```bash
pip install -r requirements.txt
python main.py
```

Example CSVs for every type (servers/storage/vms/switches/connections)
are in `examples/`.

## Status and changelog

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Thanks

Ovaj alat je nastao u suradnji s Claude-om (Anthropic) — od prve ideje do
zadnjeg bugfixa.

Iako su i kod i app,pa i ideja ponuđeni besplatno, ako smatrate da 
Vam se sviđa i da vam skraćuje vrijeme rada, možete uplatiti koji EUR
za pivu i whisk(e)y autoru programa <3 koji će onda imati više volje 
provesti u djelo još koju ideju ,)
Revolut: revolut.me/@ivan50ba6

Although the code, app, and idea are offered for free, if you think you 
like it and it saves you time, you can donate a few EUR for beer and whisk(e)y 
to the author of the program <3 who will be more willing to put 
new ideas into practice ,)
Revolut: revolut.me/@ivan50ba6

## License

MIT — see [`LICENSE`](LICENSE).
