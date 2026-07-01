from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_51_20'


def copy_any(src: Path, dst: Path) -> None:
    if src.is_dir():
        if dst.exists() and dst.is_file():
            dst.unlink()
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            copy_any(item, dst / item.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    for item in PAYLOAD.iterdir():
        copy_any(item, ROOT / item.name)
    print('applied V111.51.20 mainchain proof + tail anchor overlay')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
