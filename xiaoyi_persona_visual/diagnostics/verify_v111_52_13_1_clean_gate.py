#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EXPECTED={'V111.52.13.1_ENTERPRISE_REPORT_REMAINING_CLEAN_GATE_FINAL','V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'}

def main():
    env=os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONPATH']='.'
    cleaner=ROOT/'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        subprocess.run([sys.executable,'-S',str(cleaner)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    version=json.loads((ROOT/'xiaoyi_persona_visual/version.json').read_text(encoding='utf-8')).get('version')
    base=subprocess.run([sys.executable,'-S',str(ROOT/'xiaoyi_persona_visual/diagnostics/verify_v111_52_13_report_remaining_close.py')], cwd=ROOT, env=env, text=True, capture_output=True)
    try:
        payload=json.loads(base.stdout)
    except Exception:
        payload={'overall':'failed','raw_stdout':base.stdout,'stderr':base.stderr}
    checks={
        'version_52_13_1_or_later': version in EXPECTED,
        'base_52_13_verify_passed': base.returncode==0 and payload.get('overall')=='passed',
        'direct_verify_self_clean_gate': (payload.get('checks') or {}).get('package_clean') is True,
    }
    out={'overall':'passed' if all(checks.values()) else 'failed','version':version,'checks':checks,'base_verify':payload}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1
if __name__=='__main__':
    raise SystemExit(main())
