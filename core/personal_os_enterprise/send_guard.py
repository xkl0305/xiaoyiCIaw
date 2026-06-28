from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Dict


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_artifact_for_send(*, path: str, generation_started_at: float, request_id: str, expected_request_id: str, max_bytes: int = 20 * 1024 * 1024) -> Dict[str, object]:
    if request_id != expected_request_id:
        return {'send_ok': False, 'blocked_send': True, 'reason': 'request_id_mismatch'}
    fp = Path(path or '')
    if not path or not fp.exists():
        return {'send_ok': False, 'blocked_send': True, 'reason': 'file_missing'}
    stat = fp.stat()
    if stat.st_mtime < float(generation_started_at or 0):
        return {'send_ok': False, 'blocked_send': True, 'reason': 'stale_file'}
    if stat.st_size <= 0 or stat.st_size > int(max_bytes):
        return {'send_ok': False, 'blocked_send': True, 'reason': 'size_out_of_range'}
    mime, _ = mimetypes.guess_type(fp.name)
    if mime is None:
        return {'send_ok': False, 'blocked_send': True, 'reason': 'unknown_mime'}
    return {'send_ok': True, 'blocked_send': False, 'mime': mime, 'size': stat.st_size, 'sha256': sha256_file(fp)}
