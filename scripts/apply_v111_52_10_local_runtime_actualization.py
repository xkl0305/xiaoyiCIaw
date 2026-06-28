from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_52_10'
FORBIDDEN_DIRS = [
    '_overlay2','_overlay3','_overlay4','_overlay5','_overlay6','_overlay7','_overlay8','_overlay9','_overlay_extract',
    'overlay_payload_v111_52_0','overlay_payload_v111_52_1','overlay_payload_v111_52_2','overlay_payload_v111_52_3','overlay_payload_v111_52_4','overlay_payload_v111_52_5','overlay_payload_v111_52_6','overlay_payload_v111_52_7','overlay_payload_v111_52_8','overlay_payload_v111_52_9','overlay_payload_v111_52_10',
    'logs','generated-images','.openclaw/state','.openclaw/hook_state','.v98_state','.v107_state','.lazy_state','.context_state','.pytest_cache',
    '.persona_visual/generated',
]
FORBIDDEN_FILES = [
    '.persona_visual/visual_request_ledger.jsonl',
    '.persona_visual/runtime_wardrobe_state.json',
]


def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            copy_any(item, dst / item.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def clean_runtime_residue() -> dict:
    removed = []
    for rel in FORBIDDEN_DIRS:
        p = ROOT / rel
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
            removed.append(rel)
    for p in list(ROOT.glob('_overlay*')) + list(ROOT.glob('overlay_payload*')):
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
            removed.append(str(p.relative_to(ROOT)))
    for rel in FORBIDDEN_FILES:
        p = ROOT / rel
        if p.exists():
            p.unlink(missing_ok=True)
            removed.append(rel)
    for pattern in ['**/__pycache__','**/*.pyc','**/*.pyo','**/*.jsonl','**/*.log','**/*.sqlite','**/*.sqlite3','**/*.db','**/.DS_Store']:
        for p in ROOT.glob(pattern):
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
                removed.append(str(p.relative_to(ROOT)))
            except Exception:
                pass
    return {'removed_count': len(set(removed)), 'removed_sample': sorted(set(removed))[:60]}


def main() -> int:
    if PAYLOAD.exists():
        for item in PAYLOAD.iterdir():
            copy_any(item, ROOT / item.name)
    clean = clean_runtime_residue()
    print({'overall': 'applied', 'version': 'V111.52.10_LOCAL_RUNTIME_ACTUALIZATION_FINAL', **clean})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
