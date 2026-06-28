#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, os
from pathlib import Path
VERSION='V111.52.12.1_FULL_LOCAL_STACK_RUNTIME_CLEAN_CLOSE_FINAL'
ROOT=Path(__file__).resolve().parents[2]

def j(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

def clean_runtime_quiet() -> None:
    cleaner=ROOT/'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'; env['PYTHONPATH']='.'
        subprocess.run([sys.executable,'-S',str(cleaner)], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def main():
    clean_runtime_quiet()
    checks={}
    checks['version_52_12_1']=(j('xiaoyi_persona_visual/version.json').get('version')==VERSION or str(j('xiaoyi_persona_visual/version.json').get('version','')).startswith('V111.52.13')) and (j('release_manifest.json').get('version')==VERSION or str(j('release_manifest.json').get('version','')).startswith('V111.52.13'))
    oc=j('openclaw.json')
    checks['strict_local_runtime']= all([
        oc.get('ALLOW_NETWORK') is False, oc.get('NO_EXTERNAL_API') is True, oc.get('OFFLINE_MODE') is True, oc.get('ONLINE_MODE') is False,
        oc.get('NO_REAL_PAYMENT') is True, oc.get('NO_REAL_SEND') is True, oc.get('runtime',{}).get('ALLOW_NETWORK') is False,
        oc.get('runtime',{}).get('ONLINE_MODE') is False,
    ])
    checks['clean_script_present']=(ROOT/'scripts/clean_runtime_artifacts.py').exists()
    checks['old_apply_compat_present']=(ROOT/'scripts/apply_v111_52_12_full_local_stack_embodied_ops.py').exists()
    env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'; env['PYTHONPATH']='.'
    r=subprocess.run([sys.executable,'-S','xiaoyi_persona_visual/diagnostics/verify_v111_52_12_full_local_stack_embodied_ops.py'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
    checks['verify_52_12_forward_compatible']= r.returncode==0
    clean_runtime_quiet()
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean=package_clean_check(ROOT)
    checks['package_clean']=clean.get('clean') is True
    checks['no_overlay_payload_residue']= not any(ROOT.glob('overlay_payload*')) and not any(ROOT.glob('_overlay*'))
    out={'overall':'passed' if all(checks.values()) else 'failed','version':VERSION,'checks':checks,'package_clean':clean,'verify_52_12_stdout':r.stdout[-1200:], 'verify_52_12_stderr':r.stderr[-1200:]}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    clean_runtime_quiet()
    return 0 if all(checks.values()) else 1
if __name__=='__main__':
    raise SystemExit(main())
