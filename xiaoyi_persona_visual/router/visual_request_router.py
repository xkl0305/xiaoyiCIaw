from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

MODULE_ROOT = Path(__file__).resolve().parents[1]

_trigger_policy = None
_last_outfit_policy = None


def _load_json(rel_path: str) -> Dict[str, Any]:
    fp = MODULE_ROOT / rel_path
    if fp.exists():
        try:
            import json
            return json.loads(fp.read_text(encoding='utf-8'))
        except:
            pass
    return {}


def load_policies() -> None:
    global _trigger_policy, _last_outfit_policy
    _trigger_policy = _load_json('policy/visual_trigger_policy.json')
    _last_outfit_policy = _load_json('policy/last_outfit_policy.json')


def is_persona_visual_request(user_message: str, semantic_scene: str = '') -> bool:
    """Determine if a request should be routed to PersonaVisualController."""
    if not _trigger_policy:
        load_policies()
    if not _trigger_policy or not _trigger_policy.get('enabled', True):
        return True  # Default to true when policy is missing

    # Check display_appearance triggers
    triggers = _trigger_policy.get('display_appearance_triggers', [])
    for t in triggers:
        if t in user_message:
            return True

    # Check scene-based rules
    if semantic_scene:
        for rule in _trigger_policy.get('trigger_rules', []):
            if rule.get('type') == 'scene' and rule.get('scene') == semantic_scene:
                return rule.get('action') == 'route_to_persona_controller'

    # Check explicit routing keywords (鸽子王等)
    keywords = _trigger_policy.get('explicit_routing_keywords', [])
    for kw in keywords:
        if kw in user_message:
            return True

    # Fallback: route to persona controller
    return _trigger_policy.get('fallback_on_unknown', 'route_to_persona_controller') == 'route_to_persona_controller'


def should_use_last_outfit(text: str, semantic_scene: str = '') -> bool:
    """Determine if last outfit continuity should be used."""
    if not _last_outfit_policy:
        return False
    if not _last_outfit_policy.get('enabled', True):
        return False

    # Scene reset check
    for reset_phrase in _last_outfit_policy.get('scene_reset_requests', []):
        if reset_phrase in text:
            return False

    # Scene-based check
    if semantic_scene:
        rules = _last_outfit_policy.get('rules', {})
        scene_rule = rules.get(semantic_scene, '')
        if scene_rule == 'no_last_outfit_continuity':
            return False

    # User explicit continuity check
    for kw in _last_outfit_policy.get('continuity_keywords', []):
        if kw in text:
            return True

    return False
