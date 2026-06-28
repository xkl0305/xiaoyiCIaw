from core.personal_os_enterprise.observability_dashboard import dashboard_report
from core.personal_os_enterprise.observability_event_bus import emit_event


def test_observability_dashboard(tmp_path):
    emit_event('unit_probe', {'ok': True}, root=tmp_path)
    r = dashboard_report(root=tmp_path)
    assert r['status'] == 'ok'
    assert r['network_egress_attempted'] is False
