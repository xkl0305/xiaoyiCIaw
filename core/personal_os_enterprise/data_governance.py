from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

DATA_CLASSES = {
    'S0': {'name': 'runtime_secret', 'ttl_days': 0, 'packaged': False, 'log_raw': False},
    'S1': {'name': 'raw_audio_screenshot_chat', 'ttl_days': 7, 'packaged': False, 'log_raw': False},
    'S2': {'name': 'embedding_ocr_cache', 'ttl_days': 30, 'packaged': False, 'log_raw': False},
    'S3': {'name': 'public_model_prompt_index', 'ttl_days': 365, 'packaged': True, 'log_raw': True},
}


def classify_data_path(path: str) -> Dict[str, Any]:
    p = str(path or '').lower()
    if 'secret' in p or p.endswith('.env'):
        level = 'S0'
    elif 'screenshot' in p or 'audio' in p or 'chat' in p:
        level = 'S1'
    elif 'embedding' in p or 'ocr' in p or 'cache' in p:
        level = 'S2'
    else:
        level = 'S3'
    out = dict(DATA_CLASSES[level])
    out['level'] = level
    out['path'] = path
    return out


def retention_policy() -> Dict[str, Any]:
    return {'classes': DATA_CLASSES, 'default_debug_log_redaction': True, 'runtime_secret_packaged': False}
