#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH = 'V111.52.13.3.1.2_ENTERPRISE_ACCEPTANCE_SUBPROCESS_FD_EXIT_CLOSE_PATCH'
ACTIVE = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'


def _read_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main() -> int:
    runner_path = ROOT / 'scripts/acceptance/enterprise_acceptance_runner.py'
    runner = runner_path.read_text(encoding='utf-8')
    version = _read_json('xiaoyi_persona_visual/version.json')

    checks = {
        'active_version_preserved': version.get('version') == ACTIVE,
        'subpatch_feature_recorded': version.get('features', {}).get('v111_52_13_3_1_2_patch_applied') == PATCH,
        'runner_uses_temp_files_for_child_output': 'NamedTemporaryFile' in runner and 'stdout=out_f' in runner and 'stderr=err_f' in runner,
        'runner_does_not_inherit_child_stdio': 'stdout=None if show else subprocess.PIPE' not in runner and 'stderr=None if show else subprocess.PIPE' not in runner,
        'runner_closes_child_fds': 'close_fds=True' in runner,
        'runner_poll_loop_timeout': 'proc.poll()' in runner and 'os.killpg(proc.pid, signal.SIGKILL)' in runner,
        'runner_replays_pytest_output_from_parent': 'if show and stdout' in runner and 'sys.stdout.write(stdout)' in runner,
        'runner_keeps_os_exit': 'os._exit(main())' in runner,
    }

    # Verify the final clean command exits and does not leave runtime residue.
    clean = subprocess.run(
        [sys.executable, '-S', 'scripts/clean_runtime_artifacts.py'],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )
    checks['clean_runtime_exits'] = clean.returncode == 0

    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    package_clean = package_clean_check(ROOT)
    checks['package_clean'] = package_clean.get('clean') is True

    result = {
        'active_version': version.get('version'),
        'patch_version': PATCH,
        'overall': 'passed' if all(checks.values()) else 'failed',
        'checks': checks,
        'package_clean': package_clean,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result['overall'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
