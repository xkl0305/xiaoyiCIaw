from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_52_6'
VERSION = 'V111.52.6_ENTERPRISE_HARDENING_FULL_CLOSE_FINAL'

RUNTIME_DIRS = [
    '.openclaw/state', '.openclaw/hook_state', '.v98_state', '.v107_state',
    '.lazy_state', '.context_state', 'logs', 'generated-images',
]


def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            copy_any(child, dst / child.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def clean_runtime(root: Path) -> None:
    for rel in RUNTIME_DIRS:
        p = root / rel
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
    for pattern in ('__pycache__', '.pytest_cache'):
        for p in root.rglob(pattern):
            if p.is_dir():
                shutil.rmtree(p)
    for p in root.rglob('*'):
        if p.is_file() and (p.suffix in {'.pyc', '.pyo', '.jsonl'} or p.name == '.DS_Store' or p.suffix in {'.sqlite', '.sqlite3', '.db', '.secret'} or p.name.endswith('.sqlite-wal') or p.name.endswith('.sqlite-shm')):
            try:
                p.unlink()
            except Exception:
                pass


def main() -> int:
    if not PAYLOAD.exists():
        raise SystemExit(f'missing payload: {PAYLOAD}')
    for item in PAYLOAD.iterdir():
        copy_any(item, ROOT / item.name)
    clean_runtime(ROOT)
    print({'overall': 'applied', 'version': VERSION})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
