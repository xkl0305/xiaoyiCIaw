from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Dict, Iterable

VERSION = "V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL"
DEFAULT_TTL_DAYS = {
    'S0_secret': 0,
    'S1_screenshot': 7,
    'S1_audio': 7,
    'S1_gui_state': 14,
    'S2_ocr_intermediate': 30,
    'S2_embedding_cache': 90,
    'S3_public_template': 3650,
    'proof_action_ledger': 3650,
}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def artifact_record(path: str | Path, *, classification: str = 'S2_artifact') -> Dict[str, object]:
    p = Path(path)
    if not p.exists():
        return {'ok': False, 'reason': 'file_missing', 'path': str(path)}
    return {
        'ok': True,
        'version': VERSION,
        'path': str(p),
        'size': p.stat().st_size,
        'sha256': sha256_file(p),
        'classification': classification,
        'content_hash_naming_recommended': True,
    }


def retention_policy() -> Dict[str, object]:
    return {'version': VERSION, 'ttl_days': DEFAULT_TTL_DAYS, 'debug_log_redaction_required': True, 'training_runtime_log_separation': True}
