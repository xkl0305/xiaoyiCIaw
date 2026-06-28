from __future__ import annotations

from typing import Any, Dict

from .capability_router import classify_capability_request
from .local_health_check import require_capabilities


def plan_screen_understanding(user_request: str, *, root=None) -> Dict[str, Any]:
    route = classify_capability_request(user_request)
    required = route.get('required_capabilities') or []
    # Screen/GUI understanding should always have deterministic OCR plus VLM semantics.
    merged = list(dict.fromkeys(list(required) + ['local_vlm', 'local_ocr']))
    required = merged
    readiness = require_capabilities(required, root=root)
    return {
        'status': 'planned' if readiness.get('ok') else 'blocked',
        'blocked': not readiness.get('ok'),
        'blocked_reason': readiness.get('blocked_reason','') if not readiness.get('ok') else '',
        'required_capabilities': required,
        'steps': ['capture_screenshot', 'local_ocr', 'local_vlm', 'state_extract', 'action_plan_dry_run', 'action_guard', 'post_action_verify'],
        'side_effects_require_proof': True,
        'allow_external_fallback': False,
        'readiness': readiness,
    }


def plan_gui_action(user_request: str, *, root=None) -> Dict[str, Any]:
    base = plan_screen_understanding(user_request, root=root)
    base['requires_explicit_approval'] = True
    base['action_guard_required'] = True
    base['post_action_screenshot_verify'] = True
    return base
