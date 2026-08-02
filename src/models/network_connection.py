from dataclasses import dataclass
import uuid

# Zajednički vokabular brzina - koristi se za Server.nic_*, NetworkSwitch.ports_*
# i NetworkConnection.speed, da se sve tri strane slažu oko istih kategorija.
SPEED_OPTIONS = ["1G", "10G", "25G", "40G", "100G", "FC"]

MEDIA_OPTIONS = ["RJ45", "SFP+", "SFP28", "QSFP+", "QSFP28", "FC"]

PURPOSE_OPTIONS = ["Uplink", "Data", "Storage", "Management", "vMotion", "Other"]

# Server.nic_<x> / NetworkSwitch.ports_<x> atribut za svaku brzinu - koristi
# se za generičko zbrajanje kapaciteta/potrošnje bez if/elif lanaca.
SPEED_ATTR = {
    "1G": "1g",
    "10G": "10g",
    "25G": "25g",
    "40G": "40g",
    "100G": "100g",
    "FC": "fc",
}


@dataclass
class NetworkConnection:
    """Jedna fizička veza: server <-> switch. Referencira strane preko uid-a
    (server_uid, switch_uid) - ako je referencirani uređaj kasnije obrisan,
    veza ostaje "orphan" i tako se i prikazuje (ne briše se automatski, da
    se ne izgubi podatak slučajno)."""

    uid: str

    server_uid: str
    switch_uid: str

    speed: str  # jedna od SPEED_OPTIONS
    media: str  # jedna od MEDIA_OPTIONS

    switch_port_label: str = ""  # opisno, npr. "Gi1/0/3", "Uplink #1" - nije obavezno
    purpose: str = "Data"  # jedna od PURPOSE_OPTIONS

    notes: str = ""

    @staticmethod
    def create_default() -> "NetworkConnection":
        return NetworkConnection(
            uid=str(uuid.uuid4()),
            server_uid="",
            switch_uid="",
            speed="25G",
            media="SFP28",
            purpose="Data",
        )
