from __future__ import annotations

from pathlib import Path
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_52_5'
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bark-[A-Za-z0-9_-]{20,}\b"),
)


def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            copy_any(item, dst / item.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def clean_runtime() -> None:
    for d in ['.openclaw/state', '.openclaw/hook_state', '.v98_state', '.v107_state', '.lazy_state', '.context_state', 'logs', 'generated-images']:
        shutil.rmtree(ROOT / d, ignore_errors=True)
    for pattern in ['*.jsonl', '*.pyc', '*.pyo', '.DS_Store']:
        for p in ROOT.rglob(pattern):
            if p.is_file():
                p.unlink()
    for p in ROOT.rglob('__pycache__'):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    for p in ROOT.glob('overlay_payload*'):
        if p.name != 'overlay_payload_v111_52_5':
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.is_file():
                p.unlink()


def scrub_secret_literals() -> None:
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.zip', '.tar', '.gz', '.tgz'}:
            continue
        if p.stat().st_size > 5_000_000:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        new = text
        for pat in SECRET_PATTERNS:
            new = pat.sub('REDACTED_SECRET_REMOVED', new)
        if new != text:
            p.write_text(new, encoding='utf-8')


def main() -> int:
    if PAYLOAD.exists():
        for item in PAYLOAD.iterdir():
            copy_any(item, ROOT / item.name)
    clean_runtime()
    scrub_secret_literals()
    print('applied V111.52.5 secret clean + runtime proof overlay')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
