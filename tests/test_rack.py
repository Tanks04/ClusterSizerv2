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


def test_cloud_site_reports_is_cloud_and_zero():
    project = ClusterProject()
    project.set_deployment_model(DR, "Cloud")

    result = compute_rack_sizing(project, DR)

    assert result.is_cloud is True
    assert result.rack_units == 0
    assert result.power_watts == 0.0


def test_cloud_site_ignores_leftover_server_rack_data():
    """A server with real rack/power values on a site flagged Cloud must
    not get summed - that data is meaningless there (e.g. a leftover
    from switching a site's deployment model)."""
    project = ClusterProject()
    project.set_deployment_model(DR, "Cloud")
    project.servers.append(_server(site=DR, rack_units=4, power_watts=1200))

    result = compute_rack_sizing(project, DR)

    assert result.rack_units == 0
    assert result.power_watts == 0.0


def test_on_premise_site_is_not_flagged_cloud():
    project = ClusterProject()
    project.servers.append(_server(rack_units=2, power_watts=500))

    result = compute_rack_sizing(project, PRIMARY)

    assert result.is_cloud is False
    assert result.rack_units == 2


def test_hybrid_project_primary_on_prem_dr_cloud():
    """The exact scenario this feature exists for - DRaaS: on-premise
    Primary with a cloud DR."""
    project = ClusterProject()
    project.set_deployment_model(DR, "Cloud")
    project.servers.append(_server(rack_units=2, power_watts=500))  # Primary, default site

    primary_result = compute_rack_sizing(project, PRIMARY)
    dr_result = compute_rack_sizing(project, DR)

    assert primary_result.is_cloud is False
    assert primary_result.rack_units == 2
    assert dr_result.is_cloud is True
    assert dr_result.rack_units == 0


def test_rack_capacity_u_for_defaults_to_zero():
    project = ClusterProject()
    assert project.rack_capacity_u_for(PRIMARY) == 0
    assert project.rack_capacity_u_for(DR) == 0


def test_rack_capacity_u_for_looks_up_the_right_site():
    project = ClusterProject()
    project.set_rack_capacity_u(PRIMARY, 84)
    project.set_rack_capacity_u(DR, 24)

    assert project.rack_capacity_u_for(PRIMARY) == 84
    assert project.rack_capacity_u_for(DR) == 24


def test_capacity_u_flows_through_to_the_summary():
    project = ClusterProject()
    project.set_rack_capacity_u(PRIMARY, 84)
    project.servers.append(_server(rack_units=12))

    result = compute_rack_sizing(project, PRIMARY)

    assert result.capacity_u == 84
    assert result.rack_units == 12


def test_over_capacity_true_when_used_exceeds_capacity():
    project = ClusterProject()
    project.set_rack_capacity_u(PRIMARY, 10)
    project.servers.append(_server(rack_units=12))

    result = compute_rack_sizing(project, PRIMARY)

    assert result.over_capacity is True


def test_over_capacity_false_when_within_capacity():
    project = ClusterProject()
    project.set_rack_capacity_u(PRIMARY, 84)
    project.servers.append(_server(rack_units=12))

    result = compute_rack_sizing(project, PRIMARY)

    assert result.over_capacity is False


def test_over_capacity_false_when_capacity_not_entered():
    """0/not-entered means nothing to compare against - never flagged
    as over, no matter how much is used."""
    project = ClusterProject()
    project.servers.append(_server(rack_units=999))

    result = compute_rack_sizing(project, PRIMARY)

    assert result.capacity_u == 0
    assert result.over_capacity is False


def test_cloud_site_still_reports_its_capacity_u_even_though_rack_units_is_zero():
    """Capacity is a site setting independent of whether the site is
    cloud - useful if a site later switches from Cloud back to
    On-Premise without losing the previously-entered capacity."""
    project = ClusterProject()
    project.set_deployment_model(DR, "Cloud")
    project.set_rack_capacity_u(DR, 24)

    result = compute_rack_sizing(project, DR)

    assert result.is_cloud is True
    assert result.rack_units == 0
    assert result.capacity_u == 24
