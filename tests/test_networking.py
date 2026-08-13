from src.models.server import Server
from src.models.storage import Storage
from src.models.network_switch import NetworkSwitch
from src.models.network_connection import NetworkConnection
from src.calculations.networking import (
    switch_port_usage, server_nic_usage, storage_port_usage,
    site_port_usage, any_over_committed, format_usage,
)


def _server(nic_1g=0, nic_fc=0):
    s = Server.create_default()
    s.nic_1g = nic_1g
    s.nic_10g = 0
    s.nic_25g = 0
    s.nic_40g = 0
    s.nic_100g = 0
    s.nic_fc = nic_fc
    s.nic_sas = 0
    return s


def _switch(ports_1g=0, ports_fc=0):
    sw = NetworkSwitch.create_default()
    sw.ports_1g = ports_1g
    sw.ports_10g = 0
    sw.ports_25g = 0
    sw.ports_40g = 0
    sw.ports_100g = 0
    sw.ports_fc = ports_fc
    sw.ports_sas = 0
    return sw


def _storage(ports_1g=0, ports_fc=0):
    st = Storage.create_default()
    st.ports_1g = ports_1g
    st.ports_10g = 0
    st.ports_25g = 0
    st.ports_40g = 0
    st.ports_100g = 0
    st.ports_fc = ports_fc
    st.ports_sas = 0
    return st


def _connection(server=None, switch=None, storage=None, speed="1G"):
    c = NetworkConnection.create_default()
    c.speed = speed
    if server is not None:
        c.server_uid = server.uid
    if switch is not None:
        c.switch_uid = switch.uid
    if storage is not None:
        c.storage_uid = storage.uid
    return c


def test_switch_port_usage_with_connections():
    server = _server(nic_1g=4)
    switch = _switch(ports_1g=8)
    connections = [_connection(server=server, switch=switch, speed="1G")]

    usage = switch_port_usage(switch, connections)
    assert len(usage) == 1
    assert usage[0].speed == "1G"
    assert usage[0].total == 8
    assert usage[0].used == 1


def test_switch_port_usage_no_connections():
    switch = _switch(ports_1g=8)
    usage = switch_port_usage(switch, [])
    assert len(usage) == 1
    assert usage[0].used == 0
    assert usage[0].free == 8


def test_server_nic_usage_with_connections():
    server = _server(nic_1g=2)
    switch = _switch(ports_1g=8)
    connections = [_connection(server=server, switch=switch, speed="1G")]

    usage = server_nic_usage(server, connections)
    assert len(usage) == 1
    assert usage[0].total == 2
    assert usage[0].used == 1


def test_server_nic_usage_no_connections():
    server = _server(nic_1g=2)
    usage = server_nic_usage(server, [])
    assert usage[0].used == 0


def test_storage_port_usage_with_connections():
    switch = _switch(ports_fc=16)
    storage = _storage(ports_fc=4)
    connections = [_connection(switch=switch, storage=storage, speed="FC")]

    usage = storage_port_usage(storage, connections)
    assert len(usage) == 1
    assert usage[0].speed == "FC"
    assert usage[0].total == 4
    assert usage[0].used == 1


def test_storage_port_usage_no_connections():
    storage = _storage(ports_fc=4)
    usage = storage_port_usage(storage, [])
    assert usage[0].used == 0


def test_multiple_speeds_tracked_independently():
    server = _server(nic_1g=4, nic_fc=2)
    switch = _switch(ports_1g=8, ports_fc=8)
    connections = [
        _connection(server=server, switch=switch, speed="1G"),
        _connection(server=server, switch=switch, speed="1G"),
        _connection(server=server, switch=switch, speed="FC"),
    ]

    usage = {u.speed: u for u in server_nic_usage(server, connections)}
    assert usage["1G"].used == 2
    assert usage["FC"].used == 1


def test_site_port_usage_aggregates_across_switches():
    switch_a = _switch(ports_1g=4)
    switch_b = _switch(ports_1g=4)
    connections = [
        _connection(switch=switch_a, speed="1G"),
        _connection(switch=switch_b, speed="1G"),
    ]

    usage = site_port_usage([switch_a, switch_b], connections)
    assert len(usage) == 1
    assert usage[0].total == 8
    assert usage[0].used == 2


def test_any_over_committed():
    switch = _switch(ports_1g=1)
    connections = [
        _connection(switch=switch, speed="1G"),
        _connection(switch=switch, speed="1G"),
    ]
    usage = switch_port_usage(switch, connections)
    assert any_over_committed(usage) is True
    assert usage[0].free == 0  # never negative


def test_format_usage_empty():
    assert format_usage([]) == "-"


def test_wrappers_do_not_cross_match_each_others_uid_field():
    """Pins the S21 refactor: server_nic_usage/switch_port_usage/
    storage_port_usage must each match ONLY their own uid field. A server
    and a switch with the SAME connection should not have that connection
    counted against the storage - and if the three wrappers' uid_attr
    arguments were ever accidentally swapped, this would fail."""
    server = _server(nic_1g=4)
    switch = _switch(ports_1g=4)
    storage = _storage(ports_1g=4)

    # This connection is Server<->Switch only - storage_uid is empty.
    connections = [_connection(server=server, switch=switch, speed="1G")]

    assert server_nic_usage(server, connections)[0].used == 1
    assert switch_port_usage(switch, connections)[0].used == 1
    # Storage was never referenced by this connection - must show 0 used,
    # not accidentally pick up the server or switch's usage.
    assert storage_port_usage(storage, connections)[0].used == 0
