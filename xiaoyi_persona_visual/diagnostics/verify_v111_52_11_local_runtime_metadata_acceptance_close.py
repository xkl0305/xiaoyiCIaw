from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.52.11_LOCAL_RUNTIME_METADATA_AND_ACCEPTANCE_CLOSE_FINAL'


def load_json(rel: str) -> dict:
    p = ROOT / rel
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def main() -> int:
    openclaw = load_json('openclaw.json')
    version = load_json('xiaoyi_persona_visual/version.json')
    release = load_json('release_manifest.json')
    hook = load_json('.openclaw/hooks/manifest.json')
    checks = {}
    checks['version_json_aligned'] = version.get('version') == VERSION and version.get('personal_os_enterprise_version') == VERSION
    checks['release_manifest_aligned'] = release.get('version') == VERSION and release.get('local_runtime_metadata_close') is True
    checks['hook_manifest_aligned'] = hook.get('version') == VERSION
    checks['openclaw_top_version_aligned'] = openclaw.get('PERSONAL_OS_ENTERPRISE_VERSION') == VERSION and openclaw.get('personalOSEnterpriseVersion') == VERSION
    checks['openclaw_nested_versions_aligned'] = (
        openclaw.get('personalOSEnterprise', {}).get('version') == VERSION and
        openclaw.get('personalOsEnterprise', {}).get('version') == VERSION and
        openclaw.get('localCapabilityRuntime', {}).get('version') == VERSION and
        openclaw.get('modePolicy', {}).get('version') == VERSION
    )
    checks['strict_local_top_and_runtime'] = all([
        openclaw.get('ALLOW_NETWORK') is False,
        openclaw.get('NO_EXTERNAL_API') is True,
        openclaw.get('OFFLINE_MODE') is True,
        openclaw.get('ONLINE_MODE') is False,
        openclaw.get('NO_REAL_PAYMENT') is True,
        openclaw.get('NO_REAL_SEND') is True,
        (openclaw.get('runtime') or {}).get('ALLOW_NETWORK') is False,
        (openclaw.get('runtime') or {}).get('NO_EXTERNAL_API') is True,
        (openclaw.get('runtime') or {}).get('OFFLINE_MODE') is True,
        (openclaw.get('runtime') or {}).get('ONLINE_MODE') is False,
        (openclaw.get('runtime') or {}).get('NO_REAL_PAYMENT') is True,
        (openclaw.get('runtime') or {}).get('NO_REAL_SEND') is True,
    ])
    checks['nested_profile_not_online_legacy'] = (
        openclaw.get('personalOSEnterprise', {}).get('defaultProfile') == 'strict_local_enterprise' and
        openclaw.get('personalOSEnterprise', {}).get('defaultRuntimeProfile') == 'strict_local_enterprise' and
        openclaw.get('personalOSEnterprise', {}).get('runtimeSecretPath') == 'env_only_no_workspace_path' and
        openclaw.get('personalOSEnterprise', {}).get('standingConnectionMode') == 'local_private_runtime_always_connected_no_external_egress' and
        openclaw.get('personalOsEnterprise', {}).get('defaultProfile') == 'strict_local_enterprise' and
        openclaw.get('personalOsEnterprise', {}).get('defaultRuntimeProfile') == 'strict_local_enterprise'
    )
    try:
        from infrastructure.packaging.source_runtime_boundary import package_clean_check, is_runtime_path
        clean = package_clean_check(ROOT)
        suffixes_ok = all(is_runtime_path(x) for x in ['x.sqlite3-wal', 'x.sqlite3-shm', 'x.db-wal', 'x.db-shm', 'x.tmp', 'x.cache'])
    except Exception as exc:
        clean = {'clean': False, 'error': str(exc)}
        suffixes_ok = False
    checks['package_clean_check_full'] = clean.get('clean') is True
    checks['runtime_boundary_suffixes_extended'] = suffixes_ok
    checks['acceptance_runner_uses_52_11'] = 'verify_v111_52_11_local_runtime_metadata_acceptance_close.py' in (ROOT / 'scripts/acceptance/run_all_enterprise_acceptance.sh').read_text(encoding='utf-8')
    # Make sure local endpoint policy remains loopback-only and external fallback is still disabled.
    try:
        from core.personal_os_enterprise.local_runtime_probe import probe_capability
        old = os.environ.get('LOCAL_LLM_ENDPOINT')
        os.environ['LOCAL_LLM_ENDPOINT'] = 'https://example.com/v1'
        probe = probe_capability('local_llm', root=ROOT)
        if old is None:
            os.environ.pop('LOCAL_LLM_ENDPOINT', None)
        else:
            os.environ['LOCAL_LLM_ENDPOINT'] = old
    except Exception as exc:
        probe = {'ready': True, 'reason': str(exc)}
    checks['non_local_endpoint_still_rejected'] = probe.get('ready') is False and probe.get('reason') == 'non_local_endpoint'
    overall = all(checks.values())
    print(json.dumps({
        'overall': 'passed' if overall else 'failed',
        'version': VERSION,
        'checks': checks,
        'package_clean_summary': {
            'runtime_file_count': clean.get('runtime_file_count'),
            'forbidden_residue_count': clean.get('forbidden_residue_count'),
            'secret_literal_count': clean.get('secret_literal_count'),
            'sample_runtime_files': clean.get('runtime_files_detected', [])[:20],
            'sample_forbidden_residue': clean.get('forbidden_residue_detected', [])[:20],
            'sample_secret_literals': clean.get('secret_literals_detected', [])[:20],
            'error': clean.get('error'),
        }
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
