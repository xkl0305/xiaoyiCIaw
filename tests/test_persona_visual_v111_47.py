from __future__ import annotations

from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request, build_focus_enhanced_prompt
from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction, prepare_generation_context


def test_focus_request_fields_include_v111_47():
    """V111.47: detect_focus_request returns reference_policy, reference_priority, focus_generation_model."""
    focus = detect_focus_request('看看腿')
    assert focus.get('reference_policy') == 'priority_context_reference'
    assert focus.get('reference_priority') == ['outfit_image', 'scene_default_image', 'seed_avatar']
    assert focus.get('focus_generation_model') == 'seedream5.0_image_to_image'
    assert focus.get('scene_direct_send_when_available') is True
    assert focus.get('focus_generate_count') == 1


def test_stealth_peek_has_common_fields():
    f = detect_focus_request('偷偷看看你')
    assert f.get('reference_policy') == 'priority_context_reference'
    assert f.get('reference_priority') == ['outfit_image', 'scene_default_image', 'seed_avatar']
    assert f.get('focus_generation_model') == 'seedream5.0_image_to_image'


def test_blocked_sensitive_has_common_fields():
    f = detect_focus_request('裸')
    assert f.get('reference_policy') == 'priority_context_reference'
    assert f.get('focus_generation_model') == 'seedream5.0_image_to_image'


def test_safe_redirect_has_common_fields():
    f = detect_focus_request('胸')
    assert f.get('secondary_generation_allowed') is True
    assert f.get('reference_policy') == 'priority_context_reference'


def test_dynamic_extraction_has_common_fields():
    f = detect_focus_request('生成嘎嘎')
    assert f.get('focus_match_mode') == 'dynamic_extraction'
    assert f.get('reference_policy') == 'priority_context_reference'
    assert f.get('focus_generation_model') == 'seedream5.0_image_to_image'


def test_none_has_common_fields():
    f = detect_focus_request('你好')
    assert f.get('focus_match_mode') == 'none'
    assert f.get('reference_policy') == 'priority_context_reference'


def test_look_legs_dry_run():
    """看看腿 with 月羽云裳 stage hints: focus on body_focus legs, reference from outfit."""
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['轻微偏头'],
    }
    result = generate_from_prediction(
        dict(pred),
        text='（月羽云裳的薄纱裙摆随风飘了一下）',
        user_message='看看腿',
        dry_run=True,
    )
    assert result.get('status') == 'dry_run_ready'
    assert result.get('focus_generation_planned') is True
    assert result.get('reference_priority_source') == 'outfit_image'
    assert '月羽云裳_reference.jpg' in result.get('reference_image', '')
    assert result.get('scene_direct_send_planned') is True
    assert result.get('generated_image_target_count') == 1
    assert result.get('max_images_this_turn') == 2
    assert result.get('focus_prompt_enhanced') is True
    assert result.get('focus_prompt_style') == 'scene_enhanced'


def test_greeting_no_false_focus():
    """你好呀 with stage hints should NOT trigger face focus."""
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'happy', 'semantic_scene': 'greeting_scene',
        'emotion_signature': ['开心'], 'expression_hints': ['微笑'],
    }
    result = generate_from_prediction(
        dict(pred),
        text='（轻轻偏头，脸有点红）',
        user_message='你好呀',
        dry_run=True,
    )
    assert result.get('focus_target') == ''
    assert result.get('focus_label') == ''
    assert result.get('focus_generation_planned') is False
    assert result.get('reference_priority_source') == 'seed_avatar'
    assert result.get('max_images_this_turn') == 1
    assert result.get('focus_prompt_enhanced') is False


def test_build_focus_enhanced_prompt_legs():
    """build_focus_enhanced_prompt should return scene_enhanced data for legs focus."""
    result = build_focus_enhanced_prompt(
        focus_target='legs',
        focus_label='腿',
        mood='shy',
        semantic_scene='bashful_scene',
        outfit='moonfeather_robe',
        outfit_prompt_suffix='月白冰蓝渐变半透幻彩薄纱长裙',
        stage_hints='月羽云裳的薄纱裙摆随风飘了一下',
        emotion_signature=['害羞'],
        expression_hints=['脸红'],
    )
    assert result.get('focus_prompt_enhanced') is True
    assert result.get('focus_prompt_style') == 'scene_enhanced'
    preview = result.get('focus_prompt_preview', '')
    assert preview  # non-empty
    # Should contain action/expression/composition/atmosphere keywords
    assert '微微抬腿' in preview or '抬腿' in preview or '双腿' in preview or '展示' in preview


def test_enhanced_prompt_contains_scene_keywords():
    """Enhanced prompt for legs should contain scene/pose/blushing/legs related enhancement."""
    result = build_focus_enhanced_prompt(
        focus_target='legs',
        focus_label='腿',
        mood='shy',
        semantic_scene='bashful_scene',
        outfit='moonfeather_robe',
        outfit_prompt_suffix='月白冰蓝渐变半透幻彩薄纱长裙',
        stage_hints='月羽云裳的薄纱裙摆随风飘了一下',
        emotion_signature=['害羞', '配合'],
        expression_hints=['脸红', '偏头'],
    )
    enhanced = result.get('enhanced_focus_prompt', '')
    # Must have at least some of: pose/show/elegant/legs/composition/expression keywords
    keywords = ['腿', '展', '姿', '裙', '害羞', '镜头']
    found = sum(1 for kw in keywords if kw in enhanced)
    assert found >= 2, f'Enhanced prompt lacks scene enhancement keywords. Got: {enhanced[:300]}'


