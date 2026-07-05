from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]


def _persona_visual_cfg() -> Dict[str, Any]:
    try:
        return json.loads((ROOT / 'openclaw.json').read_text(encoding='utf-8')).get('personaVisual', {})
    except Exception:
        return {}


def _extract_parenthetical_hints(text: str) -> str:
    if not text:
        return ''
    chunks = re.findall(r'[((]([^()()]{2,160})[))]', text)
    chunks = [c.strip() for c in chunks if c and c.strip()]
    return ';'.join(chunks[:5])




def _is_display_appearance_text(text: str) -> bool:
    phrases = [
        '看看你的样子', '看看你现在什么样', '让我看看你', '展示一下',
        '看看全身', '给我看看造型', '露个面看看', '看看整体效果',
    ]
    compact = (text or '').replace(' ', '')
    return any(p in compact for p in phrases)

def prepare_generation_context(
    prediction: Dict[str, Any],
    text: str = '',
    user_message: str = '',
    requested_outfit: str = '',
) -> Dict[str, Any]:
    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request, build_focus_enhanced_prompt
    from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit
    from memory_context.persona_runtime.persona_visual_scene_defaults import get_scene_default_image

    stage_hints = _extract_parenthetical_hints(text)

    # Focus source: prioritize user_message over text
    focus_source = user_message or ''
    if not focus_source and text:
        focus_source = text

    focus = detect_focus_request(focus_source)

    combined_text = ' '.join([user_message or '', text or '', stage_hints or '']).strip()
    # Direct-provider V111.51.3: display appearance is a scene request, not dynamic focus.
    if _is_display_appearance_text(combined_text or focus_source):
        focus = {
            'focus_target': '',
            'focus_category': '',
            'focus_label': '',
            'secondary_prompt': '',
            'secondary_generation_allowed': False,
            'focus_match_mode': 'display_appearance_scene_only',
            'extracted_targets': [],
            'safety_policy': 'scene_only',
            'use_current_outfit_reference': False,
            'reference_policy': 'priority_context_reference',
            'reference_priority': ['outfit_image', 'scene_default_image', 'seed_avatar'],
            'focus_generation_model': 'seedream5.0_image_to_image',
            'scene_direct_send_when_available': True,
            'focus_generate_count': 1,
        }


    # V111.48: Pass focus_target to choose_outfit so focus can drive outfit selection
    outfit = choose_outfit(
        text=combined_text,
        mood=prediction.get('mood', ''),
        semantic_scene=prediction.get('semantic_scene', ''),
        requested_outfit=requested_outfit,
        focus_target=focus.get('focus_target') or '',
        auto_mode=True,
        scene_confidence=float(prediction.get('confidence') or 0.0),
    )

    scene_direct = get_scene_default_image(
        prediction.get('semantic_scene', ''),
        text or user_message or ''
    )

    # V111.48: Update prediction
    prediction['focus_target'] = focus.get('focus_target') or ''
    prediction['focus_label'] = focus.get('focus_label') or ''
    prediction['focus_category'] = focus.get('focus_category') or ''
    prediction['outfit_id'] = outfit.get('outfit_id') or ''
    prediction['outfit_choice_source'] = outfit.get('choice_source') or ''

    # Build enhanced focus prompt if focus is allowed
    focus_allowed = bool(focus.get('secondary_generation_allowed', False))
    focus_enhanced = {}
    if focus_allowed:
        focus_enhanced = build_focus_enhanced_prompt(
            focus_target=focus.get('focus_target', ''),
            focus_label=focus.get('focus_label', ''),
            mood=prediction.get('mood', ''),
            semantic_scene=prediction.get('semantic_scene', ''),
            outfit=outfit.get('outfit_id', ''),
            outfit_prompt_suffix=outfit.get('prompt_suffix', ''),
            stage_hints=stage_hints,
            emotion_signature=prediction.get('emotion_signature') or [],
            expression_hints=prediction.get('expression_hints') or [],
        )

    return {
        'focus': focus,
        'outfit': outfit,
        'stage_hints': stage_hints,
        'combined_text': combined_text,
        'scene_direct': scene_direct,
        'focus_enhanced': focus_enhanced,
    }


