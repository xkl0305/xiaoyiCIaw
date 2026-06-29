#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH_VERSION = 'V111.52.13.3.1_ENTERPRISE_ACCEPTANCE_TIMEOUT_AND_FAST_PATH_CLOSE_PATCH'
ACTIVE_VERSION = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def _json(path: str) -> dict:
    return json.loads(_read(path))


def _clean() -> None:
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='.')
        subprocess.run([sys.executable, '-S', str(cleaner)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _clean()
    checks: dict[str, bool] = {}
    vj = _json('xiaoyi_persona_visual/version.json')
    manifest = _json('release_manifest.json')
    runner = _read('scripts/acceptance/enterprise_acceptance_runner.py')
    run_all = _read('scripts/acceptance/run_all_enterprise_acceptance.sh')

    checks['active_version_preserved'] = vj.get('version') == ACTIVE_VERSION and manifest.get('version') == ACTIVE_VERSION
    checks['patch_feature_recorded'] = vj.get('features', {}).get('v111_52_13_3_1_patch_applied') == PATCH_VERSION
    checks['manifest_records_patch'] = manifest.get('last_patch_version') == PATCH_VERSION
    checks['runner_has_hard_timeout_handling'] = 'subprocess.TimeoutExpired' in runner and 'SystemExit(124)' in runner and 'timed out' in runner
    checks['runner_has_process_group_timeout_guard'] = 'start_new_session=True' in runner and 'signal.SIGKILL' in runner
    checks['runner_has_fast_path_gates'] = all(x in runner for x in ['active_metadata_fast', 'forward_compat_fast', 'clean_gate_fast'])
    checks['runner_does_not_subprocess_nested_legacy_verifiers'] = all((x not in runner) for x in [
        "run('forward_compat'",
        "run('clean_gate'",
        "verify_v111_52_12_1_full_local_stack_runtime_clean_close.py",
    ])
    checks['run_all_calls_runner'] = 'enterprise_acceptance_runner.py' in run_all
    checks['pytest_matrix_still_required'] = all(x in runner for x in ['tests/acceptance', 'test_ocr_vlm_consistency.py', 'test_persona_visual_anatomy.py', 'test_wardrobe_state.py'])
    checks['strict_52_13_3_still_called'] = 'verify_v111_52_13_3_acceptance_matrix_and_proof_contract_strict_close.py' in runner
    checks['runner_source_compiles'] = compile(runner, 'scripts/acceptance/enterprise_acceptance_runner.py', 'exec') is not None

    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    _clean()
    clean = package_clean_check(ROOT)
    checks['package_clean'] = clean.get('clean') is True

    out = {
        'overall': 'passed' if all(checks.values()) else 'failed',
        'patch_version': PATCH_VERSION,
        'active_version': vj.get('version'),
        'checks': checks,
        'enterprise_acceptance_run_policy': 'not recursively executed inside this verifier; run bash scripts/acceptance/run_all_enterprise_acceptance.sh as the top-level acceptance command',
        'package_clean': clean,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
