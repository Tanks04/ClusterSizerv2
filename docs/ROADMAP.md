# ROADMAP

## v4.19.0 (10 real defects from an external code review, including a guaranteed Compare-page crash)

A friend ran two independent LLM code analyses of this repo and
diffed their findings. Verified all 12 claimed issues against the
current codebase before touching anything - every single one was
confirmed still real and current, not stale findings from an old
snapshot.

- **CRASH - `comparison.py`**: `build_reports()` has returned
  `dict[str, SiteReport]` since N-site support replaced the old fixed
  3-tuple, but this file still unpacked it as `pa, dra, dcka =
  build_reports(...)` - the Compare page crashed with a `ValueError`
  the moment anyone opened it, on any project with other than exactly
  3 sites (i.e. every default 2-site project). New `_reports_for()`
  helper looks up Primary/DR by name instead of tuple position, and
  pulls DR readiness from `build_failover_report()` (a `FailoverReport`)
  instead of misreading nonexistent `SiteReport` attributes
  (`protected_vm_count` etc. don't exist - the real fields are
  `assigned_vm_count` and friends). Delta storage summing also
  generalized from hardcoded Primary+DR to every site, matching how
  every other delta card on that row already worked.
- **WRONG - `docx_report.py`**: 3 of 4 sections (Servers, Storage,
  Network) iterated a hardcoded `(PRIMARY, DR)` pair while a 4th
  (Failover) already correctly used `project.site_names` - a 3-site
  project produced device rows tagged DR2 with no DR2 summary row
  anywhere in the report. All four sections now consistent.
- **WRONG - missing signals**: `_emit_everything_changed()` (fired on
  every undo/redo) only emitted 4 of 7 narrow signals - `clusters_
  changed`, `backup_changed`, and `pricing_changed` were missing, so
  undoing a change to Clusters/Backup/Pricing didn't refresh those
  pages. Also fixed the class docstring, which still only listed 4 of
  the 7 signals that actually exist.
- **RISK - 6 `remove_*` methods matched by `id()`** (object identity)
  instead of `.uid`: `remove_servers`, `remove_storages`, `remove_
  backup_destinations`, `remove_maintenance_items`, `remove_vms`
  (partially - cascade cleanup already used uid, the primary list
  filter didn't), `remove_connections`. Silently removes NOTHING if
  the caller holds a different-but-equal object (e.g. a deep copy from
  an undo/redo snapshot) - confirmed with a test reproducing exactly
  that scenario. All 6 now match by `.uid`, consistent with `remove_
  switches`/`remove_vlans`/`remove_clusters`, which already did.
- **WRONG - `import_engine.py`**: Smart Import validated each row's
  site against a hardcoded `("Primary", "DR")` tuple - a row
  legitimately tagged "DR2" silently fell back to the wizard's default
  site instead. New `valid_sites` parameter on `convert_rows()`,
  threaded from `ImportWizardDialog`'s own site list (which it already
  had, for the default-site dropdown).
- **WRONG - `csv_io.py`**: both `hyperthreading_enabled` and `enabled`
  defaulted to `True` when their column was absent from the CSV -
  doubling effective cores in the unsafe direction, and silently
  re-enabling servers an admin had deliberately disabled. Both now
  default to `False`, matching the "undercount rather than overcount"
  posture this app uses elsewhere; unaffected for round-tripping the
  app's own CSV export, which always includes both columns.
- **RISK - `project_repository.py`**: `save_project()` wrote directly
  to the target `.clsz` path - a crash or power loss mid-write would
  corrupt the file with no recovery. Now writes to a temp file in the
  same directory (guarantees same filesystem) and atomically replaces
  the target only after a successful fsync'd write; the original file
  is untouched by any interruption. Verified with a simulated crash
  mid-write.
- **NIT**: the VMs tab's "CPU Oversub." summary card silently only
  ever reported the Primary site while sitting next to cards that
  correctly total the whole project - relabeled "CPU Oversub.
  (Primary)" rather than trying to sum a ratio across sites (which
  isn't meaningful the way summing raw demand is).
- 23 new tests covering every fix above, including the exact failure
  scenarios described (crash reproduction, deep-copy removal, DR2 row
  silently dropped, simulated mid-write crash) - 831 passed total.

## v4.18.0 (Storage array zoning moved to Servers tab; Cluster-based bulk assign)

Requested directly: array-level storage zoning is fundamentally a
server/host concept (which hosts a storage array is presented to), not
a VM one - "Add Storage Array" moved off the VMs tab entirely, onto
Servers where it belongs. Also introduces a Cluster as a bulk-assign
shortcut: "pools are basically assigned to either a server or a
Cluster."

- **New: `Storage.server_uids`** - array-wide host zoning, parallel to
  the existing `StoragePool.server_uids` one level down (a specific
  pool within the array). Meaningful for an array that hasn't been
  split into pools; once pools exist, per-pool zoning is normally more
  precise, but this stays available as a simpler default.
- **New: "Add Storage Array" row on the Servers tab** - a storage
  dropdown with "Selected"/"All" buttons for individually-picked
  servers, PLUS an "or Cluster:" picker that expands to every server
  CURRENTLY in that cluster and zones them all at once. Explicitly a
  one-time starting point, not a standing link - a server added to the
  cluster afterward does NOT retroactively get zoned; existing zoning
  can still be edited/removed per-server afterward. New
  `ProjectService.add_servers_to_storage_zoning()` - additive, no
  duplicates, one undo step regardless of how many servers.
- **Removed "Add Storage Array" from the VMs tab** entirely (the
  array-level bulk-assign row and its methods) - only the pool-
  specific row remains there, relabeled **"VM Pool:"** for clarity now
  that array-level zoning lives elsewhere.
- Found and fixed the same "silently reset on save" bug class hit
  twice before (`cluster_name`, then `disk_count`/`raid_level`/pools):
  `StorageDialog.get_storage()` was resetting `server_uids` to empty
  on every save, since no widget in that dialog edits it directly -
  preserved the same way as the earlier fixes.
- Deleted `test_vm_bulk_storage_assignment.py` entirely (13 tests for
  the now-removed VMs-tab feature) and fixed one test in
  `test_vm_bulk_pool_assignment.py` that referenced the old label.
- 16 new tests (additive zoning with no duplicates, undo, all three
  Servers-tab bulk-assign paths including the cluster snapshot-not-
  sync behavior, and the `server_uids` preservation fix) - 808 passed
  total.

## v4.17.2 (Two more lint warnings in main.py - both legitimate false positives)

Flagged directly: Pylance's `reportAttributeAccessIssue` on `sys.
_MEIPASS` (line 68) and ruff's `SIM115` on a raw `open()` call (line
46).

- **`sys._MEIPASS`**: PyInstaller injects this attribute into `sys`
  only at runtime for a frozen build - it has no type stubs, so
  Pylance can't know it's valid even though the code already guards
  access behind `if getattr(sys, "frozen", False)`. Switched to
  `getattr(sys, "_MEIPASS")`, which sidesteps Pylance's static check.
  That in turn triggered ruff's own B009 ("don't use getattr with a
  constant name, it's not safer") - a real case of two tools
  disagreeing, since ruff has no way to know the getattr was chosen
  specifically to satisfy Pylance. Suppressed with an explanatory
  `# noqa: B009` rather than picking one tool's opinion by trial and
  error every time this file is touched.
- **The raw `open()`**: intentional, not an oversight - the crash log
  file is meant to stay open for the ENTIRE application lifetime
  (`faulthandler` and the custom excepthook both write to it
  continuously), not scoped to the function that opens it. A `with`
  block would close it immediately, defeating persistent crash
  logging entirely. Suppressed with `# noqa: SIM115` and an inline
  reason instead of restructuring working, correct code to satisfy a
  rule that doesn't apply to this pattern.
- Scanned the rest of `src/`/`tests/` for the same two rule categories
  - none found, both were isolated to these two lines. 805 passed,
    unchanged.

## v4.17.1 (Import order cleanup - ruff)

Flagged directly by ruff in an editor: unsorted imports at the top of
`main.py`.

- Ran `ruff check --select I --fix` across `main.py`, `src/`, and
  `tests/` - 192 accumulated import-ordering issues (stdlib/third-
  party/first-party grouping, alphabetization within each group),
  built up gradually over many rounds of ad-hoc edits without ever
  being swept in one pass. Purely mechanical - reordering import
  statements never changes behavior, confirmed by the full test suite
  passing unchanged (805 passed, same as before).

## v4.17.0 (PCI passthrough storage pools; VM highlighting)

Requested with a concrete real-world example: a security VM with two
physical disk groups (Sec_data_os, Sec_data_log) wired directly to it
via PCI passthrough - the opposite assignment direction from a normal
pool, where the cluster/hosts never see it at all, only that one VM
does.

- **New: `StoragePool.is_passthrough` / `passthrough_vm_uid`** - marks
  a pool as bypassing the hypervisor entirely, connected to exactly
  one VM instead of zoned to hosts. Persists through the same nested-
  dataclass mechanism already in place for pools generally - no
  additional persistence work needed.
- **New in `StoragePoolDialog`**: a "PCI Passthrough" checkbox that
  swaps the "Zoned Servers" checklist for a "Connected VM" picker when
  checked (server zoning is meaningless for a pool the hosts never
  see). `StorageDialog` now threads the project's VM list through to
  this picker via its existing `service` reference.
- **New: colored border on the VMs table** for any VM connected to a
  passthrough pool - same technique already used for switch redundancy
  pairing (a custom `QStyledItemDelegate` reading a dedicated role off
  the model), kept as its own small delegate rather than cross-coupling
  the switch and VM table models. A fixed purple (not a name-derived
  hash like the switch version) since the useful signal here is simply
  "this VM has passthrough," not telling several setups apart. Verified
  with a rendered screenshot. A VM with multiple passthrough pools
  (the exact reported scenario) still gets exactly one border, not one
  per pool.
- Also confirmed and documented: the Word export always includes the
  full project (Cluster/Storage Pool/VLAN data) regardless of whether
  Advanced Mode is on in the GUI - Advanced Mode only affects what's
  shown live on screen, nothing is excluded from the report.
- Fixed a small bug in an already-in-progress test file
  (`test_vm_bulk_pool_assignment.py`) from earlier bulk-pool-assignment
  work - a leftover broken widget-search line that predated a working
  one right below it.
- 19 new tests (model fields, persistence fresh and backward-compatible,
  the dialog's checkbox/picker toggle and save/load round-trip, and the
  VM table border - single pool, no pool, ordinary pool assignment not
  triggering it, two different VMs each with their own pool, and one
  VM with two passthrough pools still getting a single border) - 805
  passed total.

## v4.16.2 (Fixed: RAID Calculator couldn't accept decimal disk sizes)

Reported directly: typing "1.09" or "1.9" TB (common real-world disk
sizes) into the RAID Calculator's disk size field silently turned into
"19" - made it unusable for a large chunk of real disk models.

