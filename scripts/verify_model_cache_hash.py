#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'profiles/model_hash_manifest.json'


def hpath(p: Path) -> str:
    h = hashlib.sha256()
    files = [p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file())
    for f in files:
        h.update(str(f.relative_to(p) if p.is_dir() else f.name).encode())
        with f.open('rb') as fp:
            for chunk in iter(lambda: fp.read(1024 * 1024), b''):
                h.update(chunk)
    return h.hexdigest()


def _required_for_execution(data: Dict[str, object]) -> bool:
    return bool(data.get('required_for_execution')) or os.environ.get('LOCAL_MODEL_HASH_STRICT', '').lower() in {'1', 'true', 'yes'}


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    strict = _required_for_execution(data)
    checks: List[Dict[str, object]] = []
    failed: List[str] = []
    pending: List[str] = []
    for it in data.get('models', []):
        cap = str(it.get('capability') or '')
        path = os.environ.get(str(it.get('path_env') or ''), '').strip()
        exp = str(it.get('expected_sha256') or '').strip()
        required = strict or bool(it.get('required_for_execution'))
        rec = dict(it)
        rec['required_for_execution_effective'] = required
        if not path:
            rec['status'] = 'blocked_not_configured' if required else 'pending_not_configured'
            rec['reason'] = 'model path env is not set'
            checks.append(rec)
            (failed if required else pending).append(cap)
            continue
        p = Path(path).expanduser()
        if not p.exists():
            rec.update({'status': 'missing_path', 'path': str(p), 'reason': 'configured path does not exist'})
            checks.append(rec)
            failed.append(cap)
            continue
        if not exp:
            actual = hpath(p)
            rec.update({'status': 'blocked_missing_expected_sha256' if required else 'pending_missing_expected_sha256', 'actual_sha256': actual, 'path': str(p), 'reason': 'expected_sha256 is empty'})
            checks.append(rec)
            (failed if required else pending).append(cap)
            continue
        actual = hpath(p)
        ok = actual == exp
        rec.update({'status': 'passed' if ok else 'hash_mismatch', 'actual_sha256': actual, 'path': str(p)})
        checks.append(rec)
        if not ok:
            failed.append(cap)
    overall = 'failed' if failed else ('pending' if pending else 'passed')
    print(json.dumps({
        'overall': overall,
        'strict_required_for_execution': strict,
        'failed': failed,
        'pending': pending,
        'checks': checks,
        'version': data.get('version'),
        'allow_external_fallback': False,
    }, ensure_ascii=False, indent=2))
    # In source-package mode, missing local models are expected pending items, not a fake pass.
    # Strict execution mode turns pending into a hard failure.
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
