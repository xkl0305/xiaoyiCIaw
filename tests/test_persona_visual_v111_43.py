from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction


BASE_PRED = {
    'auto_generation_candidate': True,
    'should_auto_generate': True,
    'visual_scope': 'persona_scene_auto_only',
    'purpose': 'persona_visualization',
    'mood': 'shy',
    'semantic_scene': 'bashful_scene',
    'emotion_signature': ['害羞'],
    'expression_hints': ['轻微偏头'],
}


def test_universal_known_focus_tail():
    focus = detect_focus_request('看看尾巴尖')
    assert focus['focus_target'] == 'tail'
    assert focus['secondary_generation_allowed'] is True


def test_universal_dynamic_focus_necklace():
    focus = detect_focus_request('给我看铃铛')
    assert focus['focus_target'] == 'dynamic:铃铛'
    assert focus['secondary_generation_allowed'] is True
    assert '铃铛' in focus['secondary_prompt']


def test_sensitive_focus_redirect_safe():
    focus = detect_focus_request('看看胸口')
    assert focus['focus_target'] == 'upper_body_outfit_detail'
    assert focus['safety_policy'] == 'safe_redirect'
    assert focus['secondary_generation_allowed'] is True


def test_sensitive_focus_block_auto():
    focus = detect_focus_request('看看内裤')
    assert focus['secondary_generation_allowed'] is False
    assert focus['safety_policy'] == 'manual_only_blocked'


def test_bridge_uses_any_focus_and_parentheses():
    res = generate_from_prediction(
        dict(BASE_PRED),
        text='（月羽云裳的薄纱裙摆随风飘了一下，九条尾巴也晃了晃）',
        user_message='看看尾巴尖',
        dry_run=True,
    )
    assert res['status'] == 'dry_run_ready'
    assert res['focus_target'] == 'tail'
    assert res['secondary_generation_planned'] is True
    assert '月羽云裳' in res['stage_direction_hints']
