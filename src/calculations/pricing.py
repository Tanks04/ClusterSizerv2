"""Two unrelated jobs, both simple on purpose:

1. Totals up what equipment costs, by category - this app just gives
   admins a sum, it isn't a sales quoting tool (no cost-vs-price,
   margin, or uplift here anymore - see docs/ROADMAP.md's v3.2.0 entry
   for why that was pulled back out after v3.0/3.1 tried it).
2. Flags Maintenance Items (licenses, warranties, subscriptions,
   support contracts) that are expiring soon or already expired - the
   whole point of tracking them is not missing a renewal.
"""

from dataclasses import dataclass
from datetime import date

from src.models.cluster_project import ClusterProject
from src.models.maintenance_item import MaintenanceItem

EXPIRING_SOON_DAYS = 90


@dataclass
class EquipmentPricingSummary:
    by_category: dict[str, float]  # "Servers" / "Storage" / "Network" / "Backup" -> total EUR
    total: float


def compute_equipment_pricing(project: ClusterProject) -> EquipmentPricingSummary:
    by_category = {
        "Servers": sum(s.price for s in project.servers),
        "Storage": sum(s.total_price for s in project.storages),  # includes shelves
        "Network": sum(s.price for s in project.switches),
        "Backup": sum(s.price for s in project.backup_destinations),
    }
    return EquipmentPricingSummary(by_category=by_category, total=sum(by_category.values()))


@dataclass
class MaintenanceStatus:
    item: MaintenanceItem
    status: str  # "expired" | "expiring_soon" | "ok" | "unknown"
    days_until_expiry: int | None  # None when expiry_date is blank or unparseable


def _parse_date(text: str) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None  # free-text field elsewhere in the app too - don't crash on an unexpected format


def compute_item_status(item: MaintenanceItem, today: date | None = None) -> MaintenanceStatus:
    today = today or date.today()
    expiry = _parse_date(item.expiry_date)
    if expiry is None:
        return MaintenanceStatus(item=item, status="unknown", days_until_expiry=None)

    days = (expiry - today).days
    if days < 0:
        status = "expired"
    elif days <= EXPIRING_SOON_DAYS:
        status = "expiring_soon"
    else:
        status = "ok"
    return MaintenanceStatus(item=item, status=status, days_until_expiry=days)


def compute_maintenance_status(project: ClusterProject, today: date | None = None) -> list[MaintenanceStatus]:
    today = today or date.today()
    return [compute_item_status(item, today) for item in project.maintenance_items]
