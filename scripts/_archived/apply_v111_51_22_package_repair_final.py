from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_51_22'

def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            copy_any(item, dst / item.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def clean_runtime() -> None:
    for pattern in ['**/__pycache__', '**/.pytest_cache']:
        for p in ROOT.glob(pattern):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
    for pattern in ['**/*.pyc', '**/*.pyo', '**/*.jsonl']:
        for p in ROOT.glob(pattern):
            try:
                p.unlink()
            except Exception:
                pass
    for rel in ['.openclaw/hook_state', '.v98_state', '.v107_state', '.lazy_state', '.context_state', 'cache', 'logs', 'generated-images']:
        p = ROOT / rel
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    for rel in ['.persona_visual/runtime_wardrobe_state.json', '.persona_visual/visual_request_ledger.jsonl']:
        p = ROOT / rel
        if p.exists():
            p.unlink()

def main() -> int:
    if PAYLOAD.exists():
        for item in PAYLOAD.iterdir():
            copy_any(item, ROOT / item.name)
    clean_runtime()
    print('applied V111.51.22 package repair final overlay')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
