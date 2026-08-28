from dataclasses import dataclass
import uuid

# Matches the labels used by the Settings page's oversubscription presets
# (src/calculations/thresholds.py PRESETS) for consistency - kept as a
# separate list rather than imported from there, since these serve
# different purposes (one drives ratios, this is just descriptive
# inventory) and shouldn't be coupled to each other.
HYPERVISOR_VENDORS = [
    "", "VMware (ESXi / vSphere)", "Microsoft Hyper-V", "Proxmox VE / KVM",
    "Nutanix AHV", "Citrix Hypervisor (XenServer)", "Other",
]


@dataclass
class Server:
    uid: str
    name: str
    site: str

    vendor: str
    model: str

    cpu_vendor: str
    cpu_model: str

    sockets: int
    cores_per_socket: int
    threads_per_core: int

    ram_gb: int

    cpu_frequency: float

    warranty_expiry: str = ""  # free format e.g. "2027-05-01", "-" if unknown
    ip_address: str = ""  # management or primary network IP, free text (not validated - IPv4/IPv6/hostname all fine)

    cluster_name: str = ""  # informational tag, e.g. a VMware/Hyper-V cluster name - several servers can share one, an environment can have several clusters

    serial_number: str = ""  # asset tag / service tag - for support tickets and RMA tracking
    bmc_ip: str = ""  # out-of-band management IP (iLO/iDRAC/BMC) - separate from ip_address, which is the main OS-facing IP
    hypervisor_vendor: str = ""  # one of HYPERVISOR_VENDORS - matches the Settings page's oversubscription presets
    hypervisor_version: str = ""  # free text, e.g. "8.0 U2", "2022" - the specific version running, since vendor alone doesn't say which

    # Rack sizing - 0 = not entered, excluded from the Summary tab's rack
    # totals rather than counted as a real zero.
    rack_units: int = 0
    power_watts: float = 0.0  # nameplate/max draw from the datasheet, not "typical" - safer for circuit/PDU planning

    # Hyperthreading/SMT gate: threads_per_core stays as the raw SMT width
    # (2 for typical x86 HT, could be higher on other architectures), but
    # it only counts toward CPU capacity math when this is True. Lets
    # someone flip HT off for a specific server (e.g. a latency-sensitive
    # host) without losing their threads_per_core setting.
    hyperthreading_enabled: bool = True

    # NIC inventory - number of physical ports per speed. Used on the
    # Network tab to track free/used ports. Fully optional - if left at 0,
    # the server simply doesn't show up in the network calculations.
    nic_1g: int = 0
    nic_10g: int = 0
    nic_25g: int = 0
    nic_40g: int = 0
    nic_100g: int = 0
    nic_fc: int = 0
    nic_sas: int = 0  # direct-attach SAS HBA ports (server -> storage, no switch)

    # When False, this server is excluded from ALL capacity math
    # (ClusterProject.servers_at() filters on this) while staying visible
    # in the Servers table - a quick way to simulate "this host is down"
    # (maintenance, a real failure, decommissioning) without deleting and
    # later re-adding its whole configuration.
    enabled: bool = True

    # Pricing (EUR) - 0 = not entered. A single price, not cost/price/
    # margin - this app just totals up what equipment costs, it isn't a
    # sales quoting tool.
    price: float = 0.0

    local_disk_raw_tb: float = 0.0  # HCI/vSAN-style local disk contribution - only meaningful when an HCI Storage entity is linked to this server

    notes: str = ""

    @property
    def total_cores(self) -> int:
        return self.sockets * self.cores_per_socket

    @property
    def total_threads(self) -> int:
        return self.total_cores * self.threads_per_core

    @property
    def effective_cores(self) -> int:
        """The pCPU pool actually used for CPU oversubscription math:
        threads if hyperthreading is enabled for this server, otherwise
        just physical cores. This is what ClusterProject.physical_cores()
        sums - see its docstring."""
        return self.total_threads if self.hyperthreading_enabled else self.total_cores

    @property
    def total_nics(self) -> int:
        return (
            self.nic_1g + self.nic_10g + self.nic_25g
            + self.nic_40g + self.nic_100g + self.nic_fc + self.nic_sas
        )

    @staticmethod
    def create_default() -> "Server":
        return Server(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
            vendor="",
            model="",
            cpu_vendor="Intel",
            cpu_model="",
            sockets=2,
            cores_per_socket=16,
            threads_per_core=2,
            ram_gb=256,
            cpu_frequency=2.5,
            hyperthreading_enabled=True,
            nic_1g=2,
            nic_10g=0,
            nic_25g=2,
            nic_40g=0,
            nic_100g=0,
            nic_fc=0,
            nic_sas=0,
        )
