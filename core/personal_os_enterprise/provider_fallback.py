from __future__ import annotations

from typing import Any, Dict, Iterable, Protocol

from .send_guard import validate_artifact_for_send
from .observability_event_bus import emit_event


class Provider(Protocol):
    name: str
    def ready(self, ctx: Dict[str, Any]) -> bool: ...
    def generate(self, ctx: Dict[str, Any]) -> Dict[str, Any]: ...


def provider_fallback_chain(ctx: Dict[str, Any], providers: Iterable[Provider], *, root=None) -> Dict[str, Any]:
    attempts = []
    for p in providers:
        name = getattr(p, 'name', p.__class__.__name__)
        try:
            if not p.ready(ctx):
                attempts.append({'provider': name, 'reason': 'not_ready'})
                continue
            r = p.generate(ctx)
            if r.get('status') == 'generated' and r.get('output_path'):
                guard = validate_artifact_for_send(
                    path=r['output_path'],
                    generation_started_at=float(ctx.get('generation_started_at') or 0),
                    request_id=str(r.get('request_id') or ctx.get('request_id') or ''),
                    expected_request_id=str(ctx.get('request_id') or ''),
                )
                if guard.get('send_ok'):
                    r['send_guard'] = guard
                    r['provider_selected'] = name
                    emit_event('provider_fallback_selected', {'provider': name, 'request_id': ctx.get('request_id')}, root=root)
                    return r
                attempts.append({'provider': name, 'reason': guard.get('reason')})
            else:
                attempts.append({'provider': name, 'reason': r.get('status') or r.get('blocked_reason') or 'unknown_error'})
        except Exception as exc:
            attempts.append({'provider': name, 'reason': f'exception:{exc.__class__.__name__}'})
    out = {'status': 'blocked', 'blocked': True, 'blocked_send': True, 'blocked_reason': 'all_local_providers_failed', 'provider_attempts': attempts}
    emit_event('provider_fallback_failed', out, root=root)
    return out
