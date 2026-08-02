"""Čista logika za Network tab: koliko je portova po brzini deklarirano na
svakom uređaju (server/switch) nasuprot koliko ih Connection zapisi troše.

Napomena o granularnosti: ovo prati AGREGATNI broj portova po brzini
(npr. "Switch1 ima 4x 25G, iskorišteno 3"), ne pojedinačni fizički port sa
svojim ID-jem/labelom. Dovoljno za overcommit upozorenje ("nemaš više
slobodnih 25G portova"), ali ne sprječava da dvije veze "dijele" isti
fizički port broj - za to bi trebao puni per-port model (razmatran, ali
namjerno ostavljen za kasnije zbog omjera trud/korist)."""

from dataclasses import dataclass

from src.models.network_connection import SPEED_OPTIONS, SPEED_ATTR
from src.models.network_switch import NetworkSwitch
from src.models.server import Server
from src.models.network_connection import NetworkConnection


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


def switch_port_usage(switch: NetworkSwitch, connections: list[NetworkConnection]) -> list[PortUsage]:
    used_by_speed = {speed: 0 for speed in SPEED_OPTIONS}
    for conn in connections:
        if conn.switch_uid == switch.uid and conn.speed in used_by_speed:
            used_by_speed[conn.speed] += 1

    result = []
    for speed in SPEED_OPTIONS:
        total = getattr(switch, f"ports_{SPEED_ATTR[speed]}")
        used = used_by_speed[speed]
        if total > 0 or used > 0:
            result.append(PortUsage(speed=speed, total=total, used=used))
    return result


def server_nic_usage(server: Server, connections: list[NetworkConnection]) -> list[PortUsage]:
    used_by_speed = {speed: 0 for speed in SPEED_OPTIONS}
    for conn in connections:
        if conn.server_uid == server.uid and conn.speed in used_by_speed:
            used_by_speed[conn.speed] += 1

    result = []
    for speed in SPEED_OPTIONS:
        total = getattr(server, f"nic_{SPEED_ATTR[speed]}")
        used = used_by_speed[speed]
        if total > 0 or used > 0:
            result.append(PortUsage(speed=speed, total=total, used=used))
    return result


def format_usage(usages: list[PortUsage]) -> str:
    if not usages:
        return "-"
    return " · ".join(f"{u.speed}: {u.used}/{u.total}" for u in usages)


def site_port_usage(switches: list[NetworkSwitch], connections: list[NetworkConnection]) -> list[PortUsage]:
    """Agregirano slobodno/zauzeto po brzini, preko svih switcheva jedne
    lokacije - za brzi pregled na vrhu Network taba."""
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
