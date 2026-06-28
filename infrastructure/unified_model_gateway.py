from __future__ import annotations
import os
try:
    from infrastructure.offline_runtime_guard import activate
    activate('unified_model_gateway')
except Exception:
    pass

def _offline() -> bool:
    return os.environ.get('NO_EXTERNAL_API','true').lower() == 'true' or os.environ.get('DISABLE_LLM_API','true').lower() == 'true' or os.environ.get('OFFLINE_MODE','true').lower() == 'true'

def call_model(prompt=None, model=None, task_type=None, *args, **kwargs):
    # Backward compatible with old callers: call_model(prompt, model, task_type)
    if _offline():
        return {
            'status': 'blocked',
            'mode': 'offline_mock',
            'requires_api': False,
            'external_api_calls': 0,
            'real_side_effects': 0,
            'result': None,
            'reason': 'NO_EXTERNAL_API_or_DISABLE_LLM_API',
            'model': model,
            'task_type': task_type,
        }
    return {
        'status': 'deferred',
        'mode': 'not_configured',
        'requires_api': True,
        'external_api_calls': 0,
        'real_side_effects': 0,
        'result': None,
        'reason': 'live_model_gateway_not_configured',
    }

def embed_text(text=None, *args, **kwargs):
    s = str(text or '')
    base = sum(ord(c) for c in s)
    return {
        'status': 'ok',
        'mode': 'local_hash_embedding',
        'requires_api': False,
        'external_api_calls': 0,
        'vector': [float((base + i * 37) % 997) / 997 for i in range(16)],
    }

# Legacy compatibility alias for old V108 gate
embed = embed_text
