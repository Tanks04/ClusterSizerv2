from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from src.calculations.sizing import SiteReport, FailoverReport
from src.calculations.thresholds import Status
from src.gui.widgets.status_badge import StatusBadge


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

        effective_cpu_label = QLabel("Effective CPU (tier-weighted):")
        effective_cpu_label.setToolTip(
            "Same demand, but each VM's vCPU is scaled by its Workload Tier's "
            "oversubscription tolerance first (Tier-0 counts at full weight, "
            "VDI at a small fraction of it) - see HOW_THE_MATH_WORKS.md \u00a72a. "
            "1.0 means \"fully booked assuming zero tolerance anywhere\"."
        )
        grid.addWidget(effective_cpu_label, row, 0)
        self.effective_cpu_bar = _bar(None)
        grid.addWidget(self.effective_cpu_bar, row, 1)
        self.effective_cpu_badge = StatusBadge()
        grid.addWidget(self.effective_cpu_badge, row, 2)
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

        self.n1_detail_label = QLabel("")
        self.n1_detail_label.setWordWrap(True)
        self.n1_detail_label.setStyleSheet("color: #ed6c02; font-style: italic;")
        self.n1_detail_label.setVisible(False)
        grid.addWidget(self.n1_detail_label, row, 0, 1, 3)
        row += 1

        grid.addWidget(QLabel("VMs Assigned (Failover):"), row, 0)
        self.failover_count_label = QLabel("-")
        grid.addWidget(self.failover_count_label, row, 1)
        self.failover_badge = StatusBadge()
        grid.addWidget(self.failover_badge, row, 2)
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

        # setRange() BEFORE setValue() everywhere below - QProgressBar
        # clamps a value to whatever range is CURRENT at the moment
        # setValue() is called, so calling them in the other order left
        # the very first refresh stuck showing a stale, wrong-looking
        # fill (e.g. a 3.0:1 CPU ratio rendering as if it were 1.5:1,
        # because setValue(300) got clamped against the constructor's
        # default range of 0-200 a moment before setRange(0, 400) ran).
        self.cpu_bar.setRange(0, 400)
        self.cpu_bar.setValue(0 if report.cpu_ratio is None else min(round(report.cpu_ratio * 100), 400))
        self.cpu_bar.setFormat("n/a" if report.cpu_ratio is None else f"{report.cpu_ratio:.1f} : 1")
        self.cpu_badge.set_status(report.cpu_status)

        self.effective_cpu_bar.setRange(0, 400)
        self.effective_cpu_bar.setValue(
            0 if report.effective_cpu_ratio is None else min(round(report.effective_cpu_ratio * 100), 400)
        )
        self.effective_cpu_bar.setFormat(
            "n/a" if report.effective_cpu_ratio is None else f"{report.effective_cpu_ratio:.2f} : 1"
        )
        self.effective_cpu_badge.set_status(report.effective_cpu_status)

        # RAM/Storage are plain percentages (0-100 is "full"), not a
        # ratio like CPU that's expected to run past 100% - a 0-200
        # range here (the _bar() constructor's default) made a healthy
        # 65% look like a third of the bar, not two-thirds. A clean
        # 0-100 range makes the fill match its own label directly; an
        # unhealthy >100% reading still shows the true number in the
        # text, just visually maxes out the bar rather than leaving a
        # permanent, confusing text-vs-fill mismatch.
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0 if report.ram_ratio is None else min(round(report.ram_ratio * 100), 100))
        self.ram_bar.setFormat("n/a" if report.ram_ratio is None else f"{report.ram_ratio * 100:.0f}%")
        self.ram_badge.set_status(report.ram_status)

        self.storage_bar.setRange(0, 100)
        self.storage_bar.setValue(
            0 if report.storage_ratio is None else min(round(report.storage_ratio * 100), 100)
        )
        self.storage_bar.setFormat(
            "n/a" if report.storage_ratio is None else f"{report.storage_ratio * 100:.0f}%"
        )
        self.storage_badge.set_status(report.storage_status)

        if report.n_plus_one_ok is None:
            self.n1_label.setText("n/a")
            self.n1_label.setToolTip("No servers at this site.")
            self.n1_detail_label.setVisible(False)
        elif report.vm_count == 0:
            self.n1_label.setText("n/a (no VMs)")
            self.n1_label.setToolTip(
                "There are no VMs at this site, so losing a host trivially "
                "\"survives\" - there's nothing running here to fail over."
            )
            self.n1_detail_label.setVisible(False)
        elif report.n_plus_one_ok:
            self.n1_label.setText("\u2705 Yes")
            self.n1_label.setToolTip(
                "RAM has zero overcommit tolerance; CPU is checked against your "
                "Settings threshold, not a strict 1:1."
            )
            self.n1_detail_label.setVisible(False)
        else:
            self.n1_label.setText("\u274c No")
            self.n1_label.setToolTip(
                "RAM or CPU demand exceeds what's left after losing your "
                "largest host, beyond your Settings threshold."
            )
            self._set_n1_detail(report.n_plus_one_check)

    def set_failover_report(self, failover: FailoverReport) -> None:
        """Deliberately minimal - just the count and a status badge, no
        extra detail text, per direct request: Summary should show
        "VMs on this site: N" plus whether it's OK, not a data dump -
        the full numbers (vCPU/RAM/disk demand) live in the Word report
        and, going forward, the Failover Assignments table on the VMs tab."""
        self.failover_count_label.setText(str(failover.assigned_vm_count))
        if failover.ready is None:
            self.failover_badge.set_status(Status.UNKNOWN)
        elif failover.ready:
            self.failover_badge.set_status(Status.OK)
        else:
            self.failover_badge.set_status(Status.CRITICAL)

    def _set_n1_detail(self, check) -> None:
        """States WHICH resource is short and by how much, instead of
        leaving "No" to speak for itself - e.g. CPU can be comfortably
        within its oversubscription tolerance while RAM alone is what
        would fail, and that's worth saying plainly."""
        if check is None:
            self.n1_detail_label.setVisible(False)
            return

        shortfalls = []
        if not check.ram_ok:
            shortfalls.append(f"+{check.ram_shortfall_gb:.0f} GB RAM")
        if not check.cpu_ok:
            shortfalls.append(f"+{check.cpu_shortfall_effective_cores:.0f} effective CPU cores")

        if not shortfalls:
            self.n1_detail_label.setVisible(False)
            return

        self.n1_detail_label.setText(
            f"\u26a0 Would need {' and '.join(shortfalls)} to survive losing a host "
            "at your current oversubscription comfort level."
        )
        self.n1_detail_label.setVisible(True)

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
