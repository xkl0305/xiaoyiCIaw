from __future__ import annotations
import hashlib
from typing import Any, Dict

def _request_id_for(text: str) -> str:
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()[:16]

def instrument_reply(
    reply_text: str = '',
    user_message: str = '',
    assistant_message: str = '',
    lobster_message: str = '',
    source: str = 'real_host_reply',
    phase: str = 'post_reply',
    event: str = 'post_reply',
    **kwargs: Any,
) -> Dict[str, Any]:
    from infrastructure.persona_visual_hook_bus import dispatch
    text = reply_text or lobster_message or assistant_message or ''
    return dispatch(
        event,
        user_message=user_message,
        reply_text=text,
        assistant_message=assistant_message or text,
        lobster_message=lobster_message or text,
        source=source,
        phase=phase,
        request_id=kwargs.get('request_id') or _request_id_for(text),
        dedupe_window_seconds=kwargs.get('dedupe_window_seconds', 45),
        **kwargs,
    )
