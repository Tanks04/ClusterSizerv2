"""Cluster Preparation - reverse-direction sizing: given the VMs you NEED
to run, how many hosts of a given spec should you buy? This is a
DIFFERENT calculation from the app's existing oversubscription-ratio
checks (Summary/VMs/Reports), which answer "given the servers I HAVE, is
my vCPU:pCPU ratio safe". Cluster Preparation uses a workload-weighted
effective-utilization model instead of a flat ratio, since a single
ratio is too blunt when sizing new hardware from scratch. No Qt
dependency, so it's testable on its own.
"""

import math
from dataclasses import dataclass, field

from src.models.cluster_project import ClusterProject, PRIMARY
from src.models.virtual_machine import VirtualMachine
from src.models.workload_profile import WORKLOAD_PROFILES, DEFAULT_WORKLOAD_PROFILE

HA_LEVELS = ["None", "Basic HA", "N+1", "N+2"]

# Extra hosts reserved on top of the base capacity requirement. "Basic HA"
# is a vSphere-style feature flag (VMs restart elsewhere on host failure)
# rather than a capacity reservation, so it adds no hosts by itself here -
# only N+1/N+2 explicitly reserve host-level capacity.
_HA_EXTRA_HOSTS = {"None": 0, "Basic HA": 0, "N+1": 1, "N+2": 2}


@dataclass
class HostSpec:
    """The candidate host you're sizing against - "if I buy hosts like
    this, how many do I need?" Mirrors the fields Server already has, so
    a result can be turned directly into real Server rows."""
    sockets: int = 2
    cores_per_socket: int = 16
    threads_per_core: int = 2
    hyperthreading_enabled: bool = True
    ram_gb: float = 512.0

    @property
    def effective_cores(self) -> int:
        cores = self.sockets * self.cores_per_socket
        return cores * self.threads_per_core if self.hyperthreading_enabled else cores


@dataclass
class SizingPolicy:
    ha_level: str = "N+1"
    growth_percent: float = 0.0
    memory_reserve_percent: float = 20.0  # hypervisor/mgmt/HA/growth overhead
    storage_overhead_percent: float = 20.0  # RAID/EC + headroom, mirrors Storage.raid_overhead_percent
    host_spec: HostSpec = field(default_factory=HostSpec)
    # Per-profile CPU utilization assumptions - starts from the catalog
    # defaults (src/models/workload_profile.py) but is editable per
    # project, since these are assumptions, not measurements.
    utilization_overrides: dict[str, float] = field(default_factory=dict)

    def utilization_for(self, profile_name: str) -> float:
        if profile_name in self.utilization_overrides:
            return self.utilization_overrides[profile_name]
        profile = WORKLOAD_PROFILES.get(profile_name) or WORKLOAD_PROFILES[DEFAULT_WORKLOAD_PROFILE]
        return profile.default_cpu_utilization


@dataclass
class SizingResult:
    vm_count: int
    workload_breakdown: dict[str, int]  # profile name -> VM count

    total_vcpu_raw: int
    total_effective_vcpu: float  # workload-weighted, drives CPU sizing
    total_ram_demand_gb: float
    total_ram_with_reserve_gb: float
    total_storage_demand_gb: float
    recommended_storage_usable_tb: float
    recommended_storage_raw_tb: float

    host_effective_cores: int
    hosts_for_cpu: int
    hosts_for_ram: int
    binding_constraint: str  # "CPU" | "RAM"
    raw_oversubscription_ratio: float | None  # simple vCPU:pCPU across required_hosts - a
    # familiar sanity-check number alongside the workload-weighted calc above,
    # not a replacement for it. None if required_hosts is 0.

    ha_extra_hosts: int
    required_hosts: int  # base (post-growth) + HA buffer

    dr_vm_count: int
    dr_hosts_for_cpu: int
    dr_hosts_for_ram: int
    dr_binding_constraint: str
    dr_required_hosts: int
    dr_storage_demand_gb: float
    dr_recommended_storage_usable_tb: float
    dr_recommended_storage_raw_tb: float


def _effective_vcpu(vm: VirtualMachine, policy: SizingPolicy) -> float:
    return vm.vcpu * policy.utilization_for(vm.workload_profile)


def _hosts_needed(demand: float, per_host: float) -> int:
    if per_host <= 0:
        return 0
    return math.ceil(demand / per_host)


