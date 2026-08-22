"""Computes the classic 3-2-1 backup rule (3 copies of data, on 2
different media types, 1 offsite) and the modern extension to 3-2-1-1
(add: 1 immutable/offline copy, protecting against ransomware reaching
every online copy) from a project's list of BackupDestination entries.

Evaluated project-wide, not per-site - 3-2-1 is about how many
independent copies of YOUR data exist across everywhere it's protected,
not a site-scoped capacity question the way Server/Storage math is.

Deliberately stops at 3-2-1-1, not the full "3-2-1-1-0" some vendors
(Veeam included) now promote - the "0" dimension is about verified,
tested-restorable backups (zero errors after a real recovery test),
which is a PRACTICE, not something derivable from static destination
configuration. Claiming to compute it from config alone would be
dishonest - it can't be checked, only diligently done.
"""

from dataclasses import dataclass

from src.models.backup_destination import BackupDestination


@dataclass
class BackupComplianceCheck:
    destination_count: int
    total_copies: int  # destinations + 1, since the rule counts the production copy too
    distinct_media_types: int
    has_offsite: bool
    has_immutable: bool

    @property
    def meets_3_2_1(self) -> bool:
        return self.total_copies >= 3 and self.distinct_media_types >= 2 and self.has_offsite

    @property
    def meets_3_2_1_1(self) -> bool:
        return self.meets_3_2_1 and self.has_immutable

    @property
    def missing(self) -> list[str]:
        """Human-readable list of what's missing, for a "here's exactly
        what to add" message rather than a bare pass/fail."""
        gaps = []
        if self.total_copies < 3:
            gaps.append(f"need at least 2 backup destinations for 3 total copies (have {self.destination_count})")
        if self.distinct_media_types < 2:
            gaps.append("need at least 2 different destination types (media diversity)")
        if not self.has_offsite:
            gaps.append("need at least 1 offsite destination")
        if self.meets_3_2_1 and not self.has_immutable:
            gaps.append("need at least 1 immutable/offline destination (ransomware protection)")
        return gaps


def compute_compliance(destinations: list[BackupDestination]) -> BackupComplianceCheck:
    distinct_types = {d.destination_type for d in destinations}
    return BackupComplianceCheck(
        destination_count=len(destinations),
        total_copies=len(destinations) + 1,
        distinct_media_types=len(distinct_types),
        has_offsite=any(d.is_offsite for d in destinations),
        has_immutable=any(d.is_immutable for d in destinations),
    )
