#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, subprocess, sys, sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ('/repo/lib/python', '/_venv_python/', '/venv/', '/.venv/')


def _split_paths(value: str) -> list[str]:
    return [x for x in (value or '').split(os.pathsep) if x]


def local_site_paths() -> list[str]:
    paths: list[str] = []
    pyver = f'python{sys.version_info.major}.{sys.version_info.minor}'
    candidates = [
        Path.home() / '.local' / 'lib' / pyver / 'site-packages',
        ROOT / '.dlx_runtime' / 'python_deps',
        ROOT / '.dlx_runtime' / 'python_deps' / 'lib' / pyver / 'site-packages',
    ]
    try:
        userbase = Path(sysconfig.get_config_var('userbase') or Path.home()/'.local')
        candidates.append(userbase / 'lib' / pyver / 'site-packages')
    except Exception:
        pass
    seen = set()
    for p in candidates:
        s = str(p)
        if p.exists() and s not in seen:
            paths.append(s); seen.add(s)
    return paths


def sanitized_env(extra_pythonpath: list[str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    raw = {k: env.get(k) for k in ['PIP_PREFIX','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'] if env.get(k)}
    for k in ['PIP_PREFIX','PYTHONHOME','VIRTUAL_ENV']:
        env.pop(k, None)
    old_paths = _split_paths(env.get('PYTHONPATH',''))
    kept_old = [p for p in old_paths if p and str(ROOT) in p and not any(f in p for f in FORBIDDEN)]
    paths = [str(ROOT)] + kept_old + local_site_paths() + list(extra_pythonpath or [])
    dedup=[]; seen=set()
    for p in paths:
        if p and p not in seen and not any(f in p for f in FORBIDDEN):
            dedup.append(p); seen.add(p)
    env['PYTHONPATH'] = os.pathsep.join(dedup)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    env['DLX_ENV_SANITIZED'] = '1'
    env['DLX_ENV_RAW_PIP_PREFIX'] = raw.get('PIP_PREFIX','') or ''
    env['DLX_ENV_RAW_PYTHONPATH'] = raw.get('PYTHONPATH','') or ''
    return env


def status() -> dict:
    env = sanitized_env()
    raw = {k: os.environ.get(k) for k in ['PIP_PREFIX','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV']}
    clean = {k: env.get(k) for k in ['PIP_PREFIX','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','PYTHONDONTWRITEBYTECODE','DLX_ENV_SANITIZED']}
    return {
        'root': str(ROOT),
        'raw_env': raw,
        'sanitized_env': clean,
        'raw_has_forbidden_repo_path': any(any(f in (v or '') for f in FORBIDDEN) for v in raw.values()),
        'sanitized_has_forbidden_repo_path': any(any(f in (v or '') for f in FORBIDDEN) for v in clean.values()),
        'local_site_paths': local_site_paths(),
    }


def run_cmd(cmd: list[str]) -> int:
    if not cmd:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    env = sanitized_env()
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def main() -> int:
    ap = argparse.ArgumentParser(description='大龙虾 V111.37 环境自愈运行器')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('cmd', nargs=argparse.REMAINDER, help='command after --')
    args = ap.parse_args()
    if args.show:
        print(json.dumps(status(), ensure_ascii=False, indent=2)); return 0
    cmd = args.cmd
    if cmd and cmd[0] == '--': cmd = cmd[1:]
    return run_cmd(cmd)

if __name__ == '__main__':
    raise SystemExit(main())
