from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    OK = "OK"
    WARNING = "Warning"
    CRITICAL = "Critical"
    UNKNOWN = "Unknown"  # no data (e.g. 0 physical resources)


@dataclass
class Thresholds:
    """Warning thresholds for oversubscription calculations. Adjustable on
    the Settings page; default values match common general-purpose
    virtualization practice (see PRESETS below for other workload types)."""

    cpu_warning_ratio: float = 4.0     # e.g. 4 vCPU per 1 physical core
    cpu_critical_ratio: float = 6.0

    ram_warning_ratio: float = 0.8     # 80% of physical RAM allocated to VMs
    ram_critical_ratio: float = 1.0    # >100% = RAM overcommit

    storage_warning_ratio: float = 0.8
    storage_critical_ratio: float = 0.95

    @staticmethod
    def status_for(ratio: float | None, warning: float, critical: float) -> Status:
        if ratio is None:
            return Status.UNKNOWN
        if ratio >= critical:
            return Status.CRITICAL
        if ratio >= warning:
            return Status.WARNING
        return Status.OK

    def cpu_status(self, ratio: float | None) -> Status:
        return self.status_for(ratio, self.cpu_warning_ratio, self.cpu_critical_ratio)

    def ram_status(self, ratio: float | None) -> Status:
        return self.status_for(ratio, self.ram_warning_ratio, self.ram_critical_ratio)

    def storage_status(self, ratio: float | None) -> Status:
        return self.status_for(ratio, self.storage_warning_ratio, self.storage_critical_ratio)


# Fixed (not Settings-adjustable) cutoffs for the tier-weighted
# "effective" CPU ratio - see HOW_THE_MATH_WORKS.md \u00a72a. 1.0 is
# intrinsically "fully booked assuming zero oversubscription tolerance
# anywhere" (Tier-0's own ratio), not a site-specific policy choice
# like the ordinary CPU/RAM/Storage thresholds above.
EFFECTIVE_CPU_WARNING_RATIO = 1.0
EFFECTIVE_CPU_CRITICAL_RATIO = 1.5


def effective_cpu_status(ratio: float | None) -> Status:
    return Thresholds.status_for(ratio, EFFECTIVE_CPU_WARNING_RATIO, EFFECTIVE_CPU_CRITICAL_RATIO)


@dataclass
class ThresholdPreset:
    key: str
    label: str
    description: str
    thresholds: Thresholds


# Commonly-cited vCPU:pCPU starting points per hypervisor vendor - NOT
# official guarantees, actual safe ratios always depend on the workload
# mix (a database cluster and a VDI farm on the same hypervisor want very
# different numbers). These are meant as a sensible starting point to
# adjust from, not a promise. RAM/storage thresholds stay the same across
# vendors since oversubscription guidance there isn't really
# vendor-specific the way vCPU:pCPU commonly is.
PRESETS: list[ThresholdPreset] = [
    ThresholdPreset(
        key="vmware",
        label="VMware (ESXi / vSphere)",
        description=(
            "Conservative baseline commonly cited for VMware ESXi: 1.5:1 to "
            "3:1 for healthy headroom. Keep CPU Ready time under 5% per VM; "
            "avoid over-allocating vCPUs to small VMs (scheduling overhead)."
        ),
        thresholds=Thresholds(
            cpu_warning_ratio=3.0, cpu_critical_ratio=5.0,
            ram_warning_ratio=0.80, ram_critical_ratio=1.00,
            storage_warning_ratio=0.80, storage_critical_ratio=0.95,
        ),
    ),
    ThresholdPreset(
        key="hyperv",
        label="Microsoft Hyper-V",
        description=(
            "Same conservative baseline as VMware (3:1 warning) - no "
            "Hyper-V-specific ratio found yet (wishlist: find one). Watch CPU "
            "Contention Time per Dispatch / jitter counters on modern Windows "
            "Server releases; MinRoot and CPU groups can isolate priority workloads."
        ),
        thresholds=Thresholds(
            cpu_warning_ratio=3.0, cpu_critical_ratio=5.0,
            ram_warning_ratio=0.80, ram_critical_ratio=1.00,
            storage_warning_ratio=0.80, storage_critical_ratio=0.95,
        ),
    ),
    ThresholdPreset(
        key="proxmox",
        label="Proxmox VE / KVM",
        description=(
            "Standard Linux cgroups scheduling generally handles up to 4:1 "
            "without issue, provided overall host physical CPU utilization "
            "stays below 70-80% at peak."
        ),
        thresholds=Thresholds(
            cpu_warning_ratio=4.0, cpu_critical_ratio=6.0,
            ram_warning_ratio=0.80, ram_critical_ratio=1.00,
            storage_warning_ratio=0.80, storage_critical_ratio=0.95,
        ),
    ),
    ThresholdPreset(
        key="nutanix",
        label="Nutanix AHV",
        description=(
            "Also KVM-based, standard cgroups scheduling - same guidance as "
            "Proxmox/KVM: generally problem-free up to 4:1 provided overall "
            "host physical CPU utilization stays below 70-80% at peak."
        ),
        thresholds=Thresholds(
            cpu_warning_ratio=4.0, cpu_critical_ratio=6.0,
            ram_warning_ratio=0.80, ram_critical_ratio=1.00,
            storage_warning_ratio=0.80, storage_critical_ratio=0.95,
        ),
    ),
    ThresholdPreset(
        key="citrix",
        label="Citrix Hypervisor (XenServer)",
        description=(
            "3.5:1 - between the VMware/Hyper-V conservative baseline and "
            "the Proxmox/KVM ceiling."
        ),
        thresholds=Thresholds(
            cpu_warning_ratio=3.5, cpu_critical_ratio=5.5,
            ram_warning_ratio=0.80, ram_critical_ratio=1.00,
            storage_warning_ratio=0.80, storage_critical_ratio=0.95,
        ),
    ),
]
