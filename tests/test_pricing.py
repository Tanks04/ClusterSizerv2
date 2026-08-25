from datetime import date

from src.models.server import Server
from src.models.storage import Storage, StorageShelf
from src.models.network_switch import NetworkSwitch
from src.models.backup_destination import BackupDestination
from src.models.maintenance_item import MaintenanceItem
from src.models.cluster_project import ClusterProject
from src.calculations.pricing import (
    compute_equipment_pricing, compute_maintenance_status, compute_item_status,
)


def _server(price=0.0):
    s = Server.create_default()
    s.price = price
    return s


def _storage(price=0.0, shelves=None):
    s = Storage.create_default()
    s.price = price
    s.expansion_shelves = shelves or []
    return s


def _switch(price=0.0):
    sw = NetworkSwitch.create_default()
    sw.price = price
    return sw


def _backup(price=0.0):
    d = BackupDestination.create_default()
    d.price = price
    return d


def _maintenance(expiry_date="", name="test"):
    return MaintenanceItem(
        uid="x", name=name, category="License", cost=100, duration_months=12,
        expiry_date=expiry_date,
    )


def test_empty_project_has_zero_equipment_pricing():
    summary = compute_equipment_pricing(ClusterProject())
    assert summary.total == 0
    assert all(v == 0 for v in summary.by_category.values())


def test_equipment_pricing_aggregates_across_all_four_types():
    project = ClusterProject()
    project.servers.append(_server(15000))
    project.servers.append(_server(15000))
    project.storages.append(_storage(40000))
    project.switches.append(_switch(5000))
    project.backup_destinations.append(_backup(9000))

    summary = compute_equipment_pricing(project)

    assert summary.by_category["Servers"] == 30000
    assert summary.by_category["Storage"] == 40000
    assert summary.by_category["Network"] == 5000
    assert summary.by_category["Backup"] == 9000
    assert summary.total == 30000 + 40000 + 5000 + 9000


def test_storage_shelves_count_toward_equipment_total():
    project = ClusterProject()
    project.storages.append(_storage(
        40000, shelves=[StorageShelf(name="shelf-1", price=8000)],
    ))

    summary = compute_equipment_pricing(project)

    assert summary.by_category["Storage"] == 48000
    assert summary.total == 48000


def test_item_status_expired():
    item = _maintenance(expiry_date="2026-01-01")
    status = compute_item_status(item, today=date(2026, 8, 25))
    assert status.status == "expired"
    assert status.days_until_expiry < 0


def test_item_status_expiring_soon():
    item = _maintenance(expiry_date="2026-09-10")
    status = compute_item_status(item, today=date(2026, 8, 25))
    assert status.status == "expiring_soon"
    assert 0 <= status.days_until_expiry <= 90


def test_item_status_ok():
    item = _maintenance(expiry_date="2027-06-01")
    status = compute_item_status(item, today=date(2026, 8, 25))
    assert status.status == "ok"
    assert status.days_until_expiry > 90


def test_item_status_unknown_when_no_expiry_date():
    item = _maintenance(expiry_date="")
    status = compute_item_status(item, today=date(2026, 8, 25))
    assert status.status == "unknown"
    assert status.days_until_expiry is None


def test_item_status_unknown_when_expiry_date_unparseable():
    item = _maintenance(expiry_date="not a date")
    status = compute_item_status(item, today=date(2026, 8, 25))
    assert status.status == "unknown"


def test_compute_maintenance_status_covers_every_item_in_the_project():
    project = ClusterProject()
    project.maintenance_items = [
        _maintenance(expiry_date="2026-01-01", name="expired-item"),
        _maintenance(expiry_date="2026-09-10", name="soon-item"),
        _maintenance(expiry_date="2027-06-01", name="ok-item"),
        _maintenance(expiry_date="", name="no-date-item"),
    ]

    statuses = compute_maintenance_status(project, today=date(2026, 8, 25))

    assert len(statuses) == 4
    by_name = {s.item.name: s.status for s in statuses}
    assert by_name["expired-item"] == "expired"
    assert by_name["soon-item"] == "expiring_soon"
    assert by_name["ok-item"] == "ok"
    assert by_name["no-date-item"] == "unknown"


def test_compute_maintenance_status_on_empty_project():
    assert compute_maintenance_status(ClusterProject()) == []
