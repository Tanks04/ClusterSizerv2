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


WORKLOAD_TIERS: dict[str, WorkloadTier] = {
    "Tier-0 / Mission-Critical": WorkloadTier(
        name="Tier-0 / Mission-Critical",
        description=(
            "Heavy databases (SQL Server, Oracle), real-time analytics, SAP - "
            "latency and zero CPU contention are mandatory."
        ),
        ratio_min=1.0, ratio_max=1.0, default_ratio=1.0,
    ),
    "Standard Production": WorkloadTier(
        name="Standard Production",
        description=(
            "General application servers, web servers, file servers, domain "
            "controllers - mixed, spiky utilization patterns."
        ),
        ratio_min=3.0, ratio_max=5.0, default_ratio=4.0,
    ),
    "Development / Test": WorkloadTier(
        name="Development / Test",
        description=(
            "Non-production environments where occasional queuing or delayed "
            "execution does not impact business SLAs."
        ),
        ratio_min=6.0, ratio_max=10.0, default_ratio=8.0,
    ),
    "High-Density VDI": WorkloadTier(
        name="High-Density VDI",
        description=(
            "Virtual Desktop Infrastructure - users are idle or active "
            "asynchronously, flattening overall instantaneous demand."
        ),
        ratio_min=12.0, ratio_max=24.0, default_ratio=12.0,
    ),
}
