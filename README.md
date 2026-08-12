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
  inventory. Batch-add N identical servers at once. Inline editing
  directly in the table.
- **Storage** — Primary/DR, raw/usable capacity, RAID/EC overhead is
  calculated automatically.
- **VMs** — every VM can be flagged as *DR Protected* with its own DR
  footprint (vcpu/ram/disk) — since DR replicas are often not a 1:1 match
  with production, and the DR calculation respects that.
- **Network** — switches (port inventory by speed: 1G/10G/25G/40G/100G/FC)
  and server↔switch connections, with a free/used overview by speed.
  Fully optional.
- **Summary** — Primary vs DR side by side: capacity, demand,
  oversubscription (OK/Warning/Critical), N+1 check, DR Readiness.
- **Settings** — recommended oversubscription presets by hypervisor
  vendor (VMware, Hyper-V, Proxmox/KVM, Citrix Hypervisor), or set your
  own thresholds manually.
- **Reports** — readable text report + CSV export of all data.
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
