from src.calculations.sizing import build_failover_scenario_report, build_site_report
from src.calculations.thresholds import Status, Thresholds
from src.models.cluster_project import DR, PRIMARY, ClusterProject
from src.models.failover_assignment import FailoverAssignment
from src.models.server import Server
from src.models.virtual_machine import VirtualMachine


def _dr_server(sockets=1, cores_per_socket=8, ram_gb=64):
    s = Server.create_default()
    s.site = DR
    s.sockets = sockets
    s.cores_per_socket = cores_per_socket
    s.hyperthreading_enabled = False
    s.ram_gb = ram_gb
    return s


def _vm(site, vcpu, ram_gb):
    vm = VirtualMachine.create_default()
    vm.site = site
    vm.vcpu = vcpu
    vm.ram_gb = ram_gb
    return vm


def _assign(project, vm, target_site, vcpu=None, ram_gb=None, disk_gb=0):
    a = FailoverAssignment.create_default()
    a.vm_uid = vm.uid
    a.target_site = target_site
    a.vcpu = vcpu if vcpu is not None else vm.vcpu
    a.ram_gb = ram_gb if ram_gb is not None else vm.ram_gb
    a.disk_gb = disk_gb
    project.failover_assignments.append(a)


def test_failover_report_uses_same_physical_capacity_as_current():
    """DR's hardware doesn't change between the two views - only demand does."""
    project = ClusterProject()
    project.servers.append(_dr_server())
    project.vms.append(_vm(DR, vcpu=2, ram_gb=8))

    current = build_site_report(project, DR, Thresholds())
    failover = build_failover_scenario_report(project, DR, Thresholds())

    assert current.physical_cores == failover.physical_cores
    assert current.physical_ram_gb == failover.physical_ram_gb
    assert current.usable_storage_gb == failover.usable_storage_gb


def test_failover_demand_includes_baseline_plus_assigned_vms():
    project = ClusterProject()
    project.servers.append(_dr_server())
    project.vms.append(_vm(DR, vcpu=2, ram_gb=8))  # always-on DR VM (e.g. AD)
    for _ in range(3):
        vm = _vm(PRIMARY, vcpu=4, ram_gb=16)
        project.vms.append(vm)
        _assign(project, vm, DR)

    current = build_site_report(project, DR, Thresholds())
    failover = build_failover_scenario_report(project, DR, Thresholds())

    assert current.vcpu_demand == 2  # only the baseline DR VM
    assert failover.vcpu_demand == 2 + 3 * 4  # baseline + 3 assigned VMs
    assert failover.ram_demand_gb == 8 + 3 * 16


def test_failover_report_can_reveal_critical_status_current_hides():
    """The whole point of the preview - a site that looks healthy today
    can go CRITICAL once the failover load is added."""
    project = ClusterProject()
    project.servers.append(_dr_server(ram_gb=32))  # small DR host
    project.vms.append(_vm(DR, vcpu=1, ram_gb=4))  # tiny baseline - looks fine
    big_vm = _vm(PRIMARY, vcpu=8, ram_gb=64)  # big failover load
    project.vms.append(big_vm)
    _assign(project, big_vm, DR)

    current = build_site_report(project, DR, Thresholds())
    failover = build_failover_scenario_report(project, DR, Thresholds())

    assert current.ram_status == Status.OK
    assert failover.ram_status == Status.CRITICAL


def test_unassigned_primary_vms_never_count_toward_failover_demand():
    project = ClusterProject()
    project.servers.append(_dr_server())
    project.vms.append(_vm(PRIMARY, vcpu=4, ram_gb=16))  # no assignment at all

    failover = build_failover_scenario_report(project, DR, Thresholds())

    assert failover.vcpu_demand == 0
    assert failover.ram_demand_gb == 0


def test_no_dr_servers_gives_none_ratios_not_a_crash():
    project = ClusterProject()
    vm = _vm(PRIMARY, vcpu=4, ram_gb=16)
    project.vms.append(vm)
    _assign(project, vm, DR)

    failover = build_failover_scenario_report(project, DR, Thresholds())

    assert failover.cpu_ratio is None
    assert failover.ram_status == Status.UNKNOWN


def test_failover_scenario_report_works_for_a_third_site_too():
    """Generic per-site, not just fixed to DR - confirms the same
    function works for any site name."""
    project = ClusterProject()
    project.add_site("DR2")
    server = Server.create_default()
    server.site = "DR2"
    server.sockets = 1
    server.cores_per_socket = 8
    server.hyperthreading_enabled = False
    server.ram_gb = 64
    project.servers.append(server)

    vm = _vm(PRIMARY, vcpu=2, ram_gb=8)
    project.vms.append(vm)
    _assign(project, vm, "DR2")

    failover = build_failover_scenario_report(project, "DR2", Thresholds())

    assert failover.site == "DR2"
    assert failover.vcpu_demand == 2
