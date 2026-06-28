#!/usr/bin/env python3
from __future__ import annotations
import json, os, os, subprocess, sys
from pathlib import Path
import tempfile

VERSION='V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL'
VERSION_13_1='V111.52.13.1_ENTERPRISE_REPORT_REMAINING_CLEAN_GATE_FINAL'
VERSION_13_2='V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'
ACCEPTED_VERSIONS={VERSION, VERSION_13_1, VERSION_13_2}
ROOT=Path(__file__).resolve().parents[2]

def j(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

def exists(path):
    return (ROOT/path).exists()

def clean_runtime_quiet() -> None:
    """Keep verification self-contained: verification imports may create runtime files.
    Clean before the package_clean gate so direct verify and acceptance verify agree.
    """
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONPATH'] = '.'
        subprocess.run([sys.executable, '-S', str(cleaner)], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def main():
    clean_runtime_quiet()
    checks={}
    v=j('xiaoyi_persona_visual/version.json')
    rm=j('release_manifest.json')
    oc=j('openclaw.json')
    current_version=v.get('version')
    checks['version_52_13']=current_version in ACCEPTED_VERSIONS and rm.get('version')==current_version and oc.get('PERSONAL_OS_ENTERPRISE_VERSION')==current_version
    checks['active_metadata_aligned']=all([
        oc.get('personalOSEnterpriseVersion')==current_version,
        (oc.get('personalOSEnterprise') or {}).get('version')==current_version,
        (oc.get('personalOsEnterprise') or {}).get('version')==current_version,
        (oc.get('localCapabilityRuntime') or {}).get('version')==current_version,
        (oc.get('personaVisual') or {}).get('version')==current_version,
    ])
    checks['strict_local_runtime']= all([
        oc.get('ALLOW_NETWORK') is False, oc.get('NO_EXTERNAL_API') is True, oc.get('OFFLINE_MODE') is True, oc.get('ONLINE_MODE') is False,
        oc.get('NO_REAL_PAYMENT') is True, oc.get('NO_REAL_SEND') is True, oc.get('runtime',{}).get('ALLOW_NETWORK') is False,
        oc.get('runtime',{}).get('ONLINE_MODE') is False,
    ])
    required=[
        'core/personal_os_enterprise/enterprise_acceptance_suite.py',
        'core/personal_os_enterprise/observability_ops.py',
        'core/personal_os_enterprise/secret_workflow_guard.py',
        'core/personal_os_enterprise/rootless_deploy_smoke.py',
        'core/personal_os_enterprise/data_retention_manager.py',
        'core/personal_os_enterprise/local_persona_image_domain.py',
        'core/personal_os_enterprise/private_network_policy.py',
        'acceptance_matrix/report_remaining_close.yaml',
        'tests/acceptance/test_offline_boot.py',
        'tests/acceptance/test_mainchain_proof.py',
        'tests/acceptance/test_send_guard.py',
        'tests/acceptance/test_provider_fallback.py',
        'tests/regression/test_ocr_vlm_consistency.py',
        'tests/regression/test_persona_visual_anatomy.py',
        'tests/regression/test_wardrobe_state.py',
        'scripts/security/verify_secret_workflow.py',
        'scripts/deployment/verify_rootless_runtime.py',
        'deployment/rootless/healthcheck.sh',
    ]
    checks['required_files_present']=all(exists(p) for p in required)
    from core.personal_os_enterprise.enterprise_acceptance_suite import acceptance_matrix, validate_acceptance_files
    matrix=acceptance_matrix(); file_check=validate_acceptance_files(ROOT)
    checks['acceptance_matrix_complete']=matrix.get('case_count',0)>=13 and file_check.get('ok') is True
    from core.personal_os_enterprise.observability_ops import SLO_TARGETS, METRIC_KEYS, build_slo_report, emit_metric
    checks['slo_metric_catalog_complete']=len(METRIC_KEYS)>=12 and SLO_TARGETS.get('network_egress_allowed') is False
    with tempfile.TemporaryDirectory() as td:
        emit_metric('offline_boot_success_total', 1, root=td)
        slo=build_slo_report(root=td)
    checks['observability_slo_report_ready']=slo.get('trace_coverage_ready') is True and slo.get('fail_closed_policy') is True
    from core.personal_os_enterprise.secret_workflow_guard import validate_secret_workflow
    checks['secret_workflow_ready']=validate_secret_workflow(ROOT).get('ok') is True
    from core.personal_os_enterprise.rootless_deploy_smoke import rootless_deploy_plan
    checks['rootless_deploy_smoke_ready']=rootless_deploy_plan(ROOT).get('ok') is True
    from core.personal_os_enterprise.data_retention_manager import retention_policy
    pol=retention_policy()
    checks['data_retention_policy_ready']=pol.get('debug_log_redaction_required') is True and 'S1_screenshot' in pol.get('ttl_days',{})
    from core.personal_os_enterprise.local_persona_image_domain import persona_image_provider_chain_status
    lp=persona_image_provider_chain_status({})
    checks['local_persona_image_fail_closed']=lp.get('status')=='blocked' and lp.get('external_fallback_allowed') is False
    from core.personal_os_enterprise.private_network_policy import private_network_policy
    pn=private_network_policy()
    checks['private_network_policy_ready']=pn.get('external_internet_egress') is False and pn.get('node_id_required_for_multi_node') is True
    clean_runtime_quiet()
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean=package_clean_check(ROOT)
    checks['package_clean']=clean.get('clean') is True
    out={'overall':'passed' if all(checks.values()) else 'failed','version':current_version,'accepted_versions':sorted(ACCEPTED_VERSIONS),'checks':checks,'acceptance_matrix':matrix,'acceptance_files':file_check,'slo_report':slo,'package_clean':clean}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if all(checks.values()) else 1
if __name__=='__main__':
    _rc = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_rc)
