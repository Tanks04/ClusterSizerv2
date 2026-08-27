# ClusterSizer

**A desktop tool for architects and IT administrators planning complex
clusters - one place to size the hardware, track the equipment behind
the numbers, and turn that into living documentation you keep updating
as the systems you manage grow and change.**

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

- **Deployment Model (On-Premise / Cloud), per site** — a hybrid setup
  (on-premise Primary with a cloud DR, i.e. DRaaS) is common enough in
  practice that this is set per site, not per project; set both the
  same for a simple all-on-prem or all-cloud project. Set on the
  Settings page, applied immediately. Currently affects Rack Sizing
  (Summary page and the Word report show "Cloud" instead of trying to
  sum rack units/power for a site where that's not a physical concept)
  - this is a first, deliberately narrow step, not full cloud-specific
  modeling throughout the app (see `docs/ROADMAP.md` v3.6.0 for what's
  in scope now vs deferred). See `examples/scenario_draas_example.clsz`
  for a worked hybrid example.
- **Servers** — site (Primary/DR), sockets/cores/threads/RAM/GHz, IP
  address, NIC inventory (incl. direct-attach SAS), and a Hyperthreading
  toggle that actually affects CPU oversubscription math (HT-adjusted
  per server, not a flat multiplier). Batch-add N identical servers at
  once. Inline editing directly in the table.
- **Storage** — Primary/DR, you enter both raw and usable capacity; the
  RAID/EC overhead percentage is derived from those two and shown
  read-only - it's informational only and doesn't feed the sizing
  calculations - plus a connectivity port inventory
  (1G/10G/25G/40G/100G/FC/SAS) with a live free/used column. 
  **HCI**
  (vSAN, Storage Spaces Direct, Nutanix AHV, etc.) storage - no separate
  physical array, the disks live in the servers - gets its own checkbox:
  link the contributing servers (each with a Local Disk (Raw) field) and
  Raw Capacity auto-sums from them instead of being typed in directly.
  Usable capacity still stays a manual entry, since the real raw-to-
  usable shrinkage depends on the storage policy (FTT/erasure coding) in
  a way this app doesn't try to model exactly.
- **VMs** — every VM can be flagged as *DR Protected* with its own DR
  footprint (vcpu/ram/disk) — since DR replicas are often not a 1:1 match
  with production, and the DR calculation respects that. Each VM also
  gets a Workload Tier (Tier-0/Mission-Critical, Standard Production,
  Development/Test, High-Density VDI — each with a commonly-cited safe
  oversubscription ratio, e.g. Tier-0 at 1:1 up to VDI at 12-24:1) for
  the 
  **Cluster Preparation** wizard — a proper Next/Next/Finish wizard
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
- **Network** — switches, firewalls, and load balancers (same entity,
  port inventory by speed: 1G/10G/25G/40G/100G/FC/SAS) and connections
  between any two of {Server, Switch, Storage} - including direct-attach
  storage links with no switch in between (e.g. FC/SAS HBAs wired
  straight to an array) - with a free/used overview by speed. Fully
  optional.
- **Backup** — a list of backup destinations (local repo, offsite,
  immutable/offline, etc. - most real setups have several), each with a
  type, backup software, dedup ratio, and Offsite/Immutable flags. Shows
  a live 3-2-1-1 compliance badge (3 copies of data, 2 different media
  types, 1 offsite, +1 immutable/offline) with an exact list of what's
  missing, not just pass/fail.
- **Pricing** — a single Price (EUR) on Servers/Storage/Network/Backup
  rolls straight into a total, broken down by category, no re-entry and
  no cost-vs-price/margin tracking - this app gives admins a running
  total, it isn't a sales quoting tool. Separately, 
  **Licenses,
  Warranties & Maintenance** tracks renewals - what it is, what it
  costs, how long it lasts, and its expiry date - flagged Expired
  (red) or Expiring Soon (orange, within 90 days) so a renewal doesn't
  get missed. Included as its own section in the Word report.
- **Summary** — the landing tab: a quick top-line card row (servers,
  cores, RAM, storage, VMs, DR readiness), then Primary vs DR side by
  side in detail: capacity, demand, oversubscription (OK/Warning/
  Critical), N+1 check, DR Readiness. "Preview DR Failover" swaps the DR
  card to show what DR would need if every DR-protected VM were
  activated there (e.g. a Veeam/backup-driven DR plan), not just what's
  actually running on DR today - same OK/Warning/Critical system, so a
  site that looks healthy can reveal it'd go CRITICAL under a real
  failover. "Show Rack Sizing" reveals total Rack Units and Power
  Consumption per site, aggregated from whatever's been entered on
  Servers/Storage/Switches.
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
- **Smart Import** — import VM inventory from VMware/Nutanix/Proxmox
  exports (CSV/XLSX/JSON) via column mapping, with reusable saved
  profiles. Each field can pull from a DIFFERENT sheet in a multi-sheet
  workbook if needed (joined by the Name field's own column) - e.g. pull
  vCPU/RAM from one RVTools sheet and a field only present on another.
  For RVTools specifically, **Tools → Import from RVTools...** is faster
  for the common case - no manual mapping, reads vHost/vInfo/vSwitch
  directly and imports Servers, VMs, and (optionally) Switches together
  in one step, correctly detecting Hyperthreading, OS (config-file or
  VMware-Tools-reported, your choice), and Cluster name. Multi-site
  environments living in one vCenter (two Datacenter objects) can map
  each Datacenter to Primary or DR individually instead of one target
  site for the whole file.
- **Tools → RAID Calculator...** — size a RAID array (0/1/5/6/10/50/60,
  hot spares) from disk count/size/type, then optionally apply the
  result straight to a Server or Storage entry already in the project.
  Warns on RAID 0 (no redundancy) and on parity levels (5/6/50/60)
  combined with spinning disks (write penalty) - deliberately doesn't
  try to guess from VM Workload Tiers elsewhere in the project, since a
  Storage entity isn't tied to specific VMs anywhere in the model.
- Undo/Redo (Ctrl+Z / Ctrl+Y) for Add/Delete/Duplicate/Import/Clear All.
- Multi-select everywhere (Ctrl/Shift-click, Delete, right-click → Edit/
  Copy/Delete), strictly-typed CSV import (each tab only accepts its own
  format), a "Clear All" button per tab, project save/load (`.clsz`, JSON).
- **File → Recent Files** — the last 5 opened/saved projects, most-recent
  first, so you don't have to browse to the same file over and over.

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

For exactly how every number on screen is calculated, with small worked
examples, see
[`docs/HOW_THE_MATH_WORKS.md`](docs/HOW_THE_MATH_WORKS.md).

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
first idea to the last bugfix. 

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

The full story of that collaboration (and why it's stated openly) is in
[`docs/ABOUT.md`](docs/ABOUT.md).

## License

MIT — see [`LICENSE`](LICENSE)
