"""Pure logic for the Network tab: how many ports per speed are declared on
each device (server/switch) versus how many Connection records consume.

Note on granularity: this tracks the AGGREGATE port count per speed
(e.g. "Switch1 has 4x 25G, 3 used"), not an individual physical port with
its own ID/label. Enough for an overcommit warning ("no free 25G ports
left"), but doesn't stop two connections from "sharing" the same physical
port number - that would need a full per-port model (considered, but
deliberately left for later given the effort/benefit ratio)."""

from dataclasses import dataclass

from src.models.network_connection import SPEED_ATTR, SPEED_OPTIONS, NetworkConnection
from src.models.network_switch import NetworkSwitch
from src.models.server import Server
from src.models.storage import Storage


@dataclass
class PortUsage:
    speed: str
    total: int
    used: int

    @property
    def free(self) -> int:
        return max(0, self.total - self.used)

    @property
    def over_committed(self) -> bool:
        return self.used > self.total


def _usage_by_speed(
    device, uid_attrs: list[str], port_prefix: str, connections: list[NetworkConnection]
) -> list[PortUsage]:
    """Shared implementation behind switch_port_usage/server_nic_usage/
    storage_port_usage - they differ only in which Connection uid
    field(s) they match and which attribute prefix holds the declared
    port counts (`ports_`/`nic_`). uid_attrs is a list because a switch
    can appear on EITHER side of a Switch<->Switch connection
    (switch_uid or switch_b_uid) - server_nic_usage/storage_port_usage
    only ever check one field, so they pass a single-item list. Kept
    as public thin wrappers below (not collapsed into one function
    with a "kind" parameter) so callers keep type-specific signatures."""
    device_uid = device.uid
    used_by_speed = {speed: 0 for speed in SPEED_OPTIONS}
    for conn in connections:
        if conn.dedicated_link:
            continue
        if any(getattr(conn, attr) == device_uid for attr in uid_attrs) and conn.speed in used_by_speed:
            used_by_speed[conn.speed] += 1

    result = []
    for speed in SPEED_OPTIONS:
        total = getattr(device, f"{port_prefix}{SPEED_ATTR[speed]}")
        used = used_by_speed[speed]
        if total > 0 or used > 0:
            result.append(PortUsage(speed=speed, total=total, used=used))
    return result


def switch_port_usage(switch: NetworkSwitch, connections: list[NetworkConnection]) -> list[PortUsage]:
    if not switch.is_combo_ports:
        return _usage_by_speed(switch, ["switch_uid", "switch_b_uid"], "ports_", connections)

    ethernet_speeds = [s for s in SPEED_OPTIONS if s in ("1G", "10G", "25G", "40G", "100G")]
    declared = {s: getattr(switch, f"ports_{SPEED_ATTR[s]}") for s in ethernet_speeds}
    combo_total = max(declared.values(), default=0)

    combo_used = 0
    for conn in connections:
        if conn.dedicated_link:
            continue
        if conn.speed in declared and any(
            getattr(conn, attr) == switch.uid for attr in ("switch_uid", "switch_b_uid")
        ):
            combo_used += 1

    populated_speeds = [s for s in ethernet_speeds if declared[s] > 0]
    combo_label = "/".join(populated_speeds) + " (combo)" if populated_speeds else "combo"

    result = []
    if combo_total > 0 or combo_used > 0:
        result.append(PortUsage(speed=combo_label, total=combo_total, used=combo_used))

    for speed, port_prefix in (("FC", "ports_fc"), ("SAS", "ports_sas")):
        total = getattr(switch, port_prefix)
        used = sum(
            1 for conn in connections
            if not conn.dedicated_link and conn.speed == speed
            and any(getattr(conn, attr) == switch.uid for attr in ("switch_uid", "switch_b_uid"))
        )
        if total > 0 or used > 0:
            result.append(PortUsage(speed=speed, total=total, used=used))

    return result


def server_nic_usage(server: Server, connections: list[NetworkConnection]) -> list[PortUsage]:
    return _usage_by_speed(server, ["server_uid"], "nic_", connections)


def storage_port_usage(storage: Storage, connections: list[NetworkConnection]) -> list[PortUsage]:
    return _usage_by_speed(storage, ["storage_uid"], "ports_", connections)


def format_usage(usages: list[PortUsage]) -> str:
    if not usages:
        return "-"
    return " · ".join(f"{u.speed}: {u.used}/{u.total}" for u in usages)


def site_port_usage(switches: list[NetworkSwitch], connections: list[NetworkConnection]) -> list[PortUsage]:
    """Aggregated free/used per speed, across all switches at one site -
    for the quick overview at the top of the Network tab."""
    totals = {speed: 0 for speed in SPEED_OPTIONS}
    used = {speed: 0 for speed in SPEED_OPTIONS}

    for switch in switches:
        for usage in switch_port_usage(switch, connections):
            totals[usage.speed] += usage.total
            used[usage.speed] += usage.used

    result = []
    for speed in SPEED_OPTIONS:
        if totals[speed] > 0 or used[speed] > 0:
            result.append(PortUsage(speed=speed, total=totals[speed], used=used[speed]))
    return result


def any_over_committed(usages: list[PortUsage]) -> bool:
    return any(u.over_committed for u in usages)
