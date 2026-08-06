# ROADMAP

## v2.0.5 (bugfix: powered-off VMs)

- CPU and RAM oversubscription (and N+1, and DR failover CPU/RAM demand)
  were counting powered-off VMs as if they were consuming physical
  CPU/RAM - they don't (a powered-off VM releases both back to the
  hypervisor). Fixed: vm_vcpu_demand()/vm_ram_demand_gb() now only sum
  VMs where powered_on=True. Disk demand is deliberately NOT filtered -
  a powered-off VM's disk files still occupy space on the datastore, so
  storage utilization and DR disk failover demand keep counting every VM
  regardless of power state. UI labels updated (Summary, VMs page cards,
  Reports) to make the powered-on-only scope explicit.

## v2.0.4 (English translation + oversubscription presets)

- Entire app translated from Croatian to English - UI labels, dialogs,
  messages, tooltips, code comments/docstrings, README/ROADMAP/ABOUT, and
  the example CSVs.
- Settings page: added "Recommended Presets" by hypervisor vendor (VMware,
  Hyper-V, Proxmox/KVM, Citrix Hypervisor) with commonly-cited vCPU:pCPU
  starting ratios - "Use This Preset" fills in the threshold fields, still
  requires "Apply" to actually save. See PRESETS in
  `src/calculations/thresholds.py`.

## v2.0.3 (the real fix for the access violation)

- crash.log showed "Windows fatal exception: access violation" inside
  app.exec() - a real native crash, not a Python exception. Two
  complementary fixes:
  1. QHeaderView.ResizeMode.ResizeToContents (persistent auto-resize mode)
     replaced with Interactive + a one-shot deferred resizeColumnsToContents()
     (MultiSelectTableView.auto_size_columns(), called from refresh()).
     Persistent ResizeToContents forces Qt to recompute layout on every
     model reset, especially risky on the FIRST real display of a tab that
     was constructed but stayed hidden until then (Qt defers layout for
     hidden widgets) - a known-unstable combination on Windows.
  2. ProjectService.changed split into servers_changed / storages_changed
     / vms_changed / network_changed - each CRUD table now only resets
     when its own data actually changed, instead of all 5 tables resetting
     on every change anywhere. Fewer unnecessary model resets = fewer
     chances to hit a timing-sensitive Qt bug. Dashboard/Summary/Reports/
     window title still listen to the general `changed` (they need to know
     about any change, but don't run beginResetModel on large tables).

## v2.0.2 (diagnostics)

- The crash-on-tab-click with no editing at all was still reported after
  the v2.0.1 fix (which remains correct, but obviously wasn't the only
  cause). Without a working PySide6 environment to reproduce it, two
  diagnostic layers were added to main.py: faulthandler (catches real
  native segfaults and writes the C+Python stack to crash.log) and a
  global sys.excepthook (catches uncaught Python exceptions inside Qt
  callbacks, also written to crash.log). The next crash should leave a
  trace in crash.log next to the app.

## v2.0.1 (bugfix)

- Fixed an intermittent crash (no message) when clicking a tab while an
  inline cell editor was open on the Servers/Storage/VMs tab. Cause: a
  reentrant model reset (setData -> touch -> changed -> refresh ->
  beginResetModel) while Qt was still closing the editor. touch() now
  defers the notify via QTimer.singleShot(0, ...).

## v2 (done)

- Multi-select everywhere: Ctrl/Shift-click, Delete key on the selection,
  right-click (Edit/Copy/Delete) - shared MultiSelectTableView component.
- Batch server add (N identical at once, auto-numbered names).
- VM DR-protection: dr_protected flag + separate DR footprint (dr_vcpu,
  dr_ram_gb, dr_disk_gb) - DR readiness calculates failover demand from
  DR-protected VMs at their own DR footprint, not from all Primary VMs.
- Network tab: NetworkSwitch (port inventory by speed: 1G/10G/25G/40G/
  100G/FC) + Server NIC inventory + NetworkConnection (server<->switch).
  Free/used by speed, with an overcommit warning. Fully optional - an
  empty Network tab doesn't block anything else.
- "Clear All" per tab (not just File > New for the whole project) - for
  quickly cleaning up a wrongly-imported file.
- Strictly-typed CSV import - each tab accepts ONLY its own format, the
  header is validated before parsing (prevents e.g. a VM CSV on the
  Servers tab).
- docs/ABOUT.md - a transparent note on the human-AI collaboration.

## v1 (done, before v2)

- Server / Storage / VM models, Primary/DR site.
- Cluster totals (CPU, threads, RAM), oversubscription calculations with
  adjustable thresholds (Settings), N+1 check per site.
- CRUD + inline editing, CSV import/export, project save/load (.clsz,
  JSON), text report.

## Deliberately out of v2 scope

- Per-port slot booking on the network side (e.g. "port #3 specifically
  used") - currently only the aggregate port count per speed per device
  is tracked. Enough for an overcommit warning, not for full cable
  management.
- Live monitoring / integration with vCenter, Proxmox, etc. - ClusterSizer
  is a planning tool, not a live-infrastructure monitoring tool.
- Pricing/licensing (e.g. vSphere core licensing calculations).
- Multi-cluster / multi-DR (the model is currently Primary + one DR site).
- Undo/redo in the tables.

## Ideas for v3 (not confirmed, just notes)

- Per-port slot booking (if the aggregate counter turns out not to be enough).
- A vSphere/Proxmox core-licensing calculator as an extra page.
- More than one DR site.
- Undo/redo.