- **Root cause**: `disk_size_spin` was a `QSpinBox` (integers only),
  not a `QDoubleSpinBox` - every other TB-capacity field in the app
  (Storage, StoragePool, Server's own local disk calculator) already
  used the correct widget; this one slipped through when the
  standalone RAID Calculator was originally built.
- **Fixed**: switched to `QDoubleSpinBox` (2 decimals) - verified with
  the exact values reported (1.09, 1.9) plus 1.2, and confirmed the
  underlying RAID math correctly uses the full decimal value (8 \u00d7
  1.09 TB in RAID 5 \u2192 8.72 TB raw, 7.63 TB usable).
- 6 new tests (widget type, each reported decimal value, the
  calculation actually using the decimal size, and Reset leaving a
  sensible default) - 775 passed total.

## v4.16.1 (Fixed: selection color still showed blue after picking a different one)

Reported directly right after v4.14.0 shipped: picking green, then
red, in Settings' color picker - selection stayed the platform's
default blue either way.

- **Root cause**: `QPalette.Highlight` alone isn't honored by some
  native OS styles (Windows' "windowsvista", macOS's native style) for
  `QAbstractItemView` (table/list) row selection - the palette value
  was being set correctly, but the active platform style was ignoring
  it for item-view painting specifically.
- **Fixed**: `apply_accent_color()` now ALSO injects an explicit QSS
  rule (`QTableView::item:selected` etc.) alongside the palette
  change - QSS-based selection styling is honored the same way
  regardless of platform style, so this is the part that actually
  guarantees the color changes everywhere. Re-picking a color cleanly
  replaces the previous QSS block (marked with a comment) rather than
  accumulating stale rules on every change.
- Verified with a real rendered screenshot showing a selected table
  row in green.
- 4 new tests (QSS injection, clean replacement on re-pick, the rest
  of the stylesheet staying intact, idempotent re-application) - 769
  passed total.

## v4.16.0 (Storage: multiple pools per array, per-pool VM assignment, RAID Calculator moved out)

A full redesign of Storage's disk-sizing workflow, requested directly:
"koncept raid calculatora bi tu maknuo... trebamo imati opciju
dodavanja vise storage poolova prema serverima, odnosno odredeni
diskovi/pool prema VMovima."

- **New: `StoragePool`** - a carved-out slice of one array's disks
  (e.g. an SSD tier and a bulk SATA tier, or a pool zoned to a
  specific set of servers), embedded in its parent `Storage` the same
  way `StorageShelf` already is. A VM can now reference a specific
  pool (`storage_pool_uid`) narrower than just picking the array as a
  whole (`storage_uid`) - fully additive, an array with no pools
  defined behaves exactly as before.
  - New "Storage Pools" management section inside `StorageDialog` -
    Add/Edit/Delete via a small `StoragePoolDialog` (name, raw/usable
    capacity, a checkable server-zoning list mirroring the existing
    HCI server checklist), listed in a mini table alongside a live
    Used/Free utilization column.
  - New `VMDialog` "Pool" dropdown, populated dynamically from
    whichever array is currently selected - shown only when that
    array actually has pools defined, hidden otherwise. Renamed the
    existing array-selector's label from "Storage Pool" to "Storage
    Array" to resolve the naming collision this created.
  - New `ClusterProject.pool_demand_gb()`/`pool_utilization_ratio()` -
    the same "one busy pool can hide behind a healthy array-wide
    average" pattern already used for Clusters, now one level deeper.
    The existing array-wide `storage_pool_demand_gb()` is unaffected
    by whether VMs are further split across sub-pools.
- **Removed the old inline disk-count/RAID-level calculator** from
  `StorageDialog` entirely - replaced by an "Open RAID Calculator..."
  button that launches the existing, far more capable standalone tool
  (real RAID 0/1/5/6/10/50/60, hot spares, apply-to-project). Caught
  and fixed the same "silently reset on save" bug class hit earlier
  with `cluster_name`: removing the old widgets meant `get_storage()`
  would reset `disk_count`/`disk_size_tb`/`raid_level`/`pools` to
  defaults on every save unless explicitly preserved.
- **Widened `StorageDialog`** (520\u2192640px) per direct request to
  comfortably fit the new section without cramping.
- Cleaned up `test_disk_calculator.py` (13 obsolete tests removed for
  the deleted calculator, 11 relevant ones for the Server disk
  calculator and FTT calculator kept and fixed).
- 55 new tests across the model (StoragePool, persistence round-trip
  fresh and backward-compatible, pool-level calculations), the pool
  management UI (Add/Edit/Delete/cancel, existing-pool loading, the
  Used/Free column with and without service access), the RAID
  Calculator button integration, and the VM dialog's dynamic pool
  selector (population, visibility gating, switching arrays, stale
  references, Advanced Mode) - 765 passed total.

## v4.15.0 (Fast VM-to-Storage-Pool assignment; new "Storage Pool" table column)

Reported directly - assigning several VMs to a specific storage pool
required opening each VM's dialog individually, matching the exact gap
already solved for Cluster/Site.

- **New: "Add Storage Pool" toolbar row** on the VMs tab, right after
  "Bulk move Cluster" - a storage dropdown plus "Selected"/"All"
  buttons, identical pattern to the existing Site/Cluster rows. Both
  use the existing `bulk_set_vm_fields()` service method, so assigning
  many VMs at once is one call, one undo step.
- **New: "Storage Pool" column** on the VMs table (right after
  Cluster) - previously the assignment existed in the data model but
  had no visible column anywhere on this table, so there was no way to
  actually see which pool a VM was on without opening its dialog.
- Storage Pool assignment is an opt-in, advanced concept like Cluster/
  VLAN - the new toolbar row and column are both hidden by default,
  shown together with Advanced Mode.
- 13 new tests (combo population/selection-preservation, both bulk
  actions in both directions including cancel/undo, the Advanced Mode
  visibility toggle, and the new table column showing assigned/
  unassigned/stale-reference states) - 733 passed total.

## v4.14.1 (Tooltip cleanup app-wide; RAID/EC Overhead's "missing arrows" fixed)

Reported directly: the Storage disk calculator's "Calc" button hint
was "waaaaay to long" - checking the rest of the app confirmed it
wasn't the only one.

- **Fixed**: `RAID/EC Overhead` on the Storage dialog looked like a
  normal white, active field with no spinner arrows and no visible
  reason it wouldn't accept input - actually `setReadOnly(True)`,
  which doesn't get the app's grey "disabled" styling the way
  `setEnabled(False)` does. Switched to the latter, matching every
  other calculated/non-editable field in the app - now visibly greyed
  out with faint arrows, immediately readable as "this is computed,
  not something you type into."
- **Shortened 21 tooltips app-wide** down to 1-2 sentences each - a
  scan turned up 27 over 150 characters, several genuinely huge (460,
  411, 376 chars) from writing very thorough explanations that had
  turned into wall-of-text hover popups. Touched storage_dialog.py,
  cluster_preparation_dialog.py, server_dialog.py, connection_dialog.py,
  vm_dialog.py, switch_dialog.py, site_capacity_widget.py, main_window.py,
  summary_page.py, reports_page.py, rvtools_import_dialog.py,
  virtual_machines_page.py, and servers_page.py.
- **New regression test** (`test_tooltip_length.py`) scanning every
  `setToolTip()` call in `src/` and failing if any exceeds 150
  characters, so this doesn't quietly creep back over time.
- 3 new tests (the length-limit scanner, plus confirming the Overhead
  field's disabled state doesn't break its auto-calculated value) -
  720 passed total.

## v4.14.0 (Configurable selection color)

Reported directly: Qt's default selection highlight (a blue, from the
platform's native palette) "ta plava mi smeta" - wasn't previously
something the app controlled or exposed.

- **New: "Appearance" box on Settings** - a color picker for the
  selection highlight used across the whole app (table rows, list
  items, text selection). Applied via `QPalette.Highlight`/
  `HighlightedText` rather than per-widget stylesheet rules, so one
  setting covers every widget type consistently instead of needing a
  separate `::selected` rule for each. Applied immediately on pick, no
  restart needed - verified with a real rendered screenshot showing a
  table row's selection color actually change.
  - Persisted as an app-level preference (same `~/.clustersizer/
    preferences.json` used for Advanced Mode), defaulting to the exact
    blue already used elsewhere in the app's own stylesheet, so nothing
    visibly changes until someone explicitly picks a different color.
  - Applied at startup (`main.py`) and live from Settings via the same
    shared `apply_accent_color()` function, so both paths can never
    drift out of sync with each other.
- 10 new tests (persistence, the palette-applying function directly,
  and the full Settings picker flow including cancel-changes-nothing)
  - 717 passed total.
- **Also raised**: a dark/light theme toggle. Scoped as a separate,
  larger follow-up rather than folded in here - a theme worth the name
  needs a deliberately-designed second palette (contrast, disabled
  states, warning/critical colors all re-checked for a dark background),
  not a mechanical inversion of the existing light QSS.

## v4.13.0 (Server's two "cluster" concepts consolidated into one)

Reported directly: "Cluster" and "Cluster Name" sitting next to each
other on the Servers table was confusing, and the reasoning for
keeping them separate (RVTools populates one as plain text; the other
is the real, colored, calculation-aware entity) didn't hold up - as
pointed out, imported data is editable like anything else, so there
was no real reason import couldn't populate the structured one
directly instead of a dead-end text field.

- **New: `find_or_create_clusters_by_name()`** (`models/cluster.py`) -
  given a batch of freshly-parsed servers, groups them by (site,
  cluster_name), reuses an existing Cluster if one already has that
  exact name at that site, otherwise creates one (auto-colored from
  the rotation), and links each server via `cluster_uid`. Re-importing
  into an already-linked cluster name reuses it rather than creating a
  duplicate.
- **RVTools import** and **CSV import** (`Servers` tab) now both run
  this automatically - the "Cluster" column from either source creates
  or reuses a real, colored Cluster entity, in the same undo step as
  the servers themselves.
- **Removed the free-text "Cluster Name" column and dialog field**
  entirely from the GUI - only the one structured, colored "Cluster"
  column/dropdown remains. The underlying model field survives for
  backward compatibility (old files still load fine) and now stays in
  sync automatically: selecting a Cluster on ServerDialog updates it
  to match, and any legacy value from before this change is preserved
  rather than blanked out when no Cluster is explicitly selected.
- Found and fixed a subtlety while wiring CSV import: the page's
  preview parse and the service's own internal re-parse produced
  different Server objects, so cluster-linking had to happen inside
  `import_servers_csv()` itself (on the objects that actually get
  added) rather than on the GUI's separate preview copy.
- 12 new tests (the grouping/reuse helper, both import paths including
  undo atomicity, and confirming the GUI truly has only one Cluster
  surface) plus fixes to 2 existing tests that referenced the removed
  field - 707 passed total.

## v4.12.0 (Settings: 2-per-row layout; editable Workload Tier ratios)

- **New: 2-per-row Settings layout** - sections that easily fit side
  by side (Sites + Deployment Model, Rack Capacity + Recommended
  Presets, CPU + RAM thresholds, Storage + Workload Tiers) no longer
  each span the full window width. Reported directly as unnecessary -
  "sve su postavke od jedne do druge strane prozora."
- **New: Workload Tiers become per-project editable** on Settings,
  alongside the CPU/RAM/Storage thresholds they already sit next to.
  Previously `WORKLOAD_TIERS`' oversubscription-tolerance ratios
  (Tier-0: 1.0, Standard: 4.0, Dev/Test: 8.0, VDI: 12.0) were fixed
  catalog constants - now a project can override any of them (e.g. "my
  Tier-0 workloads can actually tolerate 1.5:1, not the textbook 1:1").
  - New `ClusterProject.tier_ratio_overrides` (persisted, empty by
    default) and `tier_ratio_for_project()`, which checks the
    project's own override before falling back to the shared catalog
    default. `effective_vcpu_demand()`, `effective_failover_vcpu_
    demand()`, and the Attention check's dominant-tier attribution all
    switched to this project-aware lookup.
  - Only stored as an override when the value actually differs from
    the catalog default - setting a spinbox back to its default clears
    the override entirely, keeping the persisted state meaningful
    (empty = nothing customized) rather than always writing all four
    tiers on every Apply.
  - Found and fixed a real persistence bug while building this:
    `ClusterProject`'s top-level fields are saved/loaded by explicit
    name in `project_repository.py` (not a generic dict dump), so a
    brand new field silently doesn't round-trip unless added to both
    the save and load code - confirmed with a round-trip test before
    trusting it.
- 29 new/updated Settings-page tests (tier spinbox defaults, override
  save/clear/reload, and a direct structural check that the boxes are
  actually paired two-per-row) plus 6 new model-layer tests (override
  lookup, effective-ratio impact, dominant-tier attribution respecting
  an override, and .clsz round-trip both fresh and backward-compatible)
  - 694 passed total.

## v4.11.1 (Effective CPU ratio now actually visible; demo example)

Reported directly right after v4.11.0 shipped: "napravio si nekakav
random case, malo se igrao s tierima i ne vidim nigdje razliku." Traced
it to a real gap: the whole feature only ever surfaced as a
conditional Attention message - there was no visible NUMBER anywhere
for the person to watch move while experimenting with tiers.

- **New: "Effective CPU (tier-weighted)" row** on Summary, right below
  the existing "CPU oversubscription" row for each site - same bar +
  status badge treatment, so the two numbers sit side by side and the
  effective one visibly moves as Workload Tier assignments change,
  while the raw one correctly stays put (it's not supposed to change -
  that was always correct behavior, just invisible next to nothing to
  compare it against).
  - `SiteReport` gained `effective_cpu_ratio`/`effective_cpu_status`
    fields, populated for both the normal site view and the Failover
    Preview scenario (new `effective_failover_vcpu_demand()` on
    `ClusterProject`, mirroring the existing raw version).
  - Factored the fixed 1.0/1.5 Warning/Critical cutoffs into a shared
    `effective_cpu_status()` function (`calculations/thresholds.py`),
    used by both the Attention check and the new Summary row instead
    of duplicating the cutoff logic in two places.
- **New example**: `scenario_tier_weighted_cpu_demo.clsz` - 2 servers
  (64 physical cores), 20 VMs at 10 vCPU each (200 total, 3.1:1 raw),
  all starting tagged Tier-0/Mission-Critical so Effective CPU opens
  already Critical at the same 3.1:1. Select all VMs, bulk-set Tier to
  High-Density VDI, and watch Effective CPU drop to ~0.26:1 (OK) on
  Summary while the raw ratio stays exactly where it was.
- 17 new tests (both SiteReport-building paths, the new
  effective-failover-demand calculation, and the widget's visible
  bar/badge actually changing when tier assignments change) - 681
  passed total.

## v4.11.0 (Workload Tier now actually affects CPU oversubscription)

Reported directly: changing a VM's Workload Tier (Tier-0, VDI, Test)
had zero visible effect on the CPU oversubscription ratio shown on
Summary/VMs, no matter what was selected.

- **Root cause found**: `WORKLOAD_TIERS`' commonly-cited safe
  oversubscription ratios (Tier-0: 1:1, Standard: 4:1, Dev/Test: 8:1,
  VDI: 12:1) were only ever consumed by the one-time Cluster
  Preparation wizard's sizing recommendation - never by the ongoing
  raw CPU ratio actually displayed once servers/VMs already exist in
  a project.
- **New: tier-weighted "effective" CPU ratio**, a second check
  alongside (not replacing) the existing raw ratio. Reuses the exact
  formula already established and tested in Cluster Preparation
  (`vm.vcpu / tier's default_ratio`, summed and compared against
  physical cores) rather than inventing a new one - keeps the two
  contexts ("should I buy more hosts" vs "am I oversubscribed given
  what I have") mathematically consistent. An earlier, simpler
  "weighted-average of tolerances" idea was considered and rejected
  after it gave a DIFFERENT answer than the wizard's own math for a
  mixed-tier scenario - confirmed by hand-checking a 10 Tier-0 + 10
  VDI example both ways before committing to the wizard's more
  rigorous, already-vetted approach.
  - Fixed thresholds (Warning >1.0, Critical >1.5) rather than
    Settings-adjustable ones - 1.0 is intrinsically "fully booked
    assuming zero tolerance anywhere" (Tier-0's own ratio), not a
    site-specific policy choice.
  - The Attention message names whichever tier is driving the risk
    (least tolerance among tiers actually present) and its share of
    vCPU demand.
  - New: each tier also carries a `recommended_hypervisor_priority`
    (vSphere CPU Shares/Reservation, Hyper-V VM CPU weight - e.g.
    "High" for Tier-0) surfaced in the same Attention message -
    informational guidance on what to configure for real, not a
    simulation of actual scheduler/contention behavior (which would
    need NUMA layout, real concurrent load, and scheduler internals
    this app has no visibility into).
- Documented in `docs/HOW_THE_MATH_WORKS.md` \u00a72a with a worked
  example matching the exact scenario reported - every number in the
  table was verified against actual code output before being written
  down, catching (and fixing) a mistake in an early draft of the table
  itself (a 1.69 ratio mis-labeled "Warning" when it's actually
  "Critical" at >1.5).
- 12 new tests (the tier-ratio lookup, effective-ratio math across
  all-Tier-0/all-VDI/mixed scenarios, the Attention check firing
  correctly including the dominant-tier and priority-recommendation
  text, and confirming the thresholds are NOT affected by the
  Settings-configurable raw CPU thresholds) - 676 passed total.

## v4.10.0 (Simple/Advanced Mode toggle)

- **New: View > Advanced Mode** - a single checkable menu action that
  hides Clusters (isolated failure domains), Storage Pool assignment,
  and VLAN assignment app-wide, since these are opt-in concepts most
  projects never touch and were adding real mental overhead for a
  simple, single-cluster project. Off by default. Nothing already set
  up is ever lost by toggling this off - Cluster entities, cluster_uid/
  storage_uid/vlan_uid assignments, and VLANs all stay exactly as they
  are; the toggle only controls whether the UI for them is shown.
  - Hides: the Clusters management section and its table column on
    Servers; the Cluster dropdown on ServerDialog; the Storage Pool/
    Cluster/VLAN dropdowns on VMDialog; the "Bulk move Cluster"
    controls, the Cluster/VLAN table columns, and the "Add to Cluster"
    right-click actions on VMs; the whole VLANs section on Network
    (Switches/Connections stay visible either way - more fundamental
    network inventory, not part of this toggle).
  - Persisted as an app-level preference (`~/.clustersizer/
    preferences.json`, same pattern as recent files) - not part of the
    project file, since it's about how the person wants to work, not
    project content.
  - Correctly interacts with lazy tab construction (pages only get
    built the first time their tab is actually visited): toggling
    updates any already-built page immediately, and any page built
    afterward picks up the current saved preference automatically at
    construction time - no extra wiring needed either way.
- **Fixed along the way**: caught and fixed a real ordering bug while
  building this - a page's `refresh()` can reset its table model,
  which would silently undo column-hidden state if that state was set
  before the refresh instead of after.
- 24 new tests covering the preference persistence, every affected
  page and dialog individually, and the full toggle-through-MainWindow
  interaction including the lazy-construction edge case - 664 passed
  total.

## v4.9.1 (Fixed radio button/checkbox indicators app-wide; wizard sizing/positioning; Servers generation step)

Direct feedback from actually running the v4.9.0 wizard - several real
bugs only visible when a real window manager positions/renders the
dialog, not in this environment's offscreen-render screenshots.

- **Fixed app-wide**: radio buttons and checkboxes showed no visible
  checked indicator (no dot, no checkmark) anywhere in the app -
  "mogu klikati po izborima ali se ne vidi selection." Root cause: once
  a stylesheet touches `QWidget`'s own background/color (added for the
  white-input-fields change a while back), Qt silently stops drawing
  the native checked indicator unless it's explicitly styled. Added
  explicit `QRadioButton::indicator`/`QCheckBox::indicator` rules -
  verified with a rendered screenshot showing both a filled radio dot
  and a checked checkbox clearly.
- **Fixed**: the wizard window appeared positioned oddly (off to one
  side) and couldn't be resized to something more reasonable. Given a
  small fixed size instead of a resizable-but-inconsistently-sized one,
  and now explicitly centers itself on its parent window when shown
  rather than leaving placement to the window manager.
- **New: Servers generation step**, the same idea as the VMs step but
  for hardware - unlike VMs (which split an aggregate total unevenly
  sized workloads), real servers are usually bought as identical units,
  so this asks for a server count plus ONE spec (sockets, cores per
  socket, RAM) and creates that many identical servers
  (`server-01`, `server-02`, ...). Optional, defaults to skip.
- 10 new tests (generate_servers, the new wizard page, the fixed dialog
  size, and full Servers+VMs generation together through MainWindow) -
  640 passed total.

## v4.9.0 (New Project Wizard)

- **New: File > New with Wizard** - an optional alternative to plain
  File > New, sitting right below it in the menu. Three quick
  questions instead of an empty project the person has to discover
  Settings/Servers/VMs all separately:
  1. **Sites** - Primary only / Primary + DR / Primary + DR + more
     (extra DR2, DR3, ... sites).
  2. **Hypervisor** - picks one of the existing threshold presets
     (VMware/Hyper-V/Proxmox/etc.), applying it immediately - exactly
     the same effect as "Use This Preset" on Settings, just moved
     earlier in the flow.
  3. **VMs** (optional) - rather than a vague size label with nothing
     concrete behind it (an earlier idea, correctly pushed back on):
     enter a VM count plus total vCPU/RAM/Disk, and that many real VM
     records get created (`vm-01`, `vm-02`, ...), splitting the totals
     evenly across them - remainder from an uneven split distributed
     so the sum always reconstructs the entered total exactly. Rename
     and adjust each one afterward; leave VM count at 0 to skip
     entirely and add VMs the normal way later.
  Cancel at any point leaves the current project completely untouched.
- 30 new tests (the wizard's three pages individually, full navigation,
  the VM-generation math including the remainder-distribution edge
  case, and the full File-menu-to-generated-VMs flow through
  MainWindow) - 630 passed total.

## v4.8.1 (Fixed switch port under-counting on Switch<->Switch links; new network redundancy example)

Found while building the first real example using v4.8.0's Switch<->
Switch connections - port usage looked wrong the moment a switch was
on the "second" side of an inter-switch link.

- **Fixed**: `switch_port_usage()` only checked a connection's
  `switch_uid` field, so a switch referenced via the newer
  `switch_b_uid` (the "second" side of a Switch<->Switch connection)
  wasn't counted at all - silently under-reporting port usage for any
  switch acting as the "B" endpoint on one or more links. A switch
  with real connections on both sides (e.g. a core switch uplinked
  from several access switches AND uplinked to a firewall pair) now
  correctly counts all of them regardless of which side it's on.
  `server_nic_usage`/`storage_port_usage` were never affected -
  neither has a "second" endpoint field.
- **New example**: `scenario_network_redundancy_example.clsz` - 4
  redundant pairs/stacks (core switch HSRP pair, Palo Alto Active/
  Passive firewall pair, a 2-switch access stack, an F5 load balancer
  Active/Standby pair), each with its own dedicated HA-sync/stacking
  link (excluded from port counting) plus the regular data uplinks
  that DO count, wired to 3 servers and a storage array. Verified with
  a real rendered screenshot showing all 4 pairs in 4 distinct border
  colors, and this is exactly what surfaced the port-counting bug
  above.
- 2 new regression tests for the fixed counting logic - 614 passed
  total.

## v4.8.0 (Site removal made discoverable; switch/firewall redundancy pairing with colored borders)

- **Fixed**: removing a site required scrolling down to the Deployment
  Model or Rack Capacity section and noticing a small "\u2715" button
  buried in one of those rows - reported directly as "gdje se briše?"
  since Add Site and Remove Site weren't symmetrically placed. Now a
  "Current sites" chip row sits right in the Sites box, directly below
  Add Site - each site shows as a small chip with its own inline
  remove button (Primary has none, matching the existing rule that it
  can never be removed).
- **New: switch/firewall redundancy pairing.** Two (or more) devices
  that form a redundant set - an HSRP/VRRP switch pair, an Active/
  Passive firewall HA pair (Palo Alto, Fortinet, Cisco ASA, etc. -
  "Firewall" and "Load Balancer" are just `switch_type` values on the
  same `NetworkSwitch` entity, so this works for those identically),
  or an MLAG/VPC stack - can now be tagged with a shared
  `redundancy_group` name and each given their own `redundancy_role`
  (Active / Standby / Passive / Member - the admin's own call, offering
  every common vendor's term rather than picking one canonical word,
  never auto-detected).
  - **Colored border, not a background fill**, per direct request:
    devices sharing the same redundancy_group get a matching-colored
    OUTLINE around their entire row on the Switches table - built a
    custom `QStyledItemDelegate` for this, since standard Qt model
    roles only support cell background/text color, not a border.
    Verified with a real rendered screenshot showing two different
    pairs in two different colors. The color itself is derived
    deterministically from the group name (same rotating palette
    Clusters use) - two switches sharing a group name always match, no
    need to set a color per switch. Caught a real bug before it
    shipped: Python's built-in `hash()` is salted per process
    (`PYTHONHASHSEED`), so the same group name would have gotten a
    different color every time the app restarted - switched to
    `zlib.crc32`, verified stable across actual separate subprocesses
    with different hash seeds.
  - **New: Switch\u2194Switch connections** - `NetworkConnection` only
    supported Server/Storage\u2194Switch before; added an optional
    `switch_b_uid` so the physical/logical link between a redundant
    pair (or a plain inter-switch uplink) can be recorded like any
    other connection, reusing the exact same dialog and port-usage
    machinery.
  - **New: "Dedicated/Proprietary link" checkbox** on a connection -
    for a stacking cable (Cisco StackWise), an HA-sync port, or any
    dedicated interconnect that does NOT consume one of the device's
    declared 1G/10G/etc ports. Excluded from the port-usage/over-commit
    counting, even though Speed/Media can still be filled in for
    reference.
- 24 new tests across the model, persistence (.clsz and CSV, both
  fresh and backward-compatible with older files), the calculation
  layer, both dialogs, and the table's border rendering - 612 passed
  total.

## v4.7.2 (VMs toolbar: clearer labels, one row for both bulk-move actions, the confusing "Assigned" checkbox replaced)

Direct feedback right after using the new Bulk move (Cluster) row from
v4.7.1 - the toolbar area had grown into 4 separate rows with long,
overlapping label text.

- **Fixed the confusing "Assigned" checkbox**: paired with "Apply
  (Selected/All)" buttons, it wasn't clear whether checking it BEFORE
  clicking Apply would create or remove a Failover Assignment -
  reported directly as "ne kužim šta radi." Replaced with an explicit
  "Add" / "Remove" dropdown right next to the site combo - the action
  it will take is stated in plain words, not implied by a checkbox
  state.
- **Combined "Bulk move site" and "Bulk move Cluster" into one row**
  (previously two separate rows) - each keeps its own label, combo,
  and Selected/All buttons, just side by side now instead of stacked.
- **Renamed and shortened labels**: "Bulk edit:" \u2192 "Set Tier:",
  "Failover to:" \u2192 "Set failover:", "Bulk move (Site \u2260 DR
  Protected...)" \u2192 "Bulk move site:", "Bulk move (Cluster -
  isolated failure domain...)" \u2192 "Bulk move Cluster:" - the long
  explanatory text that used to sit inline now lives in each label's
  tooltip instead, shown on hover rather than always taking up space.
  Button text also shortened ("Set Tier (Selected)" \u2192 "Selected",
  "Apply (Selected)" \u2192 "Selected", etc.) since the row's own label
  already gives the context.
- **Investigated, could not reproduce**: a separate report that adding
  a Cluster made Summary's "Sites" count go from 1 to 2. Traced
  `add_cluster()` end to end - it only touches `project.clusters`,
  never `project.site_names` - and a direct reproduction attempt
  showed no change. Most likely explanation: a new project's
  `site_names` already defaults to `["Primary", "DR"]` independent of
  any cluster action (in place since the multi-site work). Left as-is
  pending exact repro steps if a real bug is still suspected.
- 6 new/updated tests covering the Add/Remove combo in both directions
  and the combined row's two independent dropdown+button groups - 584
  passed total.

## v4.7.1 (Fast VM-to-Cluster assignment at scale; ServersPage layout fix)

Reported directly after using the new Cluster feature with ~70 VMs -
editing each VM individually to assign a cluster was far too slow.

- **New: right-click "Add to Cluster (name)"** on the VMs table, one
  entry per existing cluster - select any number of VMs, one click
  assigns them all, one undo step. Same pattern as the existing "Move
  to {site}" and "Assign to Failover ({site})" actions.
- **New: "Bulk move (Cluster)" toolbar row** on the VMs tab, matching
  the existing Site row exactly - a cluster dropdown plus "Move
  Selected to Cluster" and "Move All to Cluster" buttons. Both use the
  existing `bulk_set_vm_fields()` service method, so a 70-VM
  reassignment is one call, one undo step.
- **Fixed**: the new Clusters section (added in v4.7.0) had squeezed
  in between the servers toolbar and the servers table, pushing the
  actual server list down to the bottom of the page - confusing since
  every other tab's main table is the first thing visible. Reordered
  so the servers table comes right after its toolbar as before, with
  the Clusters section now below it, right above the summary cards row.
- **Investigated, could not reproduce**: a report that adding a
  Cluster made the Summary "Sites" count go from 1 to 2. Traced the
  exact code path - `add_cluster()` only appends to `project.clusters`
  and never touches `project.site_names`, and a direct reproduction
  attempt showed no change to site_names after adding a cluster. Most
  likely explanation: a new project's `site_names` already defaults to
  `["Primary", "DR"]` (2 sites) independent of any cluster action, a
  behavior in place since the multi-site work and discussed separately
  before - probably just noticed for the first time here, not caused
  by the cluster addition. Left as-is pending exact repro steps if a
  real bug is still suspected.
- 19 new tests (right-click assignment, bulk toolbar row in both Add/
  Replace-equivalent modes, combo population/selection-preservation,
  no-clusters-yet messaging, and the ServersPage layout order) - 580
  passed total.

## v4.7.0 (Isolated Clusters within a site; generalized import conflicts; HCI workflow; bulk edit)

- **New example**: `scenario_vlan_microsegmentation_example.clsz` - a
  VMware environment with 6 VLAN-based security zones (DMZ-Web incl.
  an F5 BIG-IP VE load balancer, App-Tier, DB-Tier with SQL Server/
  Oracle, Mail, Mgmt-Infra with AD/vCenter/monitoring/backup, and a
  fully isolated Dev-Test zone), 21 VMs distributed realistically
  across them with per-zone IP addressing, 3 ESXi hosts, shared
  storage, and 3-2-1-1 backup - verified through the full pipeline
  (Summary, Attention, VLAN VM-count column, Word report) with zero
  Attention items.
- **New example**: `scenario_multi_cluster_example.clsz` - the exact
  scenario discussed directly: 3 isolated Hyper-V Failover Clusters at
  one site (HV-Cluster-A and HV-Cluster-B, 3 hosts/10 VMs each,
  healthy) plus a small single-host HV-Cluster-Edge deliberately
  oversubscribed at 5:1 - triggers exactly one Attention item (the
  Edge cluster by name), while the site-wide aggregate stays a
  comfortable 0.72:1, completely hiding the problem on its own.
  Verified with a real rendered screenshot: each cluster's own color
  (red/blue/orange) shows correctly in both the Clusters management
  table and the main Servers table's badge column.


A large batch of direct feedback, closing out several longstanding
threads at once.

- **New: `Cluster` entity** - an isolated compute failure domain (a
  vSphere Cluster, a Nutanix cluster, a Proxmox cluster, one of several
  independent Hyper-V Failover Clusters) that a single site can host
  several of side by side (e.g. 6 hosts at Primary split into two
  3-node clusters). Colored, site-scoped, managed from a new "Clusters"
  section above the Servers table (Add/Edit/Delete/Clear All, with a
  real color picker). `Server.cluster_uid` and `VirtualMachine.
  cluster_uid` are new, fully optional references - completely
  separate from Server's existing free-text `cluster_name` field,
  which is unchanged and still what RVTools import populates.
  - Per-cluster CPU/RAM tracking (`cluster_cpu_ratio`, `cluster_ram_ratio`,
    etc.) mirrors the Storage Pool pattern exactly: a site's aggregate
    can look perfectly healthy (proven with a 1:1 site ratio) while one
    specific cluster is critically oversubscribed (8:1) - invisible
    without this.
  - New Attention Needed check flags an over-subscribed cluster by
    name, using the same CPU/RAM thresholds as the ordinary site-wide
    check.
  - Cluster dropdowns on both ServerDialog and VMDialog (same pattern
    as Storage Pool/VLAN assignment), and a new colored "Cluster"
    column on both the Servers and VMs tables (Server's table also
    keeps its original free-text column, now labeled "Cluster Name"
    for clarity, right next to the new one).
  - Fully backward compatible: old projects load with zero clusters
    and empty cluster_uid everywhere, unaffected.
- **New: generalized import-conflict (Add/Replace/Cancel) prompt**,
  extending the pattern already built for Cluster Preparation's
  per-site Add button to every import path in the app: all 7 CSV
  imports (Servers, Storage, VMs, Backup, Maintenance, Switches,
  VLANs), Smart Import, and the actual RVTools import. Replacing VMs
  now correctly cascades to clear any FailoverAssignment records that
  would otherwise point at a deleted VM.
- **New: HCI disk workflow.**
  - FTT-based Usable estimate on StorageDialog (FTT=0/1/2 Mirroring/
    Erasure Coding) - shown only when HCI is checked (the disk-count
    calculator's row disappears in that mode instead, since Raw comes
    from linked servers there, not a manual count).
  - "Create HCI Storage from Selected" on the Servers table - select
    the servers that make up an HCI cluster, one action creates the
    linked Storage entity with Raw auto-computed, validated to reject
    a selection spanning multiple sites.
- **New: generic Bulk Edit** for Servers (right-click "Bulk Edit
  Selected") - a reusable dialog with a checkbox+input per field, only
  checked fields get applied, one undo step for the whole selection
  and however many fields. Fixes the exact reported pain point (wrong
  disk count/size entered on several identical servers) in one action
  instead of editing each server's dialog separately.
- **New: right-click "Assign to Failover"** on the VMs table - select
  one or more VMs, assign them all to a target site's failover pool in
  one action (footprint defaulting to each VM's own current size),
  instead of using the Add Failover Assignment dialog per VM.
- **Fixed**: `Server.hyperthreading_enabled` still defaulted to True -
  now False, consistent with the Cluster Preparation wizard's own HT
  question.
- **Fixed**: the "Show Rack Sizing" toggle on Summary was easy to miss
  - now light green, matching Preview Failover's earlier fix.
- **New: live preset preview** on Settings - selecting a different
  preset immediately fills in the threshold values below, instead of
  only after clicking "Use This Preset."
- 129 new tests across every layer of this batch - 568 passed total.

## v4.6.0 (Quick polish round: HT default, Rack Sizing visibility, live preset preview)

First 3 items from a larger batch of direct feedback - the rest (bulk
edit, generic import-conflict prompts, HCI disk workflow, drag-and-drop
Failover Assignments, a microsegmentation VLAN example) are larger and
follow in subsequent passes.

- **Fixed**: `Server.hyperthreading_enabled` still defaulted to True -
  reported directly as still on despite the Cluster Preparation
  wizard's own HT question already defaulting to off. Now False in
  both the dataclass default and `create_default()`, consistent with
  the wizard.
- **Fixed**: the "Show Rack Sizing" toggle on Summary was easy to miss
  - now light green, matching the same visibility fix already applied
  to Preview Failover.
- **New: live preset preview** on Settings - selecting a different
  preset in the dropdown now immediately fills in the threshold
  spinboxes below, instead of only after clicking "Use This Preset".
  That button now just confirms the already-shown selection (shows the
  "loaded below - click Apply to save" status). Found and fixed a
  real construction-order bug while building this: the initial preset-
  description call ran before the threshold spinboxes existed yet,
  and separately verified the real project's saved threshold values
  still win over any preset preview when the page first opens.
- 6 new tests (HT default, button styling, preset preview across
  construction/selection/confirmation/re-selection) - 468 passed total.

## v4.5.1 (Disk calculator GUI polish, RAID-level Usable estimate, white input fields)

Direct hands-on feedback on v4.5.0's new disk calculators.

- **Fixed**: the Calc button was invisible on both ServerDialog and
  StorageDialog - the calculator row's fields were wide enough to push
  it past the dialog's edge. Widened both dialogs (440\u2192520px),
  shortened labels ("TB each" \u2192 "TB", "Calculate \u2192 Raw" \u2192 "Calc"),
  and capped the spinboxes' width so the button has guaranteed room -
  verified with real rendered screenshots this time, not just widget
  geometry checks (which read "fits" even when a render showed it cut
  off - a real discrepancy in the offscreen test environment worth
  being skeptical of going forward).
- **Fixed**: StorageDialog's calculator did nothing while HCI was
  checked, with no indication why - correctly self-diagnosed directly
  ("valjda jer je HCI i vuče s diskova"). Rather than leaving a
  disabled-but-visible control, the entire "Disk Calculator" row
  (label included) now disappears via `QFormLayout.setRowVisible()`
  while HCI is checked, since Raw is auto-summed from linked servers
  in that mode and the calculator simply doesn't apply.
- **New: RAID-level Usable estimate**, addressing the non-uniform-disk
  case directly (e.g. a ZFS box with 12 disks of mixed sizes) - a RAID
  Level dropdown (RAID 0/JBOD, 1/10, 5, 6) next to the existing disk
  count \u00d7 size calculator. Calc now optionally fills Usable Capacity
  too (e.g. RAID5 = disk count - 1 disks' worth), but - consistent with
  every other calculator in this app - Usable stays the real, stored,
  independently-editable value afterward, so a real non-uniform number
  can always override the estimate directly, exactly as requested.
  New `Storage.raid_level` field (persisted, CSV-optional, defaults to
  "" = no estimate offered, Calc only fills Raw as before).
- **New: white input fields.** Every widget the person types or picks
  a value into (text fields, spin boxes, dropdowns) now has a white
  background, distinct from the app's gray - disabled fields get a
  subtle gray-out instead. Direct request: "app ostane siv, ali polja
  koja omogućuju unos neka budu bijela."
- 23 new tests (RAID formula, GUI row-hiding, Usable-stays-editable
  after estimate, persistence, backward compat) - 462 passed total.

## v4.5.0 (Storage: disk-count calculators, per-pool VM assignment, and the bug that started it)

Prompted directly by a real RVTools import + manual HCI setup: a newly
created "VSAN" Storage entry with 48TB Raw simply didn't show up
anywhere on Summary. Root cause (not a bug): every capacity check in
the app uses Usable, never Raw, and Usable had been left at 0 (its
deliberate reset-on-HCI-checked default from v3.6.1, meant to force a
real number rather than a misleading stale one - but nothing stopped
saving before actually filling it in).

- **New Attention Needed check**: a Storage entity with Raw capacity
  entered but Usable still 0 is now flagged by name - would have caught
  this exact situation immediately instead of a silent no-show on
  Summary.
- **New: disk count \u00d7 size calculators** on both ServerDialog (local/
  HCI disk) and StorageDialog (works for traditional arrays AND HCI
  alike, per direct request - "for all"). Fills the existing Raw field
  as a one-time convenience; Raw stays the real, independently-editable
  stored value afterward (not a live-bound formula) so spares/rounding
  can still be adjusted by hand. The Storage calculator button disables
  itself while HCI is checked, since that field is auto-summed from
  linked servers instead - using the calculator there would silently
  override the auto-sum.
- **New: per-pool storage assignment.** A VM can now be assigned to a
  SPECIFIC Storage entity (`VirtualMachine.storage_uid`, a new optional
  field on the VM dialog labeled "Storage Pool" - same pattern as VLAN
  assignment exactly, including graceful fallback to "(none)" if the
  referenced storage is later deleted). When unset (every project
  before this, and any VM that doesn't need this), disk demand counts
  toward the site-wide aggregate exactly as it always has - fully
  backward compatible, purely opt-in. `ClusterProject.
  storage_pool_demand_gb()`/`storage_pool_utilization_ratio()` compute
  the assigned-VM demand against one specific pool's usable capacity.
- **New: "Pool Utilization" column on the Storage tab**, showing each
  entity's own assigned-VM demand vs. its usable capacity, colored and
  marked using the same Warning/Critical thresholds as the site-wide
  check. Demonstrated directly: two 10TB pools at one site, one at 88%
  from its assigned VM and one at 5% - the site-wide aggregate reads a
  comfortable ~46% the whole time, completely hiding that Pool A is
  nearly full. The Storage page now also refreshes on VM changes (it
  previously only listened for storage/network changes), since this
  column depends on VM-to-pool assignments.
- **New Attention Needed check**: a storage pool whose assigned-VM
  utilization crosses into Warning/Critical is flagged by name, using
  the exact same thresholds as the ordinary site-wide storage check -
  the whole reason this feature exists, surfaced automatically rather
  than requiring a trip to the Storage tab to notice.
- Fixed the reported project directly: the "VSAN" entry now has a real
  Usable Capacity entered.
- 45 new tests across the three new model fields (Server/Storage disk
  calculators, VM storage_uid), the two new ClusterProject methods, two
  dialog calculators, the VM dialog's Storage Pool dropdown, the
  Storage table's new column plus its live-refresh wiring, and both new
  Attention Needed checks - 452 passed total.

## v4.4.0 (Cluster Preparation wizard overhaul - a real bug found live, plus 6 requested improvements)

Prompted by hands-on testing of the wizard with a real 15-VM/120-vCPU
scenario, which surfaced a genuine calculation bug alongside a batch of
concrete workflow requests.

- **Fixed a real bug**: `failover_cpu_ok()` compared raw physical cores
  against raw vCPU demand (`physical_cores >= vcpu_demand`) - effectively
  requiring near 1:1 CPU provisioning, flagging a perfectly healthy
  3.75:1 oversubscribed Primary site as "does not have enough capacity
  for its assigned failover VMs." Now uses the same Warning/Critical
  ratio thresholds as ordinary CPU status. Threaded `Thresholds` through
  `failover_cpu_ok`/`failover_ready`/`build_failover_report` and all 4
  call sites (Summary, Reports, Attention, Word report).
- **Fixed**: Effective Cores showed the same number as Total Cores when
  Hyperthreading is off (redundant/confusing) - now shows "-".
- **Fixed**: ResultPage had no scroll area, so its hypervisor-CPU-
  reservation warning was silently clipped off-screen - confirmed via a
  real screenshot showing the text cut off entirely.
- **Fixed**: clicking "Add Recommended Cluster" gave no visible
  confirmation - the old code appended text to the SAME already-
  overflowing label, compounding the scroll bug above. Now a real
  QMessageBox stating plainly that nothing is saved until Finish.
- **New: a real, configurable hypervisor CPU reserve.** Previously only
  a warning NOTE, never actually subtracted from capacity - `Sizing
  Policy.hypervisor_cpu_reserve_cores` (default 2 physical cores/host,
  0 to disable) is now applied in both the optimizer and the final host
  count, scaling correctly with Hyperthreading.
- **New: Hyperthreading question moved to the Policy page**, asked
  upfront rather than only discoverable as a post-hoc edit on Result -
  defaults to OFF (HT gains vary by workload, so sizing without relying
  on it is the safer starting point).
- **New: manual aggregate demand entry** for a brand-new environment
  with no VMs entered yet - a "no VMs yet" box on the Workload page
  accepts total vCPU/RAM/disk plus one workload tier for the whole
  total, sized exactly like real VM data (growth, reserve, ratio, all
  applied identically). Ignored automatically the moment real VMs
  exist. Found and fixed two bugs in an earlier, incomplete pass at
  this feature before shipping it: `total_storage_demand_gb` was only
  set in the manual-demand branch (NameError for every normal call),
  and `required_hosts` didn't check for manual demand at all (always 0
  hosts in that mode).
- **New: existing-equipment Add/Replace/Cancel prompt** - if the target
  site already has servers/storage when adding a recommended cluster,
  asks whether to add alongside, replace, or cancel, instead of
  silently double-provisioning.
- **New: N-site recommendations**, not just a fixed Primary+DR pair.
  `compute_site_recommendation()` sizes ANY site, driven by DR Category
  selection (Core/Important/Standard/Non-Essential, default Core+
  Important) rather than requiring FailoverAssignment records to
  already exist - matches how a real DR conversation actually goes
  ("everything except DWH and test/dev"). A new "Additional Sites" page
  shows one block per non-Primary site in `project.site_names`; adding
  a site's recommended cluster ALSO auto-creates a FailoverAssignment
  for each qualifying VM (defaulting to the VM's own current size),
  reusing Primary's host spec for consistent hardware. The older DR-
  specific fields (driven by pre-existing FailoverAssignment records)
  are unchanged and still work, kept alongside this rather than
  replaced, to avoid destabilizing already-tested code for a
  fixed-DR-only workflow some users may already rely on.
- **New: optional Backup page** - a mini-form (name, site, type,
  software, capacity, dedup, offsite/immutable, location) with an Add
  button that queues it and resets the form for the next one, so a
  typical local-plus-offsite-immutable pair takes two quick fills
  rather than leaving the wizard and using the Backup tab separately.
- 47 new tests across the calculation layer, the two newly-discovered-
  and-fixed bugs, and five new/updated real-Qt GUI test files - 414
  passed total.

## v4.3.1 (CSV import rejected valid older files over newer optional columns)

- **Fixed**: CSV import validation checked for EVERY known column
  (including newer optional ones like VM's `dr_category`, Server's
  `serial_number`/`bmc_ip`/`hypervisor_vendor`/`hypervisor_version`,
  Backup Destination's `location`) - so a perfectly valid CSV exported
  by an older ClusterSizer version, simply missing a column that
  didn't exist yet when it was made, got rejected outright with "This
  doesn't look like a VMs CSV." Reported directly, and it raised a
  real, important question about version compatibility generally: the
  validation was stricter than the actual parsing it was guarding -
  every `import_*()` function already tolerated a missing optional
  column via `row.get(field, default)`, so only the schema-CHECK
  needed fixing, not the import logic itself.
  - Each entity type now has a small `_CORE_FIELDS` list (e.g. VMs:
    name/site/vcpu/ram_gb/disk_gb) - the minimal, foundational columns
    that genuinely distinguish "this is a VMs CSV" from "this is a
    Servers CSV," and are very unlikely to ever change. Only these are
    validated; everything else is optional exactly as the parsing
    layer already treated it. The original wrong-file-type protection
    (e.g. importing a Servers CSV on the VMs tab) still works -
    verified directly, since it's exactly what this mechanism exists
    to catch.
  - **On the broader question this raised - what happens to an older
    PROJECT (`.clsz`) on a newer version**: unlike CSV, `.clsz` already
    has real, deliberate version handling and always has, going back to
    the v6-to-v7 pricing migration - a schema_version number, and every
    field read tolerates missing/renamed data with an explicit
    migration path when the shape actually changed (e.g. v4.0.0's
    Primary/DR-to-site-list, or the dr_protected-to-FailoverAssignment
    migration). No one loses project work moving to a newer version.
    CSV import just hadn't received the same discipline until now -
    it's a much simpler, flatter format with no version number of its
    own, and its schema check had drifted stricter than the parsing
    layer, so a project made in v4.1 will fully re-open in whatever
    version comes after this one.
- 14 new tests: one per entity type confirming a missing NEWER optional
  column still imports, plus two confirming a missing CORE column (a
  genuine wrong-file-type mistake) is still correctly rejected - 362
  passed total.

## v4.3.0 (Critical: Reports tab crashed on every use since v4.0.0; all examples now backup-compliant)

- **Fixed a severe regression that had zero test coverage**: reports_page.py's
  `_build_report_text()` still unpacked `build_reports()` as a fixed
  `primary, dr, dr_check` 3-tuple - but v4.0.0's multi-site refactor
  changed that function to return a `dict` keyed by site name months
  ago. Every single time the Reports tab was shown, refreshed, or a
  new project was loaded while it already existed, this raised
  (`ValueError: not enough values to unpack`, then cascading into
  `AttributeError` on the next redraw) - reported directly as "loaded
  several example files in a row and nothing happened after the
  first." Reports had NO test file at all before this, which is
  exactly how something this broken went undetected through v4.0.0,
  v4.1.x, and v4.2.x. Rewritten to loop over `project.site_names`
  generically, matching the same approach already used in the Word
  report - now also includes Rack Sizing and Failover Assignment data
  per site, which the text report never had before at all.
  - Re-verified every tab + two sequential project loads produces zero
    exceptions, not just Reports specifically.
  - 5 new tests, including the exact reported scenario (Reports page
    already open, then a different project gets loaded).
- **Fixed backup compliance in the 3 examples that had none**:
  `scenario_vsan_example.clsz` and `scenario_stretched_vsan_3site_
  example.clsz` had zero Backup Destinations at all (added a local
  Veeam repository plus an offsite immutable copy to each), and
  `scenario_draas_example.clsz` had only one (added a second, Cloud-
  type Azure copy, matching its own DRaaS theme) - all 7 example
  projects are now genuinely 3-2-1-1 compliant with zero Attention
  Needed items related to backup.

## v4.2.2 (ServerDialog missed the dynamic-sites fix - found and fixed)

- **Fixed**: ServerDialog's site dropdown was still hardcoded to
  Primary/DR only - reported directly ("2 servers on Primary, 3 on DR,
  3 should go on DR2, but DR2 isn't in the list when editing a
  server"). Root cause: back in v4.0.0's audit of every dialog with a
  hardcoded site list, the search pattern was a single-line literal
  (`["Primary", "DR"]`) - ServerDialog's was written across multiple
  lines with a trailing comma, a formatting variant that search missed
  entirely. Now takes a `sites` parameter and is wired from
  ServersPage exactly like the other 7 dialogs fixed back then
  (StorageDialog, SwitchDialog, VlanDialog, BackupDestinationDialog,
  VMDialog, RVToolsImportDialog, ImportWizardDialog).
- **Re-audited every dialog, page, and widget file** (not just the
  original single-line grep) for any other literal "Primary"/"DR"
  occurrence, to make sure nothing else was hiding behind a formatting
  difference. Found two more hits, both confirmed as the Cluster
  Preparation wizard's already-documented, deliberate Primary+one-DR
  scope limit (not a bug) - nothing else was missed.
- 4 new tests (ServerDialog with a 3-site list, its Primary/DR
  fallback, and ServersPage's Add/Edit call sites, verified by
  spying on the constructor rather than actually opening a modal
  dialog in the test).

## v4.2.1 (Fixed the multisite example's missing backup; no blanket "dismiss" for Attention)

- **Fixed**: `scenario_multisite_example.clsz` had zero Backup
  Destinations - the same class of oversight as the storage gap fixed
  in v4.2.0, just the next thing the example was missing. Added a
  local Veeam repository on Primary plus an offsite, immutable copy on
  DR - now genuinely 3-2-1-1 compliant, zero Attention items.
- **Deliberately declined**: a general "acknowledge/dismiss" option for
  every Attention Needed item, considered after the backup gap above
  first looked like it needed one. The FailoverAssignment acknowledge
  feature (v4.2.0) works because it attaches to one concrete,
  addressable record and resolves a genuinely AMBIGUOUS situation (a
  larger DR footprint could be a mistake or a deliberate choice - both
  are plausible). "Zero backup destinations," like CPU/RAM Critical or
  a failed N+1 check, isn't ambiguous - it's a real, unresolved risk
  the app is designed to keep surfacing until it's actually fixed. A
  blanket per-item dismiss button would let any of these be silenced
  and forgotten, undermining the whole point of the panel - matching
  why no override exists anywhere else in the app for N+1 or
  oversubscription status either. Fix the underlying gap instead of
  suppressing the warning about it.

## v4.2.0 (Acknowledge stale failover footprints; storage-gap detection; Preview Failover made visible)

- **Preview Failover button styled orange** on Summary - reported as
  "well hidden" as a plain default-styled button sitting among the
  other controls.
- **New: acknowledge an intentionally larger failover footprint.** The
  stale-assignment warning added just before this (an assignment
  exceeding the VM's current size) couldn't tell "forgotten update"
  apart from "deliberately over-provisioned warm standby." Right-click
  → Acknowledge on the Failover Assignments table (VMs tab) sets a new
  `footprint_confirmed` flag on that assignment - silences both the
  Attention Needed warning and the table's orange marker for exactly
  that assignment. Un-acknowledge reverts it. Does NOT reset
  automatically if the numbers change again later, by design - simpler
  and more predictable than guessing whether a change was "big enough"
  to need re-confirming. No new file or storage mechanism needed - it's
  one boolean field on the FailoverAssignment record that already gets
  saved with everything else; a missing field on an older file just
  defaults to `False` via the existing tolerant loader, no migration
  required.
- **New: flag real VM disk demand with zero storage capacity anywhere**
  as Critical - found directly from a real project (a full 3-site
  scenario with substantial VM disk demand and not a single Storage
  entity or server-local disk entered anywhere). Deliberately distinct
  from the ordinary storage-status "Unknown" case, which stays silent
  for a genuinely empty, not-yet-started site - the new check only
  fires when there's real demand (disk_demand_gb > 0) with nothing to
  check it against, a genuine blind spot rather than "haven't started
  yet."
- **Fixed the example that surfaced this**:
  `scenario_multisite_example.clsz` had 3.4TB of VM disk demand across
  7 VMs and no storage anywhere - added a Pure Storage array per site,
  sized comfortably above each site's real/failover demand.
- 12 new tests across the model, ProjectService, the table model
  (column-specific marker + acknowledge), the Attention aggregation
  (both new checks, plus confirming a healthy-project test itself had
  been missing storage), and the VMs page's right-click action - 345
  passed total.

## v4.1.2 (Settings: field widths, and the real cause of "settings changing themselves")

- **Fixed**: every combo/spin box on Settings stretched to fill the
  full window width (`QFormLayout`'s default field growth policy).
  Reported directly from a screenshot - now `FieldsStayAtSizeHint` on
  all 5 form layouts, so each field is only as wide as its content
  (e.g. "On-Premise") and stays left-aligned, leaving the rest of the
  row empty and clickable-through to the page behind it.
- **Fixed the actual root cause of "I scrolled up and down and it
  changed Deployment Model and the oversubscription settings"**: Qt
  lets a combo/spin box under the mouse cursor consume a wheel-scroll
  event and change ITS value instead of scrolling the page underneath
  it - with no click or focus needed at all. A request for a Settings
  "Cancel" button would have papered over this rather than fixed it
  (and would have interacted awkwardly with the existing per-change
  undo system, which already reverts each of these edits one at a
  time via Ctrl+Z). Instead, every input on the page now ignores wheel
  scroll unless it already has keyboard focus (click or Tab into a
  field first to intentionally scroll its value) - verified the
  accidental-change path is blocked while normal interaction (click,
  keyboard, programmatic set) is untouched.
- 4 new tests (field growth policy, wheel-without-focus on both a
  dynamic Deployment Model combo and a static threshold spinbox, and a
  regression check that real interaction still works).

## v4.1.1 (Settings page scroll fix - real bug reported from a screenshot)

- **Fixed**: SettingsPage had no scroll area at all, same class of
  problem already fixed on SummaryPage and the entity dialogs. It went
  unnoticed until now because the page used to be short enough to fit
  most windows - v4.0.0 added the Sites section and made Deployment
  Model/Rack Capacity dynamic per site (each site adds a row to both),
  so a project with even one extra site (very much the point of this
  app now) pushes the page well past a typical window's height.
  Reported directly with a screenshot showing word-wrapped note labels
  rendering cut off/overlapping - worse than simple clipping, since
  Qt's layout was squeezing labels into less vertical space than their
  wrapped text needs rather than just hiding the overflow. Reproduced
  exactly (a 3-site project needs 1078px of content in a 500px window)
  and confirmed fixed with an actual rendered screenshot, not just
  code inspection.
- 1 new regression test.

## v4.1.0 (Three new example projects, exercising v4.0.0's multi-site features)

- **`scenario_stretched_vsan_3site_example.clsz`** - vSAN stretched
  across 3 sites (4 HCI hosts each), a 100G DWDM full-mesh backbone
  (3 pairwise NetworkConnections between each site's core switch), and
  3 independent Fortinet firewalls in an active-active-active mesh
  (documented in each firewall's notes, since ClusterSizer doesn't
  model firewall-to-firewall replication protocols directly - real
  workloads run at all 3 sites, with 2 of them explicitly failover-
  assigned to both other sites.
- **`scenario_hyperv_core_dr_example.clsz`** - a 3-host Hyper-V Primary
  (2x24 cores/512GB each, 20 VMs sized across all 4 DR Categories) with
  a deliberately smaller 2-host DR that only receives the 5 Core /
  Mission-Critical VMs via Failover Assignments - everything else
  (Important/Standard/Non-Essential) stays Primary-only. Commvault
  backs up to a Primary NAS, replicated to DR as an immutable Auxiliary
  Copy - verified 3-2-1-1 compliant.
- **`scenario_hyperv_azure_dr_example.clsz`** - the same Primary layout
  and same 5 Core VMs as the previous example, but DR is a Cloud site
  (Azure) instead of physical hardware - no servers there at all,
  matching how every other Cloud-flagged site in this app behaves
  (Rack Sizing shows "Cloud", and failover readiness correctly reports
  "not applicable" rather than a false Critical, since there's no
  physical capacity to check against elasticity). Backup adds a Cloud-
  type destination (immutable Azure Blob copy) alongside the same
  on-prem Commvault/NAS setup, with its recurring monthly cost tracked
  as a Maintenance Item - same pattern as the DRaaS example from
  v3.5.0, rather than inventing a second pricing model on Backup
  Destination itself.
- All three verified through the full pipeline (Summary, Word report,
  backup compliance, rack sizing) before saving - no new test files,
  since these are example DATA, not code, but every save was validated
  against the real calculation/report functions rather than trusted
  blind.

## v4.0.0 (Multi-site support - configurable sites, per-site failover assignments)

The big one deferred from v3.10.0's equipment-inventory review: some
organizations (banks especially) run 3+ sites, not just Primary/DR.
"Primary"/"DR" were hardcoded throughout nearly every layer of the app
before this - every dropdown, every calculation signature, the Summary
page's fixed two-card layout, the whole DR Readiness/failover concept.
Genuine N-site support meant a foundational model change, not a field
addition - touched close to 30 files.

- **Sites are now a real, editable list** (`project.site_names`,
  default `["Primary", "DR"]` so every existing project loads
  unchanged) instead of two hardcoded string constants. Add/remove
  sites from Settings - Primary can never be removed (too much of the
  app assumes it always exists as "the main site"), and a site still
  referenced by any Server/Storage/VM/Switch/Backup Destination/VLAN/
  Failover Assignment can't be removed either, until those are
  reassigned or deleted first.
- **Deployment Model and Rack Capacity became per-site lookups**
  (dicts keyed by site name) instead of the `primary_X`/`dr_X` field
  pairs introduced in v3.6.0/v3.10.0 - those simply didn't scale past
  two sites.
- **New: FailoverAssignment** - replaces VM's old `dr_protected`/
  `dr_vcpu`/`dr_ram_gb`/`dr_disk_gb` fields entirely. The failover
  model discussed at length turned out to be simpler than initially
  proposed: no fixed "failover target," no per-VM footprint filtering
  by category - just an explicit, standalone list (VM -> target site,
  with its own vCPU/RAM/disk footprint) that someone fills in
  deliberately. The same VM can appear in several rows (one per target
  site) with a DIFFERENT footprint on each - a bank's core VM might
  need less on a budget DR2 than a full-size DR. Managed centrally in
  a new **Failover Assignments** table on the VMs tab (same pattern as
  Switches/Connections/VLANs on the Network tab), plus a target-site-
  aware bulk toggle (checkbox + site combo + Apply Selected/All) for
  quickly assigning many VMs at once.
  - **New: VM DR Category** (Core / Mission-Critical, Important,
    Standard, Non-Essential - editable combo, type your own for a
    specific compliance framework's categories e.g. NIS2). Purely
    informational - deliberately does NOT gate what can be assigned in
    Failover Assignments, confirmed directly rather than assumed.
  - Every readiness/capacity calculation generalized from "Primary vs.
    DR" to "any site vs. its assigned failover load": `failover_ready
    (site)`, `failover_vcpu_demand(site)`, etc. on ClusterProject; the
    old fixed `DRReport` became a generic `FailoverReport`; `build_
    reports()` now returns a dict keyed by site name instead of a
    fixed 3-tuple.
- **Summary page**: one capacity card per site (2 per row, so Primary/
  DR still land side by side as before - additional sites just form
  further rows in the same size/style, per direct suggestion for
  keeping the layout change simple). Each card shows a new, minimal
  "VMs Assigned (Failover): N [OK/Warning/Critical]" row rather than a
  full data dump - the detailed numbers live in the Failover
  Assignments table and the Word report. "Preview Failover" now
  applies to every site's card at once. Also fixed: SummaryPage had no
  scroll area at all (found while building this - a page with several
  site cards plus a long Attention list can exceed a typical window's
  height).
- **Word report**: loops over every site in `project.site_names`
  instead of a hardcoded Primary/DR pair - confirmed by adding a third
  site to a test project and regenerating with zero code changes
  needed for that site to appear correctly.
- **Every dialog with a site dropdown** (Server, Storage, Switch, VM,
  Backup Destination, VLAN, RVTools Import, CSV Import Wizard) now
  populates from the project's actual site list instead of a hardcoded
  pair - 8 call sites across 7 files. Found and fixed a real bug in
  the process: Import Wizard's site combo referenced an out-of-scope
  local variable inside a separate `_build_ui()` method (a `NameError`
  waiting to happen) - caught by writing the dynamic-sites test for it.
- **Full migration for existing files**: an old project's `primary_
  deployment_model`/`dr_deployment_model` and `primary_rack_capacity_u`/
  `dr_rack_capacity_u` migrate into the new per-site dicts automatically.
  Critically, any VM with `dr_protected=True` becomes exactly one
  FailoverAssignment targeting DR, preserving its old DR footprint
  numbers - verified against a simulated old-format file to confirm
  nothing is silently dropped. Schema bumped to v8.
- **New example**: `scenario_multisite_example.clsz` - a 3-site bank
  scenario (Primary + DR + DR2, 2 large Primary hosts vs. 3x smaller
  hosts per DR site, matching the exact numbers discussed), 7 VMs
  tagged across all four DR Categories, and Failover Assignments to
  both DR sites for everything except the DWH and test-environment VMs
  - mirroring "sell everything except DWH and test/dev, since the
  business can tolerate losing those for a while."
- 62 new/rewritten tests across the model, persistence/migration, and
  GUI layers (FailoverAssignmentDialog, its table model, VMs-page
  integration, dynamic-sites coverage for all 7 dialogs, plus updates
  to every pre-existing test that touched a removed field or method) -
  325 passed total.

## v3.10.0 (Server inventory fields, Backup Cloud/Location, Rack Capacity)

From a direct equipment-inventory review - "have we covered what an
admin actually needs to track?" - across Servers, Backup, and rack
planning. A fourth item from the same review (supporting more than two
sites - some banks run 3+ DCs) was deliberately deferred: "Primary"/
"DR" are hardcoded throughout nearly every layer of the app (every
dropdown, every calculation signature, the Summary page's fixed
two-card layout, the whole DR Readiness/failover direction), so genuine
N-site support is a foundational redesign, not a field addition - it
needs its own dedicated discussion, not to be bundled in here.

- **Server gains four inventory fields**: Serial Number (asset/service
  tag, for support tickets and RMA), BMC/Management IP (out-of-band
  iLO/iDRAC/BMC address, separate from the main OS-facing IP - ties in
  naturally with the VLAN work from v3.9.0, since this is exactly the
  kind of thing that lives on its own management VLAN), and Hypervisor
  vendor + version. `HYPERVISOR_VENDORS` deliberately mirrors the
  Settings page's oversubscription preset labels (VMware/Hyper-V/
  Proxmox/Nutanix/Citrix) for consistency, but is kept as its own
  separate list rather than imported from `thresholds.py` - one drives
  ratios, the other is just descriptive inventory, and they shouldn't
  be coupled to each other. An unrecognized/legacy hypervisor_vendor
  value (e.g. from an older save, or a discontinued option) falls back
  to the blank entry rather than crashing the dialog.
- **Backup Destination gains a "Cloud" destination type** and a new
  free-text `location` field (e.g. "Azure Blob Storage - West Europe",
  "Iron Mountain Vault Zagreb"). Deliberately free text rather than a
  fixed enum, per direct request - Site (Primary/DR) doesn't capture
  which cloud region or which specific offsite facility, and there's
  no reasonable fixed list of every provider/facility a customer might
  use. Recurring cloud storage cost is tracked via Maintenance Items
  (same pattern already used for the DRaaS subscription example) -
  Backup Destination itself keeps its single one-time `price` field
  rather than gaining a second pricing model.
- **New: Rack Capacity, per site** (Settings page, applied immediately -
  same UI pattern as Deployment Model). Separate from Rack Sizing,
  which only totals what's been *entered* on Servers/Storage/Switches -
  this is how much is *available*. `RackSizingSummary` gained
  `capacity_u` and an `over_capacity` property (only meaningful once
  capacity is actually entered - 0/not-entered never counts as "over",
  regardless of how much is used). Summary page and the Word report
  both show "12 / 84 U" once capacity is set, with a red "\u26a0 ...
  (over capacity)" warning when equipment exceeds it - DR intentionally
  supports its own smaller number, since a DR rack is very often
  physically smaller than Primary in practice.
- Updated `scenario_full_example.clsz` with realistic values throughout
  rather than a separate example file: serial numbers/BMC IPs/
  hypervisor details on all three servers, fixed a naming mismatch that
  predates this feature (a destination literally named
  "cloud-immutable" was typed as "Offsite" before "Cloud" existed as an
  option - corrected, plus added a location), and set Primary/DR rack
  capacity (42U/12U - DR deliberately smaller, matching the point that
  prompted this feature).
- 34 new tests across the model/persistence/CSV layer and five real-Qt
  GUI test files (ServerDialog, BackupDestinationDialog, SettingsPage,
  SummaryPage, the Word report) - 294 passed total.

## v3.9.0 (VLANs - network segments; Summary tab scroll fix)

- **New: VLANs.** Closes the long-open "RVTools Folder" question from
  much earlier - RVTools' Cluster is the whole virtual environment
  (already captured as `Server.cluster_name`), but within that
  environment VMs can be split into network segments (RVTools'
  vNetwork sheet's "Network" column, i.e. the portgroup/VLAN a VM
  connects to). Modeled as `Vlan` (name, site, network e.g.
  "192.168.10.0/24", gateway, notes) - a project-level, site-scoped
  list, deliberately NOT owned by a specific NetworkSwitch, since a
  real VLAN is a logical construct that commonly trunks across several
  physical switches rather than belonging to just one (confirmed
  directly rather than assumed, given the user's own phrasing could
  have been read either way). Managed on the Network tab, in a third
  section alongside Switches and Connections.
  - **VMs get an optional VLAN dropdown**, deliberately independent of
    IP Address - assigning a VM to a VLAN never requires also entering
    an IP, per direct request. Multiple VMs can share one VLAN. A
    VM's `vlan_uid` pointing at a since-deleted VLAN falls back to
    "(none)"/"-" everywhere rather than crashing.
  - Deleting a VLAN (or Clear All) clears `vlan_uid` on every VM that
    referenced it - the VM itself is never deleted, just unassigned -
    and is fully undoable in one step along with the VLAN removal
    itself.
  - VLAN table's VM-count column is live (counts matching `vlan_uid`
    across the project's VMs on every refresh) - not a stored/stale
    number that could drift from the real assignments.
  - `vlan_uid` deliberately excluded from the VM CSV schema (same
    precedent as StorageShelf/hci_server_uids) - a re-imported VLANs
    CSV generates fresh UIDs, so a stored cross-reference would go
    stale immediately. Full support via `.clsz` and the GUI. RVTools
    import still doesn't set this automatically - stays a manual
    assignment, per direct request.
  - Added a representative 3-VLAN scenario (DMZ/Management/Backend) to
    `scenario_full_example.clsz`, assigned to the existing web-*/dc-*/
    db-* VMs by name pattern, rather than inventing a whole new example
    file for this.
- **Fixed**: SummaryPage had no scroll area at all - found while
  double-checking the brand new Attention Needed panel (v3.8.0) could
  grow past a typical window's height with no way to reach the rest of
  the page, the same class of problem already fixed on the entity
  dialogs earlier. Wrapped the page content in a QScrollArea the same
  way; verified with a 20-item Attention list stress test.
- 36 new tests across the model/persistence/CSV layer, ProjectService
  CRUD (including the cascade-clear-on-delete behavior and its undo),
  and five real-Qt GUI test files (VlanDialog, VlanTableModel,
  VMDialog's dropdown, VMTableModel's column, NetworkPage's
  integration) - 264 passed total.

## v3.8.0 (Attention Needed panel - Summary tab)

- **New: "Attention Needed" panel** at the bottom of the Summary tab.
  Pulls together every existing "is something wrong" status already
  computed elsewhere in the app - CPU/RAM/Storage oversubscription,
  N+1, DR Readiness, backup 3-2-1-1 compliance, Maintenance Item
  expiry - into one severity-sorted list (Critical before Warning), so
  a periodic project review doesn't require clicking through 4-5
  different tabs to see if anything needs attention. Shows a plain
  "No issues found" when everything's fine. Deliberately adds no new
  calculations of its own (`src/calculations/attention.py` only
  selects and formats what sizing.py/backup.py/pricing.py already
  compute) and skips the backup-compliance check entirely for a
  project with no VMs yet, so a brand new project doesn't get nagged
  about having no backup destinations before there's anything to back
  up. Refreshes live via the existing `service.changed` signal, same
  as the rest of the Summary tab.
  - Testing this against the project's own long-running example
    surfaced a genuine, pre-existing finding: `scenario_full_example.
    clsz` has drifted to 200% RAM oversubscription on Primary (1026GB
    demand vs 512GB physical) somewhere across this project's many
    revisions - exactly the kind of thing this panel exists to catch
    without having to go looking for it.
- 18 new tests: 12 for the pure aggregation logic (empty/healthy
  projects, each status source flagged correctly, the no-VMs backup
  guard, severity sorting), 4 for the panel widget itself, 2 for its
  live-refresh wiring into SummaryPage - 226 passed total.

## v3.7.0 (Recent Files; two real HCI dialog bugs found from live testing)

- **New: Recent Files** (File menu) - remembers the last 5 opened/
  saved project paths, most-recently-used first, persisted to
  `~/.clustersizer/recent_files.json` (same app-data directory the
  crash log already uses - separate from any .clsz project). Rebuilt
  every time the submenu is about to show, so it's always current
  within the same session too. Re-opening/re-saving a file already in
  the list bumps it to the front rather than duplicating it. Opening
  an entry whose file no longer exists shows a clear message and
  removes it from the list automatically rather than leaving a dead
  entry behind. "Clear Recent Files" included. Deliberately does NOT
  track Save Scenario Copy As - that saves a comparison snapshot, not
  something meant to become the active project again via a quick
  reopen.
- **Fixed two real bugs in the Storage dialog's HCI section**, found
  from live use after the v3.6.1 fixes shipped:
  - **Raw Capacity could still be nudged via the spinner arrows or
    mouse wheel while HCI was checked**, despite being meant to be
    fully auto-computed and locked. Root cause: `setReadOnly()` on a
    QDoubleSpinBox only blocks keyboard typing in Qt - it does NOT
    block the up/down step buttons or wheel scrolling. Switched to
    `setEnabled()`, which properly blocks all real user interaction
    (confirmed the distinction matters: calling `.stepUp()` directly
    in Python bypasses Qt's input layer entirely either way, so that
    alone can't tell the two apart - the real difference is in actual
    mouse/keyboard interaction, which `setEnabled()` correctly locks).
  - **Usable Capacity stayed stuck at its 80.0 default** (sized for a
    traditional array, from before HCI existed) even after Raw
    Capacity auto-summed to something much smaller from real servers
    (e.g. 0, or 32 after adding local disk) - silently describing a
    physically impossible usable-exceeds-raw array. Now resets to 0.0
    the moment HCI is freshly checked, but ONLY if it's still sitting
    at the untouched 80.0 default - never clobbers a value the user
    (or a previously saved project) actually set, verified specifically
    for the edit-existing-HCI-storage case where the real saved value
    loads moments after the same toggle fires.
- 13 new tests: 8 for Recent Files persistence, 5 for its MainWindow/
  menu integration (missing-file handling via a mocked QMessageBox,
  since a real one would block waiting for a click in a test), plus 4
  for the two dialog bugs (one superseding an old test that had been
  asserting the ineffective `isReadOnly()` check) - 208 passed total.

## v3.6.1 (HCI list scrolling, RAM rounded to known configs, finer spinbox steps)

- **Fixed**: the Storage dialog's HCI "Linked Servers" checklist only
  showed ~2 servers at once with no visible way to scroll, found using
  a real 4-server vSAN cluster - `setMaximumHeight(120)` plus the
  default "as needed" scrollbar policy meant the scrollbar was easy to
  miss sitting inside the dialog's own outer scroll area, forcing arrow
  keys to reach the rest of the list. Now `setMinimumHeight(160)` (fits
  ~7 servers without scrolling) with `ScrollBarAlwaysOn` so it's
  discoverable once there are more than that.
- **New: `round_up_to_known_ram_gb()`** in the RVTools importer. Found
  investigating a real report: RVTools showed 383.7GB host memory for
  hosts confirmed to have 256GB of physical DIMMs installed - checked
  and ruled out vSphere Memory Tiering (explicitly `noTiering` in the
  export) as the cause, but couldn't pin down the exact source of the
  ~127GB gap from the export data alone. Real servers are built from a
  short, well-known list of standard RAM configurations (128/192/256/
  384/512/768GB, etc. - doubling/1.5x steps driven by DIMM slot count x
  DIMM size) - a host never actually has an odd figure like 383GB
  installed. Rounds UP to the nearest known configuration at-or-above
  the reported value (383.7 -> 384, not down to 256), since a host
  can't have LESS installed than what vCenter measured. Scoped to
  Server imports only, deliberately NOT applied to VM RAM (a VM isn't
  built from physical DIMMs and can legitimately have any RAM
  allocation - rounding those would be wrong).
- **Spinbox step sizes**: Server RAM now steps by 32 (one DIMM
  increment) instead of the previous 1024, which was too coarse for
  fine adjustment. Storage's Raw/Usable Capacity and Server's Local
  Disk (Raw) - all TB-denominated - now step by 1.0 instead of Qt's
  default of 1 unit at 2 decimal places (effectively 0.01), matching
  how these fields actually get sized in practice.
- 21 new tests: 6 for `round_up_to_known_ram_gb()` and the RVTools
  Server/VM RAM scoping (including the exact 383.7GB real-world case),
  1 for the HCI list scrollbar fix, 4 for the new spinbox step sizes -
  192 passed total.

## v3.6.0 (Deployment Model per site - Step 1 of cloud support; CI fix)

- **New: per-site Deployment Model (On-Premise / Cloud)** on
  Settings, applied immediately (not batched with the threshold Apply
  button). Deliberately per-SITE, not per-project - a hybrid setup
  (on-premise Primary with a cloud DR, i.e. DRaaS) is extremely
  common in practice, and this gets that case "for free": setting
  both sites to the same model covers the simple case, setting them
  differently covers the hybrid one, with no extra concept needed.
  `ClusterProject.deployment_model_for(site)` / `.is_cloud(site)` are
  the lookup helpers other code uses instead of branching on
  PRIMARY/DR itself. Defaults to On-Premise for both sites, so every
  existing project loads completely unchanged.
- **First real effect**: Rack Sizing. Rack units/power draw is a
  physical-hardware concept that's simply meaningless for a site
  whose compute lives in someone else's data center -
  `compute_rack_sizing()` now returns an `is_cloud` flag and, when
  true, doesn't even try to sum whatever Server/Storage/Switch rows
  might exist there (e.g. leftovers from switching a site's model
  after the fact) - just reports zero. Both the Summary page's Rack
  Sizing cards and the Word report now show "Cloud" instead of a
  number for a cloud-flagged site.
  - Along the way, found and closed an old gap: the Word report never
    had a Rack Sizing section at all, something flagged as missing
    back in the v3.0.0 report-gaps list and never revisited since -
    added now, with the cloud handling built in from the start rather
    than as an afterthought.
- This is explicitly scoped as Step 1 only, discussed and agreed on
  directly - broader cloud terminology changes (Server fields,
  pricing model, tab labels) are deliberately deferred until this
  narrow first step is validated in real use, rather than guessing at
  a large redesign upfront. A "Project Planning" wizard idea (guided
  Q&A to bootstrap a brand-new project) was also discussed and
  explicitly dropped - no reliable way to recommend specific resource
  numbers without guessing, which isn't a trade-off worth making.
- **CI fix**: GitHub Actions started failing outright on the four
  real-Qt test files added in v3.5.0 - `ImportError: libEGL.so.1:
  cannot open shared object file`. `pip install PySide6` only
  installs the Python packages; the native Qt/EGL shared libraries it
  links against at import time (confirmed via `ldd` against the
  actual installed PySide6 build: libEGL, libGL/libGLX/libGLdispatch,
  libxkbcommon, libxcb, libdbus-1, libfontconfig, libX11 and a few
  X11 support libs) come from the OS package manager, not pip, and a
  bare `ubuntu-latest` runner doesn't have them preinstalled. Added an
  `apt-get install` step to the workflow before the Python dependency
  install - all 19 package names verified to actually resolve via a
  real `apt-get install --dry-run` against archive.ubuntu.com on
  Ubuntu 24.04 "noble" (what `ubuntu-latest` currently is), not
  guessed. `QT_QPA_PLATFORM=offscreen` (already set for the test step
  since v3.5.0) needs those libraries to even be importable in the
  first place, regardless of not needing a real display.
- main.py now carries a version comment at the very top
  (`# ClusterSizer vX.Y.Z - see src/version.py for the single source
  of truth`), kept in sync on every future version bump, per direct
  request.
- 16 new tests across deployment-model persistence, rack sizing (both
  the pure calculation and a false-positive caught and fixed in a
  first draft - a test that placed its server on the wrong site,
  passing for the wrong reason), the Word report section, and two new
  real-Qt UI test files for the Settings and Summary pages - 181
  passed total.

## v3.5.0 (Firewall/Load Balancer support, and PySide6 finally testable)

- **Network tab now supports Firewalls and Load Balancers**, not just
  switches. `NetworkSwitch`'s existing fields (name/vendor/model, port
  inventory by speed, rack/power/price, notes) already generalize fine
  to any rack-mounted network appliance, so this was a type-list
  extension, not a new entity: new `SWITCH_TYPES` constant (`LAN`,
  `SAN/FC`, `Unified`, `Firewall`, `Load Balancer`), matching the
  `DESTINATION_TYPES`/`CATEGORIES` pattern already used by
  BackupDestination/MaintenanceItem. User-facing labels updated
  throughout the Network tab and dialog ("Network Device" instead of
  "Switch") without touching internal class/variable names. Firewall
  subscriptions (threat prevention, etc.) are tracked as Maintenance
  Items instead of new fields on the device - `applies_to` names the
  device, e.g. "Perimeter Firewall" - closing a loop that already
  existed by coincidence: the example project has had a "Firewall
  subscription" Maintenance Item since v3.2.0, referencing a firewall
  that didn't actually exist as a device until now.
- **PySide6 became actually installed in the dev sandbox for the first
  time in this project's history.** Every prior "GUI" test in this repo
  was source-inspection or pure-math-simulation based specifically
  because real Qt widgets couldn't be instantiated to test against -
  each said so directly in its own docstring. That's no longer true:
  `requirements-dev.txt` already pulled in PySide6 (via
  requirements.txt) and works headlessly with `QT_QPA_PLATFORM=
  offscreen` - added that to the CI workflow's test step, since GitHub
  Actions runners have no display server either.
  - **Found a real bug immediately** that source-inspection could never
    have caught: a fresh "Add Storage" dialog never populated the HCI
    server checkbox list at all - only `load()` (the "Edit" path) did.
    Checking "HCI" on a brand new Storage entry showed an empty list
    with no way to select any server. Fixed: `_on_hci_toggled()` now
    populates the list itself the first time it's shown, guarded so
    toggling HCI off and back on within one session doesn't wipe
    already-checked servers.
  - Rewrote `test_site_capacity_widget.py` and
    `test_multi_select_table.py` from source-inspection/simulation to
    real widget instantiation - both now exercise actual QProgressBar/
    QTableView behavior instead of a hand-written model of what Qt is
    believed to do. Added `test_storage_dialog_hci.py` and
    `test_switch_dialog.py`, both real-Qt. 165 tests total, up from 152.

## v3.4.0 (HCI/vSAN storage - disks live in the servers, not a separate array)

The user's own real-world case: working with a vSAN cluster where there's
no dedicated storage array at all, but it's still a real storage pool
that needs to show up on the Storage tab.

- **New: `Server.local_disk_raw_tb`** - a single simple number (not a
  full per-disk/cache-vs-capacity-tier breakdown - deliberately scoped
  down after discussion, to avoid a mini-RAID-calculator's worth of new
  complexity bolted onto Server for what would often be false
  precision anyway, given vSAN's actual raw-to-usable math depends on
  per-VM storage policies).
- **New: `Storage.is_hci` + `Storage.hci_server_uids`.** When HCI is
  checked, Raw Capacity is auto-summed from whichever servers are
  checked in a list on the Storage dialog (each showing its own Local
  Disk (Raw) value) instead of being typed in directly - Raw Capacity
  becomes read-only while HCI is active. Usable Capacity stays a manual
  entry either way, same reasoning as `raid_overhead_percent` already
  being informational rather than authoritative for traditional arrays
  - the real shrinkage depends on the storage policy (FTT/erasure
  coding) in a way this app doesn't try to model exactly. Manual
  server selection (a checkbox list), not automatic "everyone at this
  Site" grouping - confirmed directly, since the user specifically
  wanted to choose which servers count.
  - `src/calculations/hci_storage.py`'s `compute_hci_raw_capacity()` is
    the actual sum - pure and testable without Qt. The Storage dialog
    calls it live as checkboxes change, AND again right before saving
    (not just trusting whatever's currently displayed), so the
    persisted number can't go stale regardless of UI interaction
    timing.
  - `hci_server_uids` deliberately excluded from the flat CSV schema
    (same precedent as StorageShelf) - a re-imported Servers CSV
    generates fresh UIDs each time, so a stored cross-reference would
    go stale immediately. Full support via `.clsz` and the GUI dialog.
    A stale/deleted server reference is silently skipped when summing,
    not an error.
  - New "Type" column (Traditional/HCI) on the Storage table.
- New dedicated example, `examples/scenario_vsan_example.clsz` - 3
  vSAN nodes (30TB local disk each), one HCI Storage entry linking all
  three (90TB raw, auto-summed and verified to match), 60TB usable
  entered manually reflecting an FTT=1 mirroring policy. Kept separate
  from the main `scenario_full_example.clsz` (which already tells a
  coherent traditional-SAN story) rather than mixing both storage
  styles into one project.
- 18 new tests: 6 for `compute_hci_raw_capacity()` (full/partial
  linking, empty selection, a stale uid skipped gracefully, no servers
  at all, zero-contribution servers), 2 persistence tests (round-trip,
  and v6 files predating these fields defaulting correctly) - 152
  passed total.

## v3.3.2 (Tables: long Notes/OS text was truncated with no way to see the rest)

Reported specifically for the VMs tab (Notes and the new OS column),
but the root cause was shared by every CRUD table in the app - all of
them build on one shared view class, `MultiSelectTableView`.

- **Root cause**: `_do_auto_size()` called `resizeColumnsToContents()`
  (which correctly widens the last column, e.g. Notes/OS, to fit its
  actual content) and then immediately called
  `setStretchLastSection(True)` right after, which silently overrode
  that computed width back down to whatever space was left in the
  viewport - squeezing a long value and ellipsizing it, with no way to
  see the rest short of opening the row's edit dialog. The Servers tab
  happened to look fine anyway, purely because it has enough OTHER
  columns (rack/power/pricing/etc.) that the table already overflowed
  the viewport and picked up a horizontal scrollbar as a side effect -
  not because it was handled any differently.
- **Fix**: removed `setStretchLastSection` entirely (both the one at
  construction and the one undoing the resize). A wide table now just
  grows past the viewport and shows a horizontal scrollbar - the same
  way a spreadsheet behaves - so any column's full content, not only
  Notes/OS, is reachable by scrolling right instead of only by opening
  the item. Added an explicit `setHorizontalScrollBarPolicy(
  ScrollBarAsNeeded)` so this is a stated design choice, not an
  implicit default.
- 2 new tests (test_multi_select_table.py, source-inspection based
  since the widget can't be instantiated without PySide6 in this
  sandbox) - guard against the method being called again, and confirm
  the scrollbar policy is explicit.

## v3.3.1 (Summary tab progress bars: fill didn't match the label)

Found from a screenshot: RAM utilization labeled "65%" but the blue
fill looked like roughly a third of the bar - "kaže 65% ali pokazuje
plavu crtu više kao da je na 35%". Two separate, confirmed bugs in
`SiteCapacityWidget.set_report()`:

- **RAM and Storage bars never had their range updated** away from the
  constructor's default of 0-200 - a plain percentage (0-100 is "full")
  rendered against a scale twice too wide, so a healthy 65% visually
  filled ~32.5% of the bar. Fixed: both now use a clean 0-100 range, so
  the fill directly matches its own label; an unhealthy >100% reading
  still shows the true number in the text, it just visually caps the
  bar rather than leaving a permanent mismatch.
- **The CPU bar called `setValue()` before `setRange()`** -
  `QProgressBar.setValue()` clamps the value against whatever range is
  CURRENT at that exact call, and a later `setRange()` does not
  retroactively un-clamp an already-stored value. On the first refresh
  (range still at the constructor's 0-200 default), a 3.0:1 ratio
  wanting to show 300/400 (75% fill) got clamped to 200 first, then the
  range widened to 0-400 afterward, landing on a stale 200/400 = 50%
  fill instead. Fixed by reordering every bar's calls (`setRange()`
  first, always) as a general defensive practice, not just for CPU.
- Verified mathematically with a standalone simulation of
  QProgressBar's real clamping semantics (PySide6 isn't installed in
  this sandbox, as elsewhere in this project) - confirmed the OLD code
  produces exactly 32.5% for the reported 65% RAM case, and the NEW
  code produces exactly 65.0%. 5 new tests
  (test_site_capacity_widget.py): call-order regression guards for all
  three bars (source-inspection based, since the widget itself can't
  be instantiated here), a range-value guard, and the clamping-math
  simulation itself.

## v3.3.0 (RVTools: a real HT bug fix, OS, Cluster Name, multi-Datacenter sites, Switch import)

- **Fixed a real, confirmed bug**: the dedicated RVTools importer set
  `threads_per_core=1` for every imported server, on the mistaken
  assumption (my own error, stated outright in the old code comment)
  that "RVTools doesn't reliably expose Hyperthreading". It does, via
  vHost's `HT Available`/`HT Active` columns - confirmed against the
  user's real export (all 4 hosts: both True). With
  threads_per_core=1, toggling the Hyperthreading checkbox after import
  had NO effect at all (1 thread/core makes the HT-enabled/disabled
  multiplication a no-op either way) - exactly the "uključio HT i ne
  mrda" (turned it on, nothing moves) symptom reported. Fixed with
  three-way handling: HT Active -> enabled + threads_per_core=2; HT
  Available but not Active -> disabled but threads_per_core STAYS 2
  (preserves the real SMT width so toggling it back on later actually
  works, matching this app's own "toggle without losing configured
  width" design intent); neither column present -> old conservative
  fallback (1 thread/core). Verified end-to-end: the user's real file
  now correctly shows 40 effective cores per host, not 20.
- **New: OS field on VirtualMachine.** The RVTools importer can prefer
  either "OS according to the configuration file" (declared at VM
  creation, always present) or "OS according to the VMware Tools"
  (detected live, blank if Tools isn't installed) - falls back to the
  other automatically when the preferred one is blank for a given VM.
  Found a real-world case in the user's own file demonstrating exactly
  why this matters: one VM's config file says "Windows Server 2012",
  while VMware Tools reports "Windows Server 2016 or later" for the
  same VM - genuinely different information depending on which source
  you trust.
- **New: Cluster Name field on Server.** Simple informational tag
  (e.g. "vSAN_HPM"), imported directly from vHost's "Cluster" column -
  no user interaction needed, several servers can share one, unlike
  Datacenter this never needs a mapping decision.
- **New: multi-Datacenter site mapping.** RVTools has no Primary/DR
  concept, but its "Datacenter" column sometimes distinguishes real
  sites living in one vCenter. `detect_datacenters()` scans the file
  first - if it finds only one value (the common case), nothing
  changes: one target site as before. If it finds more than one, the
  import dialog shows a mapping row per Datacenter found (each ->
  Primary or DR), and `import_servers()`/`import_vms()`/
  `import_switches()` all accept an optional `site_map` to route each
  row to the right site individually, falling back to the dialog's
  default site for any unmapped value rather than crashing.
- **New: optional Switch import** from the vSwitch sheet - one
  NetworkSwitch per distinct switch name found (deduplicated, since the
  same switch typically appears once per connected host), name only -
  port counts/speed aren't in a form this app's model can use directly,
  flagged for manual review. Behind a checkbox in the import dialog,
  since not everyone wants Network tab entries created automatically.
  `ProjectService.add_servers_and_vms()` gained an optional `switches`
  parameter so all three entity types land in one undo step.
- 25 new tests (22 in test_rvtools_import.py covering all of the above,
  including the three HT scenarios; CSV round-trip tests for the two
  new model fields) - 137 passed total.

## v3.2.0 (Pricing simplified back down - it isn't a quoting tool)

The user's own framing: "netko će ovo koristiti za sebe, a netko za
prodaju" (some people use this for themselves, some for selling) - but
after using v3.0/3.1's CAPEX/OPEX/margin/uplift system for real, the
verdict was clear: "ovo sa ponudom je grozan pokušaj... ne uklapa se
ovako u app" (this quote-style attempt is a bad fit for the app).
Pulled it back out and replaced it with something admin-shaped instead.

- **Equipment pricing simplified to one field.** `unit_cost` +
  `unit_price` (cost-vs-price for margin) removed from Server, Storage
  (+ StorageShelf), NetworkSwitch, and BackupDestination - replaced
  with a single `price`. No more CostPriceMarginFields widget, no more
  Uplift %, no more per-category margin percentages. The Pricing tab
  just sums `price` by category (Servers/Storage/Network/Backup,
  Storage including its shelves) into a total - what it's for now:
  giving an admin a running total, not building a customer quote.
- **Services & Recurring Costs removed entirely** - OPEX monthly/
  one-time views, contract-term amortization, "Apply Uplift to
  Everything", total project value: all gone. Replaced with
  **Maintenance Items** (`src/models/maintenance_item.py`) - a
  renewal-reminder list for licenses, warranties, subscriptions, and
  support contracts: what it is, category, cost, duration in months,
  start/expiry dates, and an optional free-text `applies_to` (e.g.
  "Firewall FW-01" - not a hard link to a specific device, since one
  license often covers several, or none in particular). New
  `compute_maintenance_status()` (src/calculations/pricing.py) flags
  each item Expired (red), Expiring Soon (orange, within 90 days), OK,
  or Unknown (blank/unparseable expiry date) - shown in both the
  Pricing tab's table and the Word report.
- **`.clsz` schema bumped to v7.** `service_line_items` +
  `contract_months` replaced by `maintenance_items`. Old
  `unit_cost`/`unit_price` pairs migrate to the new single `price` on
  load - prefers the old `unit_price` (closer in spirit to "what
  actually gets paid"), falls back to `unit_cost` if price was never
  set, so upgrading an old file doesn't silently zero out pricing data
  someone already entered. Verified against the project's own example
  file (esxi-p01's price correctly migrated from unit_price=22000, not
  unit_cost=15000). CSV schemas and all example files updated the same
  way - migrated, not just reset to blank.
- **Fixed a real bug found along the way**: `ServerDialog` (and, it
  turned out, all four other entity dialogs) had grown taller than
  many screens over the course of adding Rack/Power/Pricing/Notes
  fields, with no scrollbar and no way to reach the OK/Cancel buttons -
  the window's bottom edge could end up off-screen, making it
  impossible to even resize by dragging. Fixed on Server, Storage,
  Switch, Backup Destination, and VM dialogs: the form now lives in a
  QScrollArea, with the buttons kept outside it so they're always
  reachable regardless of how tall the form grows.
- Backup dialog wording: "Offsite (geographically separate)" ->
  "Offsite (separate)", per direct request.
- Test suite: `test_pricing.py` fully rewritten (10 tests) for the new
  equipment-total + maintenance-status model; 2 stale
  `test_docx_report.py` tests rewritten for the same reason; 4 new
  migration-specific tests added to `test_project_repository.py`
  (unit_price preferred, unit_cost fallback, shelf price migration,
  missing maintenance_items key defaulting to empty) - 124 passed.
- `docs/HOW_THE_MATH_WORKS.md` and this README's Pricing description
  both rewritten to match - no more CAPEX/OPEX/margin/uplift
  terminology anywhere in the docs.

## v3.1.1 (fixed a real formula bug: uplift vs margin were conflated)

The user's own example caught it: "cost 100, +10% = 110" is uplift (%
of cost), not margin (the standard accounting definition - % of
price/revenue). v3.1.0 computed the aggregate "margin_percent" figures
as `margin / cost`, which is uplift math wearing a margin label - on
that same 100/110 example, the correct margin is 110's profit as a %
of 110 = 9.1%, not 10%.

- Fixed `CapexBreakdown.margin_percent`, `PricingSummary.
  capex_margin_percent`, `.opex_monthly_margin_percent`, and `.
  total_project_margin_percent` to divide by PRICE, not cost - the
  correct definition. None (not 0) now triggers on price=0, not
  cost=0, since price is the new denominator. On the example project,
  this changed CAPEX margin from an incorrectly-computed 43.3% to the
  correct 30.2%.
- Renamed the per-item field from "Margin %" to "Uplift %" throughout
  (`CostPriceMarginFields`, all 5 pricing dialogs, the "Apply Uplift to
  Everything" bulk action, formerly "Apply Markup...") - its formula
  (price = cost x (1 + X%)) was always correct, it just had the wrong
  label. Two different, deliberately-not-interchangeable percentages
  now exist side by side: Uplift is what you type to SET a price from
  a known cost; Margin is what gets REPORTED for profitability, on the
  aggregate cards and in the Word report.
- Word report's CAPEX table gained a Margin % column, and "Total
  margin" now shows the percentage alongside the EUR figure - visually
  verified by rendering to PDF (30.2% CAPEX margin, 32.7% total margin
  on the example project, matching the GUI).
- Updated `docs/HOW_THE_MATH_WORKS.md`'s Pricing section, which had
  been written with the same wrong assumption baked into its own
  worked example - now correctly distinguishes the two percentages
  with the exact 100/110/9.1% example that surfaced the bug.
- Test suite updated: rewrote the `margin_percent` tests with correct
  expected values (e.g. cost=15000/price=22000 is 31.8% margin, not
  46.7%), fixed the zero-value edge case to test price=0 instead of
  cost=0, and added a dedicated test pinning the exact 100/110/9.09%
  example so this distinction can't silently regress back to uplift
  math again.

## v3.1.0 (Pricing UX: margin editing, global markup, layout fix)

- **Margin is now directly editable**, not just a derived display. New
  reusable `CostPriceMarginFields` (Cost/Price/Margin % trio, shared by
  all 5 pricing dialogs - Server, Storage, Switch, Backup Destination,
  Service Line Item) - editing any ONE of the three recomputes the
  appropriate other field: editing Cost keeps the current margin fixed
  and recomputes Price; editing Margin recomputes Price from Cost;
  editing Price recomputes the displayed Margin from Cost. Covers the
  per-item side of "some people price item by item, some just want a
  standard markup."
- **New: Apply Markup to Everything** (Pricing tab) - one field + one
  button sets price = cost x (1 + markup%) across EVERY priced entity
  (Servers, Storage + shelves, Switches, Backup Destinations, Service
  Line Items) in a single undo step - the "selling a project at a
  standard margin" workflow the per-item fields don't cover well on
  their own. Confirms before running since it overwrites existing
  prices. The actual logic (`apply_markup_to_all()`) lives in
  `src/calculations/pricing.py`, not `ProjectService`, matching the
  established calculations/ vs services/ split - `ProjectService` is
  now just a thin wrapper adding the undo snapshot and notification,
  and the logic itself is directly testable without Qt.
- **Margin percentage now shown**, not just the absolute EUR figure -
  CAPEX Total and Total Project Value cards on the Pricing tab show
  e.g. "€113,000.00 (43.3%)". New `margin_percent` properties on
  `CapexBreakdown` and `PricingSummary` (capex/opex_monthly/total) -
  return `None` (not 0) when cost is 0, since "no cost entered yet" and
  "confirmed 0% margin" are different things that shouldn't look
  identical on screen.
- **Layout fix**: OPEX Monthly/One-time, CAPEX Total, and Total Project
  Value cards were using the tall (110px) card style meant for a handful
  of headline numbers - switched to the compact (55px) style already
  used for the CAPEX-by-category cards, and gave the Services &
  Recurring Costs table a stretch priority so it grows into the
  reclaimed space instead of staying a fixed small size while the cards
  above it dominated the tab.
- Storage's expansion-shelf sub-table keeps plain Cost/Price columns
  (no live margin column) - scoped down deliberately, since computing a
  synced margin cell inside an embedded QTableWidget is meaningfully
  more complex than a dedicated dialog's spinboxes, for what's usually
  a minor edge case (few projects have more than 0-1 shelves).
- 8 new tests: 4 for `margin_percent` (CapexBreakdown, PricingSummary
  across all three levels, the None-on-zero-cost case) and 4 for
  `apply_markup_to_all()` (cross-entity-type application including
  shelves, overwriting existing prices, 0% markup setting price equal
  to cost, empty project touching nothing).

## v3.0.0 (Pricing - CAPEX, OPEX, margin)

Opens v3. README's opening description updated to reflect what the tool
actually is now - a planning-and-documentation tool for architects and
IT administrators, not just a sizing calculator.

- **Unit Cost / Unit Price (EUR)** on Servers, Storage (including each
  expansion shelf separately - a shelf is commonly its own SKU on a real
  vendor quote), Network Switches, and Backup Destinations. Both fields,
  not just one - cost is your own/vendor price, price is what you'd
  charge the customer, kept separate so margin is visible rather than a
  single opaque number. Deliberately fixed to EUR, not a per-project
  currency picker - kept simple per explicit request.
- New **Pricing** tab (after Backup): CAPEX auto-summed from equipment
  already entered (by category - Servers/Storage/Network/Backup, no
  re-entry), a free-form **Services & Recurring Costs** list for
  everything else (implementation, licensing with activation/expiry
  dates, support contracts...) billed One-time/Monthly/Annual, a
  contract-term field (36/60 months, whatever applies), and a Total
  Project Value summary (cost/price/margin) projected across that term.
  Deliberately NOT modeled on any fixed WBS/task taxonomy (the kind a
  services company builds for its own quoting) - every company's
  costing methodology differs, so this is a generic, user-driven list
  rather than an attempt to replicate one specific structure.
- New `src/models/service_line_item.py` (`ServiceLineItem`) and
  `src/calculations/pricing.py` (`compute_pricing()`) - Annual billing
  normalizes to a monthly-equivalent (amount / 12) so it can be added
  to Monthly lines into one meaningful "cost per month" figure;
  One-time lines are tracked separately and don't pollute that view.
  Listens to the general `service.changed` signal, not a narrower one -
  CAPEX depends on Server/Storage/Switch/Backup data that isn't itself
  a "pricing" change, avoiding the exact staleness bug found and fixed
  on the VMs tab earlier.
- `.clsz` schema bumped to v6 (`service_line_items` list,
  `contract_months` field). CSV schemas for all four priced entity
  types gained unit_cost/unit_price columns; new
  `SERVICE_LINE_ITEM_FIELDS` CSV for the Services list. Examples
  updated with realistic EUR figures matched to each entry's real
  vendor/model (same approach as the Rack Sizing example update) plus
  three demo service line items (one-time implementation, monthly
  support, annual licensing with dates) - CAPEX total on the example
  project is now ~261k/374k EUR (cost/price), landing in the same order
  of magnitude as the real-world quote this feature was modeled on.
- New **Pricing** section in the Word report (CAPEX by category, OPEX
  monthly/one-time breakdown, full service line item table, Total
  Project Value with the margin line colored green/red) - visually
  verified by rendering to PDF, not just checked for text presence.
- Fixed a recurring papercut: the same hardcoded
  `SCHEMA_VERSION == N` assertion in test_project_repository.py has now
  gone stale THREE times as the schema kept evolving (v4, v5, v6) -
  removed it this time instead of bumping it again, since it wasn't
  testing round-trip behavior in the first place (scope creep in an
  otherwise-unrelated test) and a routine, intentional version bump
  isn't a regression that needs a brittle guard.
- 19 new tests: 11 for pricing calculation logic (empty project,
  cross-entity CAPEX aggregation, per-category breakdown, shelves
  counting toward CAPEX, Monthly/Annual/One-time OPEX handling,
  quantity multiplication, full contract-term total, margin
  properties) and 3 for the new Word report section (CAPEX figures
  present, service line items listed, empty-pricing project doesn't
  crash) plus the existing sections test extended to check for
  "Pricing".
- Explicitly deferred (separate discussion, not part of this release):
  a "Plan a Project" wizard (Tools menu) for bootstrapping a brand-new
  project from a guided Q&A (on-prem/cloud/managed, existing VM list
  or not, target scale) - agreed to keep this decoupled from the
  Pricing work.

## v2.17.2 (examples now demonstrate Rack Sizing - it wasn't there before)

The user asked directly: did the examples get updated for Rack
Units/Power when that feature was built? Checked - no, every example
(the full `.clsz` and all Servers/Storage/Switches CSVs) still had
rack_units=0/power_watts=0 everywhere, so opening any of them and
clicking "Show Rack Sizing" would've shown a wall of dashes. Fixed:

- Populated realistic rack_units/power_watts on every example, matched
  to each entry's actual vendor/model (Dell PowerEdge R750 = 2U/800W,
  Pure Storage FlashArray//X = 3U/1200W, Cisco Nexus 93180YC-FX =
  1U/300W, etc. - commonly-cited ballpark nameplate figures for each
  real product line, not arbitrary numbers).
- `examples/scenario_full_example.clsz` also got a demo
  `StorageShelf` attached to its primary storage, so that feature has a
  visible example too, not just the flat fields.
- Found and documented a real design question while doing this:
  `esxi-p02` in that same example is deliberately `enabled=False` (from
  an earlier N+1 demonstration) - and `compute_rack_sizing()` counts it
  anyway, unlike every capacity calculation (`servers_at()` and
  everything built on it), which excludes disabled servers entirely.
  Decided this is correct AS-IS rather than a bug: "disabled" means
  "exclude from compute capacity planning" (simulating a host being
  down), not "physically removed from the rack" - a disabled server
  still occupies its U and still draws power if it's plugged in.
  Documented this explicitly in `rack.py`'s module docstring (so it
  doesn't look like an oversight to the next person reading it), added
  a pinning regression test, and added the same explanation to
  `docs/HOW_THE_MATH_WORKS.md`.

## v2.17.1 (ELI5 math documentation)

- New `docs/HOW_THE_MATH_WORKS.md` - plain-language explanation of every
  calculation in the app, with small worked numeric examples: CPU/RAM/
  Storage oversubscription, why CPU is a ratio but RAM/Storage are
  percentages, Hyperthreading's effective-cores math, N+1/N+2 (including
  the corrected Basic HA semantics), DR Readiness vs the DR Failover
  Preview, Cluster Preparation's workload-tier weighting, all 7 RAID
  formulas, backup 3-2-1-1 compliance, and rack sizing. Linked from
  README's Scope & Assumptions section. Every formula and worked example
  in it was checked against the actual current code before writing (the
  Basic HA explanation was initially drafted wrong - from an EARLIER,
  since-corrected version of that logic - caught and fixed before
  publishing, not after).

## v2.17.0 (real-usage feedback batch: a genuine cross-page staleness bug, DR Failover Preview, missing Notes/IP fields, dialog polish)

Tested by loading `scenario_full_example.clsz` and using the app - found
and fixed a real bug, plus a batch of smaller gaps:

- **Fixed a real bug**: VMs tab's "CPU Oversub." card only refreshed on
  `vms_changed`, but the ratio also depends on Server data (physical
  cores, HT, enabled/disabled) - a Servers-only change (toggling HT,
  re-enabling a disabled host) never fired `vms_changed`, so the card
  went stale while Summary (listening to the general `changed` signal)
  correctly showed the current number - exactly the reported "VMs tab
  says 3.7:1, Summary says 1.8:1 for the same project" symptom. VMs page
  now also listens to `service.changed`.
- **New: DR Failover Preview.** A "Preview DR Failover" toggle on the
  Summary tab (same pattern as "Show Rack Sizing") swaps the DR card
  from "what's actually running on DR right now" to "what DR would need
  if every DR-protected VM were activated there" (e.g. a Veeam/backup-
  driven DR plan) - same physical DR hardware, demand becomes the
  failover scenario, reusing the exact same OK/Warning/Critical status
  system as every other capacity check. Confirmed the underlying model
  (`dr_failover_*_demand()`) already correctly combined VMs that live on
  DR permanently (e.g. a redundant always-on domain controller) with
  DR-protected Primary VMs (the Veeam scenario) - this was a display
  gap, not a logic gap. New `build_dr_failover_report()`
  (src/calculations/sizing.py), 5 new tests including one that
  demonstrates a site looking healthy in the current view while going
  CRITICAL in the failover view - the whole point of the feature.
- **Notes was invisible on every entity table** (Server/Storage/Switch/
  VM) despite the model field existing on all four - added to all four
  table models. VMDialog and ServerDialog had NO notes field in the GUI
  at all (StorageDialog too, added alongside its new Rack/Shelves
  section) - fixed all three; SwitchDialog already had one.
- **New: VM IP Address** (guest OS IP) - model, CSV schema, Smart
  Import mappable field, VMDialog field. The dedicated RVTools importer
  now also populates it from RVTools' "Primary IP Address" column when
  present (confirmed against the user's real export: 58 of 72 VMs had
  it - the rest presumably lack VMware Tools, which RVTools needs to
  report a guest IP at all).
- Server dialog: Cores/Socket now steps by 2 (cores per socket are
  always even), RAM steps by 1024 GB (common DIMM-friendly increment) -
  VM dialog's RAM deliberately left stepping by 1, per explicit request.
- VMs tab card order: VM Storage moved between RAM Demand and CPU
  Oversub (was after CPU Oversub).
- Window title no longer includes the full file path - just
  "ClusterSizer {version} - {project name}".
- Confirmed NOT a bug: the plain "Import CSV" button is intentionally
  CSV-only (expects our exact schema); "Smart Import" already supports
  CSV/XLSX/JSON/XLSM - likely just the wrong button was clicked.
- A static-import check caught a real bug before packaging this time:
  `storage_dialog.py`'s new Notes field used `QPlainTextEdit` without
  importing it - would have crashed the Storage dialog on open. Fixed
  before shipping, not after.

## v2.16.0 (Rack sizing - Rack Units + Power Consumption)

- New `rack_units`/`power_watts` fields on Server, Storage, and Network
  Switch - 0 means "not entered", excluded from totals rather than
  counted as a real zero, same convention as every other optional
  numeric field in this app. Power is meant as nameplate/max draw from
  the datasheet, not "typical" - safer for circuit/PDU capacity
  planning (a single field, not min/max - deliberately not
  over-engineering this).
- New `StorageShelf` - expansion shelves/trays are embedded directly in
  their parent Storage (not a separate top-level entity - a shelf never
  exists independently of the storage it expands, usually SAS-cabled to
  the head unit or the previous shelf in a chain). `Storage.
  total_rack_units`/`total_power_watts` include attached shelves
  automatically. Edited via a small embedded sub-table in the Storage
  dialog (add/remove rows), not its own tab or CSV file.
- New `src/calculations/rack.py` - aggregates U and W per site across
  Servers + Storage (incl. shelves) + Switches. Summary tab gained a
  "Rack Sizing" section below Cluster Summary, same card style as the
  top-line row, behind a "Show Rack Sizing" toggle (hidden by default -
  a project with nothing entered would just show a row of dashes).
- `.clsz` schema bumped to v5. `_build()`'s generic shallow-field-filter
  doesn't reconstruct NESTED dataclasses (StorageShelf would come back
  as a plain dict, breaking `.rack_units` attribute access) - added a
  dedicated `_build_storage()` that reconstructs shelves properly.
  Verified round-trip and v4-file backward compatibility (missing
  rack_units/power_watts/expansion_shelves keys all default correctly).
- CSV schemas for Servers/Storage/Switches gained rack_units/power_watts
  columns (examples updated). Table models and dialogs for all three
  gained Rack (U) and Power (W) fields/columns.
- 12 new tests: 6 for rack aggregation (empty project, unset-fields-
  excluded, cross-entity aggregation, shelves counting toward the total,
  site independence, Storage's own total_* properties) and 6 for
  persistence (shelf reconstruction as real objects not dicts, v4
  backward compat).

## v2.15.0 (Server IP Address, cross-sheet field mapping in Smart Import)

- New `Server.ip_address` field (management or primary network IP, free
  text) - Server dialog, table column, CSV schema
  (examples/servers_*.csv updated to match). The dedicated Tools > Import
  from RVTools importer now populates it automatically when RVTools'
  "Host" column is itself an IP (common - confirmed against the user's
  real export, all 4 hosts identified by IP) - a simple IPv4-shape check,
  left blank when Host is a real hostname instead.
- **Smart Import wizard: per-field cross-sheet mapping.** Each mapped
  field (Name, vCPU, RAM, Disk, ...) can now independently pull its
  source column from a DIFFERENT sheet in the same workbook, not just
  the one primary sheet - pick a sheet per field, one at a time, until
  everything needed is mapped. Sheets are joined by whatever the Name
  field's own column is (RVTools' "VM" column is consistent across
  vInfo/vCPU/vMemory/vPartition/etc, so this needs no extra
  configuration for RVTools specifically). Verified end-to-end against
  the user's real 27-sheet export: pulled a vCPU-sheet-only column
  ("Sockets", absent from vInfo) into a VM field, correctly varying
  per-VM (not a constant), proving the join matches the right row for
  each VM rather than the first/any row.
  - `ColumnMapping` gained `source_sheet` (blank = the primary sheet
    currently selected - fully backward compatible, existing profiles
    and single-sheet files are unaffected).
  - `convert_rows()` now accepts optional `sheets_data` (other sheets'
    rows, keyed by sheet name) and `join_key_column` (defaults to the
    Name field's own column) - builds a lookup index per referenced
    sheet, falls back to blank/default (never crashes) when a join key
    isn't found or a referenced sheet wasn't loaded.
  - The wizard lazily loads and caches only the sheets actually
    referenced by a field's sheet choice, not the whole workbook - a
    27-sheet RVTools export doesn't get fully parsed just because one or
    two fields use a non-primary sheet. Cache is cleared on file/sheet
    reload and on header-row changes (a stale cache would otherwise read
    a different sheet under the wrong header-row assumption).
- 6 new tests (tests/test_import_engine.py) covering: single-sheet
  behavior is unchanged, a real two-sheet join, three distinct graceful-
  fallback cases (key not found / sheets_data is None / referenced sheet
  absent from sheets_data), and that profile auto-matching still works
  with the new field present on ColumnMapping.
- Also fixed 2 real Smart Import bugs found testing against the user's
  actual RVTools export for the first time (see v2.14.2's entry above
  for the mechanism) - this release builds directly on those fixes.

## v2.14.2 (two real RVTools import bugs, found against a real export)

Tested against a real 27-sheet RVTools export for the first time (all
prior testing used a synthetic fixture) - found and fixed two genuine
bugs:

- **Smart Import wizard: mapping UI could silently show the WRONG
  sheet's columns.** Root cause: `QComboBox.setCurrentIndex()` only
  emits `currentIndexChanged` when the index actually changes - a no-op
  call fires no signal. `_load_file()` auto-selects a matching profile
  via `setCurrentIndex()` and relied on that signal to trigger rebuilding
  the mapping UI. RVTools' vInfo and vCPU sheets both best-match the same
  built-in "RVTools (vInfo tab)" preset (both have VM, Powerstate, CPUs,
  "OS according to..."), so switching vInfo -> vCPU -> vInfo left the
  profile combo at the SAME index the whole time - the second vInfo visit
  fired no signal, and the mapping UI stayed showing vCPU's 7 columns
  instead of vInfo's real 90. This matched the exact symptom reported:
  Name/vCPU still mappable (both sheets happen to have VM/CPUs), Memory
  missing (vCPU has no Memory column). Fixed by calling the rebuild
  directly after auto-matching a profile, instead of depending on the
  signal firing. Also fixed the related first-load case (the initial
  sheet dropdown population via `addItems()` isn't a reliable way to
  auto-trigger the first load either) - now falls through to load the
  first sheet directly instead of returning and hoping the signal fires.
- **RVTools preset pointed at the wrong disk column, both in Smart
  Import's built-in profile and the dedicated Tools > Import from
  RVTools importer.** "Provisioned MB" (Smart Import preset) doesn't
  exist in a real RVTools export - confirmed against one. Real column:
  "Total disk capacity MiB". The dedicated importer's "Provisioned MiB"
  (which DOES exist) measures something different - datastore space
  actually reserved, including thin-provisioning and snapshot overhead -
  and reads far higher than a VM's configured disk size (confirmed: 68TB
  vs 29TB on the same real file). Both paths now prefer "Total disk
  capacity MiB", matching what "how big is this VM's disk" should mean
  for capacity planning, and matching the user's own by-hand
  verification (~30TB) almost exactly (28.76TB) - previously this same
  file imported at roughly 21TB via a workaround, neither number
  matching the correct total.
- 3 new tests (tests/test_import_presets.py) pin both fixes: the
  preset's disk column name, the vInfo/vCPU same-preset-match condition
  that caused the signal bug (so a future preset edit that removes the
  overlap doesn't silently invalidate the regression guard), and an
  end-to-end conversion check against a realistic row.
- Tested end-to-end against the real export (not shared, per the user's
  request - analyzed in place, never copied into the repo or any
  output): 72 VMs, 4 hosts, totals now consistent between the Smart
  Import path and the dedicated RVTools importer, both matching the
  user's independent by-hand calculation.

## v2.14.1 (backup example added to the full example project)

- `examples/scenario_full_example.clsz` now includes 3 backup
  destinations, deliberately designed to demonstrate FULL 3-2-1-1
  compliance (not a failing example) - a fast local Disk Appliance repo
  at Primary, a NAS copy at DR (different media type, offsite relative
  to Primary), and an immutable Offsite/cloud copy (object-lock enabled)
  covering the ransomware-protection leg. 3 distinct destination types,
  offsite and immutable both present. Re-saved through the app's own
  writer, verified round-trip - the rest of the project (3 servers, 2
  storages, 45 VMs, 4 switches, 5 connections) is untouched.

## v2.14.0 (Backup tab - destinations + 3-2-1-1 compliance)

- New **Backup** tab (right after Storage) - same CRUD pattern as every
  other entity tab (Add/Edit/Delete/Duplicate/CSV Import-Export/Clear
  All, inline table editing, right-click menu). A *list* of backup
  destinations, not a single flat config - a real setup usually has
  several (a fast local repo, an offsite copy, maybe an immutable one
  too), and the 3-2-1-1 check needs something real to count across.
- Each destination: name, site, type (NAS / Disk Appliance / Storage
  Array / Offsite / Tape-Offline), backup software (free text - Veeam,
  CommVault, etc.), raw capacity, dedup ratio (effective capacity =
  raw x ratio), and two independent flags - Offsite (geographic
  separation) and Immutable/Offline (ransomware protection) - since a
  single destination can be neither, either, or both.
- New `src/calculations/backup.py` - computes the classic 3-2-1 rule (3
  total copies incl. production, 2+ distinct media types, 1+ offsite)
  and the modern 3-2-1-1 extension (+1 immutable/offline copy).
  Evaluated project-wide, not per-site - 3-2-1 is about how many
  independent copies of your data exist anywhere, not a site-scoped
  capacity question. Deliberately stops at 3-2-1-1, not the fuller
  "3-2-1-1-0" some vendors promote - the "0" (verified, tested-
  restorable backups) is a PRACTICE, not something derivable from
  static config, and claiming to compute it would be dishonest. The tab
  shows a compliance badge (Full / 3-2-1 only / Not met) plus an exact
  list of what's missing, not just pass/fail.
- Data model: `ClusterProject.backup_destinations` (new list field),
  `.clsz` schema bumped to v4 (adds a `backup_destinations` key) - older
  v3 files still load fine, defaulting to an empty list, same tolerance
  every other schema addition has had. New `ProjectService` CRUD +
  `backup_changed` signal, new CSV import/export
  (`BACKUP_DESTINATION_FIELDS`).
- 21 new tests total: 8 for the compliance logic (empty/single/same-type/
  full 3-2-1/full 3-2-1-1/exact gap messages/flags-on-one-destination),
  1 CSV round-trip, 2 `.clsz` persistence (round-trip + v3-file backward
  compat, including fixing a stale `SCHEMA_VERSION == 3` assertion the
  bump broke).
- Deliberately NOT built yet (flagged as later ideas, not part of this
  pass): a reverse-sizing Backup Wizard (VM list + retention + change
  rate -> required destination capacity, same spirit as Cluster
  Preparation) and a Backup<->DR replication link (a Primary destination
  pointing at a DR destination it copies to, enabling recovery-from-
  backup as a third DR path alongside live VM replication).

## v2.13.0 (RAID Calculator)

- New Tools > RAID Calculator... - disk type, size, count, RAID level
  (0/1/5/6/10/50/60, including nested with a groups input), and optional
  hot spares, with live-updating raw/usable/overhead%/fault-tolerance
  output. Deliberately does NOT cross-reference the choice against VM
  Workload Tiers elsewhere in the project - a Storage entity isn't tied
  to specific VMs anywhere in the data model, so "you have a Tier-0 VM
  somewhere, but chose RAID 5 HERE" would often be a false alarm (that
  VM might live on a completely different array). The warning is scoped
  to what's actually knowable from the RAID config alone: parity levels
  (5/6/50/60) combined with spinning-disk types trigger a write-penalty/
  rebuild-time warning; RAID 0 always warns regardless of disk type
  (zero redundancy is true no matter what runs on it).
- Apply to a Server or Storage already in the project, or leave the
  target at "None" to just play with the numbers - switching the target
  dropdown never discards what's been entered, only Apply commits
  anything. Storage gets real fields (raw_capacity_tb, usable_capacity_tb,
  raid_overhead_percent) - a confirmation dialog appears first if the
  target already has nonzero capacity set, so a calculation doesn't
  silently clobber real data. Server has no local-disk fields in the
  data model (deliberately not adding any - nothing currently sums
  server-local storage into any calculation, and adding fields nothing
  reads risks confusing double-accounting later) - applying to a Server
  appends a descriptive note instead ("Local RAID: 8x 4TB SAS SSD in
  RAID 6 = 24.0 TB usable, tolerates 2 disk failures").
- `src/calculations/raid_calculator.py` - pure math, Qt-free, no project
  dependency at all (the dialog is the only thing that knows about
  Server/Storage). 16 new tests covering every RAID level's capacity
  formula, hot spares, both warning branches and their absence, and
  input validation (too few disks, uneven RAID 50/60 groups, groups
  smaller than the minimum, zero disk size, spares >= disk count).

## v2.12.0 (Import from RVTools)

- New Tools > Import from RVTools... - reads a standard RVTools export
  (.xlsx, "Export all to Excel" - the common single-file case, not the
  per-tab CSV folder variant). `vHost` sheet becomes Servers, `vInfo`
  becomes VMs, both added to a single site chosen in the dialog (RVTools
  has no Primary/DR concept of its own - one export is normally one
  vCenter's inventory). One undo step for the whole import
  (`ProjectService.add_servers_and_vms()`, same pattern as
  `add_servers_and_storages()`).
- `src/persistence/rvtools_import.py` - Qt-free, same architecture as
  `generic_import.py`. Column lookups try a short alias list per field
  (RVTools' naming has drifted slightly across versions) rather than one
  exact name. RVTools labels values "MB"/"GB" but they're actually
  MiB/GiB (base-2) - every memory/disk value is divided by 1024, not
  1000, verified against a synthetic export with known values.
  Hyperthreading is deliberately left at a conservative default
  (disabled) since RVTools doesn't reliably expose it across versions -
  flagged in the imported server's notes for manual review, same
  treatment given to Workload Tier and DR Protected on the VM side
  (concepts RVTools has no equivalent of at all).
- 6 new tests (tests/test_rvtools_import.py) against a synthetic
  RVTools-shaped export: field mapping, MiB->GiB conversion, a
  not-actually-RVTools file raising a clear error, and graceful handling
  when only one of the two sheets is present.

## v2.11.3 (the four deferred decisions, resolved)

- **S25 (CI)** — recommended keeping it: zero cost, already caught one
  real bug (the stale `enabled` column test). It was never deleted from
  this local copy - `.github/workflows/tests.yml` is intact and will be
  included in the next delivery. The user should confirm with the
  collaborator who removed it from GitHub so it doesn't happen again.
- **S7 (build doc)** — decided: not needed. [A7] fixed as a result -
  `ClusterSizer.spec`'s dangling `docs/BUILD.md` reference replaced with
  the actual build commands inline (venv setup, PySide6-Essentials swap,
  pyinstaller invocation) instead of a pointer to a file that will never
  exist.
- **S14 (units)** — decided: leave as-is. No change.
- **S22 (HT classification duplication)** — resolved by adding the
  site-agnostic API the gap actually called for, rather than leaving it
  duplicated with a justifying comment. New `ClusterProject.
  hyperthreading_summary(site=None)` returns state AND on_count/
  total_count together (`HyperthreadingSummary`, same pattern as
  `NPlusOneCheck`) - `site=None` covers all servers project-wide (what
  `ServersPage`'s global HT toggle needs for its "(3/8 have HT on)"
  label), a specific site matches the existing per-site behavior.
  `hyperthreading_state(site)` is now a one-line wrapper around it, so
  every existing caller (`sizing.py`) is unaffected.
  `ServersPage._refresh_ht_global()` now calls the model instead of
  recomputing the same classification inline - the duplication is gone,
  not just commented. 2 new regression tests.

## v2.11.2 (second external audit fix pass - 9 actionable items, local repo)

A second audit (audit.md) compared issues.md against a LATER commit than
what this local copy was built from - it found the GitHub repo (managed
directly by a collaborator, "Tanks04") had DIVERGED from what was last
delivered here: `.github/workflows/tests.yml` was deleted on GitHub 2m51s
after being fixed, and several files this copy already had deleted
(html_report.py, workload_profile.py, the two empty __init__.py files)
still existed there. Those discrepancies are GitHub-repo-only and can't
be fixed from here - see below. Everything else the audit found WAS
present in this local copy and is fixed now:

- **A1** — `tests/test_docx_report.py` now starts with
  `pytest.importorskip("docx")`, so a missing optional python-docx
  degrades to one skipped test instead of aborting the entire suite
  (exit 2, 0 tests run). Verified both ways: uninstalled python-docx
  locally -> 30 passed, 1 skipped, exit 0; reinstalled -> 35 passed.
  Also gave `docx_report.py` the same guarded-import treatment
  `generic_import.py` already has for openpyxl - `build_docx_report()`
  now raises a clear diagnostic (interpreter path, exact pip command,
  and an explicit callout of the docx-vs-python-docx PyPI trap) instead
  of a bare ImportError reaching the Reports tab.
- **A3** — README's Storage bullet no longer contradicts itself
  ("shown for information" + "not derived automatically" in the same
  sentence) - now states plainly that the RAID/EC % is derived from
  raw/usable, shown read-only, and doesn't feed sizing math.
- **A4** — `import_wizard_dialog.py`'s
  `except (UnsupportedFileError, Exception)` (the tuple made the first
  member redundant, and bypassed report_error entirely) split into two
  handlers - the specific message stays for UnsupportedFileError, the
  general case now logs a traceback via report_error().
- **S17** — `report_error()` now shows `str(exc)` only for the app's own
  message-carrying exception types (`CsvSchemaError`,
  `UnsupportedFileError`) - anything else shows "Something went wrong.
  Details were saved to: ~/.clustersizer/crash.log" instead of a raw
  `KeyError: 'name'`-style repr. The traceback still always gets logged.
- **A6** — Cluster Preparation wizard had zero `try`/`except` across 523
  lines. The optimizer call (`recompute()`) and the write-back
  (`add_primary_cluster()`/`add_dr_cluster()`) are now the two guarded
  failure points - both route through `report_error()`; a failure in
  either leaves nothing queued rather than a half-applied result.
- **A8** — Network tab's Clear All (Switches, Connections) now say "You
  can undo with Ctrl+Z.", matching Servers/Storage/VMs - both already
  pushed an undo snapshot, only the wording was stale from before S9.
- **A13** — the mixed-Hyperthreading label's hardcoded `#ed6c02` replaced
  with `status_badge.WARNING_COLOR`, a new public alias for callers that
  need the warning color but aren't keyed by `Status`.
- **S19** — the 7 remaining single-dot `from .` imports (cluster_project.py
  x5, sizing.py, site_capacity_widget.py - the last one added by code
  written after the original S19 pass, reintroducing exactly the mixed-
  style pattern that pass was meant to eliminate) converted to absolute
  `from src.…`. Verified every resulting import resolves to a real file.
- **A9** — new `tests/test_networking.py` (11 tests) pins the S21 refactor:
  each of the three port-usage wrappers tested with and without
  connections, across 2+ speeds, plus site aggregation and
  over-committed detection. Deliberately mutated one wrapper's
  `uid_attr` (matching the audit's own acceptance test) and confirmed 3
  tests fail - then reverted.
- **A10** (partial - only what's local) — `examples/scenario_full_example.clsz`
  re-saved through the app's own writer with one server (esxi-p02) now
  `enabled=False`, so the Disable-a-server feature has a demonstration
  in the shipped example. `scenario.clsz`/`scenario2.clsz`/the
  duplicate `scenario_prim-dr(ht)_strg_net.clsz` the audit found only
  exist in the GitHub repo, not here - can't fix files this copy never
  had; flagged for the user to delete or re-save directly.

**Not touched - needs a decision (per the audit's own instruction):**
S25 (was the `.github/workflows` deletion on GitHub intentional?), S7
(no build doc), S14 units (binary vs decimal GB - changes sizing output
for every existing project), S22 (HT classification duplication -
`ServersPage._refresh_ht_global` vs `ClusterProject.
hyperthreading_state`). A7 falls out of S7.

## v2.11.1 (CI actually run for real - caught a genuinely stale test)

- GitHub Actions correctly ran `.github/workflows/tests.yml` on the first
  real push (that's what `on: push:` in that file does - automatically,
  no separate action needed) and failed - `python -m pytest` had never
  actually been run end-to-end before this point, since pytest wasn't
  installed anywhere it could be invoked earlier. First real run: 34/35
  passed, 1 failed - `test_import_servers_accepts_float_formatted_ints`
  built its own inline test CSV that predated the `enabled` column added
  to Server/SERVER_FIELDS in v2.10.0 (the Disable-a-server feature), so
  the schema check correctly flagged "missing column: enabled" -
  correct behavior from the schema validator, a stale fixture in the
  test. Fixed the fixture; 35/35 now pass, exit code 0.

## v2.11.0 (PDF report replaced with a structured, editable Word report)

- Reports tab's "Export PDF Report" replaced with "Export Word Report"
  (.docx) - a PDF nobody was going to print wasn't earning its place;
  a Word document is something the recipient can actually keep working
  with (add a letterhead, trim sections, rebrand for a client).
- New structure, in order: **Servers** (per-site summary table, then
  every server listed individually - name, vendor, model, sockets x
  cores, HT, effective cores, RAM, enabled/disabled status), **Storage**
  (same summary-then-detail pattern), **Network** (switches + full
  connections list, endpoint names resolved), **Cluster** (the
  Primary/DR breakdown that used to be the whole report - demand,
  oversubscription with color-coded status, N+1 with the v2.10.1
  shortfall detail, DR readiness, thresholds used), **Virtual Machines**
  (every VM - vCPU/RAM/disk/Workload Tier/DR Protected/power state).
  Every inventory section leads with an aggregate table, then the full
  per-device listing below it, deliberately always all sections (no
  section-picker dialog) - trimming what's not needed is a few clicks in
  Word afterward.
- New `python-docx` dependency (same precedent as openpyxl for Smart
  Import) - `src/calculations/docx_report.py`, Qt-free like
  `html_report.py` was, fully testable by inspecting the returned
  `Document` object's paragraphs/tables directly
  (tests/test_docx_report.py). `html_report.py` and the QTextDocument/
  QPrinter PDF-printing path are both deleted - dead code once nothing
  calls them.
- Verified visually: rendered a real example project's report through
  LibreOffice to PDF and inspected the page images - tables, color-coded
  status text (green/orange/red), and the N+1 shortfall message all
  render correctly.

## v2.10.1 (N+1 explains WHAT is short, not just Yes/No)

- Follow-up to v2.10.0's N+1 CPU-tolerance fix: a bare "No" left the
  actual blocker invisible - on the real example project, RAM alone was
  short (RAM demand already exceeds total capacity even with both hosts
  up) while CPU was comfortably within tolerance, but the old display
  gave no way to tell the two apart.
- New `ClusterProject.n_plus_one_check(site, cpu_warning_ratio)` returns
  an `NPlusOneCheck` (ram_ok, cpu_ok, ram_shortfall_gb,
  cpu_shortfall_effective_cores) instead of a bare bool -
  `n_plus_one_ok()` is now a thin wrapper around it, unchanged for
  existing callers. `SiteReport` carries the full check alongside the
  bool. Summary tab now shows a specific line under a failing N+1 - e.g.
  "Would need +514 GB RAM to survive losing a host" - instead of leaving
  the reader to guess whether it's a CPU or RAM problem, or by how much.
  Same detail added to the Reports text export.

## v2.10.0 (N+1 CPU tolerance fix, Server Disable toggle)

- **Fixed a real N+1 correctness bug**, caught by testing against
  `scenario_full_example.clsz`: `n_plus_one_ok()` compared CPU demand
  against remaining capacity at a strict, literal 1:1 vCPU:pCPU ratio -
  meaning almost ANY healthy, normally-oversubscribed virtualized
  cluster would show "Survives N+1: No", even when losing a host would
  land well within a totally reasonable oversubscription range (verified
  case: 176 vCPU across 48 remaining cores = 3.67:1, comfortably within
  Dev/Test-tier tolerance, but the strict check failed it outright).
  `n_plus_one_ok(site, cpu_warning_ratio=1.0)` now takes the project's
  configured CPU warning threshold (Settings) as an optional parameter -
  `build_site_report()` passes it in for a realistic answer everywhere
  it's shown (Summary/Reports/Compare). RAM deliberately keeps ZERO
  overcommit tolerance regardless of the ratio passed in - RAM overcommit
  (swapping/ballooning) is a fundamentally different, worse risk than
  CPU time-slicing, so "survives" for RAM still means literal capacity
  covers demand. Direct callers not passing a ratio keep the old strict
  behavior by default (no silent behavior change for existing callers).
- Also fixed a confusing display case surfaced by the same investigation:
  a site with a server but ZERO VMs assigned to it trivially "survives"
  N+1 (nothing to fail over) - the Summary tab now shows "n/a (no VMs)"
  with an explanatory tooltip there, instead of a bare "Yes" that reads
  like a real resilience claim.
- **New: Disable a server without deleting it.** Right-click a server
  (or a multi-selection) -> "\U0001f6d1 Disable" / "\u2705 Enable". A
  disabled server is excluded from ALL capacity math (`ClusterProject.
  servers_at()` is the one choke point every calculation already goes
  through) while staying fully visible in the Servers table - a "Status"
  column shows Enabled/\u26a0 Disabled. This is exactly what's needed to
  quickly simulate "this host is down" (a real failure, maintenance) and
  see the effect on oversubscription/N+1 immediately, without the
  previous delete-then-recreate friction. New `Server.enabled` field
  (CSV column added, old files without it default to enabled=True) and
  `ProjectService.set_enabled_for_servers()` (selection-scoped, one undo
  snapshot for the whole selection).

## v2.9.3 (honest disclosure: CPU-for-hypervisor not modeled, scope notes added)

- Verified via web search (not memory) that there's no universal fixed
  "N CPUs reserved" figure for VMware ESXi the way IBM's own
  product-specific docs sometimes state (that 2-core figure is IBM
  Spectrum Accelerate's own requirement, not a general VMware rule) -
  the closest real vendor-best-practices figure found is ~8-10% CPU
  overhead (Delphix, citing VMware's resource management guide), same
  magnitude as RAM overhead. No clean current figure was found for
  Hyper-V's CPU overhead specifically (only RAM, 512MB-2GB for the
  parent partition) - noted honestly as "tends to be higher, no single
  widely-quoted number" rather than inventing one.
- Cluster Preparation's Result page now states plainly that Memory
  Reserve covers RAM overhead but nothing reserves CPU overhead the same
  way - with the figures above, not a fabricated precise number.
- New README "Scope & Assumptions" section - the same "intentionally
  simple, no NUMA/CPU reservations/RAID overhead beyond a flat %" spirit
  already baked into the app's own tone, now stated explicitly where
  someone evaluating the tool will actually see it.

## v2.9.2 (VM Site bulk-move - distinct from DR Protected)

- Clarified a real distinction that was causing confusion: DR Protected
  (v2.9.0) flags a VM as replicated to DR while it keeps living on its
  current site - it does NOT relocate the VM. Moving a VM's actual
  location (Primary <-> DR) is a separate concept, `VirtualMachine.site`.
  Both now have the same bulk/selection tooling: new second row on the
  VMs tab, "Bulk move" - a Site combo (Primary/DR) with "Set Site
  (Selected)" / "Set Site (All)" buttons, plus matching right-click
  context actions ("\U0001f4cd Move to Primary" / "Move to DR"). New
  `ProjectService.set_site_for_vms()` (selection-scoped, one undo
  snapshot). Every confirmation dialog for this explicitly states it's
  different from DR Protected, to head off the exact confusion that
  prompted this.

## v2.9.1 (full ready-to-load example project)

- New `examples/scenario_full_example.clsz` - a complete project (3
  servers Primary/DR with mixed Hyperthreading, 2 storage systems, 45
  VMs, 4 switches, 5 connections incl. a direct-attach FC link) that
  loads directly via File > Open, instead of importing 5 separate CSVs
  by hand to reconstruct the same scenario. Verified it round-trips
  cleanly through project_repository (save -> load -> same counts).

## v2.9.0 (selection-scoped DR Protected / Workload Tier, two new example files)

- New examples: `vms_no_dr_example.csv` (45 VMs, none DR-protected - a
  clean starting point for the "select some, mark as DR" workflow below)
  and `servers_2primary_1dr_example.csv` (2 Primary hosts with HT off, 1
  DR host with HT on - a mixed-HT scenario for testing).
- VMs tab: right-click a selection now offers "\U0001f6e1 Mark DR
  Protected" / "Un-mark DR Protected" (with a confirmation dialog stating
  the count) - the common real workflow is loading a full VM list, then
  selecting just the subset that should actually go to DR (e.g. 12 of
  45), not touching the other 33. The existing top "Bulk edit" row's DR
  Protected checkbox and Workload Tier combo each gained an "Apply
  (Selected)" button alongside the existing "Apply (All)", covering the
  same selection-scoped case a second way.
- New `ProjectService.set_dr_protected_for_vms()` / 
  `set_workload_tier_for_vms()` - selection-scoped siblings of the
  existing set_all_vms_* methods, one undo snapshot per action regardless
  of how many VMs are in the selection.
- `MultiSelectTableView` (shared by Servers/Storage/VMs/Network) gained
  generic `set_custom_actions()` extensibility for page-specific
  right-click menu items, instead of hardcoding VM-only concepts (DR
  Protected) into a widget the other three pages also use.
- Confirmed existing behaviour, no change needed: Cluster Preparation's
  2-host minimum floor only applies to ITS OWN recommendation - the
  Servers tab has no such restriction, adding a single server manually
  (e.g. to check one box's own oversubscription) has always worked and
  still does.

## v2.8.2 (HA semantics corrected - Basic HA and None share host count, N+1 is the real reservation)

The v2.8.0 fix went too far: it made "Basic HA" behave exactly like
"N+1" (reserve one extra host). The actual distinction, per further
clarification: "None" and "Basic HA" size for the SAME fewest-hosts
count - the difference is whether the HA feature is configured at all,
not host count. "None" means no automatic VM restart on a host failure
(that host's VMs stay down). "Basic HA" means restart IS automatic
(vSphere HA / Failover Clustering with no admission control), but no
capacity is pre-reserved - survivors take the full load in a heavy
overload until capacity is added back. Only "N+1"/"N+2" explicitly
reserve host-level capacity so a failure causes NO shortfall at all -
survivors stay within the target oversubscription ratio instead of
overloading. `_HA_EXTRA_HOSTS` reverted to `{"None": 0, "Basic HA": 0,
"N+1": 1, "N+2": 2}`; the Policy page's live explanation text and the
regression test both rewritten to match.

## v2.8.1 (VM Storage card, Settings preset feedback)

- VMs tab: "RAM Oversub." card replaced with "VM Storage" (total disk_gb
  across all VMs, Primary+DR, including powered-off ones since disk
  persists regardless of power state) - RAM oversubscription info is
  still available on the Summary tab, this card duplicated it without
  adding anything new.
- Settings preset buttons ("Use This Preset", "Apply") now show a
  visible confirmation after each click. Root cause of the reported
  "only works once, then Use This Preset and Apply seem to disappear":
  they never disappeared or stopped working - verified the underlying
  logic re-applies correctly on every click, in sequence, across all 5
  presets. What actually happened: several presets now share IDENTICAL
  CPU ratios after the v2.7.x research-driven updates (VMware/Hyper-V
  both 3:1/5:1) - switching between two presets with the same numbers
  produced no visible spinbox change, which looked exactly like a dead
  button. The buttons now say so explicitly instead of changing values
  silently.

## v2.8.0 (Cluster Preparation: real optimizer, not a form; plus a batch of fixes from field testing)

Major rework driven by testing against a real 45-VM example file - the
wizard was recommending 6 hosts (2x16-core) for only 176 vCPU of demand,
landing at 0.5:1 utilization when the target was ~2.25:1. Root cause:
the Host Spec page pre-filled a guess BEFORE Growth/HA/Reserve were
known, so the guessed RAM/host was too small once those were applied,
forcing far more hosts than necessary.

- **Host Spec removed as a separate input page.** It's now an OUTPUT,
  computed on the Result page by `_optimize_host_spec()` (src/
  calculations/cluster_preparation.py): a grid search over common
  core-count (8-64/socket) and RAM (64GB-2TB) combinations, picking the
  one needing the FEWEST hosts, and among ties, the one landing closest
  to a target CPU oversubscription ratio (derived from the chosen
  hypervisor - roughly 3/4 of its warning threshold, e.g. 2.25:1 for a
  3:1 VMware warning). The Result page still shows the spec fields, but
  editable and pre-filled with the OPTIMIZED answer - "Reset to
  Optimized Suggestion" button discards manual edits and recomputes.
  `SizingPolicy.host_spec` is now optional (None = auto-optimize).
- **Minimum 2-host floor** - a single host is never a "cluster" (no
  maintenance windows, no resilience), so compute_sizing() never
  recommends fewer than 2 regardless of HA setting. This, combined with
  the optimizer fix above, is what turned the "6 hosts, 2x16-core,
  1536GB RAM, 0.5:1 ratio" degenerate result into a realistic "2-3
  hosts, right-sized cores/RAM, ratio near target".
- **"Basic HA" now reserves failover capacity (same math as N+1)** -
  real vSphere HA / Hyper-V Failover Clustering admission control
  reserves capacity for a host failure by default once turned on; the
  earlier "Basic HA = 0 extra hosts" modeled a feature flag, not what
  HA actually does. The Policy page now shows a live explanation of what
  each HA level means as you select it.
- **Expected Growth defaults to 30%** (was 0%).
- **VDI tier default lowered from 18:1 to 12:1** (was the range
  midpoint; the jump from Development/Test's 8:1 felt too large).
- **Explicit Back button layout** on the wizard - some Qt wizard
  styles/platforms were reportedly hiding it; the button layout is now
  spelled out explicitly (Back/Stretch/Cancel/Next/Finish) rather than
  relying on a platform default.
- **Workload/Result pages now state the Primary vs already-on-DR VM
  split explicitly** ("39 Primary VMs... 6 more VMs already tagged
  site=DR, excluded") - fixes the "I loaded 45, it shows 39, is that a
  bug?" confusion (it wasn't a bug - 6 VMs in the example file are
  genuinely tagged site=DR).
- **New bulk-edit row on the VMs tab**: "Set Workload Tier" and "DR
  Protected: Apply to All", each one undo step for every VM at once
  (`ProjectService.set_all_vms_workload_tier`/`set_all_vms_dr_protected`)
  - mirrors the existing per-server Hyperthreading bulk toggle.
- **Add vs Replace choice** when applying a Cluster Preparation
  recommendation to a site that already has servers/storage - new
  `ProjectService.replace_servers_and_storages_at_site()` (one atomic
  undo step) alongside the existing additive
  `add_servers_and_storages()`.
- **Fixed a real bug**: the Servers tab's "Total Threads" card ignored
  each server's own Hyperthreading toggle - a server with HT explicitly
  disabled still contributed its full SMT width to the card. Renamed to
  "Effective Cores (HT)" and now uses the same HT-aware calculation used
  everywhere else in the app (new `ClusterProject.total_effective_cores`
  property).
- Investigated the reported "DR Protected summary doesn't update after
  unprotecting VMs" - could not reproduce; the signal chain
  (`update_vm()`/`set_all_vms_dr_protected()` -> `vms_changed` +
  `changed` -> `SummaryPage.refresh()`) and the underlying
  `dr_protected_vm_count()`/`dr_ready()` calculations are both stateless
  and recompute fresh on every call, verified directly. Added a manual
  "Reset to Optimized Suggestion" / recompute path on the Result page
  regardless, as a safety net.
- Regression tests rewritten for the new optimizer-based API
  (tests/test_cluster_preparation.py) - `suggest_host_spec()` removed
  (superseded by the optimizer), 11 tests covering the HA/floor fixes,
  DR-site exclusion, and the optimizer's override/auto-pick behavior.

## v2.7.1 (preset refinements: Nutanix split out, Citrix given a real number)

- Nutanix AHV is now its own preset (was grouped into the Proxmox/KVM
  label) - same 4:1/6:1 guidance (also KVM-based, same cgroups
  scheduling reasoning), just its own dropdown entry for clarity. 5
  presets total now.
- Citrix Hypervisor moved off the "same as VMware, no real data"
  placeholder to an explicit 3.5:1/5.5:1.
- Hyper-V stays at 3:1/5:1 (no vendor-specific ratio found) - flagged in
  both the ROADMAP and the preset's own description as a wishlist item
  if a real number ever turns up.

## v2.7.0 (Workload Tier replaces Workload Profile; Settings presets updated from research)

- **Settings hypervisor presets updated** with vendor-specific research
  (r/sysadmin, Microsoft Tech Community, oversubscription guides):
  VMware moves from 4:1/6:1 to a more conservative **3:1/5:1**
  ("commonly-cited conservative baseline: 1.5:1 to 3:1 for healthy
  headroom, watch CPU Ready time under 5%"). Hyper-V stays at 3:1/5:1
  (same conservative baseline, per explicit direction - no vendor-
  specific ratio was found for Hyper-V itself). Proxmox VE / KVM /
  Nutanix AHV stays at 4:1/6:1 ("cgroups scheduling generally
  problem-free up to 4:1 provided host utilization stays under 70-80%
  at peak" - label updated to explicitly include Nutanix AHV, grouped
  under this preset per the research rather than a dedicated entry).
  Citrix Hypervisor stays at 3:1/5:1 but is now explicitly labeled as a
  placeholder with no vendor-specific research behind it.
- **Workload Tier replaces Workload Profile** - a full swap, not an
  addition. The earlier "CPU Intensive / Balanced / Memory Intensive /
  Storage Intensive / Light" categories with an assumed CPU utilization
  % each are gone. In their place: "Tier-0 / Mission-Critical" (1:1),
  "Standard Production" (3:1-5:1, default 4:1), "Development / Test"
  (6:1-10:1, default 8:1), "High-Density VDI" (12:1-24:1, default 18:1)
  - a more standard, industry-recognized SLA-tolerance framing
  (src/models/workload_tier.py). Cluster Preparation's effective-vCPU
  formula changed from `vcpu * utilization%` to `vcpu / tier_ratio` -
  mathematically the same DIRECTION of effect (not every allocated vCPU
  needs a full physical core), just parameterized the way sysadmins
  actually discuss oversubscription. VirtualMachine.workload_profile
  renamed to workload_tier throughout (model, VM dialog, VM table
  column, CSV schema - old workload_profile CSV column is no longer
  recognized, falls back to the Standard Production default via the
  same schema-drift tolerance every other field already has).
  Regression tests in tests/test_cluster_preparation.py updated to use
  real tier names instead of the retired profile names.
- Host Spec page (v2.6.0) is now pre-filled by `suggest_host_spec()`
  (src/calculations/cluster_preparation.py) instead of generic hardcoded
  defaults - a real proposal computed from the VMs' actual demand
  (core-count tier by total effective vCPU, RAM/host rounded to a common
  DIMM-friendly step, never below the single largest VM's RAM), not a
  blank form. Expected Growth's tooltip and label now explicitly state
  it applies equally to vCPU, RAM, AND storage demand together.

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
