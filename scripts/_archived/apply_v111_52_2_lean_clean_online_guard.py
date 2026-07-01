from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'overlay_payload_v111_52_2'
VERSION = 'V111.52.2_PERSONAL_OS_ENTERPRISE_LEAN_CLEAN_FINAL'

COPY_FILES = [
    'release_manifest.json',
    'xiaoyi_persona_visual/version.json',
    'xiaoyi_persona_visual/diagnostics/verify_v111_52_2_lean_clean_online_guard.py',
]

RUNTIME_DIRS = [
    '.openclaw/hook_state',
    '.openclaw/state',
    '.v98_state',
    '.v107_state',
    '.lazy_state',
    '.context_state',
    'logs',
    '.pytest_cache',
]

RUNTIME_FILES = [
    '.persona_visual/visual_request_ledger.jsonl',
    '.persona_visual/runtime_wardrobe_state.json',
    'post_overlay_check_result.json',
    '1778744344238_V111_52_0_personal_os_enterprise_core_overlay.zip',
    '#U5927#U9f99#U867e_V111_52_#U975e#U4eba#U683c#U57fa#U7840#U878d#U5408#U8986#U76d6#U547d#U4ee4.txt',
]

STALE_OVERLAY_DIRS = [
    'overlay_payload_v111_52_0',
    'overlay_payload_v111_52_1',
    'overlay_payload_v111_52_non_persona_foundation',
]


def copy_payload_file(rel: str) -> None:
    src = PAYLOAD / rel
    if not src.exists():
        return
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def remove_path(rel: str) -> bool:
    p = ROOT / rel
    if not p.exists() and not p.is_symlink():
        return False
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    else:
        p.unlink()
    return True


def clean_generated_bytecode() -> int:
    count = 0
    for p in list(ROOT.rglob('__pycache__')):
        if p.is_dir():
            shutil.rmtree(p)
            count += 1
    for pattern in ('*.pyc', '*.pyo', '.DS_Store'):
        for p in list(ROOT.rglob(pattern)):
            try:
                if p.is_file() or p.is_symlink():
                    p.unlink()
                    count += 1
            except FileNotFoundError:
                pass
    return count


def clean_jsonl_ledgers() -> int:
    count = 0
    for p in list(ROOT.rglob('*.jsonl')):
        # Runtime ledgers only; source schemas should be json, not jsonl.
        try:
            if p.is_file():
                p.unlink()
                count += 1
        except FileNotFoundError:
            pass
    return count


def ensure_openclaw_version() -> None:
    p = ROOT / 'openclaw.json'
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return
    data['ONLINE_MODE'] = True
    data['OFFLINE_MODE'] = False
    data['CONNECTED_RUNTIME_ALWAYS_ON'] = True
    data['ZERO_COST_MODE'] = True
    data.setdefault('personalOsEnterprise', {})['version'] = VERSION
    data.setdefault('personalOsEnterprise', {})['defaultProfile'] = 'always_connected_enterprise'
    data.setdefault('personalOsEnterprise', {})['packageClean'] = True
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')


def main() -> int:
    copied = []
    if PAYLOAD.exists():
        for rel in COPY_FILES:
            copy_payload_file(rel)
            copied.append(rel)

    ensure_openclaw_version()

    removed = []
    for rel in RUNTIME_DIRS + RUNTIME_FILES + STALE_OVERLAY_DIRS:
        if remove_path(rel):
            removed.append(rel)

    bytecode_removed = clean_generated_bytecode()
    jsonl_removed = clean_jsonl_ledgers()

    # Remove current payload after copying so the workspace stays a clean source tree.
    if PAYLOAD.exists():
        shutil.rmtree(PAYLOAD)
        removed.append('overlay_payload_v111_52_2')

    result = {
        'overall': 'applied',
        'version': VERSION,
        'copied': copied,
        'removed': removed,
        'bytecode_removed': bytecode_removed,
        'jsonl_removed': jsonl_removed,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
