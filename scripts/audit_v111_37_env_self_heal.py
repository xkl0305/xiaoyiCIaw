#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORBIDDEN = ('/repo/lib/python', '/_venv_python/', '/venv/', '/.venv/')


def run_clean(args: list[str]) -> dict:
    p = subprocess.run([sys.executable, str(ROOT/'scripts/dlx_env.py'), '--'] + args, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {'returncode': p.returncode, 'stdout': p.stdout[-4000:], 'stderr': p.stderr[-4000:]}


def import_check(mod: str) -> dict:
    code = f"import {mod}; print(getattr({mod}, '__version__', 'ok'))"
    r = run_clean([sys.executable, '-c', code])
    return {'module': mod, 'ok': r['returncode'] == 0, 'output': (r['stdout'] or r['stderr']).strip()[-500:]}


def read_json(rel: str, default):
    try:
        p = ROOT / rel
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:
        return default


def main() -> int:
    import importlib.util
    spec = importlib.util.spec_from_file_location('dlx_env_direct', ROOT/'scripts/dlx_env.py')
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    env = mod.status()
    dirty = {
        'repo_exists': (ROOT/'repo').exists(),
        '_venv_python_exists': (ROOT/'_venv_python').exists(),
        'venv_exists': (ROOT/'venv').exists(),
        'dot_venv_exists': (ROOT/'.venv').exists(),
        'pyc_count': len(list(ROOT.rglob('*.pyc'))),
        'pycache_count': len(list(ROOT.rglob('__pycache__'))),
        'pytest_cache_exists': (ROOT/'.pytest_cache').exists(),
    }
    cfg = read_json('openclaw.json', {})
    runtime = cfg.get('runtime') if isinstance(cfg.get('runtime'), dict) else {}
    cfg_ok = cfg.get('ONLINE_MODE') is False and cfg.get('OFFLINE_MODE') is True and cfg.get('NO_EXTERNAL_API') is True and runtime.get('ONLINE_MODE') is False and runtime.get('OFFLINE_MODE') is True and runtime.get('NO_EXTERNAL_API') is True
    deps = [import_check('pytest'), import_check('pydantic')]
    collect = run_clean([sys.executable, '-m', 'pytest', '--collect-only', '-q', '-p', 'no:cacheprovider'])
    report = {
        'version': 'V111.37',
        'env': env,
        'dirty': dirty,
        'config_zero_external_ok': cfg_ok,
        'dependency_imports': deps,
        'pytest_collect': {'ok': collect['returncode'] == 0, 'returncode': collect['returncode'], 'stdout_tail': collect['stdout'][-1200:], 'stderr_tail': collect['stderr'][-1200:]},
        'runner_files': {p: (ROOT/p).exists() for p in ['scripts/dlx_env.py','scripts/dlx_pytest.py','scripts/bootstrap_local_deps_v111_37.py','requirements-dev.txt']},
    }
    # collection/dependency can be warn because zero-external may not install deps; sanitizer/package cleanliness are hard gates.
    hard_ok = (not env['sanitized_has_forbidden_repo_path']) and (not dirty['repo_exists']) and cfg_ok and all(report['runner_files'].values())
    report['status'] = 'ok' if hard_ok else 'fail'
    if not all(x['ok'] for x in deps): report['dependency_status'] = 'warn_missing_dev_dependency'
    if not report['pytest_collect']['ok']: report['pytest_status'] = 'warn_collect_not_green'
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/V111_37_ENV_SELF_HEAL_AUDIT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT/'reports/V111_37_ENV_SELF_HEAL_AUDIT.txt').write_text('status: '+report['status']+'\n'+json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'ok' else 1

if __name__ == '__main__':
    raise SystemExit(main())
