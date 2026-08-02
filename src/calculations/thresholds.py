from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    OK = "OK"
    WARNING = "Warning"
    CRITICAL = "Critical"
    UNKNOWN = "Unknown"  # nema podataka (npr. 0 fizičkih resursa)


@dataclass
class Thresholds:
    """Pragovi upozorenja za oversubscription izračune. Podesivo na Settings
    stranici; default vrijednosti odgovaraju uobičajenoj sysadmin praksi."""

    cpu_warning_ratio: float = 4.0     # npr. 4 vCPU po 1 fizičkoj jezgri
    cpu_critical_ratio: float = 6.0

    ram_warning_ratio: float = 0.8     # 80% fizičkog RAM-a alociran VM-ovima
    ram_critical_ratio: float = 1.0    # >100% = overcommit RAM-a

    storage_warning_ratio: float = 0.8
    storage_critical_ratio: float = 0.95

    @staticmethod
    def status_for(ratio: float | None, warning: float, critical: float) -> Status:
        if ratio is None:
            return Status.UNKNOWN
        if ratio >= critical:
            return Status.CRITICAL
        if ratio >= warning:
            return Status.WARNING
        return Status.OK

    def cpu_status(self, ratio: float | None) -> Status:
        return self.status_for(ratio, self.cpu_warning_ratio, self.cpu_critical_ratio)

    def ram_status(self, ratio: float | None) -> Status:
        return self.status_for(ratio, self.ram_warning_ratio, self.ram_critical_ratio)

    def storage_status(self, ratio: float | None) -> Status:
        return self.status_for(ratio, self.storage_warning_ratio, self.storage_critical_ratio)
