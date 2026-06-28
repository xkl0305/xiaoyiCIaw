from __future__ import annotations

import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.52.8_LOCAL_CAPABILITY_RUNTIME_FUSION'


def _exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def run_verification() -> dict:
    from core.personal_os_enterprise.local_capability_registry import assert_declared_capabilities, list_capabilities
    from core.personal_os_enterprise.capability_router import classify_capability_request, route_request
    from core.personal_os_enterprise.local_health_check import health_check
    from core.personal_os_enterprise.local_model_registry import model_manifest_summary

    checks = {}
    required_files = [
        'core/personal_os_enterprise/capability_router.py',
        'core/personal_os_enterprise/local_capability_registry.py',
        'core/personal_os_enterprise/local_model_registry.py',
        'core/personal_os_enterprise/local_runtime_probe.py',
        'core/personal_os_enterprise/local_health_check.py',
        'core/personal_os_enterprise/local_provider_base.py',
        'core/personal_os_enterprise/local_providers.py',
        'core/personal_os_enterprise/offline_model_cache.py',
        'core/personal_os_enterprise/metrics_catalog.py',
        'core/personal_os_enterprise/observability_dashboard.py',
        'core/personal_os_enterprise/data_governance.py',
        'core/personal_os_enterprise/embodied_screen_agent.py',
        'core/personal_os_enterprise/rootless_deploy.py',
        'profiles/local_capabilities.example.toml',
        'governance/local_capability_policy.json',
        'acceptance_matrix/local_capability_runtime.yaml',
    ]
    checks['required_files_present'] = all(_exists(p) for p in required_files)
    reg = assert_declared_capabilities()
    checks['registry_ok'] = reg.get('ok') is True
    caps = list_capabilities()
    for name in ['local_llm','local_vlm','local_ocr','local_asr','local_tts','local_embedding','local_reranker','persona_visual_mainchain']:
        checks[f'capability_declared_{name}'] = name in caps

    samples = {
        'text': ('帮我总结这段文字', ['local_llm']),
        'ocr': ('识别图片文字', ['local_ocr']),
        'vlm': ('看一下截图里有什么按钮', ['local_vlm']),
        'screen': ('识别截图文字并判断界面状态', ['local_ocr','local_vlm']),
        'asr': ('把这段录音转文字', ['local_asr']),
        'tts': ('把回复念出来', ['local_tts']),
        'embedding': ('从知识库做语义检索', ['local_embedding']),
        'reranker': ('把检索结果重排一下', ['local_reranker']),
        'persona': ('鸽子王看看你的样子', ['persona_visual_mainchain']),
    }
    for key, (text, expected) in samples.items():
        route = classify_capability_request(text)
        got = route.get('required_capabilities') or []
        checks[f'route_{key}'] = all(e in got for e in expected)
        checks[f'route_{key}_no_external'] = route.get('allow_external_fallback') is False

    with tempfile.TemporaryDirectory() as td:
        blocked = route_request('识别图片文字', root=td, require_ready=True)
        checks['missing_local_capability_fail_closed'] = blocked.get('blocked') is True and blocked.get('blocked_reason') == 'capability_not_available'
        checks['missing_local_capability_no_external'] = blocked.get('allow_external_fallback') is False and blocked.get('network_egress_attempted') is False
        health = health_check(root=td)
        checks['health_check_no_external'] = health.get('allow_external_fallback') is False and health.get('network_egress_attempted') is False
        summary = model_manifest_summary(root=td)
        checks['model_manifest_no_external'] = summary.get('allow_external_fallback') is False


    from core.personal_os_enterprise.offline_model_cache import check_model_cache
    from core.personal_os_enterprise.observability_dashboard import dashboard_report
    from core.personal_os_enterprise.data_governance import retention_policy, classify_data_path
    from core.personal_os_enterprise.embodied_screen_agent import plan_screen_understanding

    cache = check_model_cache(root=ROOT)
    checks['offline_model_cache_no_network'] = cache.get('network_egress_attempted') is False
    checks['data_governance_secret_not_packaged'] = retention_policy()['classes']['S0']['packaged'] is False
    checks['data_governance_classifies_secret'] = classify_data_path('secrets/runtime.env')['level'] == 'S0'
    screen_plan = plan_screen_understanding('看一下截图里有什么按钮', root=ROOT)
    checks['embodied_screen_agent_uses_local_vlm_ocr'] = 'local_vlm' in screen_plan.get('required_capabilities', []) and 'local_ocr' in screen_plan.get('required_capabilities', [])
    with tempfile.TemporaryDirectory() as obs_td:
        dash = dashboard_report(root=obs_td)
        checks['observability_dashboard_local'] = dash.get('backend') == 'sqlite_wal' and dash.get('network_egress_attempted') is False

    try:
        openclaw = json.loads((ROOT / 'openclaw.json').read_text(encoding='utf-8'))
    except Exception:
        openclaw = {}
    checks['openclaw_version_aligned'] = (openclaw.get('PERSONAL_OS_ENTERPRISE_VERSION') == VERSION or str(openclaw.get('PERSONAL_OS_ENTERPRISE_VERSION')).startswith('V111.52.9') or str(openclaw.get('PERSONAL_OS_ENTERPRISE_VERSION')).startswith('V111.52.10') or str(openclaw.get('PERSONAL_OS_ENTERPRISE_VERSION')).startswith('V111.52.11'))
    checks['openclaw_strict_local'] = openclaw.get('NO_EXTERNAL_API') is True and openclaw.get('ALLOW_NETWORK') is False
    checks['openclaw_local_runtime_enabled'] = openclaw.get('LOCAL_CAPABILITY_RUNTIME_FUSION') is True or openclaw.get('localCapabilityRuntime',{}).get('enabled') is True

    overall = all(checks.values())
    return {'overall': 'passed' if overall else 'failed', 'version': VERSION, 'checks': checks}


if __name__ == '__main__':
    print(json.dumps(run_verification(), ensure_ascii=False, indent=2, sort_keys=True))
