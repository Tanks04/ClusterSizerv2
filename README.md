# ClusterSizer

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

<<<<<<< HEAD
## Features
=======

ClusterSizer

A desktop tool for system administrators: size virtualization clusters, analyze resource utilization 
and plan disaster recovery (DR) capacity — without manually adding everything up in Excel for the third time.

About the Application

ClusterSizer helps you plan infrastructure for virtualization clusters. Enter your servers (quantity, CPU sockets, cores, RAM), storage (Primary and DR), and virtual machines, and the tool instantly calculates total available resources, CPU/RAM/storage oversubscription, whether the cluster can withstand the loss of a host (N+1), and whether the DR site actually has enough capacity to handle a failover.

It is designed for the moment when you're preparing a proposal or planning a new cluster and need quick answers to questions like: "How much RAM do I really need?", "Can these five servers handle the workload if one fails?", or "Does the DR site have enough capacity to take over production—and only for the VMs that are actually replicated, not every VM?" It also covers the networking side by tracking which switches still have available 25GbE ports and how each server is physically connected, because those details are usually the first to be overlooked and the last to be discovered.

ClusterSizer is not a monitoring tool—it doesn't monitor the live state of a running cluster. Instead, it's a planning and sizing tool used before hardware is ordered or procurement begi

## Značajke
>>>>>>> bfffacda52a6004c73fcdae3c04e87566a75ccc9

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

This tool was built in collaboration with Claude (Anthropic) — from the
first idea to the last bugfix. What would have taken me weeks to put
together in my spare time came together here in a handful of sessions:
I'd describe the problem the way a sysadmin sees it, and the code,
architecture, and fixes mostly came from the other side — with plenty of
my own testing, pushback, and "that's not right, try again." Including
hunting down one particularly nasty Windows crash that didn't want to be
found.

The full story of that collaboration (and why it's stated openly) is in
[`docs/ABOUT.md`](docs/ABOUT.md).

Thanks, Claude. 🥰

## License

MIT — see [`LICENSE`](LICENSE). Before publishing on GitHub, replace
`[YOUR NAME / ORGANIZATION]` in the LICENSE file with your own name.