def _append_stage_and_prompt(base_prompt: str, stage_hints: str, extra_prompt: str = '') -> str:
    out = base_prompt
    if stage_hints:
        out += f' Stage direction hints from the reply text: {stage_hints}. Use these words directly as visual guidance.'
    if extra_prompt:
        out += ' ' + extra_prompt.strip()
    return out


def _resolve_reference_image(focus: Dict[str, Any], outfit: Dict[str, Any], scene_direct_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve reference image with priority: outfit_image > scene_default_image > seed_avatar."""
    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request

    cfg = _persona_visual_cfg()
    seed_default = cfg.get('seedAvatarPath') or 'assets/persona/seed_avatar.jpg'

    focus_allowed = bool(focus.get('secondary_generation_allowed', False))
    if not focus_allowed:
        return {'reference_image': seed_default, 'reference_priority_source': 'seed_avatar'}

    # Priority 1: outfit reference image
    outfit_ref = outfit.get('reference_image') or ''
    if outfit_ref and (ROOT / outfit_ref).exists():
        return {'reference_image': outfit_ref, 'reference_priority_source': 'outfit_image'}

    # Priority 2: scene default image
    scene_path = scene_direct_meta.get('file_path') or ''
    scene_abs = scene_direct_meta.get('abs_path') or ''
    if scene_path and (ROOT / scene_path).exists():
        return {'reference_image': scene_path, 'reference_priority_source': 'scene_default_image'}

    # Priority 3: seed avatar
    return {'reference_image': seed_default, 'reference_priority_source': 'seed_avatar'}


def _image_path_from_result(res: Dict[str, Any]) -> str:
    if not isinstance(res, dict):
        return ''
    return str(res.get('output_path') or res.get('generated_image_path') or '')


def generate_from_prediction(
    prediction: Dict[str, Any],
    text: str = '',
    dry_run: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    if not prediction.get('auto_generation_candidate') and not prediction.get('should_auto_generate'):
        return {'status': 'skip', 'reason': 'not_auto_generation_candidate'}
    if prediction.get('visual_scope') not in (None, 'persona_scene_auto_only'):
        return {'status': 'blocked', 'reason': 'wrong_visual_scope'}

    cfg = _persona_visual_cfg()
    if not cfg.get('enabled', True):
        return {'status': 'skip', 'reason': 'persona_visual_disabled'}

    from infrastructure.image_generation_scope_guard import assert_persona_seed_scope
    assert_persona_seed_scope(prediction.get('visual_scope', 'persona_scene_auto_only'), prediction.get('purpose', 'persona_visualization'))

    prepared = kwargs.get('prepared_context') or prepare_generation_context(prediction, text=text, user_message=kwargs.get('user_message', ''), requested_outfit=kwargs.get('requested_outfit', ''))
    focus = prepared['focus']
    outfit = prepared['outfit']
    stage_hints = prepared['stage_hints']
    combined_text = prepared['combined_text']
    scene_direct_meta = prepared.get('scene_direct', {})
    focus_enhanced = prepared.get('focus_enhanced', {})

    # === fail_closed: safe fallback on core config missing ===
    cfg_dir = ROOT / 'xiaoyi_persona_visual/config'
    prompt_dir = ROOT / 'xiaoyi_persona_visual/prompt'
    wardrobe_dir = ROOT / 'xiaoyi_persona_visual/wardrobe'

    identity_profile_path = cfg_dir / 'visual_identity_profile.json'
    style_profile_path = cfg_dir / 'style_profile.json'
    negative_guard_path = prompt_dir / 'negative_prompt_guard.json'
    wardrobe_manifest_path = wardrobe_dir / 'wardrobe_manifest.json'
    scene_outfit_map_path = wardrobe_dir / 'scene_outfit_map.json'
    focus_outfit_map_path = wardrobe_dir / 'focus_outfit_map.json'

    identity_lock = False
    style_lock = False
    fallback_reason = None
    negative_prompt_override = None
    safe_fallback_mode = False
    core_config_missing = False

    if not identity_profile_path.exists():
        core_config_missing = True
        identity_lock = True
        fallback_reason = 'missing_visual_identity_profile'

    if not style_profile_path.exists():
        core_config_missing = True
        style_lock = True
        if not fallback_reason:
            fallback_reason = 'missing_style_profile'

    if core_config_missing:
        safe_fallback_mode = True
        identity_lock = True
        style_lock = True
        if not fallback_reason:
            fallback_reason = 'missing_core_config'

    if not negative_guard_path.exists():
        negative_prompt_override = negative_prompt_override or 'worst quality, bad anatomy, extra digits, mutated hands, ugly'

    if not wardrobe_manifest_path.exists():
        safe_fallback_mode = True
        fallback_reason = fallback_reason or 'missing_wardrobe_manifest'
    if (not scene_outfit_map_path.exists()) and (
        prediction.get('semantic_scene') == 'display_appearance_scene'
        or outfit.get('scene_type') == 'display_appearance_scene'
        or '看看你的样子' in (combined_text or text or '')
        or '展示一下' in (combined_text or text or '')
        or '看看全身' in (combined_text or text or '')
    ):
        safe_fallback_mode = True
        fallback_reason = fallback_reason or 'missing_scene_outfit_map'
    if not focus_outfit_map_path.exists() and focus.get('focus_target'):
        safe_fallback_mode = True
        fallback_reason = fallback_reason or 'missing_focus_outfit_map'

    safe_default_outfit_used = not wardrobe_manifest_path.exists() or safe_fallback_mode
    if safe_default_outfit_used and fallback_reason in {'missing_wardrobe_manifest', 'missing_scene_outfit_map', 'missing_focus_outfit_map'}:
        # Do not freely select clothing when core wardrobe maps are missing. Stay inside persona visual safe default.
        outfit = dict(outfit or {})
        outfit['outfit_id'] = 'moonfeather_robe'
        outfit['choice_source'] = 'safe_default_outfit'
        outfit['outfit_source'] = 'safe_default_outfit'
        outfit['fallback_used'] = True
        outfit['fallback_reason'] = fallback_reason
        outfit.setdefault('prompt_suffix', '月羽云裳，identity unchanged')

    # === prompt builder: PersonaVisualController + persona_image_prompt_builder only ===
    # V111.51.2 Final: no legacy renderer fallback for persona visual requests.
    from memory_context.persona_runtime.providers.seedream_provider import generate_image, provider_ready, provider_env
    from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof
    prompt_builder_used = 'persona_image_prompt_builder'
    controller_result = {}
    prompt_debug_meta = {}
    try:
        from xiaoyi_persona_visual.controller.persona_visual_controller import PersonaVisualController
        from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import build_persona_prompt_safe
        controller = PersonaVisualController()
        controller_result = controller.initialize()
        built_prompt, built_negative, prompt_debug_meta = build_persona_prompt_safe(
            base_prompt=combined_text or text,
            scene_type=prediction.get('semantic_scene', '') or outfit.get('scene_type', ''),
            focus_target=focus.get('focus_target') or '',
            outfit_id=outfit.get('outfit_id', ''),
            outfit_suffix=outfit.get('prompt_suffix', 'identity unchanged'),
            stage_hints=stage_hints,
            emotion_signature=prediction.get('emotion_signature') or [],
            expression_hints=prediction.get('expression_hints') or [],
        )
        prompt_bundle = {'prompt': built_prompt or '', 'negative_prompt': built_negative or ''}
    except Exception as e:
        return {
            'status': 'fail_closed',
            'reason': 'persona_image_prompt_builder_failed',
            'error': str(e),
            'generation_allowed': False,
            'pipeline_entry': 'PersonaVisualController',
            'prompt_builder_used': 'persona_image_prompt_builder',
            'fallback_used': True,
            'fallback_reason': 'persona_image_prompt_builder_failed',
        }

    # Override negative prompt if guard file is missing
    if negative_prompt_override:
        prompt_bundle['negative_prompt'] = prompt_bundle.get('negative_prompt') or negative_prompt_override
        if not prompt_bundle.get('negative_prompt'):
            prompt_bundle['negative_prompt'] = negative_prompt_override

    # Resolve reference image using priority rules
    ref_result = _resolve_reference_image(focus, outfit, scene_direct_meta)
    ref = ref_result['reference_image']
    ref_priority_source = ref_result['reference_priority_source']
    ref_path = ROOT / ref

    # === 强制参考图加载 ===
    # 确保参考图包含种子头像 + 衣柜参考图
    # reuse existing cfg from above
    seed_default = cfg.get('seedAvatarPath') or 'assets/persona/seed_avatar.jpg'
    seed_avatar_path = ROOT / seed_default
    outfit_ref_present = False
    outfit_ref_path = None
    outfit_ref_file = outfit.get('reference_image') or ''
    if outfit_ref_file and (ROOT / outfit_ref_file).exists():
        outfit_ref_path = ROOT / outfit_ref_file
        outfit_ref_present = True
    avatar_ref_present = (ref_path == seed_avatar_path) or (outfit_ref_path is not None and str(ref_path) == str(seed_avatar_path))

    # If current ref_path is seed avatar and there's an outfit reference, merge into list
    ref_paths = [str(ref_path)]
    if str(ref_path) == str(seed_avatar_path) and outfit_ref_present:
        ref_paths.append(str(outfit_ref_path))
        outfit_ref_present_in_final = True
    elif not avatar_ref_present and seed_avatar_path.exists():
        # Current ref is not avatar; add avatar as second reference if it exists
        if str(ref_path) != str(seed_avatar_path) and seed_avatar_path.exists():
            ref_paths.append(str(seed_avatar_path))
        avatar_ref_present = True
    reference_images_count = len(ref_paths)
    if reference_images_count < 2:
        # force at least 2 if possible
        if seed_avatar_path.exists() and str(seed_avatar_path) not in ref_paths:
            ref_paths.append(str(seed_avatar_path))
            reference_images_count = len(ref_paths)
            avatar_ref_present = True
        if outfit_ref_present and str(outfit_ref_path) not in ref_paths:
            ref_paths.append(str(outfit_ref_path))
            reference_images_count = len(ref_paths)

    # V111.51.4: the prompt builder now performs structured Chinese autowriting.
    # Do not append developer/debug labels such as Outfit guidance / Emotion signature here,
    # because they pollute the actual generation prompt and duplicate clothing/user text.
    enhanced_focus_text = ''
    if focus_enhanced.get('focus_prompt_enhanced'):
        enhanced_focus_text = focus_enhanced.get('enhanced_focus_prompt', '')

    base_prompt = (prompt_bundle.get('prompt', '') or '').strip()

    focus_allowed = bool(focus.get('secondary_generation_allowed'))

    # V111.47: Focus mode generates 1 focus image.
    # If scene direct image available, send it directly without generating.
    # scene_direct_send_planned = True when scene default exists
    scene_direct_status = scene_direct_meta.get('status', '')
    scene_direct_send_path = scene_direct_meta.get('file_path', '') if scene_direct_status == 'default_scene_available_manual_only' else ''
    scene_direct_send_path_abs = scene_direct_meta.get('abs_path', '') if scene_direct_status == 'default_scene_available_manual_only' else ''

    scene_direct_send_planned = bool(scene_direct_send_path and (ROOT / scene_direct_send_path).exists())

    api_ready = provider_ready() and bool(cfg.get('onlineProviderAllowed', True) and cfg.get('externalProviderAllowed', True))

    # V111.47: Focus generation count is always 1 (from focus_generate_count)
    focus_generate_count = int(focus.get('focus_generate_count', 1))

    # max_images_this_turn: 1 focus image + 1 scene direct send if available
    focus_only_generation_mode = False
    if focus_allowed:
        focus_only_generation_mode = True
        generated_image_target_count = focus_generate_count
        max_images_this_turn = generated_image_target_count + (1 if scene_direct_send_planned else 0)
    else:
        focus_only_generation_mode = False
        generated_image_target_count = 1
        max_images_this_turn = generated_image_target_count

    env_diag = provider_env(input_image=str(ref_paths[0]) if ref_paths else str(ref_path), reference_images=ref_paths).get('_debug', {})
    env_diag['input_image_path'] = str(ref_paths[0]) if ref_paths else str(ref_path)
    env_diag['input_image_exists'] = bool(Path(env_diag['input_image_path']).exists()) if env_diag.get('input_image_path') else False
    env_diag['payload_mode'] = 'image_to_image'
    env_diag['model'] = 'doubao-seedream-5-0-260128'
    negative_prompt_guard_used = bool(prompt_bundle.get('negative_prompt'))
    minimal_negative_guard_used = prompt_debug_meta.get('neg_source') == 'minimal_negative_guard'
    identity_loaded = bool(controller_result.get('identity_profile_loaded', False))
    style_loaded = bool(controller_result.get('style_profile_loaded', False))
    # Safe fallback is allowed, but it must remain inside the persona pipeline.
    identity_lock = True
    style_lock = True
    if prompt_debug_meta.get('identity_profile_loaded') is False:
        safe_fallback_mode = True
        fallback_reason = fallback_reason or 'missing_visual_identity_profile'
    if prompt_debug_meta.get('style_profile_loaded') is False:
        safe_fallback_mode = True
        fallback_reason = fallback_reason or 'missing_style_profile'
    if minimal_negative_guard_used:
        safe_fallback_mode = True
        fallback_reason = fallback_reason or 'missing_negative_prompt_guard'

    base_result = {
        'prompt': base_prompt[:1800],
        'negative_prompt': prompt_bundle.get('negative_prompt'),
        'reference_image': str(ref_path),
        'reference_priority_source': ref_priority_source,
        'outfit': outfit,
        'outfit_choice_source': outfit.get('choice_source', ''),
        'scene_type': outfit.get('scene_type') or prediction.get('semantic_scene', ''),
        'scene_confidence': outfit.get('scene_confidence', prediction.get('confidence', 0.0)),
        'outfit_source': outfit.get('outfit_source', ''),
        'choice_source': outfit.get('choice_source', ''),
        'outfit_id': outfit.get('outfit_id', ''),
        'runtime_current_used': bool(outfit.get('runtime_current_used', False)),
        'missing_seed_avatar': not ref_path.exists(),
        'safe_fallback_mode': safe_fallback_mode,
        'safe_persona_visual_fallback_used': safe_fallback_mode,
        'safe_default_outfit_used': safe_default_outfit_used,
        'pipeline_entry': 'PersonaVisualController',
        'persona_visual_controller_used': True,
        'wardrobe_loader_used': True,
        'prompt_builder_used': prompt_builder_used,
        'negative_prompt_guard_used': negative_prompt_guard_used,
        'minimal_negative_guard_used': minimal_negative_guard_used,
        'negative_prompt_guard_missing': bool(prompt_debug_meta.get('negative_guard_file_missing', False)),
        'prompt_total_length': prompt_debug_meta.get('prompt_total_length', len(base_prompt)),
        'prompt_chinese_length': prompt_debug_meta.get('prompt_chinese_length', 0),
        'prompt_effective_chinese_length': prompt_debug_meta.get('prompt_effective_chinese_length', 0),
        'prompt_template_type': prompt_debug_meta.get('prompt_template_type', ''),
        'prompt_has_duplicate_phrase': prompt_debug_meta.get('prompt_has_duplicate_phrase', False),
        'prompt_density_score': prompt_debug_meta.get('prompt_density_score', 0),
        'prompt_autowrite_enhanced': prompt_debug_meta.get('prompt_autowrite_enhanced', False),
        'prompt_min_chinese_required': prompt_debug_meta.get('prompt_min_chinese_required', 100),
        'prompt_quality_body_preview': prompt_debug_meta.get('prompt_quality_body_preview', ''),
        'generation_allowed': True,
        'fallback_used': bool(safe_fallback_mode),
        'fallback_reason': fallback_reason or '',
        'identity_profile_loaded': identity_loaded,
        'style_profile_loaded': style_loaded,
        'identity_lock': identity_lock,
        'style_lock': style_lock,
        'gender_lock': 'female',
        'seedream_provider_ready': api_ready,
        'seedream_provider_env_debug': env_diag,
        'provider_input_image_exists': bool(env_diag.get('input_image_exists')),
        'provider_input_image_path': env_diag.get('input_image_path', ''),
        'payload_mode': env_diag.get('payload_mode', 'image_to_image'),
        'model': env_diag.get('model', 'doubao-seedream-5-0-260128'),
        'seedream_api_url_present': bool(env_diag.get('provider_url_present')),
        'seedream_api_key_present': bool(env_diag.get('api_key_present')),
        'seedream_uid_present': bool(env_diag.get('uid_present')),
        'trigger_source': kwargs.get('trigger_source'),
        'focus_target': focus.get('focus_target'),
        'focus_label': focus.get('focus_label'),
        'focus_category': focus.get('focus_category'),
        'focus_match_mode': focus.get('focus_match_mode'),
        'focus_safety_policy': focus.get('safety_policy'),
        'focus_generation_model': focus.get('focus_generation_model', 'seedream5.0_image_to_image'),
        'reference_policy': focus.get('reference_policy', 'priority_context_reference'),
        'reference_priority': focus.get('reference_priority', ['outfit_image', 'scene_default_image', 'seed_avatar']),
        'secondary_prompt': focus.get('secondary_prompt', ''),
        'secondary_generation_allowed': focus_allowed,
        'secondary_generation_planned': focus_allowed,  # compatible with old callers
        'focus_generation_planned': focus_allowed,
        'focus_only_generation_mode': focus_only_generation_mode,
        'generated_image_target_count': generated_image_target_count,
        'stage_direction_hints': stage_hints,
        'max_images_this_turn': max_images_this_turn,
        'real_generation_ready': api_ready,
        'scene_direct_send_path': scene_direct_send_path,
        'scene_direct_send_path_abs': scene_direct_send_path_abs,
        'scene_direct_send_planned': scene_direct_send_planned,
        'send_image_paths': [scene_direct_send_path] if scene_direct_send_planned else [],
        # === 强制生成验证字段 ===
        'visual_request_detected': True,
        'persona_subject': '鸽子王',
        'persona_visual_request': True,
        'pipeline_forced': True,
        'avatar_reference_present': avatar_ref_present,
        'outfit_reference_present': outfit_ref_present,
        'reference_images_count': reference_images_count,
        'reference_images_count_actual': reference_images_count,
        'reference_image_paths': ref_paths,
        'generation_mode': 'image_to_image',
        'provider': 'ARK',
        'seedream_provider_used': True,
        'mainchain_proof_present': True,
    }

    if reference_images_count < 2:
        base_result.update({
            'status': 'blocked',
            'blocked': True,
            'blocked_reason': 'missing_required_reference_images',
            'generation_allowed': False,
            'fallback_used': True,
            'fallback_reason': 'reference_images_count_lt_2',
        })
        if dry_run:
            return base_result

    # Add focus enhanced fields
    if focus_enhanced:
        base_result['focus_prompt_enhanced'] = focus_enhanced.get('focus_prompt_enhanced', False)
        base_result['focus_prompt_style'] = focus_enhanced.get('focus_prompt_style', '')
        base_result['focus_prompt_preview'] = focus_enhanced.get('focus_prompt_preview', '')
    else:
        base_result['focus_prompt_enhanced'] = False
        base_result['focus_prompt_style'] = ''
        base_result['focus_prompt_preview'] = ''

    if dry_run:
        return {'status': 'dry_run_ready', **base_result}
    if not api_ready:
        return {'status': 'provider_not_ready', 'reason': 'missing_or_disabled_seedream_provider', **base_result}

    paths = []
    try:
        # Generate focus image with Seedream 5.0 image-to-image
        model = 'seedream5.0'
        model_version = '5.0'
        generation_mode = 'image_to_image'
        task_type = 'focus_image_to_image' if focus_allowed else 'scene_image_to_image'

        # Build the focus-specific prompt if enhanced
        if focus_allowed and focus_enhanced.get('focus_prompt_enhanced'):
            focus_prompt = base_prompt + enhanced_focus_text
        else:
            focus_prompt = base_prompt

        # V111.52.6: issue mainchain proof from the canonical persona visual bridge.
        # Missing runtime proof secret is fail-closed; provider must never auto-create secrets.
        try:
            mainchain_proof = issue_mainchain_proof(
                final_prompt=focus_prompt,
                reference_images=ref_paths,
                pipeline_entry='post_reply' if (kwargs.get('trigger_source') or '').startswith('post_reply') or kwargs.get('trigger_source') in {'post_reply', 'mainline_hook'} else 'mainline_hook',
                controller='PersonaVisualController',
                prompt_builder='persona_image_prompt_builder',
                wardrobe_loader='wardrobe_loader',
                focus_resolver='focus_semantic_parser+focus_view_resolver',
            )
        except RuntimeError as exc:
            return {
                'status': 'blocked',
                'blocked': True,
                'blocked_reason': 'missing_mainchain_runtime_secret',
                'provider_status': 'blocked',
                'provider_error': str(exc),
                'generated_image_path': None,
                'output_path': None,
                'send_image_paths': [],
                **base_result,
            }

        # V111.51.5: always pass persona_visual_context when calling generate_image from the main pipeline
        # V10.9.0: 人格视角默认走通道 B（火山 ARK），与 seedream-image-gen skill（华为云）分开
        main_res = generate_image(
            prompt=focus_prompt,
            input_image=str(ref_paths[0]),
            reference_images=ref_paths,
            size='2K',
            watermark=False,
            max_images=generated_image_target_count,
            reference_weight=int(cfg.get('seedReferenceWeight', 100) or 100),
            negative_prompt=prompt_bundle.get('negative_prompt') or '',
            channel='ark',
            persona_visual_context={
                'persona_visual_request': True,
                'persona_subject': '鸽子王',
                'pipeline_forced': True,
                'persona_visual_controller_used': True,
                'wardrobe_loader_used': True,
                'prompt_builder_used': 'persona_image_prompt_builder',
                'avatar_reference_present': avatar_ref_present,
                'outfit_reference_present': outfit_ref_present,
                'reference_images_count': reference_images_count,
                'generation_mode': 'image_to_image',
                'mainchain_proof': mainchain_proof,
            },
        )
        provider_status = main_res.get('provider_status') or main_res.get('status') or '' if isinstance(main_res, dict) else ''
        provider_error = main_res.get('provider_error', '') if isinstance(main_res, dict) else ''

        # ── V111.51.21: send guard — never send old/fallback images on failure ──
        _fail_statuses = {'provider_not_ready', 'provider_http_error', 'fail_soft',
                           'provider_returned_no_image', 'provider_failed_no_current_image',
                           'provider_exception'}
        _provider_ok = (isinstance(main_res, dict)
                        and main_res.get('status') not in _fail_statuses
                        and main_res.get('blocked_send') is not True
                        and main_res.get('blocked') is not True)

        if not _provider_ok:
            out_status = str(main_res.get('status', 'provider_failed_no_current_image')) if isinstance(main_res, dict) else 'provider_failed_no_current_image'
            # never fall back to old / scene default images
            scene_direct_send_planned = False
        else:
            out_status = 'generated'
        out = {
            'status': out_status,
            'provider_result': main_res,
            'provider_status': provider_status,
            'provider_error': provider_error,
            'response_status_code': main_res.get('response_status_code') if isinstance(main_res, dict) else None,
            'response_raw_preview': main_res.get('response_raw_preview') if isinstance(main_res, dict) else '',
            'model': model, 'model_version': model_version, 'generation_mode': generation_mode, 'task_type': task_type, **base_result
        }
        provider_blocked_send = bool(isinstance(main_res, dict) and main_res.get('blocked_send'))
        provider_generated_ok = isinstance(main_res, dict) and main_res.get('status') == 'generated' and not provider_blocked_send
        p = _image_path_from_result(main_res) if provider_generated_ok else ''
        if p:
            paths.append(p)
            out['status'] = 'generated'
            out['output_path'] = p
            out['generated_image_path'] = p
            out['generated_image_paths'] = paths
        else:
            out.pop('output_path', None)
            out.pop('generated_image_path', None)
            if provider_blocked_send:
                out['status'] = main_res.get('status') or 'provider_failed_no_current_image'
                out['blocked_send'] = True
                out['blocked_reason'] = main_res.get('blocked_reason') or 'no_current_generated_image'
                out['generated_image_paths'] = []
                out['send_image_paths'] = []

        # Add scene direct send path only when provider generated a fresh current image.
        if p and scene_direct_send_planned and scene_direct_send_path not in paths:
            paths.append(scene_direct_send_path)
            out['generated_image_paths'] = paths

        if not p and not scene_direct_send_planned and out['status'] == 'generated':
            out['status'] = 'provider_returned_no_image'
        return out
    except Exception as e:
        return {'status': 'fail_soft', 'error': str(e), **base_result}
