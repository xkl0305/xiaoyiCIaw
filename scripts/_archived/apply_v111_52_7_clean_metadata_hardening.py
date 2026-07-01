from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_52_7'
VERSION = 'V111.52.7_CLEAN_METADATA_HARDENING_FINAL'

RUNTIME_DIRS = [
    '.openclaw/state', '.openclaw/hook_state', '.v98_state', '.v107_state',
    '.lazy_state', '.context_state', 'logs', 'generated-images', '.pytest_cache',
]
RUNTIME_SUFFIXES = {
    '.pyc', '.pyo', '.jsonl', '.sqlite', '.sqlite3', '.db', '.secret', '.env'
}


def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            copy_any(child, dst / child.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except Exception:
            pass


def clean_runtime_and_delivery_residue(root: Path) -> None:
    # Remove old overlay payloads left by prior cover packages. This is the key V111.52.7 repair.
    for p in root.glob('overlay_payload*'):
        remove_path(p)

    for rel in RUNTIME_DIRS:
        remove_path(root / rel)

    for pattern in ('__pycache__', '.pytest_cache'):
        for p in list(root.rglob(pattern)):
            if p.is_dir():
                remove_path(p)

    for p in list(root.rglob('*')):
        if not p.is_file():
            continue
        if (
            p.suffix in RUNTIME_SUFFIXES
            or p.name == '.DS_Store'
            or p.name.endswith('.sqlite-wal')
            or p.name.endswith('.sqlite-shm')
        ):
            remove_path(p)


def main() -> int:
    if not PAYLOAD.exists():
        raise SystemExit(f'missing payload: {PAYLOAD}')
    for item in PAYLOAD.iterdir():
        copy_any(item, ROOT / item.name)
    clean_runtime_and_delivery_residue(ROOT)
    print({'overall': 'applied', 'version': VERSION, 'overlay_payload_removed': True})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
