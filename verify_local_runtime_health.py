#!/usr/bin/env python3
"""
V111.52.14_ENV_LIMITED_LOCAL_MODEL_WIRING_AND_STUB_PENDING_CLOSE

Standalone health check for local model runtime.
Distinguishes between:
  - wiring_ready: capability is declared/enabled in config
  - stub_ready_only: command stub (python -c "print(...)") or stub endpoint provides mock responses
  - real_model_ready: real model path, real inference server, or non-stub command
  - environment_blocked: enabled but environment lacks resources for real inference
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent

from core.personal_os_enterprise.local_model_stack_binding import local_stack_status, RECOMMENDED_STACK
from core.personal_os_enterprise.local_runtime_probe import probe_all_capabilities


def main() -> int:
    print('[verify] V111.52.14 local runtime health check', flush=True)
    print('[verify] root:', ROOT, flush=True)

    # ---- full stack status ----
    status = local_stack_status()
    overall_ready = len(status['ready']) == len(RECOMMENDED_STACK)
    print('[verify] recommended_stack_count:', len(RECOMMENDED_STACK), flush=True)
    print('[verify] wiring_present:', status.get('wiring_present', []), flush=True)
    print('[verify] ready:', status['ready'], flush=True)
    print('[verify] missing:', status['missing'], flush=True)
    print('[verify] real_model_ready:', status['real_model_ready'], flush=True)
    print('[verify] environment_blocked:', status['environment_blocked'], flush=True)
    print('[verify] environment_blocked_reason:', status['environment_blocked_reason'], flush=True)

    # ---- per-capability ready_kind ----
    all_probes = probe_all_capabilities()
    print('', flush=True)
    print('[verify] === per-capability detail ===', flush=True)
    for cap in RECOMMENDED_STACK:
        p = all_probes['probes'].get(cap, {})
        rk = p.get('ready_kind', 'unknown')
        r = p.get('ready', False)
        reason = p.get('reason', '?')
        checks = p.get('checks', {})
        print('  {}: ready={} kind={} reason={}'.format(cap, r, rk, reason), flush=True)
        for ck, cv in checks.items():
            print('    - {}: {}'.format(ck, cv), flush=True)

    # ---- summary ----
    kinds = all_probes.get('ready_kinds', {})
    wiring_cnt = sum(1 for k in kinds.values() if k != 'not_configured' and k != 'disabled')
    stub_cnt = sum(1 for k in kinds.values() if k == 'stub_ready_only')
    real_cnt = sum(1 for k in kinds.values() if k == 'real_model_ready')
    blocked_cnt = sum(1 for k in kinds.values() if k == 'environment_blocked')

    print('', flush=True)
    print('[verify] === summary ===', flush=True)
    print('  wiring_ready_count:       {}'.format(wiring_cnt), flush=True)
    print('  stub_ready_only_count:    {}'.format(stub_cnt), flush=True)
    print('  real_model_ready_count:   {}'.format(real_cnt), flush=True)
    print('  environment_blocked_count:{}'.format(blocked_cnt), flush=True)
    print('  real_model_ready:         {}'.format(all_probes.get('real_model_ready', False)), flush=True)
    print('  overall_probe_status:     {}'.format(all_probes.get('overall', '?')), flush=True)

    # ---- machine-readable output ----
    report = {
        'version': status['version'],
        'recommended_stack_count': len(RECOMMENDED_STACK),
        'wiring_present': status.get('wiring_present', []),
        'ready': status['ready'],
        'missing': status['missing'],
        'real_model_ready': all_probes.get('real_model_ready', False),
        'environment_blocked': status.get('environment_blocked', False),
        'ready_kinds': kinds,
        'wiring_ready_count': wiring_cnt,
        'stub_ready_only_count': stub_cnt,
        'real_model_ready_count': real_cnt,
        'environment_blocked_count': blocked_cnt,
        'overall_probe_status': all_probes.get('overall', '?'),
        'environment_blocked_reason': status.get('environment_blocked_reason', ''),
        'overall': 'passed' if overall_ready else 'partial',
        'real_model_ready_overall': False,
    }
    report_path = str(ROOT / 'reports' / 'current' / 'local_runtime_health_report.json')
    os.makedirs(str(ROOT / 'reports' / 'current'), exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print('', flush=True)
    print('[verify] report written:', report_path, flush=True)
    print('[verify] output:', json.dumps(report), flush=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
