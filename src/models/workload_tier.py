"""Workload tier catalog for VM classification and Cluster Preparation
sizing - replaces the earlier "CPU Intensive/Balanced/..." utilization-%
approach with a more standard, industry-recognized framing: how much
CPU oversubscription can this workload's SLA actually tolerate, not "how
busy is it on average". Each tier carries a commonly-cited safe
oversubscription-ratio range plus a representative default (its
midpoint, or 1:1 for Tier-0 where there's no range) - a sizing
ASSUMPTION, not a measurement. Adjustable per-project via the Cluster
Preparation wizard."""

from dataclasses import dataclass

WORKLOAD_TIER_NAMES = [
    "Tier-0 / Mission-Critical",
    "Standard Production",
    "Development / Test",
    "High-Density VDI",
]

DEFAULT_WORKLOAD_TIER = "Standard Production"


@dataclass
class WorkloadTier:
    name: str
    description: str
    ratio_min: float  # commonly-cited safe vCPU:pCPU range, lower bound
    ratio_max: float  # upper bound
    default_ratio: float  # representative value used for sizing unless overridden
    # Informational only - never computed/simulated. A real hypervisor
    # scheduler (vSphere CPU Shares, Hyper-V VM CPU weight/reservation)
    # protects a VM from contention by giving it priority ahead of
    # lower-priority neighbors on the same host - this names which
    # priority tier makes sense to configure for real, not a guess at
    # how much CPU time it would actually get (that depends on NUMA
    # layout, actual concurrent load, and scheduler internals this app
    # has no visibility into and isn't trying to model).
    recommended_hypervisor_priority: str = "Normal"


WORKLOAD_TIERS: dict[str, WorkloadTier] = {
    "Tier-0 / Mission-Critical": WorkloadTier(
        name="Tier-0 / Mission-Critical",
        description=(
            "Heavy databases (SQL Server, Oracle), real-time analytics, SAP - "
            "latency and zero CPU contention are mandatory."
        ),
        ratio_min=1.0, ratio_max=1.0, default_ratio=1.0,
        recommended_hypervisor_priority="High (CPU Shares/Reservation)",
    ),
    "Standard Production": WorkloadTier(
        name="Standard Production",
        description=(
            "General application servers, web servers, file servers, domain "
            "controllers - mixed, spiky utilization patterns."
        ),
        ratio_min=3.0, ratio_max=5.0, default_ratio=4.0,
        recommended_hypervisor_priority="Normal",
    ),
    "Development / Test": WorkloadTier(
        name="Development / Test",
        description=(
            "Non-production environments where occasional queuing or delayed "
            "execution does not impact business SLAs."
        ),
        ratio_min=6.0, ratio_max=10.0, default_ratio=8.0,
        recommended_hypervisor_priority="Low",
    ),
    "High-Density VDI": WorkloadTier(
        name="High-Density VDI",
        description=(
            "Virtual Desktop Infrastructure - users are idle or active "
            "asynchronously, flattening overall instantaneous demand."
        ),
        ratio_min=12.0, ratio_max=24.0, default_ratio=12.0,
        recommended_hypervisor_priority="Low (Normal for login-storm-sensitive pools)",
    ),
}


def tier_ratio_for(tier_name: str) -> float:
    """The catalog default_ratio for a tier name, falling back to
    DEFAULT_WORKLOAD_TIER's for an unrecognized/blank name (same
    fallback SizingPolicy.ratio_for uses in the Cluster Preparation
    wizard, minus that class's per-project override support - this is
    for the ongoing/live effective-CPU check, which has no override
    concept of its own)."""
    tier = WORKLOAD_TIERS.get(tier_name) or WORKLOAD_TIERS[DEFAULT_WORKLOAD_TIER]
    return tier.default_ratio
