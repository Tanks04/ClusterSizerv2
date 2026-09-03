import uuid
from dataclasses import dataclass

CATEGORIES = ["License", "Warranty", "Subscription", "Support Contract", "Other"]


@dataclass
class MaintenanceItem:
    """A license, warranty, subscription, or support contract tracked as
    a renewal reminder - not a line in a sales quote. Covers the
    "firewall license subscription running for 12 months, costs X,
    expires on Y" case: what it is, what it costs, how long it lasts,
    and when it needs attention again. `applies_to` is free text (e.g.
    "Firewall FW-01", "All ESXi hosts") rather than a hard link to a
    specific Server/Storage/Switch row - keeps this simple, since one
    license or contract often covers several devices at once, or none
    in particular."""

    uid: str
    name: str
    category: str  # one of CATEGORIES

    cost: float  # EUR, for the whole duration below - not a monthly rate
    duration_months: int

    start_date: str = ""   # free format, e.g. "2026-01-01"
    expiry_date: str = ""  # free format, e.g. "2027-01-01" - the actionable reminder date

    applies_to: str = ""  # free text, e.g. "Firewall FW-01" - optional, not a hard link
    notes: str = ""

    @staticmethod
    def create_default() -> "MaintenanceItem":
        return MaintenanceItem(
            uid=str(uuid.uuid4()),
            name="",
            category="License",
            cost=0.0,
            duration_months=12,
        )
