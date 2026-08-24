from src.models.server import Server
from src.models.virtual_machine import VirtualMachine
from src.models.cluster_project import ClusterProject, PRIMARY, DR
from src.calculations.sizing import build_site_report, build_dr_failover_report
from src.calculations.thresholds import Thresholds, Status


def _dr_server(sockets=1, cores_per_socket=8, ram_gb=64):
    s = Server.create_default()
    s.site = DR
    s.sockets = sockets
    s.cores_per_socket = cores_per_socket
    s.hyperthreading_enabled = False
    s.ram_gb = ram_gb
    return s


def _vm(site, vcpu, ram_gb, dr_protected=False, dr_vcpu=None, dr_ram_gb=None):
    vm = VirtualMachine.create_default()
    vm.site = site
    vm.vcpu = vcpu
    vm.ram_gb = ram_gb
    vm.dr_protected = dr_protected
    if dr_protected:
        vm.dr_vcpu = dr_vcpu if dr_vcpu is not None else vcpu
        vm.dr_ram_gb = dr_ram_gb if dr_ram_gb is not None else ram_gb
    return vm


def test_failover_report_uses_same_physical_capacity_as_current():
    """DR's hardware doesn't change between the two views - only demand does."""
    project = ClusterProject()
    project.servers.append(_dr_server())
    project.vms.append(_vm(DR, vcpu=2, ram_gb=8))

    current = build_site_report(project, DR, Thresholds())
    failover = build_dr_failover_report(project, Thresholds())

    assert current.physical_cores == failover.physical_cores
    assert current.physical_ram_gb == failover.physical_ram_gb
    assert current.usable_storage_gb == failover.usable_storage_gb


def test_failover_demand_includes_baseline_plus_protected_vms():
    project = ClusterProject()
    project.servers.append(_dr_server())
    project.vms.append(_vm(DR, vcpu=2, ram_gb=8))  # always-on DR VM (e.g. AD)
    for _ in range(3):
        project.vms.append(_vm(PRIMARY, vcpu=4, ram_gb=16, dr_protected=True))

    current = build_site_report(project, DR, Thresholds())
    failover = build_dr_failover_report(project, Thresholds())

    assert current.vcpu_demand == 2  # only the baseline DR VM
    assert failover.vcpu_demand == 2 + 3 * 4  # baseline + 3 protected VMs
    assert failover.ram_demand_gb == 8 + 3 * 16


def test_failover_report_can_reveal_critical_status_current_hides():
    """The whole point of the preview - a site that looks healthy today
    can go CRITICAL once the failover load is added."""
    project = ClusterProject()
    project.servers.append(_dr_server(ram_gb=32))  # small DR host
    project.vms.append(_vm(DR, vcpu=1, ram_gb=4))  # tiny baseline - looks fine
    project.vms.append(_vm(PRIMARY, vcpu=8, ram_gb=64, dr_protected=True))  # big failover load

    current = build_site_report(project, DR, Thresholds())
    failover = build_dr_failover_report(project, Thresholds())

    assert current.ram_status == Status.OK
    assert failover.ram_status == Status.CRITICAL


def test_unprotected_primary_vms_never_count_toward_failover_demand():
    project = ClusterProject()
    project.servers.append(_dr_server())
    project.vms.append(_vm(PRIMARY, vcpu=4, ram_gb=16, dr_protected=False))

    failover = build_dr_failover_report(project, Thresholds())

    assert failover.vcpu_demand == 0
    assert failover.ram_demand_gb == 0


def test_no_dr_servers_gives_none_ratios_not_a_crash():
    project = ClusterProject()
    project.vms.append(_vm(PRIMARY, vcpu=4, ram_gb=16, dr_protected=True))

    failover = build_dr_failover_report(project, Thresholds())

    assert failover.cpu_ratio is None
    assert failover.ram_status == Status.UNKNOWN
