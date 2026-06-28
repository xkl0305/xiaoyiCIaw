from __future__ import annotations
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'V111.51.18_PROVIDER_GUARD_ACTUAL_PAYLOAD_FINAL'

REMOVE_FILES = [
    'memory_context/persona_runtime/providers/seedream_provider.py.backup',
]
REMOVE_DIR_NAMES = {'__pycache__', '.pytest_cache'}
REMOVE_RUNTIME_FILES = [
    '.persona_visual/runtime_wardrobe_state.json',
    '.persona_visual/visual_request_ledger.jsonl',
    '.openclaw/hook_state/persona_visual_dedupe.json',
    '.v107_state/unified_observability_ledger.jsonl',
]
REMOVE_RUNTIME_DIRS = [
    'logs',
    'cache',
]

def rm_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

def main() -> int:
    print(f'[APPLY] {VERSION}')
    for rel in REMOVE_FILES + REMOVE_RUNTIME_FILES:
        p = ROOT / rel
        if p.exists() or p.is_symlink():
            rm_path(p)
            print(f'[CLEAN] removed {rel}')
    for rel in REMOVE_RUNTIME_DIRS:
        p = ROOT / rel
        if p.exists():
            rm_path(p)
            print(f'[CLEAN] removed {rel}/')
    for p in list(ROOT.rglob('*')):
        if p.name in REMOVE_DIR_NAMES and p.is_dir():
            rm_path(p)
            print(f'[CLEAN] removed {p.relative_to(ROOT)}')
    for p in list(ROOT.rglob('*.pyc')):
        rm_path(p)
        print(f'[CLEAN] removed {p.relative_to(ROOT)}')
    print('[OK] provider guard actual payload final cleanup applied')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
