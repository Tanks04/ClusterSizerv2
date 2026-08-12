"""Workload profile catalog for VM classification and Cluster Preparation
sizing. Each profile carries a default assumed average CPU utilization %
- a sizing ASSUMPTION, not a measurement (see docs on the Cluster
Preparation dialog). Adjustable per-project via the dialog's editable
fields; these are just sensible starting points."""

from dataclasses import dataclass

WORKLOAD_PROFILE_NAMES = [
    "CPU Intensive",
    "Balanced",
    "Memory Intensive",
    "Storage Intensive",
    "Light",
]

DEFAULT_WORKLOAD_PROFILE = "Balanced"


@dataclass
class WorkloadProfile:
    name: str
    description: str
    default_cpu_utilization: float  # 0.0-1.0, used for sizing (effective vCPU demand)


WORKLOAD_PROFILES: dict[str, WorkloadProfile] = {
    "CPU Intensive": WorkloadProfile(
        name="CPU Intensive",
        description="Databases, application servers, analytics, CPU-heavy workloads.",
        default_cpu_utilization=0.70,
    ),
    "Balanced": WorkloadProfile(
        name="Balanced",
        description="General purpose VMs, AD, web servers, mixed workloads.",
        default_cpu_utilization=0.40,
    ),
    "Memory Intensive": WorkloadProfile(
        name="Memory Intensive",
        description="In-memory databases, large application servers, caching.",
        default_cpu_utilization=0.40,
    ),
    "Storage Intensive": WorkloadProfile(
        name="Storage Intensive",
        description="File servers, backup servers, high I/O workloads.",
        default_cpu_utilization=0.30,
    ),
    "Light": WorkloadProfile(
        name="Light",
        description="Domain controllers, monitoring, small infra services, low-utilization VMs.",
        default_cpu_utilization=0.20,
    ),
}
