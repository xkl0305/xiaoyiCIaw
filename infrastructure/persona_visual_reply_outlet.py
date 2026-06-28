from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.openclaw' / 'hook_state'
PATCH_STATE = STATE / 'reply_outlet_patch_state.json'
_IN_FINALIZE = False
_INSTALLED = False


def _log(payload: Dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'reply_outlet_events.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'ts': time.time(), **payload}, ensure_ascii=False, default=str) + '\n')


def _write_patch_state(payload: Dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    PATCH_STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def status() -> Dict[str, Any]:
    st = {
        'status': 'ok',
        'installed': _INSTALLED,
        'patch_state_file': str(PATCH_STATE),
        'state_dir': str(STATE),
        'reply_events_file': str(STATE / 'reply_outlet_events.jsonl'),
    }
    if not PATCH_STATE.exists():
        _write_patch_state({'status': 'ok', 'installed_at': time.time(), 'mode': 'reply_outlet_ready'})
    try:
        st['patch_state'] = json.loads(PATCH_STATE.read_text(encoding='utf-8'))
    except Exception:
        st['patch_state'] = {'status': 'unreadable'}
    return st


def finalize_reply(
    reply_text: str = '',
    user_message: str = '',
    source: str = 'real_host_reply',
    phase: str = 'post_reply',
    **kwargs: Any,
) -> Dict[str, Any]:
    global _IN_FINALIZE
    text = reply_text or kwargs.get('assistant_message') or kwargs.get('lobster_message') or ''
    if not text:
        return {'status': 'skip', 'reason': 'empty_reply'}
    if _IN_FINALIZE:
        return {'status': 'skip', 'reason': 'reentrant_guard'}
    _IN_FINALIZE = True
    try:
        _log({'status': 'received', 'source': source, 'phase': phase, 'reply_preview': text[:160]})
        from infrastructure.persona_visual_event_adapter import instrument_reply

        hook = instrument_reply(
            reply_text=text,
            user_message=user_message,
            assistant_message=kwargs.get('assistant_message') or text,
            lobster_message=kwargs.get('lobster_message') or text,
            source=source,
            phase=phase,
            dry_run=kwargs.get('dry_run', False),
        )
        out = {'status': 'ok', 'hook_result': hook, 'reply_text': text}
        _log({
            'status': 'ok',
            'source': source,
            'phase': phase,
            'hook_status': hook.get('status') if isinstance(hook, dict) else None,
            'hook_called': hook.get('called') if isinstance(hook, dict) else None,
            'generation_status': (hook.get('result') or {}).get('generation_status') if isinstance(hook, dict) else None,
        })
        return out
    except Exception as e:
        out = {'status': 'fail_soft', 'error': str(e), 'reply_text': text}
        _log(out)
        return out
    finally:
        _IN_FINALIZE = False


def finalize_visible_reply(reply_text: str, user_message: str = '', **kwargs: Any) -> str:
    finalize_reply(reply_text=reply_text, user_message=user_message, **kwargs)
    return reply_text


def install_auto_hooks() -> Dict[str, Any]:
    global _INSTALLED
    if _INSTALLED:
        if not PATCH_STATE.exists():
            _write_patch_state({'status': 'ok', 'installed_at': time.time(), 'mode': 'reply_outlet_ready'})
        return {'status': 'already_installed', 'patch_state_file': str(PATCH_STATE)}
    _INSTALLED = True
    payload = {
        'status': 'ok',
        'installed_at': time.time(),
        'mode': 'reply_outlet_ready',
        'note': 'Use finalize_visible_reply() in final reply outlet for hard binding.',
    }
    _write_patch_state(payload)
    return {'status': 'ok', 'patch_state_file': str(PATCH_STATE), **payload}