def compute_sizing(project: ClusterProject, policy: SizingPolicy) -> SizingResult:
    growth_factor = 1 + (policy.growth_percent / 100)
    reserve_factor = 1 - (policy.memory_reserve_percent / 100)
    if reserve_factor <= 0:
        reserve_factor = 0.01  # guard against a 100%+ reserve making RAM sizing infinite

    primary_vms = project.vms_at(PRIMARY)

    breakdown: dict[str, int] = {}
    for vm in primary_vms:
        breakdown[vm.workload_profile] = breakdown.get(vm.workload_profile, 0) + 1

    total_vcpu_raw = sum(vm.vcpu for vm in primary_vms)
    total_effective_vcpu = sum(_effective_vcpu(vm, policy) for vm in primary_vms) * growth_factor
    total_ram_demand_gb = sum(vm.ram_gb for vm in primary_vms)
    total_ram_with_reserve_gb = (total_ram_demand_gb * growth_factor) / reserve_factor
    total_storage_demand_gb = sum(vm.disk_gb for vm in primary_vms) * growth_factor

    storage_overhead_factor = max(0.01, 1 - (policy.storage_overhead_percent / 100))
    recommended_storage_usable_tb = total_storage_demand_gb / 1024
    recommended_storage_raw_tb = recommended_storage_usable_tb / storage_overhead_factor

    host_effective_cores = policy.host_spec.effective_cores
    hosts_for_cpu = _hosts_needed(total_effective_vcpu, host_effective_cores)
    hosts_for_ram = _hosts_needed(total_ram_with_reserve_gb, policy.host_spec.ram_gb)

    base_hosts = max(hosts_for_cpu, hosts_for_ram, 1 if primary_vms else 0)
    binding_constraint = "RAM" if hosts_for_ram >= hosts_for_cpu else "CPU"

    ha_extra = _HA_EXTRA_HOSTS.get(policy.ha_level, 0)
    required_hosts = base_hosts + ha_extra if primary_vms else 0

    raw_oversubscription_ratio = (
        total_vcpu_raw / (required_hosts * host_effective_cores)
        if required_hosts > 0 and host_effective_cores > 0 else None
    )

    # DR: reuses each VM's OWN dr_protected flag + DR footprint (already
    # editable per-VM on the VMs tab) rather than a separate global "DR
    # capacity %" - see the module/VirtualMachine docstrings for why.
    dr_vms = [vm for vm in primary_vms if vm.dr_protected]
    dr_effective_vcpu = sum(
        vm.effective_dr_vcpu * policy.utilization_for(vm.workload_profile) for vm in dr_vms
    ) * growth_factor
    dr_ram_with_reserve = (
        sum(vm.effective_dr_ram_gb for vm in dr_vms) * growth_factor
    ) / reserve_factor

    dr_hosts_for_cpu = _hosts_needed(dr_effective_vcpu, host_effective_cores)
    dr_hosts_for_ram = _hosts_needed(dr_ram_with_reserve, policy.host_spec.ram_gb)
    dr_base_hosts = max(dr_hosts_for_cpu, dr_hosts_for_ram, 1 if dr_vms else 0)
    dr_binding_constraint = "RAM" if dr_hosts_for_ram >= dr_hosts_for_cpu else "CPU"
    dr_required_hosts = dr_base_hosts + ha_extra if dr_vms else 0

    dr_storage_demand_gb = sum(vm.effective_dr_disk_gb for vm in dr_vms) * growth_factor
    dr_recommended_storage_usable_tb = dr_storage_demand_gb / 1024
    dr_recommended_storage_raw_tb = dr_recommended_storage_usable_tb / storage_overhead_factor

    return SizingResult(
        vm_count=len(primary_vms),
        workload_breakdown=breakdown,
        total_vcpu_raw=total_vcpu_raw,
        total_effective_vcpu=total_effective_vcpu,
        total_ram_demand_gb=total_ram_demand_gb,
        total_ram_with_reserve_gb=total_ram_with_reserve_gb,
        total_storage_demand_gb=total_storage_demand_gb,
        recommended_storage_usable_tb=recommended_storage_usable_tb,
        recommended_storage_raw_tb=recommended_storage_raw_tb,
        host_effective_cores=host_effective_cores,
        hosts_for_cpu=hosts_for_cpu,
        hosts_for_ram=hosts_for_ram,
        binding_constraint=binding_constraint,
        raw_oversubscription_ratio=raw_oversubscription_ratio,
        ha_extra_hosts=ha_extra,
        required_hosts=required_hosts,
        dr_vm_count=len(dr_vms),
        dr_hosts_for_cpu=dr_hosts_for_cpu,
        dr_hosts_for_ram=dr_hosts_for_ram,
        dr_binding_constraint=dr_binding_constraint,
        dr_required_hosts=dr_required_hosts,
        dr_storage_demand_gb=dr_storage_demand_gb,
        dr_recommended_storage_usable_tb=dr_recommended_storage_usable_tb,
        dr_recommended_storage_raw_tb=dr_recommended_storage_raw_tb,
    )
