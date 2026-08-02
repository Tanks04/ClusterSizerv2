from dataclasses import dataclass
import uuid


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

    warranty_expiry: str = ""  # slobodan format npr. "2027-05-01", "-" ako nepoznato

    # NIC inventar - broj fizičkih portova po brzini. Koristi se na Network
    # tabu za praćenje slobodnih/zauzetih portova. Potpuno opcionalno -
    # ako ostane 0, server se jednostavno ne pojavljuje u network izračunu.
    nic_1g: int = 0
    nic_10g: int = 0
    nic_25g: int = 0
    nic_40g: int = 0
    nic_100g: int = 0
    nic_fc: int = 0

    notes: str = ""

    @property
    def total_cores(self) -> int:
        return self.sockets * self.cores_per_socket

    @property
    def total_threads(self) -> int:
        return self.total_cores * self.threads_per_core

    @property
    def total_nics(self) -> int:
        return (
            self.nic_1g + self.nic_10g + self.nic_25g
            + self.nic_40g + self.nic_100g + self.nic_fc
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
            nic_1g=2,
            nic_10g=0,
            nic_25g=2,
            nic_40g=0,
            nic_100g=0,
            nic_fc=0,
        )
