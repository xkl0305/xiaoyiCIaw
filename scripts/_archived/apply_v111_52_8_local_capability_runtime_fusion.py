from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_52_8'
VERSION = 'V111.52.8_LOCAL_CAPABILITY_RUNTIME_FUSION'

RUNTIME_DIRS = [
    '.openclaw/state', '.openclaw/hook_state', '.v98_state', '.v107_state',
    '.lazy_state', '.context_state', 'logs', 'generated-images', '.pytest_cache',
]
RUNTIME_SUFFIXES = {'.pyc', '.pyo', '.jsonl', '.sqlite', '.sqlite3', '.db', '.secret', '.env'}


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


def clean_runtime(root: Path) -> None:
    for rel in RUNTIME_DIRS:
        remove_path(root / rel)
    for p in list(root.rglob('*')):
        if p.is_dir() and (p.name == '__pycache__' or p.name.startswith('overlay_payload_v111_52_') and p.name != 'overlay_payload_v111_52_8'):
            remove_path(p)
            continue
        if p.is_file() and (p.suffix in RUNTIME_SUFFIXES or p.name == '.DS_Store'):
            remove_path(p)


def apply() -> dict:
    if not PAYLOAD.exists():
        return {'overall': 'failed', 'reason': 'payload_missing', 'payload': str(PAYLOAD)}
    copied = []
    for child in PAYLOAD.iterdir():
        if child.name == 'scripts':
            # copy scripts too, but avoid copying current payload into itself
            pass
        copy_any(child, ROOT / child.name)
        copied.append(child.name)
    clean_runtime(ROOT)
    # Keep delivered workspace clean: remove payload after successful copy.
    remove_path(PAYLOAD)
    return {'overall': 'applied', 'version': VERSION, 'copied_top_level': copied}


if __name__ == '__main__':
    import json
    print(json.dumps(apply(), ensure_ascii=False, indent=2, sort_keys=True))
