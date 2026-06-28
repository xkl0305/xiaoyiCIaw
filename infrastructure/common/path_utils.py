from __future__ import annotations
from pathlib import Path
import os
def get_workspace_root(anchor=None) -> Path:
    env=os.environ.get('OPENCLAW_WORKSPACE') or os.environ.get('WORKSPACE_ROOT'); candidates=[]
    if anchor is not None:
        try:
            p=Path(anchor).resolve(); p=p.parent if p.is_file() else p; candidates += [p,*p.parents]
        except Exception: pass
    if env: candidates.append(Path(env).expanduser().resolve())
    cwd=Path.cwd().resolve(); candidates += [cwd,*cwd.parents]
    for x in candidates:
        try:
            if (x/'openclaw.json').exists() or ((x/'core').exists() and (x/'infrastructure').exists()): return x
        except Exception: pass
    return cwd
