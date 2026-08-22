from dataclasses import dataclass
import uuid

DESTINATION_TYPES = ["NAS", "Disk Appliance", "Storage Array", "Offsite", "Tape / Offline"]


@dataclass
class BackupDestination:
    """One backup destination at the Primary or DR site. A real backup
    setup usually has SEVERAL of these (e.g. a local disk-based repo for
    fast restores, plus a copy job to an offsite/cloud target) - this is
    a list on ClusterProject, not a single flat backup config, so the
    3-2-1-1 check (see src/calculations/backup.py) has something real to
    count across."""

    uid: str
    name: str
    site: str  # "Primary" | "DR"

    destination_type: str  # one of DESTINATION_TYPES
    backup_software: str  # e.g. "Veeam", "CommVault" - free text, not a fixed enum

    raw_capacity_tb: float
    dedup_ratio: float  # e.g. 5.0 means 5:1 - effective_capacity_tb is raw * this

    is_offsite: bool  # geographically separate - protects against a site-level disaster
    is_immutable: bool  # offline/immutable copy - protects against ransomware reaching this copy too

    notes: str = ""

    @property
    def effective_capacity_tb(self) -> float:
        return self.raw_capacity_tb * self.dedup_ratio

    @staticmethod
    def create_default() -> "BackupDestination":
        return BackupDestination(
            uid=str(uuid.uuid4()),
            name="",
            site="Primary",
            destination_type="Disk Appliance",
            backup_software="",
            raw_capacity_tb=20.0,
            dedup_ratio=1.0,
            is_offsite=False,
            is_immutable=False,
        )
