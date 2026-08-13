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
  gets a Workload Tier (Tier-0/Mission-Critical, Standard Production,
  Development/Test, High-Density VDI — each with a commonly-cited safe
  oversubscription ratio, e.g. Tier-0 at 1:1 up to VDI at 12-24:1) for
  the **Cluster Preparation** wizard — a proper Next/Next/Finish wizard
  (Hypervisor → Workload → Policy → Result), the reverse
  question from the rest of the app: not "do these VMs fit the servers I
  have" but "how many servers should I buy for these VMs". Reuses the
  same hypervisor presets as Settings for a sanity-check ratio, accounts
  for growth (applied equally to vCPU/RAM/storage), HA (N+1/N+2), memory
  reserve, and reuses each VM's DR protection for a separate DR host AND
  storage estimate. The host spec is OPTIMIZED for you at the end (fewest
  hosts, landing near the target ratio for your hypervisor) - editable
  afterward, "Reset to Optimized Suggestion" if you want it back. Turns
  straight into real Server AND Storage rows via one button, sized for
  the same demand (with a RAID/EC overhead assumption you can adjust).
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
- **Reports** — readable text report, a structured Word (.docx) report
  (Servers → Storage → Network → Cluster config → VMs, each with a
  summary plus the full per-device listing - editable afterward, add a
  letterhead or trim what a client doesn't need to see), and CSV export
  of all data.
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

## Scope & Assumptions

ClusterSizer is intentionally simple: no NUMA topology, no per-VM CPU
reservations, no storage RAID/erasure-coding overhead beyond the flat
percentage you enter on the Storage tab. Every ratio, tier, and
percentage in this tool (oversubscription ratios, Workload Tiers,
Memory Reserve, Storage Overhead) is a sizing ASSUMPTION meant as a
sensible starting point, not a measurement of your actual environment -
adjust them to match what you know about your own workload.

One specific gap worth calling out: Cluster Preparation reserves RAM for
the hypervisor itself (Memory Reserve), but does NOT reserve CPU the
same way - real hypervisors do consume some CPU (commonly cited around
8-10% overhead for VMware ESXi; Hyper-V's parent partition runs a full
Windows Server, so it tends to need more, though there's no single
widely-quoted figure the way there is for VMware). Leave yourself a
small margin if you're sizing close to the edge.

## Running it

```bash
pip install -r requirements.txt
python main.py
```

Example CSVs for every type (servers/storage/vms/switches/connections)
are in `examples/`. `examples/scenario_full_example.clsz` is a complete
ready-to-load project (Primary+DR, mixed Hyperthreading, storage, and
network already wired up) - File > Open it directly instead of importing
each CSV separately.

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
