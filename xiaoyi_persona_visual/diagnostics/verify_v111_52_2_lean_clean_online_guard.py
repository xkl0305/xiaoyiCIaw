from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.52.2_PERSONAL_OS_ENTERPRISE_LEAN_CLEAN_FINAL'
ACCEPTED_DESCENDANT_VERSIONS = {'V111.52.3_SIDE_EFFECT_PROOF_FULL_FUSION', 'V111.52.4_SIDE_EFFECT_FUSION_CLEAN_REPAIR_FINAL'}

FORBIDDEN_PATHS = [
    'overlay_payload_v111_52_1',
    'overlay_payload_v111_52_2',
    '.openclaw/hook_state',
    '.openclaw/state',
    '.v98_state',
    '.v107_state',
    '.lazy_state',
    '.context_state',
    'logs',
    'post_overlay_check_result.json',
    '1778744344238_V111_52_0_personal_os_enterprise_core_overlay.zip',
]

REQUIRED_FILES = [
    'core/personal_os_enterprise/action_guard.py',
    'core/personal_os_enterprise/runtime_profile.py',
    'core/personal_os_enterprise/side_effect_proof.py',
    'core/personal_os_enterprise/observability_event_bus.py',
    'profiles/always_connected_enterprise.toml',
    'acceptance_matrix/personal_os_enterprise_online_guard.yaml',
]


def read_json(rel: str) -> dict:
    try:
        return json.loads((ROOT / rel).read_text(encoding='utf-8'))
    except Exception:
        return {}


def main() -> int:
    release = read_json('release_manifest.json')
    version = read_json('xiaoyi_persona_visual/version.json')
    openclaw = read_json('openclaw.json')

    forbidden_existing = [p for p in FORBIDDEN_PATHS if (ROOT / p).exists()]
    pycache = [str(p.relative_to(ROOT)) for p in ROOT.rglob('__pycache__')]
    pyc = [str(p.relative_to(ROOT)) for p in ROOT.rglob('*.pyc')]
    jsonl = [str(p.relative_to(ROOT)) for p in ROOT.rglob('*.jsonl')]
    ds_store = [str(p.relative_to(ROOT)) for p in ROOT.rglob('.DS_Store')]
    missing_required = [p for p in REQUIRED_FILES if not (ROOT / p).exists()]

    checks = {
        'release_version': release.get('version') in {VERSION, *ACCEPTED_DESCENDANT_VERSIONS},
        'enterprise_version': version.get('personal_os_enterprise_version') in {VERSION, 'V111.52.1_PERSONAL_OS_ENTERPRISE_ONLINE_GUARD', *ACCEPTED_DESCENDANT_VERSIONS} or openclaw.get('personalOsEnterprise', {}).get('version') in {VERSION, *ACCEPTED_DESCENDANT_VERSIONS},
        'openclaw_online': openclaw.get('ONLINE_MODE') is True and openclaw.get('OFFLINE_MODE') is False,
        'always_connected': openclaw.get('CONNECTED_RUNTIME_ALWAYS_ON') is True,
        'required_files_present': not missing_required,
        'no_forbidden_runtime_paths': not forbidden_existing,
        'no_pycache': not pycache,
        'no_pyc': not pyc,
        'no_jsonl_ledgers': not jsonl,
        'no_ds_store': not ds_store,
    }
    result = {
        'overall': 'passed' if all(checks.values()) else 'failed',
        'version': VERSION,
        'checks': checks,
        'details': {
            'forbidden_existing': forbidden_existing[:50],
            'missing_required': missing_required,
            'pycache_count': len(pycache),
            'pyc_count': len(pyc),
            'jsonl_count': len(jsonl),
            'ds_store_count': len(ds_store),
        }
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['overall'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
