## 
Tiers – Explanation

Think of vCPUs as people waiting in line at a checkout.
Imagine that the physical CPU cores are checkout counters in a store, while the vCPUs assigned to VMs are the people waiting in line.

The question is: **How many people can you put in line at a single checkout before the queue becomes too long?**

The answer depends on **who is waiting in line**:

* Someone buying just one item (quick to process) → you can have more of them waiting at the same checkout.
* Someone with a full shopping cart (takes a long time to process and occupies the checkout for longer) → you need to assign fewer of them per checkout, 
otherwise a queue starts building up.

VMs work in much the same way. Some are **"quick to process"** because they rarely make heavy use of the CPU, while others are **"slow to process"** 
because they constantly demand CPU resources and cannot afford to wait.

That is why we have four different **Workload Tiers**:

| Workload Tier                         |                                                   How many can share one physical core |
| ------------------------------------- | -------------------------------------------------------------------------------------: |
| Tier-0 (databases, critical systems)  |                           **1** — needs its own checkout and should never have to wait |
| Standard Production (regular servers) |                                                      **4** — can tolerate some waiting |
| Dev/Test                              |                                                     **8** — some waiting is acceptable |
| VDI (virtual desktops)                | **12** — most users are idle most of the time and only occasionally need CPU resources |

This is the value that can now be adjusted manually in **Settings**.

## Formula – How Much Capacity Does a VM Really Consume?
The effective capacity consumed by a VM is calculated as:
**Effective VM consumption = Number of vCPUs / Tier ratio**

Examples:

**Tier-0 VM with 8 vCPUs = 8 / 1 = 8**

It carries its full weight because nothing is being shared.

**VDI VM with 8 vCPUs= 8 / 12 = 0.67**

Its effective consumption is much lower because most of the time those vCPUs are not actively demanding physical CPU resources.

## Example, Step by Step

You have:
**20 VMs, 200 vCPUs in total, running on 64 physical CPU cores.**
### First Number – Raw vCPU Oversubscription Ratio
This number **NEVER changes**:
**200 / 64 = 3.1:1**

This simply tells us:
> "How much virtual CPU capacity have I allocated compared with how much physical CPU capacity I actually have?"

It does not care what type of VMs they are or how heavily they use the CPU.

### Second Number – Tier-Adjusted CPU Load

This number **DOES change depending on the workload tier**.

Here we are asking:

> "Given the type of workloads these VMs are running, how much physical CPU capacity are they effectively consuming?"

**If all VMs are Tier-0:**

200 / 1 = **200 effective vCPUs**
200 / 64 = **3.1**

This is the same as the raw oversubscription ratio because Tier-0 workloads receive no sharing discount.

**Result: Critical — heavily oversubscribed.**

**If all VMs are VDI:**

200 / 12 = **16.7 effective vCPUs**

16.7 / 64 = **0.26**

**Result: Excellent — plenty of physical CPU capacity available.**

**If the environment is 50% Tier-0 and 50% VDI:**

(100 / 1 + 100 / 12) / 64 = (100 + 8.33) / 64 = **1.69**

**Result: Still critical**, because the Tier-0 half of the environment carries its full weight and pulls the overall tier-adjusted load significantly upward.
