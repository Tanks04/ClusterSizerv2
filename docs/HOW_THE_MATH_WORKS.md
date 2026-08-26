# How ClusterSizer Calculates Things

This explains, in plain language with small worked examples, exactly how
every number in the app is calculated. No code, no jargon left
unexplained - if you've ever been asked "how did it get to that number",
point people here.

Everything in this document follows one rule stated in
[the README's Scope & Assumptions](../README.md#scope--assumptions):
every ratio and percentage here is a sizing ASSUMPTION meant as a
sensible starting point, not a measurement of your actual environment.

## 1. The core idea: oversubscription

"Oversubscription" just means: how much you've PROMISED to VMs versus
how much PHYSICAL hardware actually exists to deliver it.

- If you have VMs that add up to 40 vCPUs, and your physical hosts only
  have 10 real CPU cores, you've oversubscribed CPU **4:1**.
- Why is this normally fine for CPU but not for RAM? Because CPU can be
  *time-sliced* - 40 vCPUs don't all need to compute at the exact same
  instant, so the scheduler shares 10 real cores between them and it
  usually works out fine, as long as you're not asking for way too much
  at once. RAM can't really be time-sliced the same way - if you promise
  VMs 500GB of RAM and only have 400GB physical, something has to give
  (swapping to disk, or a VM simply can't start), which is why RAM is
  tracked as **% used**, not as a ratio, and healthy is "under 80%", not
  "some healthy multiple".
- Storage works the same way as RAM - tracked as % used, not a ratio.

## 2. CPU Oversubscription (ratio, e.g. "4.0 : 1")

```
CPU ratio = (sum of vCPU across powered-on VMs at this site)
            / (sum of effective cores across enabled servers at this site)
```

**Effective cores**, not just physical cores - see Hyperthreading below.

**Worked example**: 2 servers, each 2 sockets x 16 cores = 32 physical
cores/server, Hyperthreading ON on both = 64 effective cores/server
(threads_per_core x 2). Two servers = 128 effective cores total. VMs
add up to 176 vCPU. Ratio = 176 / 128 = **1.375 : 1**.

Status color (Settings tab lets you change these per hypervisor):
- Green (OK): below the "warning" threshold (e.g. under 4:1 for a
  Proxmox/KVM preset)
- Orange (Warning): between warning and critical
- Red (Critical): above the "critical" threshold

## 3. RAM Utilization (%)

```
RAM % = (sum of RAM across powered-on VMs at this site)
        / (sum of physical RAM across enabled servers at this site)
```

No Hyperthreading-style adjustment here - RAM is RAM. **Worked
example**: 2 servers x 512GB RAM = 1024GB physical. VMs ask for 820GB
total. RAM % = 820 / 1024 = **80%** (right at the typical warning line).

## 4. Storage Utilization (%)

```
Storage % = (sum of disk size across ALL VMs, even powered-off)
            / (sum of USABLE storage capacity at this site)
```

Disk counts VMs regardless of power state (a powered-off VM's disk
still occupies real space on the array). "Usable" capacity is whatever
you entered on the Storage tab - already net of RAID/erasure-coding
overhead, which is why nothing here re-applies a RAID percentage again.

For **HCI storage** (vSAN, Storage Spaces Direct, Nutanix AHV, etc. -
checked via the Storage tab's HCI option), Raw Capacity is auto-summed
from the linked servers' Local Disk (Raw) field instead of being typed
in directly:

```
Raw Capacity = sum of local_disk_raw_tb across whichever servers are checked
```

Usable Capacity still has to be entered manually either way - the real
raw-to-usable shrinkage for HCI depends on the storage policy (FTT/
erasure coding), which varies too much to model exactly, so it's
treated the same as `raid_overhead_percent` on a traditional array:
informational, not authoritative. Once Usable is entered, storage
utilization is calculated exactly the same way regardless of whether
the storage behind it is a traditional array or an HCI cluster.

## 5. Hyperthreading - "effective cores"

Each server has its own Hyperthreading Enabled toggle - this app never
assumes it's on or off for the whole cluster, since real clusters often
mix hosts with different settings (e.g. a slower-but-safer DR host with
HT off).

```
effective_cores = sockets x cores_per_socket x (threads_per_core if HT enabled, else 1)
```

**Worked example**: 2 sockets x 16 cores/socket = 32 physical cores.
With HT on (2 threads/core) -> 64 effective cores. With HT off -> stays
32. This "effective cores" number is what CPU Oversubscription and N+1
actually divide by - not the raw physical core count.

## 6. N+1 / N+2 - "does it survive losing a host?"

The question: if your BIGGEST host died right now, would the REMAINING
hosts still cover everything?

- **RAM check**: strict, zero tolerance. Remove the RAM-largest host's
  RAM from the total. Remaining RAM must be >= current RAM demand. RAM
  overcommit causes swapping - a fundamentally worse failure mode than
  CPU contention, so no slack is given here.
- **CPU check**: allows the SAME oversubscription tolerance as your
  chosen hypervisor preset (Settings tab) - because a healthy cluster is
  EXPECTED to run some CPU oversubscription day to day. Remove the
  cores-largest host's effective cores from the total. Remaining
  effective cores x your target ratio must be >= current raw vCPU
  demand.
- "None" and "Basic HA" size for the SAME fewest-hosts count - the
  difference between them isn't host count, it's whether the HA feature
  is configured at all. "None" means no automatic VM restart on a host
  failure (that host's VMs just stay down). "Basic HA" means restart IS
  automatic (real vSphere HA / Failover Clustering with no admission
  control), but no capacity is pre-reserved - survivors take the full
  load in a heavy overload until capacity is added back. Only **"N+1"**
  (reserves 1 extra host) and **"N+2"** (reserves 2) actually guarantee
  NO capacity shortfall after a failure.
- If the check fails, the app tells you exactly which resource is short
  and by how much (e.g. "+514 GB RAM needed") - not just a bare "No".

## 7. DR Readiness & DR Failover Preview

DR capacity has to cover TWO different kinds of load at once:

1. VMs that live on DR **permanently** (e.g. a redundant domain
   controller that's just always running there) - normal VMs with
   Site = DR.
2. VMs marked **DR Protected** on Primary - these DON'T run on DR right
   now, they're backed up/replicated (Veeam, etc.) and would only be
   spun up on DR during an actual disaster. Each has its OWN "DR
   footprint" (vcpu/ram/disk) separate from its Primary sizing, since a
   DR copy is often smaller/cheaper than the real production VM.

```
DR failover demand = (demand from VMs already on DR)
                    + (DR footprint of every DR-Protected VM on Primary)
```

DR Readiness checks whether DR's physical capacity covers this COMBINED
number. The Summary tab's DR card, by default, shows DR's CURRENT
demand only (type 1) - it does NOT include the failover load, so DR
doesn't look artificially overloaded by VMs that aren't actually
running there yet. Click **"Preview DR Failover"** to see the same card
recalculated with the FULL combined demand instead - this is how you
find out "if I actually hit the big red disaster-recovery button right
now, does DR still hold up, or do I need more hardware first".

## 8. Cluster Preparation - reverse sizing (VMs -> hosts to buy)

Every other calculation in the app asks "given the servers I HAVE, is
this safe". Cluster Preparation asks the opposite question: "given the
VMs I NEED to run, how many hosts should I buy, and how big?"

**Workload Tiers** replace a flat "count every vCPU the same" approach.
Each VM gets a tier (Tier-0/Mission-Critical, Standard Production,
Development/Test, High-Density VDI), and each tier has its own
commonly-cited safe oversubscription ratio:

| Tier | Ratio | What it means |
|---|---|---|
| Tier-0 / Mission-Critical | 1:1 | No oversubscription tolerance - full weight |
| Standard Production | 4:1 (default) | Typical mixed workload |
| Development / Test | 8:1 (default) | Tolerates queuing/delay |
| High-Density VDI | 12:1 (default) | Users idle asynchronously |

```
effective vCPU for one VM = vm.vcpu / tier_ratio
```

**Worked example**: an 8-vCPU Tier-0 database counts as 8 / 1 = **8**
effective vCPU (full weight). An 8-vCPU VDI desktop counts as 8 / 12 =
**0.67** effective vCPU (barely any weight - it tolerates heavy
oversubscription). This is why a cluster full of VDI desktops needs far
fewer physical cores than the same vCPU count in databases would.

The wizard then **optimizes** a host spec (sockets/cores/RAM) by
searching common configurations, picking the one that needs the fewest
hosts while landing close to your hypervisor's target ratio (roughly
3/4 of its "warning" threshold - e.g. 2.25:1 for a 3:1 VMware warning).
You can still edit the suggested spec afterward.

## 9. RAID Calculator

Standard formulas, given `N` = active disks (after removing hot
spares) and `size` = size per disk:

| RAID | Usable capacity | Tolerates |
|---|---|---|
| RAID 0 | N x size | 0 disk failures |
| RAID 1 | (N/2) x size | 1 per mirrored pair |
| RAID 5 | (N-1) x size | 1 disk failure |
| RAID 6 | (N-2) x size | 2 disk failures |
| RAID 10 | (N/2) x size | 1 per mirrored pair |
| RAID 50 | (N - groups) x size | 1 per group |
| RAID 60 | (N - 2 x groups) x size | 2 per group |

**Worked example**: 8x 4TB disks in RAID 6 = (8-2) x 4TB = **24TB
usable**, tolerates 2 disk failures. Hot spares are bought (count toward
"raw" capacity) but don't count as active disks in the formula above.

The calculator also warns when RAID 5/6/50/60 (parity RAID has a real
write penalty) is combined with spinning disks - not because of what
workload you said you'd run, but because that combination is
intrinsically slower regardless of what's on it.

## 10. Backup 3-2-1-1 compliance

The classic rule: **3** copies of your data, on **2** different kinds
of media, with **1** of them offsite. The modern extension adds: **+1**
copy that's immutable/offline (survives ransomware reaching every
online system).

```
total copies = number of backup destinations you've entered, + 1 (the production copy itself)
```

- Meets 3-2-1 if: total copies >= 3, AND at least 2 different
  destination types are used, AND at least one destination is flagged
  Offsite.
- Meets 3-2-1-1 if it meets 3-2-1 AND at least one destination is
  flagged Immutable/Offline (can be the SAME destination as the offsite
  one, or a different one).

This app does NOT try to check the "0" some vendors now add
(zero errors after a verified restore test) - that's a PRACTICE (did
you actually test a restore recently), not something derivable from a
list of destinations someone typed in.

## 11. Rack Sizing (Rack Units + Power)

The simplest calculation in the app - just addition, no formula to
speak of:

```
Total rack units = sum of every enabled Server's U + every Storage's U (including its shelves) + every Switch's U, at that site
Total power (W)  = same, but for power_watts instead of rack_units
```

Anything left at 0 (never entered) is excluded, not counted as a real
zero - so a project where only half the equipment has this filled in
still gives a meaningful (if partial) total instead of looking broken.
Power is meant to be the nameplate/max draw from the datasheet, not
"typical" - safer for circuit/PDU planning than an optimistic average.

One deliberate difference from every other calculation in this app: a
**disabled** server (see the Servers tab's Disable feature) still counts
here. "Disabled" means "exclude from compute capacity planning" (e.g.
simulating a host being down) - it doesn't mean the server was
physically removed from the rack. If it's still plugged in, it's still
occupying its U and still drawing power, so Rack Sizing still counts it
even while CPU/RAM/Storage oversubscription treats it as if it doesn't
exist.


## 12. Pricing

Deliberately simple, on purpose - this app gives admins a running
total of what things cost, it isn't a sales quoting tool. (An earlier
version tried cost-vs-price/margin/uplift tracking here - it didn't
fit, so it was pulled back out.)

**Equipment pricing** - each Server, Storage (including every
expansion shelf separately), Network Switch, and Backup Destination
has one Price field, entered right on that entity - no separate
re-entry. The Pricing tab just sums it up by category:

```
Servers total  = sum of every Server's price
Storage total  = sum of every Storage's price + every one of its shelves' price
Network total  = sum of every Network Switch's price
Backup total   = sum of every Backup Destination's price
Grand total    = sum of the four category totals
```

**Worked example**: 2 servers at 22,000 EUR each, 1 storage array at
120,000 EUR with one 17,000 EUR expansion shelf, 4 switches averaging
15,500 EUR each, 1 backup destination at 13,500 EUR. Servers total =
44,000. Storage total = 120,000 + 17,000 = 137,000. Network total =
62,000. Backup total = 13,500. Grand total = **256,500 EUR**.

**Licenses, Warranties & Maintenance** - a separate, unrelated list for
tracking renewals: what it is, what it costs, how long it lasts, and
when it expires. The only "calculation" here is a status flag per item,
based on comparing its expiry date to today:

```
days_until_expiry = expiry_date - today

days_until_expiry < 0           -> Expired
0 <= days_until_expiry <= 90    -> Expiring Soon
days_until_expiry > 90          -> OK
expiry_date blank or unparseable -> Unknown (not flagged either way)
```

**Worked example**: a support contract expiring in 68 days shows
"Expiring Soon" - close enough that it's worth renewing now rather than
finding out it lapsed. One expiring in 860 days shows "OK" - nothing to
do yet. One that expired 24 days ago shows "Expired", in red, since it
already needs attention.
