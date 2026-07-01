from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_51_23'

RUNTIME_DIRS = [
    '.openclaw/state',
    '.openclaw/hook_state',
    '.v98_state',
    '.v107_state',
    '.lazy_state',
    '.context_state',
    'legacy_readonly',
    'cache',
    'logs',
]

DELETE_PATTERNS = [
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '*.jsonl',
    '.DS_Store',
    'README_#U*',
]


def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            copy_any(item, dst / item.name)
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
    for pat in DELETE_PATTERNS:
        for p in ROOT.rglob(pat):
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
            except Exception:
                pass
    for p in ROOT.rglob('*/cache/*.json'):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    if not PAYLOAD.exists():
        raise SystemExit(f'payload not found: {PAYLOAD}')
    for item in PAYLOAD.iterdir():
        copy_any(item, ROOT / item.name)
    clean_runtime()
    print('applied V111.51.23_STRICT_TRIGGER_AND_PROOF_FINAL overlay')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
