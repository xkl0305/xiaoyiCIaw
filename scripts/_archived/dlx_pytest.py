#!/usr/bin/env python3
from __future__ import annotations
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    cmd = [sys.executable, str(ROOT/'scripts/dlx_env.py'), '--', sys.executable, '-m', 'pytest'] + sys.argv[1:]
    return subprocess.call(cmd, cwd=str(ROOT))

if __name__ == '__main__':
    raise SystemExit(main())
