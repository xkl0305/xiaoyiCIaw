from __future__ import annotations
from typing import Any

def _ensure_persona_visual_registered() -> dict:
    try:
        from xiaoyi_persona_visual.registry.register_persona_visual import register_persona_visual
        return register_persona_visual(app=None)
    except Exception as e:
        return {'registered': False, 'error': str(e)}


def run(user_message: str = '', assistant_message: str = '', lobster_message: str = '', reply_text: str = '', final_reply: str = '', draft_reply: str = '', **kwargs: Any):
    try:
        registration = _ensure_persona_visual_registered()
        from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
        from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction, prepare_generation_context
        from memory_context.persona_runtime.persona_visual_dedupe_gate import make_dedupe_key, reserve_once

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
        selected_text = obs.get('selected_text', '')
        prepared = prepare_generation_context(pred, text=selected_text, user_message=user_message, requested_outfit=kwargs.get('requested_outfit', ''))
        focus = prepared.get('focus', {})
        outfit = prepared.get('outfit', {})
        if not pred.get('auto_generation_candidate'):
            gen = {'status': 'skip', 'reason': 'below_auto_threshold'}
        else:
            key = kwargs.get('dedupe_key') or make_dedupe_key(selected_text, pred, kwargs.get('request_id', ''))
            reserve = reserve_once(key, int(kwargs.get('dedupe_window_seconds', 45)), {
                'mood': pred.get('mood'),
                'scene': pred.get('semantic_scene'),
                'focus': pred.get('focus_target'),
                'outfit': pred.get('outfit_id'),
                'text_preview': selected_text[:120],
            })
            if not reserve.get('allowed'):
                gen = {'status': 'deduped_skip', 'reason': reserve.get('reason'), 'dedupe_key': key}
            else:
                gen = generate_from_prediction(
                    pred,
                    text=selected_text,
                    user_message=user_message,
                    dry_run=kwargs.get('dry_run', False),
                    trigger_source=obs.get('trigger_source'),
                    prepared_context=prepared,
                )
        return {
            'status': 'ok',
            'visual_checked': True,
            'phase': 'post_reply',
            'auto_generation_candidate': pred.get('auto_generation_candidate', False),
            'auto_generation_executed': gen.get('status') == 'generated',
            'generation_status': gen.get('status'),
            'generated_image_path': gen.get('output_path') or gen.get('generated_image_path'),
            'generated_image_paths': gen.get('generated_image_paths') or [],
            'secondary_generated_image_path': gen.get('secondary_generated_image_path'),
            'fallback_image_path': gen.get('fallback_image_path'),
            'mood': pred.get('mood'),
            'semantic_scene': pred.get('semantic_scene'),
            'confidence': pred.get('confidence'),
            'confidence_level': pred.get('confidence_level'),
            'trigger_source': obs.get('trigger_source'),
            'selected_text': selected_text,
            'focus': focus,
            'outfit': outfit,
            'emotion_signature': pred.get('emotion_signature'),
            'expression_hints': pred.get('expression_hints'),
            'generation': gen,
            'persona_visual_registration': registration,
            'register_persona_visual_called': bool(registration.get('registered')),
            'pipeline_entry': gen.get('pipeline_entry'),
            'prompt_builder_used': gen.get('prompt_builder_used'),
            'negative_prompt_guard_used': gen.get('negative_prompt_guard_used'),
            'provider_ready': gen.get('seedream_provider_ready'),
            'generation_allowed': gen.get('generation_allowed'),
            'focus_target': focus.get('focus_target') or gen.get('focus_target'),
            'scene_type': pred.get('semantic_scene') or gen.get('scene_type'),
            'wardrobe_loader_used': gen.get('wardrobe_loader_used'),
            'reference_images_count_actual': gen.get('reference_images_count_actual') or gen.get('reference_images_count'),
            'provider_input_image_path': gen.get('provider_input_image_path'),
            'blocked_send': gen.get('blocked_send'),
            'http_client_used': gen.get('http_client_used'),
            'requests_available': gen.get('requests_available'),
            'mainchain_proof_present': gen.get('mainchain_proof_present'),
            'mainchain_proof_valid': gen.get('mainchain_proof_valid'),
            'blocked_reason': gen.get('blocked_reason'),
            'send_image_paths': gen.get('send_image_paths') or gen.get('generated_image_paths') or [],
        }
    except Exception as e:
        return {'status': 'fail_soft', 'error': str(e), 'visual_checked': False, 'phase': 'post_reply'}
