from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from src.calculations.sizing import SiteReport
from .status_badge import StatusBadge


def _bar(ratio: float | None, max_percent: int = 200) -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, max_percent)
    bar.setTextVisible(True)
    if ratio is None:
        bar.setValue(0)
        bar.setFormat("n/a")
    else:
        percent = round(ratio * 100)
        bar.setValue(min(percent, max_percent))
        bar.setFormat(f"{percent}%")
    return bar


class SiteCapacityWidget(QFrame):
    """Card showing the complete state of one site (Primary/DR): physical
    capacity, VM demand, oversubscription ratios, and N+1 status.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("SiteCapacityWidget")

        outer = QVBoxLayout(self)

        header = QLabel(title)
        header_font = header.font()
        header_font.setBold(True)
        header_font.setPointSize(13)
        header.setFont(header_font)
        outer.addWidget(header)

        grid = QGridLayout()
        outer.addLayout(grid)

        row = 0

        grid.addWidget(QLabel("Servers / pCPU cores (HT-adj.):"), row, 0)
        self.servers_label = QLabel("-")
        grid.addWidget(self.servers_label, row, 1)
        self.ht_tag_label = QLabel("")
        self.ht_tag_label.setVisible(False)
        grid.addWidget(self.ht_tag_label, row, 2)
        row += 1

        grid.addWidget(QLabel("Physical RAM:"), row, 0)
        self.ram_label = QLabel("-")
        grid.addWidget(self.ram_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Usable storage:"), row, 0)
        self.storage_label = QLabel("-")
        grid.addWidget(self.storage_label, row, 1)
        row += 1

        grid.addWidget(QLabel("VM demand (powered-on vCPU/RAM, all Disk):"), row, 0)
        self.demand_label = QLabel("-")
        grid.addWidget(self.demand_label, row, 1)
        row += 1

        grid.addWidget(QLabel("CPU oversubscription:"), row, 0)
        self.cpu_bar = _bar(None)
        grid.addWidget(self.cpu_bar, row, 1)
        self.cpu_badge = StatusBadge()
        grid.addWidget(self.cpu_badge, row, 2)
        row += 1

        grid.addWidget(QLabel("RAM utilization:"), row, 0)
        self.ram_bar = _bar(None)
        grid.addWidget(self.ram_bar, row, 1)
        self.ram_badge = StatusBadge()
        grid.addWidget(self.ram_badge, row, 2)
        row += 1

        grid.addWidget(QLabel("Storage utilization:"), row, 0)
        self.storage_bar = _bar(None)
        grid.addWidget(self.storage_bar, row, 1)
        self.storage_badge = StatusBadge()
        grid.addWidget(self.storage_badge, row, 2)
        row += 1

        grid.addWidget(QLabel("Survives 1 host failure (N+1):"), row, 0)
        self.n1_label = QLabel("-")
        grid.addWidget(self.n1_label, row, 1)
        row += 1

    def set_report(self, report: SiteReport) -> None:
        self.servers_label.setText(
            f"{report.server_count} servers / {report.physical_cores} cores "
            f"({report.physical_threads} threads)"
        )
        self._set_ht_tag(report.ht_state)
        self.ram_label.setText(f"{report.physical_ram_gb:.0f} GB")
        self.storage_label.setText(f"{report.usable_storage_gb / 1024:.1f} TB")
        self.demand_label.setText(
            f"{report.vm_count} VMs \u2014 {report.vcpu_demand} vCPU / "
            f"{report.ram_demand_gb:.0f} GB / {report.disk_demand_gb / 1024:.1f} TB"
        )

        self.cpu_bar.setValue(0 if report.cpu_ratio is None else min(round(report.cpu_ratio * 100), 400))
        self.cpu_bar.setFormat("n/a" if report.cpu_ratio is None else f"{report.cpu_ratio:.1f} : 1")
        self.cpu_bar.setRange(0, 400)
        self.cpu_badge.set_status(report.cpu_status)

        self.ram_bar.setValue(0 if report.ram_ratio is None else min(round(report.ram_ratio * 100), 200))
        self.ram_bar.setFormat("n/a" if report.ram_ratio is None else f"{report.ram_ratio * 100:.0f}%")
        self.ram_badge.set_status(report.ram_status)

        self.storage_bar.setValue(
            0 if report.storage_ratio is None else min(round(report.storage_ratio * 100), 200)
        )
        self.storage_bar.setFormat(
            "n/a" if report.storage_ratio is None else f"{report.storage_ratio * 100:.0f}%"
        )
        self.storage_badge.set_status(report.storage_status)

        if report.n_plus_one_ok is None:
            self.n1_label.setText("n/a")
        elif report.n_plus_one_ok:
            self.n1_label.setText("\u2705 Yes")
        else:
            self.n1_label.setText("\u274c No")

    def _set_ht_tag(self, ht_state: str) -> None:
        """HT ENABLED (red, bold) when every server at this site has
        Hyperthreading on - loud on purpose, so the HT-adjusted core count
        above doesn't get mistaken for a plain physical core count. HT
        MIXED (orange, bold) when servers disagree - a blanket "enabled"
        tag would be misleading there, since only part of the pool is
        thread-boosted. Nothing shown when HT is off everywhere, or there
        are no servers at this site."""
        if ht_state == "all_on":
            self.ht_tag_label.setText("HT ENABLED")
            self.ht_tag_label.setStyleSheet("color: #c62828; font-weight: bold;")
            self.ht_tag_label.setVisible(True)
        elif ht_state == "mixed":
            self.ht_tag_label.setText("HT MIXED")
            self.ht_tag_label.setStyleSheet("color: #ed6c02; font-weight: bold;")
            self.ht_tag_label.setVisible(True)
        else:
            self.ht_tag_label.setVisible(False)
