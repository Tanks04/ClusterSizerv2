# ROADMAP

## v2.1.2 (better openpyxl-missing diagnostics)

- "Reading .xlsx requires openpyxl" kept showing even after pip install -
  almost certainly a different Python interpreter/venv running the app
  than the one openpyxl was installed into (very common in IDEs like
  Visual Studio, which often have their own selected interpreter separate
  from a plain terminal's). The error message now shows sys.executable
  (exactly which interpreter is running the app) and the precise
  underlying import exception, plus the exact pip command to fix it for
  that specific interpreter. The import guard was also broadened from
  `except ImportError` to `except Exception`, in case a partially broken
  install raises something else.
- Also noted: an "Unhandled Python exception" log entry with a truncated
  traceback (just the `def` line, no call site) is a normal, non-fatal
  exception caught by our sys.excepthook inside a Qt-connected slot - Qt
  reports and continues, it's not the access-violation crash. Left
  uninvestigated per explicit request until a fuller traceback is available.

## v2.1.1 (structural fix attempt: lazy tab construction)

- The Windows access violation kept happening after the v2.0.3/v2.0.6
  fixes, now reproducible on the FIRST click on ANY tab (Servers or VMs,
  whichever was clicked first) right after a fresh launch - before any
  user interaction. This points at the pattern itself, not a specific
  widget: MainWindow used to construct all 8 pages up front, most of them
  staying hidden until clicked. Every crash trigger found so far (first
  QHeaderView.ResizeToContents, likely QSortFilterProxyModel's deferred
  sort/layout since v2.0.6) has been some Qt computation deferred while a
  widget is hidden, then catching up unsafely on first real show.
  Structural fix: LazyTabContainer - each page is now only actually built
  the moment its tab is first selected, never "constructed now, shown
  later." This removes the whole pattern instead of chasing the next
  specific trigger. Still unconfirmed on the reporter's machine as of
  this entry - see the note requesting PySide6 version / Python
  architecture / non-VS-launch test if it recurs.

## v2.1.0 (Smart Import wizard - any VM export, not just our CSV format)

- New "🧙 Smart Import" button on the VMs tab, next to the regular CSV
  import. Reads CSV/XLSX/JSON, lets you pick which row is the real header
  (handles messy exports with junk rows before the real data - the file
  that prompted this feature had one, though it turned out to be from
  manual editing, not a genuine vCenter export artifact - see the caveat
  on the VMware preset below), maps source columns to ClusterSizer fields
  (Name/vCPU/RAM/Disk/Power/Notes) with per-field unit selection
  (auto-detect "8 GB" style text, or force a fixed unit for bare numbers
  like Proxmox's byte counts), and shows a live "N VMs ready to import"
  count before you commit.
- 4 built-in starting-point profiles: VMware vCenter, RVTools (vInfo),
  Nutanix Prism, Proxmox VE (pvesh JSON). These are convenience presets,
  not guarantees - export formats drift between tool versions (and the
  VMware one specifically was built from a file we later learned had been
  hand-edited before we saw it, so it's explicitly marked "unverified
  sample" - not confirmed to match a real untouched vCenter export). This
  is exactly why manual mapping is the real mechanism underneath, not the
  presets.
- Mappings can be saved as named profiles at the user level
  (~/.clustersizer/import_profiles.json, not tied to one project) - map
  a new/unrecognized export once, every future import from that same
  tool auto-matches by header signature and needs zero re-mapping.
- New dependency: openpyxl (for reading .xlsx exports directly, without
  a separate conversion step).
- Scope: VMs only for this release - Servers/Storage/Network smart import
  may follow later if it turns out to be worth the same treatment.

## v2.0.6 (bugfix: column sorting didn't actually sort)

- setSortingEnabled(True) was on since v1, but the table models are plain
  QAbstractTableModel subclasses that never implemented sort() - Qt's
  default sort() does nothing, so clicking a header showed the arrow but
  left row order untouched. Fixed properly: MultiSelectTableView now
  wraps every table in a QSortFilterProxyModel (set_source_model()
  instead of setModel()), so header clicks actually reorder rows -
  Servers, Storage, VMs, Switches, Connections. selected_rows() maps
  proxy rows back to source-model rows transparently, so no other page
  code needed to change. Sorting is case-insensitive for text columns.

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
