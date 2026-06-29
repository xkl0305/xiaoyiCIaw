#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRS = ['repo','_venv_python','venv','.venv','.pytest_cache','.mypy_cache','.ruff_cache','.hypothesis']
OBSOLETE_FILES = [
 'README_V111_35.txt','README_V111_36.txt',
 '大龙虾_V111_35_零外接主架构收口命令.txt','大龙虾_V111_36_本地优先零外接加固命令.txt',
 'scripts/apply_v111_36_local_first_hardening.py','scripts/package_clean_source_v111_35.sh',
 'scripts/audit_v111_35_zero_external.py','scripts/apply_v111_35_zero_external_overlay.py',
 'scripts/package_clean_source_v111_36.sh','scripts/audit_v111_36_local_first_hardening.py'
]
OBSOLETE_GLOBS = ['.v111_*_backup_*','reports/V111_35*','reports/V111_36*','openclaw_v111_35*','openclaw_v111_36*','openclaw_zero_external_overlay.json']
def read_json(rel, default):
    p=ROOT/rel
    try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception: return default
def write_json(rel, data):
    p=ROOT/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); print('WRITE', rel)
def rm(p, removed):
    if not p.exists() and not p.is_symlink(): return
    rel=str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p)
    if p.is_dir() and not p.is_symlink(): shutil.rmtree(p, ignore_errors=True)
    else:
        try: p.unlink()
        except FileNotFoundError: pass
    removed.append(rel)
def clean():
    removed=[]
    for rel in RUNTIME_DIRS: rm(ROOT/rel, removed)
    for pat in ['*.pyc','*.pyo','*.jsonl']:
        for p in list(ROOT.rglob(pat)): rm(p, removed)
    for p in list(ROOT.rglob('__pycache__')): rm(p, removed)
    for rel in OBSOLETE_FILES: rm(ROOT/rel, removed)
    for gp in OBSOLETE_GLOBS:
        for p in list(ROOT.glob(gp)): rm(p, removed)
    rm(ROOT/'.openclaw'/'hook_state', removed)
    return {'removed_count':len(removed),'removed_sample':removed[:200]}
def patch_config():
    cfg=read_json('openclaw.json', {})
    if not isinstance(cfg, dict): cfg={}
    runtime=cfg.setdefault('runtime', {})
    for t in (cfg, runtime):
        t['ONLINE_MODE']=True; t['OFFLINE_MODE']=False; t['CONNECTED_RUNTIME_ALWAYS_ON']=True; t['ALLOW_NETWORK']=True
        t['NO_EXTERNAL_API']=False; t['DISABLE_LLM_API']=False
        t['NO_REAL_PAYMENT']=True; t['NO_REAL_SEND']=True; t['NO_REAL_DEVICE']=True
    cfg['dependencyInstallPolicy']={'version':'V111.38','defaultInstallMode':'offline_wheelhouse_only','allowNetworkInstallOnlyWithFlag':'--allow-network','wheelhouse':'vendor/wheels','target':'.dlx_runtime/python_deps'}
    cfg['environmentPolicy']={'version':'V111.38','sanitizeInjectedPythonEnv':True,'doNotBundleVirtualEnvironments':True,'sourcePackageMustExclude':['repo/','_venv_python/','venv/','.venv/','.dlx_runtime/','__pycache__/','*.pyc','*.pyo','.pytest_cache/','*.jsonl','.v111_*_backup_*/','*V111_35*','*V111_36*','*v111_35*','*v111_36*'],'forbiddenPythonPathFragments':['/repo/lib/python','/_venv_python/','/venv/','/.venv/'],'runtimeDependencyMode':'explicit_local_runtime_or_user_site_not_source_bundle','defaultInstallMode':'offline_wheelhouse_only'}
    cfg['modePolicy']={'version':'V111.38','productRuntimeMode':'always_online_connected','testAndPackageMode':'no_external_side_effects_by_default','reason':'产品运行态保持在线连接；测试、打包、依赖安装默认不联网，二者分离，避免 OFFLINE_MODE 误伤主运行态。'}
    write_json('openclaw.json', cfg)
def patch_gitignore():
    gi=ROOT/'.gitignore'; lines=gi.read_text(encoding='utf-8',errors='ignore').splitlines() if gi.exists() else []
    add=['repo/','_venv_python/','venv/','.venv/','.dlx_runtime/','__pycache__/','*.pyc','*.pyo','.pytest_cache/','*.jsonl','.openclaw/hook_state/','generated-images/','.v111_*_backup_*','reports/V111_35*','reports/V111_36*','README_V111_35.txt','README_V111_36.txt','*V111_35*','*V111_36*','*v111_35*','*v111_36*']
    seen=set(lines)
    for x in add:
        if x not in seen: lines.append(x); seen.add(x)
    gi.write_text('\n'.join(lines).rstrip()+'\n', encoding='utf-8'); print('WRITE .gitignore')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--yes', action='store_true'); args=ap.parse_args()
    if not args.yes: print('需要确认执行：PYTHONNOUSERSITE=1 python3 -S scripts/apply_v111_38_online_runtime_and_clean_release.py --yes'); return 2
    patch_config(); patch_gitignore(); c=clean(); report={'status':'ok','version':'V111.38','applied_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'runtime_online':True,'dependency_install_default_offline':True,'cleanup':c}
    write_json('reports/V111_38_APPLY_RESULT.json', report); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
