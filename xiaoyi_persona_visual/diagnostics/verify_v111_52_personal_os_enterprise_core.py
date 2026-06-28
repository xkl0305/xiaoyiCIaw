from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    required = [
        'core/personal_os_enterprise/offline_profile.py',
        'core/personal_os_enterprise/side_effect_proof.py',
        'core/personal_os_enterprise/side_effect_registry.py',
        'core/personal_os_enterprise/action_guard.py',
        'core/personal_os_enterprise/runtime_secret_provider.py',
        'core/personal_os_enterprise/acceptance_matrix_runner.py',
        'core/personal_os_enterprise/observability_event_bus.py',
        'core/personal_os_enterprise/local_capability_registry.py',
        'profiles/offline_enterprise.toml',
        'governance/side_effect_policy.json',
        'governance/failure_pattern_registry.json',
        'infrastructure/packaging/source_runtime_boundary.py',
        'infrastructure/observability/metrics_catalog.json',
        'acceptance_matrix/personal_os_enterprise.yaml',
    ]
    checks = {f'file_exists:{p}': (ROOT / p).exists() for p in required}

    from core.personal_os_enterprise.acceptance_matrix_runner import run_acceptance_matrix
    result = run_acceptance_matrix(root=ROOT)
    checks['acceptance_matrix_runner_passed'] = result.get('overall') == 'passed'
    checks.update({f'matrix:{k}': v for k, v in result.get('checks', {}).items()})

    from core.personal_os_enterprise.offline_profile import load_offline_profile
    profile = load_offline_profile(ROOT / 'profiles' / 'offline_enterprise.toml')
    checks['offline_network_disabled'] = profile.get('ALLOW_NETWORK') is False
    checks['external_api_disabled'] = profile.get('NO_EXTERNAL_API') is True

    from infrastructure.packaging.source_runtime_boundary import is_runtime_path
    checks['runtime_secret_boundary'] = is_runtime_path('.openclaw/state/personal_os_enterprise/secrets/x.secret') is True
    checks['pyc_boundary'] = is_runtime_path('pkg/__pycache__/x.pyc') is True
    checks['legacy_boundary'] = is_runtime_path('legacy_readonly/old.md') is True

    overall = all(checks.values())
    out = {'version': 'V111.52.0_PERSONAL_OS_ENTERPRISE_CORE', 'overall': 'passed' if overall else 'failed', 'checks': checks}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
