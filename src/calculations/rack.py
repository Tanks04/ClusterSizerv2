"""Aggregates rack units (U) and power draw (W) across everything that
occupies physical rack space at a site - Servers, Storage (including
their expansion shelves), and Network Switches. Fields left at 0
(not entered) don't count as real zeros - they're simply excluded, same
convention as every other optional numeric field in this app.

Deliberately does NOT filter by Server.enabled the way capacity math
(servers_at(), physical_cores(), etc.) does - "disabled" means "exclude
from compute capacity planning" (e.g. simulating a host being down), not
"physically removed from the rack". A disabled server still occupies its
U and, if it's still plugged in, still draws power - so it stays counted
here even when it's invisible to CPU/RAM/storage oversubscription.
"""

from dataclasses import dataclass

from src.models.cluster_project import ClusterProject


@dataclass
class RackSizingSummary:
    rack_units: int
    power_watts: float
    is_cloud: bool = False
    capacity_u: int = 0  # 0 = not entered - "how many U are used" with no "of how many" context, same as before this existed

    @property
    def over_capacity(self) -> bool:
        """Only meaningful once capacity_u is actually entered - with
        0/not-entered, there's nothing to compare against, so this is
        always False rather than a misleading "yes you're over 0 U"."""
        return self.capacity_u > 0 and self.rack_units > self.capacity_u


def compute_rack_sizing(project: ClusterProject, site: str) -> RackSizingSummary:
    capacity_u = project.rack_capacity_u_for(site)

    if project.is_cloud(site):
        # Rack/power is a physical-hardware concept - meaningless for a
        # site whose compute lives in someone else's data center. Don't
        # even bother summing whatever Server/Storage/Switch rows might
        # exist there (e.g. leftover from switching a site's deployment
        # model) - the display layer shows "Cloud" instead of a number.
        return RackSizingSummary(rack_units=0, power_watts=0.0, is_cloud=True, capacity_u=capacity_u)

    servers = [s for s in project.servers if s.site == site]  # NOT servers_at() - see module docstring
    storages = [s for s in project.storages if s.site == site]
    switches = [s for s in project.switches if s.site == site]

    rack_units = (
        sum(s.rack_units for s in servers)
        + sum(s.total_rack_units for s in storages)  # includes attached shelves
        + sum(s.rack_units for s in switches)
    )
    power_watts = (
        sum(s.power_watts for s in servers)
        + sum(s.total_power_watts for s in storages)  # includes attached shelves
        + sum(s.power_watts for s in switches)
    )

    return RackSizingSummary(
        rack_units=rack_units, power_watts=power_watts, is_cloud=False, capacity_u=capacity_u,
    )
