# ROADMAP

## v2.6.0 (Cluster Preparation redesigned as a Next/Next/Finish wizard)

- Rebuilt the whole dialog as a real QWizard (5 pages: Hypervisor,
  Workload, Policy, Candidate Host Spec, Result) instead of one long
  scrollable form - per-decision pages, skip a page and its sensible
  default applies (N+1 HA, no growth, 20% reserve, VMware if the
  Hypervisor page is left untouched).
- New Hypervisor page reuses the SAME vendor presets already on the
  Settings tab (Thresholds.PRESETS - VMware/Hyper-V/Proxmox/Citrix), so
  the Result page's "commonly-cited ~4:1 vCPU:pCPU" reference is the
  exact same number as Settings, not a second independent guess.
- Workload page no longer asks you to configure 5 utilization
  percentages as a required step - it reads the Workload Profile already
  set per VM on the VMs tab and shows the breakdown read-only. Fine-
  tuning the per-profile defaults is now an explicitly opt-in, unchecked-
  by-default section ("pick something, tweak later" instead of "you must
  configure this first").
- Result page now shows TWO complementary numbers side by side: the
  workload-weighted host recommendation (drives the actual "buy N hosts"
  answer) AND a simple raw vCPU:pCPU sanity-check ratio compared against
  the chosen vendor's typical guidance - both kept, neither replaces the
  other (a sysadmin-familiar number alongside the more precise one).
- New Hyperthreading hint on the Result page - ACTUALLY re-runs the
  sizing calculation with HT flipped and reports the real host-count
  difference, only shown when there is one (no vague "this workload
  isn't CPU-heavy" qualitative claims - a computed before/after
  comparison, or nothing).
- SizingResult gained `raw_oversubscription_ratio` (src/calculations/
  cluster_preparation.py) - pure, testable, no Qt dependency, same as
  the rest of that module.

## v2.5.2 (Cluster Preparation dialog no longer clips on smaller/scaled displays)

- Reported: on 1920x1080 @ 125% Windows scaling, the dialog opened tall
  and narrow with the bottom (Result section + Add buttons) cut off and
  unreachable. Cause: a fixed 560x780 size with everything (Policy, Host
  Spec, 5 workload utilization fields, Result, buttons) stacked in one
  plain QVBoxLayout - taller than the usable screen height once Windows
  scaling and taskbar/title bar are accounted for, with nothing to make
  the overflow reachable. Fixed: the whole content now lives inside a
  QScrollArea, so it's always fully reachable regardless of screen size
  or DPI scaling - the window itself opens at a smaller, more reasonable
  620x700 (down from 560x780) with a 480x400 minimum, and scrolls for
  the rest instead of relying on fitting everything unscrolled.

## v2.5.1 (Cluster Preparation now also sizes Storage)

- Fixed a real gap: `total_storage_demand_gb` was already being computed
  but nothing was done with it - the wizard reported the number but
  never turned it into a recommendation. Now SizingResult includes
  `recommended_storage_usable_tb`/`recommended_storage_raw_tb` for
  Primary, and the DR equivalents computed from each VM's OWN DR disk
  footprint (not primary disk - a VM's DR replica can be smaller). New
  `storage_overhead_percent` policy field (RAID/EC + headroom, same idea
  as the Storage tab's own overhead field).
- "Add Recommended Servers to Project" buttons renamed to "Add
  Recommended Cluster to Project" (Primary/DR) - now add servers AND a
  sized storage system together. New `ProjectService.
  add_servers_and_storages()` does both in ONE undo snapshot, not two,
  so a single Ctrl+Z removes the whole recommendation.
- Verified end-to-end: after adding the recommended cluster, the
  project's own Storage usable capacity is sufficient for the VMs' total
  disk demand - the wizard's output and the app's own capacity math
  agree (same consistency property already verified for hosts/N+1 in
  v2.5.0).
- Network intentionally NOT sized by the wizard - switch/port count
  doesn't follow principally from VM count the way CPU/RAM/storage do
  (it depends on physical topology choices the wizard has no way to
  know). Left as a manual step on the Network tab; flagged in ROADMAP
  as a possible v3 addition if a reasonable heuristic emerges.

## v2.5.0 (Cluster Preparation - reverse sizing)

- New "🧮 Cluster Preparation" button on the VMs tab (enabled once there's
  at least one VM). Answers a genuinely different question than the rest
  of the app: not "given the servers I HAVE, do these VMs fit" (the
  existing oversubscription-ratio checks on Summary/VMs/Reports/Compare,
  unchanged), but "given the VMs I NEED to run, how many hosts should I
  buy". Two complementary calculations, not one replacing the other -
  see src/calculations/cluster_preparation.py's module docstring.
- VirtualMachine gained `workload_profile` (CPU Intensive / Balanced /
  Memory Intensive / Storage Intensive / Light), each with an assumed
  average CPU utilization % (src/models/workload_profile.py) - editable
  per-project in the wizard, since these are sizing ASSUMPTIONS, not
  measurements. Purely additive: doesn't touch the existing flat
  vCPU:pCPU oversubscription-ratio math anywhere else in the app.
- Sizing accounts for: workload-weighted effective vCPU demand, a memory
  reserve % (hypervisor/mgmt overhead), expected growth %, HA policy
  (None/Basic/N+1/N+2), and a candidate host spec you're sizing against.
  Reports which resource (CPU or RAM) was the binding constraint, so
  "why 4 hosts" has an answer.
- DR sizing deliberately reuses each VM's EXISTING dr_protected flag +
  per-VM DR footprint (already on the VMs tab) instead of inventing a
  parallel "DR tier" concept - one source of truth for "what needs to
  run on DR", not two that can drift apart.
- Deliberately excludes CPU vendor/model suggestions (stays at "required
  cores: 48, recommended: 2x24-core") - per docs/vision.md's explicit
  scope guard against becoming a hardware shopping tool.
- "Add Recommended Servers to Project" turns the result directly into
  real Server rows (via the existing add_servers batch method - one
  undo step) at Primary and/or DR, pre-filled with the candidate host
  spec, ready to review/adjust like any other server.
- Verified end-to-end: a wizard recommendation, applied back to the
  project as real servers, passes the project's OWN N+1 check and shows
  OK-status CPU/RAM ratios on the existing oversubscription math - the
  two calculation directions agree with each other (regression test:
  test_cluster_preparation.py::test_recommendation_survives_own_n_plus_one_check).

## v2.4.3 (external audit fix pass - 22 of 26 issues)

An external code audit (issues.md, 26 findings from a manual read of all
46 Python files) turned out to be accurate on every issue independently
verified - all 4 "blocking" findings reproduced with concrete numbers
before being fixed. Fixed in this pass:

- **Blocking:** S1 (`_bool()` ignored `default` for blank CSV cells -
  every VM with an empty `powered_on` column imported as powered off),
  S2 (N+1 check picked one host by RAM then checked CPU headroom against
  that same host - a heterogeneous cluster could report N+1-ready while
  actually failing on CPU), S3 (Settings thresholds were never persisted
  to `.clsz` - reset to defaults on every reopen; now schema v3, with v2
  files loading fine via existing schema-drift tolerance), S8 (`int()` on
  socket/core CSV fields crashed on Excel-round-tripped "2.0" strings).
- **High:** S4 (QWidget had no background-color, unreadable in OS dark
  mode - light theme is now explicit, not half-native), S5
  (`ClusterSizer.spec` didn't exist in this checkout - written fresh,
  bundling `src/resources/`; `main.py` now resolves resource paths
  correctly under a frozen PyInstaller build via `_resource_root()`, and
  logs to stderr instead of failing silently when a resource is
  missing), S6 (crash log moved to `~/.clustersizer/crash.log`, wrapped
  in try/except - an unwritable install directory could previously
  prevent the app from starting at all).
- **Medium:** S9 (three "cannot be undone" dialogs were false - Clear All
  is undoable), S10 (Duplicate on Storage/VMs/Switches/Connections now
  batches into one undo snapshot, not N - new `add_storages`/
  `add_switches`/`add_connections` service methods), S11 (PDF/text report
  now stamps the app version - `src/version.py` is the single source,
  avoiding a main_window<->reports_page circular import), S12 ("Export
  All CSV" now writes all 5 entity types, not 3), S13
  (`projects_are_identical` compared `uid`s, which are random per
  instance - now compares value fields excluding `uid`; `project.name`
  deliberately doesn't participate), S15 (`ComparePage` had reintroduced
  persistent `QHeaderView.ResizeToContents`, the exact pattern the
  v2.0.x-v2.1.1 Windows crash fix removed - now Interactive + a one-shot
  deferred resize).
- **Low:** S16 (`save_user_profiles` OSError now caught at the GUI layer
  - profile save failure warns but doesn't abort the import), S17 (new
  `report_error()` helper logs full tracebacks to the crash log at all 21
  sites that used to show only `str(exc)`), S18 (Smart Import wizard
  preview now converts a 200-row sample per keystroke instead of the
  whole file - the real import on Accept still processes everything),
  S19 (all relative `from ..` imports converted to absolute `from src.…`,
  the majority style - `pyproject.toml`'s `pythonpath` no longer strictly
  required but kept for convenience), S20 (function-local `copy`/`uuid`
  imports moved to module level, 5 files), S21 (`switch_port_usage`/
  `server_nic_usage`/`storage_port_usage` deduplicated into one private
  `_usage_by_speed()` helper behind three thin typed wrappers), S23
  (stale "Dashboard" references updated to "Summary" - the two
  intentional-history mentions in `summary_page.py` left untouched), S25
  (`.github/workflows/tests.yml` runs pytest on push/PR), S26 (deleted
  `src/utils/__init__.py` and `src/resources/__init__.py` - dead
  scaffolding for a directory with no Python code and a data-only
  directory respectively).
- **T0:** `pyproject.toml`, `requirements-dev.txt`, `tests/` with
  regression tests for S1, S2, S3, S8, S13.

**Not fixed - needs a decision, not a mechanical edit (per the audit's
own "ask first" list):**
- **S7** — `py2exe.txt` (build/release instructions) is gone from this
  checkout; unclear whether that was deliberate.
- **S14** — Storage TB→GB uses binary (×1024) while VM disk figures are
  plain decimal GB, a ~2.4%/TB headroom overstatement. Standardizing
  changes sizing output for every existing project - product decision.
  (The doc-only part of S14 - the README overselling RAID/EC as
  "calculated automatically" - IS fixed above.)
- **S22** — `ServersPage._refresh_ht_global` duplicates
  `ClusterProject.hyperthreading_state`'s classification logic because
  the model method is per-site and the page needs an all-sites view plus
  raw counts for its "(3/8 have HT on)" label. Needs a deliberate
  site-agnostic API addition, not a forced substitution.
- **S24** — the .gitignore Croatian comment IS fixed above. The
  README "Thanks" section, as reconstructed for this fix pass, has no
  Croatian text - the audit's finding may reflect a different local
  state of that file than what this pass had to work from.

## v2.4.2 (PDF report export)

- Reports tab gained "📄 Export PDF Report" next to the existing .txt
  export - a color-coded, nicely laid-out PDF (site tables, status
  badges matching the app's OK/Warning/Critical palette, HT ENABLED/
  MIXED tags) suitable for handing to a client or attaching to a ticket.
  Deliberately built with Qt's OWN printing support (QTextDocument +
  QPrinter, both already part of PySide6/PySide6-Essentials) instead of
  adding reportlab or a similar PDF library as a new dependency - the
  report is generated as HTML (src/calculations/html_report.py, no Qt
  dependency, kept deliberately old-school table-based markup since
  QTextDocument's HTML renderer only supports a fairly basic CSS subset)
  and Qt itself prints that to PDF. No new pip packages required.
- If QtPrintSupport isn't available for some reason, the button fails
  with a clear message instead of a crash (pip install PySide6-Addons
  as a fallback suggestion).

## v2.4.1 (global HT toggle + HT indicators)

- Servers tab toolbar gained a "Hyperthreading (all servers)" checkbox -
  reflects whether EVERY server currently has HT on, and clicking it
  bulk-sets HT for all servers in one undoable action (single Ctrl+Z
  reverts the whole toggle, not one per server). When servers disagree,
  the checkbox shows unchecked with a "(N/M have HT on - click to
  normalize)" note instead of guessing.
- HT ENABLED (red, bold) now shows on the Summary page next to each
  site's "Servers / pCPU cores (HT-adj.)" line when every server at that
  site has HT on - deliberately loud, so the HT-adjusted core count
  doesn't get mistaken for a plain physical core count. Added a second
  state, HT MIXED (orange, bold), for when servers at a site disagree -
  a blanket "enabled" tag would be misleading there. Nothing shown when
  HT is off everywhere. Same HT ENABLED/MIXED tagging added to the
  Reports text export and a dedicated "Hyperthreading" row on the
  Compare page (useful there since two scenarios can genuinely differ).
- ClusterProject.hyperthreading_state(site) and SiteReport.ht_state are
  the shared source of truth all of the above read from.

## v2.4.0 (Hyperthreading toggle + Storage connectivity)

- Server gets a "Hyperthreading Enabled" checkbox (Servers tab dialog),
  separate from the Threads/Core value so an unusual SMT width can stay
  configured even while HT is toggled off. CPU oversubscription math is
  now genuinely per-server HT-aware: ClusterProject.physical_cores()
  sums Server.effective_cores (threads if HT on, physical cores if off)
  instead of a flat core count - affects CPU oversubscription ratio, N+1
  check, and DR CPU check everywhere they're shown (Summary/VMs/Reports/
  Compare). Server table gained "HT" and "Effective Cores" columns;
  "Total Cores" (raw physical) stays unaffected as a separate reference
  column. Labels that show this HT-adjusted number are marked
  "(HT-adj.)" so it's clear it isn't a straight core count.
- Storage connectivity, same pattern as Network switches: Storage gets a
  port inventory (1G/10G/25G/40G/100G/FC/SAS) and a live "Used/Free"
  column on the Storage tab. NetworkConnection gained a storage_uid field
  (backward compatible - old .clsz files with only server_uid/switch_uid
  load unchanged) supporting THREE link kinds: Server<->Switch (original),
  Storage<->Switch, and Server<->Storage direct-attach (no switch - the
  4-port/2-port FC HBA-straight-to-array case). The Connections dialog
  now has a Connection Type selector that swaps the two entity dropdowns
  accordingly; the Connections table shows Type + Endpoint A/B instead of
  fixed Server/Switch columns. Server also gained nic_sas for direct-
  attach SAS HBAs.
- CSV formats updated: servers gained hyperthreading_enabled + nic_sas;
  storage gained the 7 port fields; connections gained a storage_name
  column (name-based, like server_name/switch_name) - exactly two of the
  three name columns should be filled per row.

## v2.3.0 (Dashboard merged into Summary, Compare redesigned)

- Dashboard tab removed - its content (top-line cards) now lives at the
  top of the Summary tab, shrunk ~50% (SummaryWidget got a `compact=True`
  mode), with the existing Primary/DR deep-dive below it. One fewer tab,
  same information, no more flipping between two "overview" tabs. Summary
  is now the first/landing tab.
- Compare tab redesigned around explicit, symmetric loading: Scenario A
  and Scenario B are now BOTH loaded independently via "Load..." or "Use
  Current Project" (a snapshot shortcut, no save-to-disk round trip
  needed) - neither slot silently tracks the live active project anymore,
  so what you're comparing can't drift out from under you while you're
  looking at it.
- Compare table: columns now stretch to fill the page (was cramped and
  left-aligned), section headers (PRIMARY/DR/DR READINESS) are bold with
  a shaded background, and rows where A and B differ are bold with a
  highlighted background - differences jump out instead of requiring a
  read-every-row comparison.
- Added a compact "at a glance" delta card row at the bottom of Compare
  (ΔServers/ΔCores/ΔRAM/ΔVMs/ΔStorage), same visual style as the
  Dashboard cards, for a one-glance summary above the detailed table.
- New src/calculations/comparison.py additions: build_delta_summary().

## v2.2.1 (Compare page: explain identical A/B instead of looking broken)

- Reported: saving a scenario copy AFTER making changes, then comparing
  immediately, showed Scenario A and B as completely identical - looked
  like a bug. It wasn't: the snapshot captures whatever state the active
  project is in AT the moment you save it, so comparing right after with
  nothing changed in between will always be identical by construction
  (same idea as diffing a git commit against itself). Added
  projects_are_identical() to comparison.py and a visible warning banner
  on the Compare page explaining exactly this, instead of a silent
  identical-looking table. Also reworded the "Scenario Saved" confirmation
  and the Save Scenario Copy As tooltip to state the workflow implication
  up front (snapshot now, keep editing, compare against it later).

## v2.2.0 (Undo/Redo + Compare Scenarios)

- Undo/Redo (Ctrl+Z / Ctrl+Y), snapshot-based: ProjectService pushes a
  deep copy of the whole project before every structural mutation
  (Add/Update/Remove/Clear/Import) across Servers/Storage/VMs/Switches/
  Connections. Deliberately snapshot-based rather than a command pattern
  with hand-written inverses - projects are small, so deep-copying the
  whole thing on each change is cheap, and every mutating method only
  needed one extra line. Scope: inline cell edits (double-click a table
  cell, type a new number) are NOT on the undo stack - low-risk (just
  retype it), and covering them would mean snapshotting on every
  keystroke's commit. Undo covers the actions where it actually matters:
  Add, Delete, Duplicate, Import, Clear All. New project / Open project
  clears the undo history (a different project's undo history doesn't
  mean anything).
- New Compare tab: current (live) project vs. a second .clsz file loaded
  read-only, side by side - servers/cores/RAM/storage, VM demand,
  oversubscription, N+1, DR readiness, all under the SAME live
  thresholds for a fair comparison. Loading Scenario B never touches the
  active project.
- New File menu action "Save Scenario Copy As..." - snapshots the
  current project to a new file WITHOUT switching the active project to
  it (unlike regular Save As), so you can branch off a "what-if" and keep
  editing the original, then load the branch later on the Compare tab.
- Comparison row-building logic lives in src/calculations/comparison.py,
  no Qt dependency, same pattern as sizing.py/networking.py.

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
