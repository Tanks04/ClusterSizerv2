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
            "Commonly-cited vCPU:pCPU starting point for VMware ESXi - "
            "around 4:1 for general-purpose workloads. Push higher for "
            "light/idle VMs, lower for CPU-intensive ones."
        ),
        thresholds=Thresholds(
            cpu_warning_ratio=4.0, cpu_critical_ratio=6.0,
            ram_warning_ratio=0.80, ram_critical_ratio=1.00,
            storage_warning_ratio=0.80, storage_critical_ratio=0.95,
        ),
    ),
    ThresholdPreset(
        key="hyperv",
        label="Microsoft Hyper-V",
        description=(
            "Commonly-cited vCPU:pCPU starting point for Hyper-V - around "
            "3:1, somewhat more conservative than the VMware rule of thumb."
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
            "Commonly-cited vCPU:pCPU starting point for Proxmox VE / plain "
            "KVM - around 4:1, similar to the VMware rule of thumb."
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
            "Commonly-cited vCPU:pCPU starting point for Citrix Hypervisor - "
            "around 3:1, in the same range as the Hyper-V rule of thumb."
        ),
        thresholds=Thresholds(
            cpu_warning_ratio=3.0, cpu_critical_ratio=5.0,
            ram_warning_ratio=0.80, ram_critical_ratio=1.00,
            storage_warning_ratio=0.80, storage_critical_ratio=0.95,
        ),
    ),
]
