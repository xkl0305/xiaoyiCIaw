#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, re, shutil, subprocess, sys, tarfile, time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
BANNED_DIR_NAMES={'_venv_python','venv','.venv','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.hypothesis'}
BANNED_SUFFIX=('.pyc','.pyo')
BANNED_MEMBER_RE=re.compile(r'(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.hypothesis)(/|$)|\.(pyc|pyo)$|(^|/)(_venv_python|venv|\.venv|\.dlx_runtime)(/|$)|(^|/)\.v111_.*_backup_|README_V111_3[56]|V111_3[56]|v111_3[56]')
def remove_generated_pycache():
    for p in list(ROOT.rglob('__pycache__')):
        try: shutil.rmtree(p)
        except Exception: pass
    for p in list(ROOT.rglob('*.pyc'))+list(ROOT.rglob('*.pyo')):
        try: p.unlink()
        except Exception: pass
def read_json(rel, default):
    try:
        p=ROOT/rel; return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception: return default
def env_status():
    remove_generated_pycache(); p=ROOT/'scripts/dlx_env.py'
    if not p.exists(): return {'ok':False,'error':'scripts/dlx_env.py missing'}
    spec=importlib.util.spec_from_file_location('dlx_env_direct',p); mod=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(mod)
    s=mod.status(); s['ok']=not s.get('sanitized_has_forbidden_repo_path'); remove_generated_pycache(); return s
def scan_root(max_items=300):
    bad_dirs=[]; bad_files=[]
    remove_generated_pycache()
    for p in ROOT.rglob('*'):
        rel=str(p.relative_to(ROOT))
        if p.is_dir() and (p.name in BANNED_DIR_NAMES or re.match(r'^\.v111_.*_backup_', p.name)): bad_dirs.append(rel)
        elif p.is_file() and (p.name.endswith(BANNED_SUFFIX) or 'V111_35' in p.name or 'V111_36' in p.name or 'v111_35' in p.name or 'v111_36' in p.name): bad_files.append(rel)
        if len(bad_dirs)+len(bad_files)>=max_items: break
    return {'ok':not bad_dirs and not bad_files,'bad_dirs_count':len(bad_dirs),'bad_files_count':len(bad_files),'bad_dirs_sample':bad_dirs[:120],'bad_files_sample':bad_files[:120]}
def scan_package(pkg):
    if not pkg: return {'checked':False,'ok':None,'reason':'no package path supplied'}
    path=Path(pkg)
    if not path.exists(): return {'checked':True,'ok':False,'error':f'package not found: {pkg}'}
    bad=[]
    try:
        with tarfile.open(path,'r:gz') as tar:
            for m in tar.getnames():
                n=m[2:] if m.startswith('./') else m
                if BANNED_MEMBER_RE.search(n): bad.append(m)
                if len(bad)>=300: break
    except Exception as e: return {'checked':True,'ok':False,'error':repr(e)}
    return {'checked':True,'ok':not bad,'bad_count':len(bad),'bad_sample':bad[:160]}
def check_config():
    cfg=read_json('openclaw.json',{}); runtime=cfg.get('runtime') if isinstance(cfg.get('runtime'),dict) else {}; dep=cfg.get('dependencyInstallPolicy') if isinstance(cfg.get('dependencyInstallPolicy'),dict) else {}; envp=cfg.get('environmentPolicy') if isinstance(cfg.get('environmentPolicy'),dict) else {}
    product_ok=(cfg.get('ONLINE_MODE') is True and cfg.get('OFFLINE_MODE') is False and cfg.get('CONNECTED_RUNTIME_ALWAYS_ON') is True and runtime.get('ONLINE_MODE') is True and runtime.get('OFFLINE_MODE') is False and runtime.get('CONNECTED_RUNTIME_ALWAYS_ON') is True)
    safety_ok=(cfg.get('NO_REAL_PAYMENT') is True and cfg.get('NO_REAL_SEND') is True and cfg.get('NO_REAL_DEVICE') is True and runtime.get('NO_REAL_PAYMENT') is True and runtime.get('NO_REAL_SEND') is True and runtime.get('NO_REAL_DEVICE') is True)
    dep_ok=(dep.get('defaultInstallMode')=='offline_wheelhouse_only' and dep.get('allowNetworkInstallOnlyWithFlag')=='--allow-network')
    env_ok=(envp.get('sanitizeInjectedPythonEnv') is True and envp.get('doNotBundleVirtualEnvironments') is True)
    return {'ok':product_ok and safety_ok and dep_ok and env_ok,'product_online_ok':product_ok,'real_side_effect_guard_ok':safety_ok,'dependency_install_policy_ok':dep_ok,'environment_policy_ok':env_ok,'top_level':{k:cfg.get(k) for k in ['ONLINE_MODE','OFFLINE_MODE','CONNECTED_RUNTIME_ALWAYS_ON','ALLOW_NETWORK','NO_EXTERNAL_API','DISABLE_LLM_API','NO_REAL_PAYMENT','NO_REAL_SEND','NO_REAL_DEVICE']},'runtime':{k:runtime.get(k) for k in ['ONLINE_MODE','OFFLINE_MODE','CONNECTED_RUNTIME_ALWAYS_ON','ALLOW_NETWORK','NO_EXTERNAL_API','DISABLE_LLM_API','NO_REAL_PAYMENT','NO_REAL_SEND','NO_REAL_DEVICE']}}
def run_collect(timeout_s):
    if timeout_s<=0: return {'checked':False,'ok':None,'reason':'pytest collect skipped'}
    cmd=[sys.executable,'-S',str(ROOT/'scripts/dlx_pytest_collect_guard.py'),'--timeout',str(timeout_s)]
    try:
        p=subprocess.run(cmd,cwd=str(ROOT),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout_s+5)
        return {'checked':True,'ok':p.returncode==0,'returncode':p.returncode,'stdout_tail':p.stdout[-2000:],'stderr_tail':p.stderr[-2000:]}
    except subprocess.TimeoutExpired as e: return {'checked':True,'ok':False,'timeout':True,'timeout_seconds':timeout_s}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--package'); ap.add_argument('--pytest-timeout',type=int,default=0); ap.add_argument('--require-pytest-green',action='store_true'); args=ap.parse_args()
    remove_generated_pycache()
    report={'version':'V111.38','generated_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'env_self_heal':env_status(),'root_cleanliness':scan_root(),'package_cleanliness':scan_package(args.package),'config_policy':check_config(),'pytest_collect':run_collect(args.pytest_timeout),'required_files':{p:(ROOT/p).exists() for p in ['scripts/dlx_env.py','scripts/dlx_pytest.py','scripts/bootstrap_local_deps_v111_37.py','scripts/package_clean_source_v111_38.sh','scripts/audit_v111_38_online_clean_release.py','requirements-dev.txt','openclaw.json']}}
    hard=(report['env_self_heal'].get('ok') is True and report['root_cleanliness'].get('ok') is True and report['config_policy'].get('ok') is True and all(report['required_files'].values()))
    if report['package_cleanliness'].get('checked'): hard=hard and report['package_cleanliness'].get('ok') is True
    if args.require_pytest_green: hard=hard and report['pytest_collect'].get('ok') is True
    report['status']='ok' if hard else 'fail'; (ROOT/'reports').mkdir(exist_ok=True); (ROOT/'reports/V111_38_ONLINE_CLEAN_RELEASE_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); (ROOT/'reports/V111_38_ONLINE_CLEAN_RELEASE_AUDIT.txt').write_text('status: '+report['status']+'\n'+json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if hard else 1
if __name__=='__main__': raise SystemExit(main())
