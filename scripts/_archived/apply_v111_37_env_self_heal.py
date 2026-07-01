#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def write(rel: str, text: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    print('WRITE', rel)

def read_json(rel: str, default):
    p = ROOT / rel
    try:
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:
        return default

def write_json(rel: str, data) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('WRITE', rel)

def clean_runtime() -> dict:
    removed = []
    for rel in ['repo','_venv_python','venv','.venv','.pytest_cache']:
        p = ROOT / rel
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            removed.append(rel)
    for pat in ['*.pyc','*.pyo']:
        for p in ROOT.rglob(pat):
            try: p.unlink(); removed.append(str(p.relative_to(ROOT)))
            except Exception: pass
    for p in list(ROOT.rglob('__pycache__')):
        try: shutil.rmtree(p); removed.append(str(p.relative_to(ROOT)))
        except Exception: pass
    for p in list(ROOT.rglob('*.jsonl')):
        try: p.unlink(); removed.append(str(p.relative_to(ROOT)))
        except Exception: pass
    hs = ROOT / '.openclaw' / 'hook_state'
    if hs.exists():
        shutil.rmtree(hs, ignore_errors=True); removed.append('.openclaw/hook_state')
    return {'removed_count': len(removed), 'removed_sample': removed[:80]}

def patch_config() -> None:
    cfg = read_json('openclaw.json', {})
    if not isinstance(cfg, dict): cfg = {}
    runtime = cfg.setdefault('runtime', {})
    for target in [cfg, runtime]:
        target['ONLINE_MODE'] = False
        target['OFFLINE_MODE'] = True
        target['NO_EXTERNAL_API'] = True
        target['CONNECTED_RUNTIME_ALWAYS_ON'] = False
        target['ALLOW_NETWORK'] = False
        target['DISABLE_LLM_API'] = target.get('DISABLE_LLM_API', True)
    cfg['environmentPolicy'] = {
        'version': 'V111.37',
        'sanitizeInjectedPythonEnv': True,
        'doNotBundleVirtualEnvironments': True,
        'sourcePackageMustExclude': ['repo/','_venv_python/','venv/','.venv/','__pycache__/','*.pyc','.pytest_cache/','*.jsonl'],
        'forbiddenPythonPathFragments': ['/repo/lib/python', '/_venv_python/', '/venv/', '/.venv/'],
        'runtimeDependencyMode': 'explicit_local_runtime_or_user_site_not_source_bundle',
        'defaultInstallMode': 'offline_wheelhouse_only',
        'allowNetworkInstallOnlyWithFlag': '--allow-network'
    }
    write_json('openclaw.json', cfg)

def patch_gitignore() -> None:
    lines = []
    gi = ROOT / '.gitignore'
    if gi.exists(): lines = gi.read_text(encoding='utf-8', errors='ignore').splitlines()
    add = ['repo/','_venv_python/','venv/','.venv/','.dlx_runtime/','__pycache__/','*.pyc','.pytest_cache/','*.jsonl','.openclaw/hook_state/','generated-images/']
    s = set(lines)
    for a in add:
        if a not in s: lines.append(a)
    gi.write_text('\n'.join(lines).rstrip()+'\n', encoding='utf-8')
    print('WRITE .gitignore')

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--yes', action='store_true')
    args = ap.parse_args()
    if not args.yes:
        print('需要确认执行：python3 scripts/apply_v111_37_env_self_heal.py --yes')
        return 2
    patch_config()
    patch_gitignore()
    result = clean_runtime()
    # scripts are already overlaid by zip, just record apply result
    report = {'status':'ok','version':'V111.37','applied_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'runtime_clean':result}
    write_json('reports/V111_37_APPLY_RESULT.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
