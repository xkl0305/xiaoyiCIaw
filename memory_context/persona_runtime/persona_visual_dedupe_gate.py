from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / '.openclaw' / 'hook_state' / 'persona_visual_dedupe.json'


def _load() -> Dict[str, Any]:
    try:
        return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def make_dedupe_key(text: str = '', prediction: Dict[str, Any] | None = None, request_id: str = '') -> str:
    pred = prediction or {}
    raw = '|'.join([
        (text or '').strip()[:500],
        str(pred.get('mood') or ''),
        str(pred.get('semantic_scene') or ''),
        str(pred.get('focus_target') or ''),
        str(pred.get('outfit_id') or ''),
        str(pred.get('focus_label') or ''),
        str(request_id or ''),
    ])
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


def reserve_once(key: str, ttl_seconds: int = 45, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not key:
        return {'allowed': False, 'reason': 'empty_dedupe_key'}
    now = time.time()
    data = _load()
    data = {k: v for k, v in data.items() if now - float(v.get('ts', 0)) <= ttl_seconds}
    if key in data:
        _save(data)
        return {'allowed': False, 'reason': 'duplicate_within_window', 'key': key, 'first': data[key]}
    data[key] = {'ts': now, **(meta or {})}
    _save(data)
    return {'allowed': True, 'reason': 'reserved', 'key': key}


def clear_dedupe_state() -> None:
    if STATE.exists():
        STATE.unlink()
