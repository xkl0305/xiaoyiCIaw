from __future__ import annotations
import shutil
from pathlib import Path

ROOT = Path.cwd()

DELETE_DIR_PATTERNS = [
    'V*_overlay', '*_overlay', '__pycache__', '.pytest_cache',
]
DELETE_FILE_PATTERNS = [
    '*.pyc', '*.pyo', '*.jsonl', 'V*_overlay.zip', 'V*_overlay.tar.gz', '*_overlay.zip', '*_overlay.tar.gz'
]
DELETE_PATHS = [
    '.openclaw/hook_state', '.v98_state', '.v107_state', '.lazy_state', '.context_state', 'cache', 'logs',
    '.persona_visual/generated', '.persona_visual/runtime_wardrobe_state.json', '.openclaw/.xiaoyienv',
]


def safe_remove(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def dereference_reference_images() -> None:
    outdir = ROOT / 'assets/persona/outfits'
    if not outdir.exists():
        return
    for p in outdir.glob('*reference.jpg'):
        if p.is_symlink():
            target = p.resolve()
            if target.exists():
                data = target.read_bytes()
                p.unlink()
                p.write_bytes(data)


def ensure_generated_dir() -> None:
    gen = ROOT / '.persona_visual/generated'
    gen.mkdir(parents=True, exist_ok=True)
    probe = gen / '.write_test.tmp'
    probe.write_text('ok', encoding='utf-8')
    probe.unlink()


def main() -> int:
    for rel in DELETE_PATHS:
        safe_remove(ROOT / rel)
    for pat in DELETE_DIR_PATTERNS:
        for p in ROOT.rglob(pat) if pat == '__pycache__' else ROOT.glob(pat):
            if p.name == 'V111_51_14_architecture_fusion_clean_overlay':
                continue
            safe_remove(p)
    for pat in DELETE_FILE_PATTERNS:
        for p in ROOT.rglob(pat):
            safe_remove(p)
    dereference_reference_images()
    ensure_generated_dir()
    print('[OK] V111.51.14 cleanup applied: overlay residue/cache/runtime removed, references dereferenced, generated dir writable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
