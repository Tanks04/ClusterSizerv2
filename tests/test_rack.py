from src.models.server import Server
from src.models.storage import Storage, StorageShelf
from src.models.network_switch import NetworkSwitch
from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.calculations.rack import compute_rack_sizing


def _server(site=PRIMARY, rack_units=0, power_watts=0.0):
    s = Server.create_default()
    s.site = site
    s.rack_units = rack_units
    s.power_watts = power_watts
    return s


def _storage(site=PRIMARY, rack_units=0, power_watts=0.0, shelves=None):
    s = Storage.create_default()
    s.site = site
    s.rack_units = rack_units
    s.power_watts = power_watts
    s.expansion_shelves = shelves or []
    return s


def _switch(site=PRIMARY, rack_units=0, power_watts=0.0):
    sw = NetworkSwitch.create_default()
    sw.site = site
    sw.rack_units = rack_units
    sw.power_watts = power_watts
    return sw


def test_empty_project_has_zero_rack_sizing():
    result = compute_rack_sizing(ClusterProject(), PRIMARY)
    assert result.rack_units == 0
    assert result.power_watts == 0


def test_unset_fields_are_excluded_not_counted_as_zero():
    """A server/storage/switch with rack_units/power_watts left at 0
    (never entered) must not skew the total - this test would pass
    trivially either way numerically, but pins the INTENT: 0 means
    "not entered", not "confirmed zero-U, zero-watt equipment"."""
    project = ClusterProject()
    project.servers.append(_server())  # nothing entered
    result = compute_rack_sizing(project, PRIMARY)
    assert result.rack_units == 0
    assert result.power_watts == 0


def test_aggregates_servers_storage_and_switches_together():
    project = ClusterProject()
    project.servers.append(_server(rack_units=2, power_watts=750))
    project.servers.append(_server(rack_units=2, power_watts=750))
    project.storages.append(_storage(rack_units=4, power_watts=1200))
    project.switches.append(_switch(rack_units=1, power_watts=150))

    result = compute_rack_sizing(project, PRIMARY)

    assert result.rack_units == 2 + 2 + 4 + 1
    assert result.power_watts == 750 + 750 + 1200 + 150


def test_storage_shelves_count_toward_the_total():
    project = ClusterProject()
    project.storages.append(_storage(
        rack_units=4, power_watts=1200,
        shelves=[
            StorageShelf(name="shelf-1", rack_units=2, power_watts=400),
            StorageShelf(name="shelf-2", rack_units=2, power_watts=400),
        ],
    ))

    result = compute_rack_sizing(project, PRIMARY)

    assert result.rack_units == 4 + 2 + 2
    assert result.power_watts == 1200 + 400 + 400


def test_sites_are_kept_independent():
    project = ClusterProject()
    project.servers.append(_server(site=PRIMARY, rack_units=2, power_watts=750))
    project.servers.append(_server(site=DR, rack_units=2, power_watts=750))

    primary = compute_rack_sizing(project, PRIMARY)
    dr = compute_rack_sizing(project, DR)

    assert primary.rack_units == 2
    assert dr.rack_units == 2
    assert primary.power_watts == dr.power_watts == 750


def test_storage_total_rack_units_and_power_properties():
    storage = _storage(
        rack_units=4, power_watts=1200,
        shelves=[StorageShelf(name="shelf-1", rack_units=2, power_watts=400)],
    )
    assert storage.total_rack_units == 6
    assert storage.total_power_watts == 1600


def test_disabled_server_still_counts_toward_rack_sizing():
    """Deliberate design choice, pinned so it can't regress silently:
    rack.py does NOT filter by Server.enabled - a disabled server is
    excluded from CAPACITY math (CPU/RAM/storage), but it's still
    physically sitting in the rack drawing power. See rack.py's module
    docstring for the full reasoning."""
    project = ClusterProject()
    server = _server(rack_units=2, power_watts=800)
    server.enabled = False
    project.servers.append(server)

    result = compute_rack_sizing(project, PRIMARY)

    assert result.rack_units == 2
    assert result.power_watts == 800
