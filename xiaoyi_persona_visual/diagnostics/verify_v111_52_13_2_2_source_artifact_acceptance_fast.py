#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ACTIVE = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'
PATCH_VERSION = 'V111.52.13.2.2_SOURCE_ARTIFACT_AND_ACCEPTANCE_FAST_CLOSE_PATCH'


def j(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def clean_runtime_quiet() -> None:
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = '.'
    subprocess.run(
        [sys.executable, '-S', str(cleaner)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def root_matches(pattern: str) -> list[str]:
    return sorted(p.name for p in ROOT.iterdir() if p.is_file() and fnmatch.fnmatch(p.name, pattern))


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    clean_runtime_quiet()

    from infrastructure.packaging.source_runtime_boundary import is_runtime_path, package_clean_check

    active_version = j('xiaoyi_persona_visual/version.json').get('version')
    run_all = ROOT / 'scripts/acceptance/run_all_enterprise_acceptance.sh'
    run_all_text = run_all.read_text(encoding='utf-8') if run_all.exists() else ''
    direct_52_12_1 = 'verify_v111_52_12_1_full_local_stack_runtime_clean_close.py' in run_all_text

    overlay_left = root_matches('overlay*.zip')
    generated_left = root_matches('generated*.jpg')
    clean = package_clean_check(ROOT)

    checks = {
        'active_version_unchanged': active_version == EXPECTED_ACTIVE,
        'cleaner_flags_root_overlay_zip': is_runtime_path('overlay.zip') is True,
        'cleaner_flags_root_generated_jpg': is_runtime_path('generated_result.jpg') is True,
        'root_overlay_zip_residue_zero': len(overlay_left) == 0,
        'root_generated_jpg_residue_zero': len(generated_left) == 0,
        'package_clean_true': clean.get('clean') is True,
        'runtime_file_count_zero': clean.get('runtime_file_count') == 0,
        'secret_literal_count_zero': clean.get('secret_literal_count') == 0,
        'run_all_no_duplicate_direct_52_12_1': direct_52_12_1 is False,
        'run_all_keeps_forward_compat_52_13_2_1': 'verify_v111_52_13_2_1_forward_compat_clean_gate.py' in run_all_text,
    }

    out = {
        'overall': 'passed' if all(checks.values()) else 'failed',
        'patch_version': PATCH_VERSION,
        'active_version': active_version,
        'checks': checks,
        'root_overlay_zip_residue': overlay_left,
        'root_generated_jpg_residue': generated_left,
        'package_clean': clean,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
