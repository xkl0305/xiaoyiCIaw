#!/usr/bin/env python3
from __future__ import annotations
import fnmatch
import json
import os
import shutil
from pathlib import Path

RUNTIME_DIR_EXACT = {
    '.openclaw/state', '.openclaw/hook_state', '.persona_visual/generated',
    '.v98_state', '.v107_state', '.lazy_state', '.context_state',
    '.pytest_cache', 'logs', 'generated-images', '__pycache__', '.acceptance_runtime_probe',
}
RUNTIME_DIR_GLOBS = ('overlay_payload*', '_overlay*')
# Root-only source artifact residues from prior overlay/test-image handoffs.
# Do not remove nested generated images that are valid source/test assets.
RUNTIME_ROOT_FILE_GLOBS = ('overlay*.zip', 'generated*.jpg')
RUNTIME_FILE_EXACT = {
    '.persona_visual/visual_request_ledger.jsonl',
    '.persona_visual/runtime_wardrobe_state.json',
    '.DS_Store',
}
RUNTIME_SUFFIXES = (
    '.pyc', '.pyo', '.jsonl', '.log', '.sqlite', '.sqlite3', '.db',
    '.sqlite-wal', '.sqlite-shm', '.sqlite3-wal', '.sqlite3-shm',
    '.db-wal', '.db-shm', '.tmp', '.cache',
)

def find_root() -> Path:
    cur = Path.cwd().resolve()
    here = Path(__file__).resolve()
    for p in [cur, *cur.parents, here.parent, *here.parents]:
        if (p / 'openclaw.json').exists() and (p / 'xiaoyi_persona_visual').exists():
            return p
    return cur

def norm_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()

def is_runtime_dir(rel: str, name: str) -> bool:
    if rel in RUNTIME_DIR_EXACT or name == '__pycache__':
        return True
    return any(fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat) for pat in RUNTIME_DIR_GLOBS)

def is_runtime_file(rel: str, name: str) -> bool:
    if '/' not in rel and any(fnmatch.fnmatch(name, pat) for pat in RUNTIME_ROOT_FILE_GLOBS):
        return True
    if rel in RUNTIME_FILE_EXACT or name in RUNTIME_FILE_EXACT:
        return True
    return name == '.DS_Store' or rel.endswith(RUNTIME_SUFFIXES)

def remove_dir(p: Path) -> bool:
    try:
        shutil.rmtree(p, ignore_errors=True)
        return True
    except Exception:
        return False

def remove_file(p: Path) -> bool:
    try:
        p.unlink(missing_ok=True)
        return True
    except Exception:
        return False

def clean_runtime(root: Path | None = None) -> dict:
    root = Path(root) if root else find_root()
    removed = []
    if not root.exists():
        return {'overall':'cleaned','root':str(root),'removed_count':0,'removed_preview':[]}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dpath = Path(dirpath)
        keep_dirs = []
        for d in list(dirnames):
            p = dpath / d
            rel = norm_rel(p, root)
            if is_runtime_dir(rel, d):
                if remove_dir(p):
                    removed.append(rel)
            else:
                keep_dirs.append(d)
        dirnames[:] = keep_dirs
        for f in filenames:
            p = dpath / f
            rel = norm_rel(p, root)
            if is_runtime_file(rel, f):
                if remove_file(p):
                    removed.append(rel)
    return {'overall':'cleaned','root':str(root),'removed_count':len(removed),'removed_preview':removed[:50]}

if __name__ == '__main__':
    print(json.dumps(clean_runtime(), ensure_ascii=False, indent=2))
