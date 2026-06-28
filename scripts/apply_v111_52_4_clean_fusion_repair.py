from __future__ import annotations

from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "overlay_payload_v111_52_4"
VERSION = "V111.52.4_SIDE_EFFECT_FUSION_CLEAN_REPAIR_FINAL"

RUNTIME_DIRS = [
    ".openclaw/state", ".openclaw/hook_state", ".v98_state", ".v107_state", ".lazy_state", ".context_state", "logs", "generated-images",
]

def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            copy_any(child, dst / child.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def clean_runtime(keep_current_payload: bool = False) -> None:
    for item in ROOT.glob("overlay_payload*"):
        if keep_current_payload and item.name == PAYLOAD.name:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        elif item.is_file():
            item.unlink()
    for rel in RUNTIME_DIRS:
        p = ROOT / rel
        if p.exists():
            shutil.rmtree(p)
    for pattern in ["*.jsonl", "*.pyc", "*.pyo", ".DS_Store"]:
        for p in ROOT.rglob(pattern):
            if p.is_file():
                p.unlink()
    for p in list(ROOT.rglob("__pycache__")):
        if p.is_dir():
            shutil.rmtree(p)


def main() -> int:
    if not PAYLOAD.exists():
        print(json.dumps({"overall": "failed", "reason": "payload_missing", "payload": str(PAYLOAD)}, ensure_ascii=False))
        return 1
    clean_runtime(keep_current_payload=True)
    for item in PAYLOAD.iterdir():
        copy_any(item, ROOT / item.name)
    clean_runtime(keep_current_payload=False)
    print(json.dumps({"overall": "applied", "version": VERSION}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
