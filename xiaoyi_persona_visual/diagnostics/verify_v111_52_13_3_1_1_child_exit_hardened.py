#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH_VERSION = 'V111.52.13.3.1.1_ENTERPRISE_ACCEPTANCE_CHILD_VERIFIER_EXIT_CLOSE_PATCH'
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
    report = _read('xiaoyi_persona_visual/diagnostics/verify_v111_52_13_report_remaining_close.py')
    strict = _read('xiaoyi_persona_visual/diagnostics/verify_v111_52_13_3_acceptance_matrix_and_proof_contract_strict_close.py')

    checks['active_version_preserved'] = vj.get('version') == ACTIVE_VERSION and manifest.get('version') == ACTIVE_VERSION
    checks['subpatch_feature_recorded'] = vj.get('features', {}).get('v111_52_13_3_1_1_patch_applied') == PATCH_VERSION
    checks['runner_keeps_os_exit'] = 'os._exit(main())' in runner
    checks['report_remaining_child_hard_exit'] = 'os._exit(_rc)' in report and 'sys.stdout.flush()' in report
    checks['strict_52_13_3_child_hard_exit'] = 'os._exit(_rc)' in strict and 'sys.stdout.flush()' in strict
    checks['runner_has_process_group_timeout_guard'] = 'start_new_session=True' in runner and 'signal.SIGKILL' in runner and 'subprocess.TimeoutExpired' in runner
    checks['pytest_matrix_still_required'] = all(x in runner for x in ['tests/acceptance', 'test_ocr_vlm_consistency.py', 'test_persona_visual_anatomy.py', 'test_wardrobe_state.py'])
    checks['report_remaining_uses_fast_gate'] = 'report_remaining_fast' in runner and 'verify_v111_52_13_report_remaining_close.py' not in runner
    checks['strict_52_13_3_uses_direct_gate'] = 'strict_52_13_3_fast' in runner and 'def _strict_52_13_3()' in runner

    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    _clean()
    clean = package_clean_check(ROOT)
    checks['package_clean'] = clean.get('clean') is True and clean.get('runtime_file_count') == 0 and clean.get('secret_literal_count') == 0

    out = {
        'overall': 'passed' if all(checks.values()) else 'failed',
        'patch_version': PATCH_VERSION,
        'active_version': vj.get('version'),
        'checks': checks,
        'package_clean': clean,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    _rc = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_rc)