def test_enhanced_prompt_uses_outfit_suffix():
    """Enhanced prompt should incorporate outfit_prompt_suffix."""
    result = build_focus_enhanced_prompt(
        focus_target='tail', focus_label='尾巴',
        outfit='moonfeather_robe',
        outfit_prompt_suffix='月白冰蓝渐变半透幻彩薄纱长裙，古风立领盘扣，露肩高开衩',
        stage_hints='尾巴轻晃',
    )
    enhanced = result.get('enhanced_focus_prompt', '')
    assert '月白冰蓝' in enhanced or '薄纱' in enhanced or '云裳' in enhanced


def test_prepare_generation_context_focus_source_priority():
    """Focus source should prioritize user_message over text."""
    prepared = prepare_generation_context(
        {'mood': 'shy', 'semantic_scene': 'bashful_scene'},
        text='（轻轻偏头，脸有点红）',
        user_message='看看腿',
    )
    focus = prepared.get('focus', {})
    assert focus.get('focus_target') == 'legs', f"Expected legs but got {focus.get('focus_target')}"


def test_prepare_generation_context_no_false_face():
    """When user_message is 你好呀 and text has （轻轻偏头，脸有点红）, should NOT detect face focus."""
    prepared = prepare_generation_context(
        {'mood': 'happy', 'semantic_scene': 'greeting_scene'},
        text='（轻轻偏头，脸有点红）',
        user_message='你好呀',
    )
    focus = prepared.get('focus', {})
    assert focus.get('focus_target') == '', f"Expected no focus but got {focus.get('focus_target')}"


def test_reference_priority_outfit_image():
    """With 看看腿 + 月羽云裳, reference_priority_source should be outfit_image."""
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['轻微偏头'],
    }
    result = generate_from_prediction(dict(pred), text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看腿', dry_run=True)
    assert result.get('reference_priority_source') == 'outfit_image'


def test_max_images_this_turn_correct():
    """With 看看腿, max_images_this_turn should be 2 (1 focus image + 1 scene direct)."""
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['轻微偏头'],
    }
    result = generate_from_prediction(dict(pred), text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看腿', dry_run=True)
    assert result.get('max_images_this_turn') == 2
    assert result.get('generated_image_target_count') == 1
    assert result.get('scene_direct_send_planned') is True


def test_no_focus_seed_avatar_reference():
    """Without focus, reference_priority_source should be seed_avatar."""
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'happy', 'semantic_scene': 'greeting_scene',
        'emotion_signature': ['开心'], 'expression_hints': ['微笑'],
    }
    result = generate_from_prediction(dict(pred), text='你好呀', user_message='你好呀', dry_run=True)
    assert result.get('reference_priority_source') == 'seed_avatar'
    assert result.get('focus_generation_planned') is False
    assert result.get('focus_only_generation_mode') is False


def test_focus_generation_model_field():
    """focus_generation_model should be seedream5.0_image_to_image."""
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['脸红'],
    }
    result = generate_from_prediction(dict(pred), text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看腿', dry_run=True)
    assert result.get('focus_generation_model') == 'seedream5.0_image_to_image'


def test_send_image_paths_includes_scene_direct():
    """send_image_paths should include scene_direct_send_path when scene is available."""
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['脸红'],
    }
    result = generate_from_prediction(dict(pred), text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看腿', dry_run=True)
    assert len(result.get('send_image_paths', [])) >= 1
    assert 'bashful' in result.get('scene_direct_send_path', '')


def test_prepare_generation_context_with_stage_hints():
    """stage_hints should be extracted from parenthetical content in text."""
    prepared = prepare_generation_context(
        {'mood': 'shy', 'semantic_scene': 'bashful_scene'},
        text='（月羽云裳的薄纱裙摆随风飘了一下）',
        user_message='看看腿',
    )
    hints = prepared.get('stage_hints', '')
    assert '月羽云裳' in hints
    assert '裙摆' in hints


def test_focus_enhanced_for_ears():
    """Enhanced prompt for ears should contain ear-related enhancement."""
    result = build_focus_enhanced_prompt(
        focus_target='ears', focus_label='耳朵',
        mood='shy', outfit='moonfeather_robe',
    )
    assert result.get('focus_prompt_enhanced') is True
    enhanced = result.get('enhanced_focus_prompt', '')
    assert '耳朵' in enhanced or '耳' in enhanced


def test_focus_enhanced_for_tail():
    """Enhanced prompt for tail should contain tail-related enhancement."""
    result = build_focus_enhanced_prompt(
        focus_target='tail', focus_label='尾巴',
        mood='playful', outfit='moonfeather_robe',
    )
    enhanced = result.get('enhanced_focus_prompt', '')
    assert '尾巴' in enhanced or '尾' in enhanced


def test_focus_enhanced_for_eyes():
    """Enhanced prompt for eyes should contain eye-related enhancement."""
    result = build_focus_enhanced_prompt(
        focus_target='eyes', focus_label='眼睛',
        mood='gentle', outfit='moonfeather_robe',
    )
    enhanced = result.get('enhanced_focus_prompt', '')
    assert '眼' in enhanced
