from __future__ import annotations
from typing import Any

def run(user_message: str = '', assistant_message: str = '', lobster_message: str = '', reply_text: str = '', final_reply: str = '', draft_reply: str = '', **kwargs: Any):
    try:
        from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
        obs = observe_turn(
            user_message=user_message,
            assistant_message=assistant_message or draft_reply or reply_text,
            lobster_message=lobster_message,
            reply_text=reply_text,
            final_reply=final_reply,
            context=kwargs.get('context') or {},
            persona_state=kwargs.get('persona_state') or {},
        )
        pred = obs.get('prediction', {})
        return {
            'status': 'ok',
            'visual_checked': True,
            'phase': 'pre_reply',
            'auto_generation_candidate': pred.get('auto_generation_candidate', False),
            'auto_generation_executed': False,
            'generation_status': 'precheck_only',
            'mood': pred.get('mood'),
            'semantic_scene': pred.get('semantic_scene'),
            'confidence': pred.get('confidence'),
            'confidence_level': pred.get('confidence_level'),
            'trigger_source': obs.get('trigger_source'),
            'selected_text': obs.get('selected_text'),
            'emotion_signature': pred.get('emotion_signature'),
            'expression_hints': pred.get('expression_hints'),
        }
    except Exception as e:
        return {'status': 'fail_soft', 'error': str(e), 'visual_checked': False, 'phase': 'pre_reply'}
