from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_52_11'

RUNTIME_DIRS = [
    '_overlay2','_overlay3','_overlay4','_overlay5','_overlay6','_overlay7','_overlay8','_overlay9','_overlay_extract',
    '.openclaw/state','.openclaw/hook_state','.v98_state','.v107_state','.lazy_state','.context_state',
    'logs','generated-images','.persona_visual/generated',
]
FILE_PATTERNS = ['*.pyc','*.pyo','*.jsonl','*.log','*.sqlite','*.sqlite3','*.sqlite3-wal','*.sqlite3-shm','*.db','*.db-wal','*.db-shm','.DS_Store']


def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            copy_any(child, dst / child.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def clean_runtime() -> None:
    for rel in RUNTIME_DIRS:
        p = ROOT / rel
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
    for p in list(ROOT.glob('overlay_payload*')) + list(ROOT.glob('_overlay*')):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    for pat in FILE_PATTERNS:
        for p in ROOT.rglob(pat):
            try:
                if '__pycache__' in str(p) or p.is_file():
                    p.unlink(missing_ok=True)
            except Exception:
                pass
    for p in ROOT.rglob('__pycache__'):
        shutil.rmtree(p, ignore_errors=True)


def main() -> int:
    if PAYLOAD.exists():
        for item in PAYLOAD.iterdir():
            copy_any(item, ROOT / item.name)
    clean_runtime()
    print('applied V111.52.11 local runtime metadata + acceptance close')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
