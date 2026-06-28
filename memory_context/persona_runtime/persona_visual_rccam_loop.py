"""V111.23 R-CCAM closed loop for persona visual generation.

Retrieval -> Cognition -> Control -> Action -> Memory.
Trigger text may come from 龙虾/assistant output, not only from user words.
"""
from __future__ import annotations
from typing import Any, Dict, Optional

def process_persona_visual_turn(message: str, context: Optional[Dict[str, Any]] = None, *, assistant_message: Optional[str] = None, lobster_message: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    context = dict(context or {})
    if assistant_message:
        context['assistant_message'] = assistant_message
    if lobster_message:
        context['lobster_message'] = lobster_message
    if dry_run:
        context['dry_run'] = True
    from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
    obs = observe_turn(user_message=message, assistant_message=assistant_message, lobster_message=lobster_message, context=context, persona_state=context.get('persona_state', {}))
    pred = obs.get('prediction', {})
    from memory_context.persona_runtime.persona_visual_auto_generation_bridge import run_auto_generation
    action = run_auto_generation(message=message, context=context, detected_mood=pred.get('predicted_visual_type') or pred.get('mood'), matched_patterns=pred.get('trigger_signals'), final_confidence=pred.get('confidence'), auto=True)
    from memory_context.persona_runtime.persona_visual_ledger import append_visual_event
    append_visual_event({'event': 'rccam_turn', 'message': message, 'trigger_source': obs.get('trigger_source'), 'selected_text': obs.get('selected_text'), 'prediction': pred, 'generation_status': action.get('generation_status')})
    return {'retrieval': {'context_keys': list(context.keys())}, 'cognition': pred, 'observer': obs, 'control': action.get('budget_status'), 'action': action, 'memory': {'ledger_written': True}}

__all__ = ['process_persona_visual_turn']
