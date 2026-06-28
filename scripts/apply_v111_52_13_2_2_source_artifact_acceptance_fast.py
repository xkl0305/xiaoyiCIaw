#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PATCH_VERSION = 'V111.52.13.2.2_SOURCE_ARTIFACT_AND_ACCEPTANCE_FAST_CLOSE_PATCH'
ACTIVE_VERSION = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'
PAYLOAD_DIR_NAME = 'overlay_payload_v111_52_13_2_2_source_artifact_acceptance_fast'


def find_root() -> Path:
    cur = Path.cwd().resolve()
    here = Path(__file__).resolve()
    for p in [cur, *cur.parents, here.parent, *here.parents]:
        if (p / 'openclaw.json').exists() and (p / 'xiaoyi_persona_visual').exists():
            return p
    return cur


def find_payload(root: Path) -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        root / PAYLOAD_DIR_NAME,
        script_dir.parent / PAYLOAD_DIR_NAME,
        Path.cwd() / PAYLOAD_DIR_NAME,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def copy_payload(root: Path) -> list[str]:
    payload = find_payload(root)
    if payload is None:
        raise RuntimeError('payload_missing:' + PAYLOAD_DIR_NAME)
    copied: list[str] = []
    for src in payload.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(payload)
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel.as_posix())
    return copied


def clean_runtime(root: Path) -> None:
    cleaner = root / 'scripts/clean_runtime_artifacts.py'
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = '.'
    if cleaner.exists():
        subprocess.run(
            [sys.executable, '-S', str(cleaner)],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def remove_overlay_dirs(root: Path) -> None:
    for p in list(root.glob('overlay_payload*')) + list(root.glob('_overlay*')):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink(missing_ok=True)


def main() -> int:
    root = find_root()
    try:
        copied = copy_payload(root)
        run_all = root / 'scripts/acceptance/run_all_enterprise_acceptance.sh'
        if run_all.exists():
            run_all.chmod(run_all.stat().st_mode | 0o111)
        remove_overlay_dirs(root)
        clean_runtime(root)
        out = {
            'overall': 'applied',
            'patch_version': PATCH_VERSION,
            'active_version_unchanged': ACTIVE_VERSION,
            'root': str(root),
            'copied_count': len(copied),
            'copied_preview': copied[:30],
            'note': 'Closes root overlay*.zip/generated*.jpg source artifact residue and removes duplicate direct 52.12.1 enterprise acceptance call. Active version intentionally unchanged.',
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({
            'overall': 'failed',
            'patch_version': PATCH_VERSION,
            'root': str(root),
            'reason': repr(e),
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
