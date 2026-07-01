#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description='V111.37 本地依赖引导。默认只允许离线 wheelhouse。')
    ap.add_argument('--wheelhouse', default='vendor/wheels')
    ap.add_argument('--allow-network', action='store_true', help='显式允许联网 pip install；默认不允许。')
    ap.add_argument('--target', default='.dlx_runtime/python_deps')
    args = ap.parse_args()
    req = ROOT / 'requirements-dev.txt'
    target = ROOT / args.target
    target.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, str(ROOT/'scripts/dlx_env.py'), '--', sys.executable, '-m', 'pip', 'install', '--upgrade', '--target', str(target), '-r', str(req)]
    if args.allow_network:
        print('WARNING: --allow-network 已显式开启，可能联网消费。')
        return subprocess.call(base, cwd=str(ROOT))
    wheelhouse = ROOT / args.wheelhouse
    if not wheelhouse.exists():
        print(f'离线 wheelhouse 不存在：{wheelhouse}')
        print('默认不联网。请把 pytest/pydantic 等 whl 放入 vendor/wheels/，或显式加 --allow-network。')
        return 2
    cmd = base + ['--no-index', '--find-links', str(wheelhouse)]
    return subprocess.call(cmd, cwd=str(ROOT))

if __name__ == '__main__':
    raise SystemExit(main())
