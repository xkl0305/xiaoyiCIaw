#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ACTIVE = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'
PATCH_VERSION = 'V111.52.13.2.1_FORWARD_COMPAT_CLEAN_GATE_PATCH'

def j(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def clean_runtime_quiet() -> None:
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        env = os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'; env['PYTHONPATH']='.'
        subprocess.run([sys.executable, '-S', str(cleaner)], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def main():
    clean_runtime_quiet()
    checks={}
    active = j('xiaoyi_persona_visual/version.json').get('version')
    checks['active_version_stays_52_13_2'] = active == EXPECTED_ACTIVE
    checks['patched_52_12_verifier_present'] = 'clean_runtime_quiet' in (ROOT/'xiaoyi_persona_visual/diagnostics/verify_v111_52_12_full_local_stack_embodied_ops.py').read_text(encoding='utf-8')
    checks['patched_52_12_1_verifier_present'] = 'clean_runtime_quiet' in (ROOT/'xiaoyi_persona_visual/diagnostics/verify_v111_52_12_1_full_local_stack_runtime_clean_close.py').read_text(encoding='utf-8')
    env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'; env['PYTHONPATH']='.'
    r=subprocess.run([sys.executable,'-S','xiaoyi_persona_visual/diagnostics/verify_v111_52_12_1_full_local_stack_runtime_clean_close.py'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=240)
    checks['verify_52_12_1_forward_compat_clean'] = r.returncode == 0
    clean_runtime_quiet()
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean=package_clean_check(ROOT)
    checks['package_clean_after_forward_compat']=clean.get('clean') is True
    out={'overall':'passed' if all(checks.values()) else 'failed','patch_version':PATCH_VERSION,'active_version':active,'checks':checks,'package_clean':clean,'verify_52_12_1_stdout':r.stdout[-1600:],'verify_52_12_1_stderr':r.stderr[-1600:]}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if all(checks.values()) else 1
if __name__=='__main__':
    raise SystemExit(main())
