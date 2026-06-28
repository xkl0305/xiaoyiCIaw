from __future__ import annotations

from pathlib import Path
import shutil
import json

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "overlay_payload_v111_52_3"

def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            copy_any(child, dst / child.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def main() -> int:
    if not PAYLOAD.exists():
        print(json.dumps({"overall": "failed", "reason": "payload_missing", "payload": str(PAYLOAD)}, ensure_ascii=False))
        return 1
    for item in PAYLOAD.iterdir():
        copy_any(item, ROOT / item.name)
    print(json.dumps({"overall": "applied", "version": "V111.52.3_SIDE_EFFECT_PROOF_FULL_FUSION"}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
