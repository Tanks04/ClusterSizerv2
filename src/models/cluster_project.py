from dataclasses import dataclass, field

from .server import Server
from .storage import Storage
from .virtual_machine import VirtualMachine
from .network_switch import NetworkSwitch
from .network_connection import NetworkConnection

PRIMARY = "Primary"
DR = "DR"


@dataclass
class ClusterProject:
    """Predstavlja jedan ClusterSizer projekt: serveri, storage, VM-ovi i
    mreža na Primary i DR lokaciji, te sve izvedene metrike potrebne za
    kapacitivno planiranje."""

    name: str = "New Project"

    servers: list[Server] = field(default_factory=list)
    storages: list[Storage] = field(default_factory=list)
    vms: list[VirtualMachine] = field(default_factory=list)
    switches: list[NetworkSwitch] = field(default_factory=list)
    connections: list[NetworkConnection] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Filtriranje po lokaciji
    # ------------------------------------------------------------------

    def servers_at(self, site: str) -> list[Server]:
        return [s for s in self.servers if s.site == site]

    def storages_at(self, site: str) -> list[Storage]:
        return [s for s in self.storages if s.site == site]

    def vms_at(self, site: str) -> list[VirtualMachine]:
        return [v for v in self.vms if v.site == site]

    def switches_at(self, site: str) -> list[NetworkSwitch]:
        return [s for s in self.switches if s.site == site]

    # ------------------------------------------------------------------
    # Ukupni (cijeli projekt, oba site-a)
    # ------------------------------------------------------------------

    @property
    def server_count(self) -> int:
        return len(self.servers)

    @property
    def total_ram(self) -> int:
        return sum(server.ram_gb for server in self.servers)

    @property
    def total_cores(self) -> int:
        return sum(server.total_cores for server in self.servers)

    @property
    def total_threads(self) -> int:
        return sum(server.total_threads for server in self.servers)

    # ------------------------------------------------------------------
    # Fizički kapacitet po lokaciji
    # ------------------------------------------------------------------

    def physical_cores(self, site: str) -> int:
        return sum(s.total_cores for s in self.servers_at(site))

    def physical_threads(self, site: str) -> int:
        return sum(s.total_threads for s in self.servers_at(site))

    def physical_ram_gb(self, site: str) -> float:
        return sum(s.ram_gb for s in self.servers_at(site))

    def usable_storage_gb(self, site: str) -> float:
        return sum(s.usable_capacity_gb for s in self.storages_at(site))

    # ------------------------------------------------------------------
    # Potražnja (VM-ovi) po lokaciji - "što stvarno radi ovdje danas"
    # ------------------------------------------------------------------

    def vm_vcpu_demand(self, site: str) -> int:
        return sum(v.vcpu for v in self.vms_at(site))

    def vm_ram_demand_gb(self, site: str) -> float:
        return sum(v.ram_gb for v in self.vms_at(site))

    def vm_disk_demand_gb(self, site: str) -> float:
        return sum(v.disk_gb for v in self.vms_at(site))

    # ------------------------------------------------------------------
    # Oversubscription (potražnja / fizički kapacitet), po lokaciji
    # ------------------------------------------------------------------

    def cpu_oversubscription_ratio(self, site: str) -> float | None:
        """vCPU : physical core. None ako nema fizičkih jezgri (dijeljenje s 0)."""
        cores = self.physical_cores(site)
        if cores == 0:
            return None
        return self.vm_vcpu_demand(site) / cores

    def ram_oversubscription_ratio(self, site: str) -> float | None:
        ram = self.physical_ram_gb(site)
        if ram == 0:
            return None
        return self.vm_ram_demand_gb(site) / ram

    def storage_utilization_ratio(self, site: str) -> float | None:
        usable = self.usable_storage_gb(site)
        if usable == 0:
            return None
        return self.vm_disk_demand_gb(site) / usable

    # ------------------------------------------------------------------
    # N+1 provjera (izdrži li cluster ispad jednog domaćina na toj lokaciji)
    # ------------------------------------------------------------------

    def n_plus_one_ok(self, site: str) -> bool | None:
        """True ako klaster na danoj lokaciji i dalje ima dovoljno RAM-a i
        jezgri za sve VM-ove kada bi ispao jedan (najveći) host. None ako
        na toj lokaciji nema servera."""
        site_servers = self.servers_at(site)
        if not site_servers:
            return None

        largest = max(site_servers, key=lambda s: s.ram_gb)
        remaining_ram = self.physical_ram_gb(site) - largest.ram_gb
        remaining_cores = self.physical_cores(site) - largest.total_cores

        ram_ok = remaining_ram >= self.vm_ram_demand_gb(site)
        cpu_ok = remaining_cores >= self.vm_vcpu_demand(site)

        return ram_ok and cpu_ok

    # ------------------------------------------------------------------
    # DR failover potražnja - "što bi DR morao ponijeti u slučaju potpunog
    # ispada Primary lokacije". NIJE isto što i vm_vcpu_demand(DR): to su
    # VM-ovi koji već danas rade na DR-u, dok je ovo VM-ovi koji bi tek
    # DOŠLI na DR (samo oni s dr_protected=True), po njihovom DR footprintu
    # (koji smije biti manji od Primary footprinta), PLUS ono što na DR-u
    # već fizički radi.
    # ------------------------------------------------------------------

    def dr_failover_vcpu_demand(self) -> int:
        protected = sum(
            v.effective_dr_vcpu for v in self.vms_at(PRIMARY) if v.dr_protected
        )
        return protected + self.vm_vcpu_demand(DR)

    def dr_failover_ram_demand_gb(self) -> float:
        protected = sum(
            v.effective_dr_ram_gb for v in self.vms_at(PRIMARY) if v.dr_protected
        )
        return protected + self.vm_ram_demand_gb(DR)

    def dr_failover_disk_demand_gb(self) -> float:
        protected = sum(
            v.effective_dr_disk_gb for v in self.vms_at(PRIMARY) if v.dr_protected
        )
        return protected + self.vm_disk_demand_gb(DR)

    def dr_protected_vm_count(self) -> int:
        return sum(1 for v in self.vms_at(PRIMARY) if v.dr_protected)

    # ------------------------------------------------------------------
    # DR spremnost: može li DR lokacija preuzeti sve dr_protected VM-ove
    # (po njihovom DR footprintu) plus ono što na DR-u već radi?
    # ------------------------------------------------------------------

    def dr_cpu_ok(self) -> bool | None:
        if not self.servers_at(DR):
            return None
        return self.physical_cores(DR) >= self.dr_failover_vcpu_demand()

    def dr_ram_ok(self) -> bool | None:
        if not self.servers_at(DR):
            return None
        return self.physical_ram_gb(DR) >= self.dr_failover_ram_demand_gb()

    def dr_storage_ok(self) -> bool | None:
        if not self.storages_at(DR):
            return None
        return self.usable_storage_gb(DR) >= self.dr_failover_disk_demand_gb()

    def dr_ready(self) -> bool | None:
        """None ako DR lokacija uopće nema definiranih resursa (nema smisla
        ocjenjivati spremnost)."""
        checks = [self.dr_cpu_ok(), self.dr_ram_ok(), self.dr_storage_ok()]
        if all(c is None for c in checks):
            return None
        return all(c is not False for c in checks)
