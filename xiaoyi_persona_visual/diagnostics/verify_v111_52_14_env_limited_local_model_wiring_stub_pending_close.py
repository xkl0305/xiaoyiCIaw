#!/usr/bin/env python3
"""
V111.52.14_ENV_LIMITED_LOCAL_MODEL_WIRING_AND_STUB_PENDING_CLOSE
Verifier: environment-limited model wiring and stub ready check.

Checks:
  1. reports/current/local_model_environment_diagnosis.json exists
  2. environment_supports_real_model_inference == false
  3. real_ready_capabilities == []
  4. real_model_ready == false (from local_stack_status)
  5. stub_ready_only_count >= 4
  6. environment_blocked_count >= 4
  7. local_llm is NOT real_model_ready
  8. local_vlm is NOT real_model_ready
  9. local_image_provider is NOT real_model_ready
  10. verify_local_runtime_health.py writes to workspace/reports/current/
  11. package_clean == true
  12. runtime_file_count == 0
  13. secret_literal_count == 0
No pip install, model download, source compile, or real model server start allowed.
"""
from __future__ import annotations

import json
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.52.14_ENV_LIMITED_LOCAL_MODEL_WIRING_AND_STUB_PENDING_CLOSE'

sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _read_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def _run_health_check() -> dict:
    """Run verify_local_runtime_health.py and capture its JSON output."""
    result = subprocess.run(
        [sys.executable, '-S', 'verify_local_runtime_health.py'],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        env={**os.environ, 'PYTHONPATH': '.', 'PYTHONDONTWRITEBYTECODE': '1'},
    )
    # Parse the JSON output from the last line containing [verify] output:
    report = None
    for line in result.stdout.splitlines():
        if line.startswith('[verify] output:'):
            try:
                report = json.loads(line[len('[verify] output:'):].strip())
            except json.JSONDecodeError:
                pass
    if report is None:
        # Fallback: read the report file directly
        report_path = ROOT / 'reports' / 'current' / 'local_runtime_health_report.json'
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding='utf-8'))
    return report or {}


def main() -> int:
    print('[52.14] verify_v111_52_14_env_limited_local_model_wiring_stub_pending_close', flush=True)
    print('[52.14] root:', ROOT, flush=True)

    # ── step: read diagnosis ──
    diag_path = ROOT / 'reports' / 'current' / 'local_model_environment_diagnosis.json'
    diag = _read_json('reports/current/local_model_environment_diagnosis.json') if diag_path.exists() else {}

    # ── step: run health check ──
    health = _run_health_check()

    # ── step: package clean ──
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    pkg_clean = package_clean_check(ROOT)

    # ── step: runtime file count & secret literal count ──
    runtime_file_count = 0
    secret_literal_count = 0
    for root_dir, _dirs, files in os.walk(ROOT):
        if '.openclaw/hook_state' in root_dir or '__pycache__' in root_dir:
            continue
        for f in files:
            # Check for .secret files (literal secret files, not .env which is config)
            if f.endswith('.secret'):
                secret_literal_count += 1
            # Count runtime artifact files
            if f.endswith('.jsonl') or f.endswith('.sqlite') or f.endswith('.db'):
                runtime_file_count += 1

    # ── checks ──
    checks: dict[str, bool | str] = {}

    checks['diagnosis_file_exists'] = diag_path.exists()

    checks['environment_supports_real_inference_false'] = (
        diag.get('environment_supports_real_model_inference') is False
    )

    checks['real_ready_capabilities_empty'] = (
        isinstance(diag.get('real_ready_capabilities'), list)
        and len(diag.get('real_ready_capabilities', [])) == 0
    )

    checks['real_model_ready_false'] = (
        health.get('real_model_ready') is False
    )

    stub_count = health.get('stub_ready_only_count', 0)
    checks['stub_ready_only_count_ge_4'] = stub_count >= 4

    blocked_count = health.get('environment_blocked_count', 0)
    checks['environment_blocked_count_ge_4'] = blocked_count >= 4

    # Per-capability checks
    kinds = health.get('ready_kinds', {})
    checks['local_llm_not_real_ready'] = kinds.get('local_llm') != 'real_model_ready'
    checks['local_vlm_not_real_ready'] = kinds.get('local_vlm') != 'real_model_ready'
    checks['local_image_provider_not_real_ready'] = kinds.get('local_image_provider') != 'real_model_ready'

    # Health report location
    health_report_path = ROOT / 'reports' / 'current' / 'local_runtime_health_report.json'
    checks['health_report_in_workspace'] = health_report_path.exists()

    checks['package_clean'] = pkg_clean.get('clean') is True

    checks['runtime_file_count_0'] = runtime_file_count == 0

    checks['secret_literal_count_0'] = secret_literal_count == 0

    # ── summary ──
    print('', flush=True)
    print('[52.14] === checks ===', flush=True)
    all_ok = True
    for name, ok in checks.items():
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            all_ok = False
            if isinstance(ok, str):
                status = f'FAIL ({ok})'
        print(f'  {status}: {name}', flush=True)

    result = {
        'version': VERSION,
        'root': str(ROOT),
        'checks': {k: str(v) if not isinstance(v, bool) else v for k, v in checks.items()},
        'stub_ready_only_count': stub_count,
        'environment_blocked_count': blocked_count,
        'real_model_ready': health.get('real_model_ready', None),
        'diagnosis_summary': {
            'environment_supports_real_model_inference': diag.get('environment_supports_real_model_inference'),
            'real_ready_capabilities': diag.get('real_ready_capabilities', []),
        },
        'package_clean': pkg_clean.get('clean') is True,
        'overall': 'passed' if all_ok else 'failed',
    }
    print('', flush=True)
    print(f'[52.14] overall: {result["overall"]}', flush=True)
    print(f'[52.14] output: {json.dumps(result)}', flush=True)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
