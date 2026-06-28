from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit
from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction, prepare_generation_context
from memory_context.persona_runtime.persona_visual_dedupe_gate import make_dedupe_key


def _prediction():
    return {
        'auto_generation_candidate': True,
        'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only',
        'purpose': 'persona_visualization',
        'mood': 'shy',
        'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'],
        'expression_hints': ['轻微偏头'],
    }


def test_stealth_peek_is_not_dynamic_you():
    res = detect_focus_request('偷偷看看你')
    assert res['secondary_generation_allowed'] is False
    assert res['focus_target'] == ''
    assert res['focus_match_mode'] == 'scene_only_stealth_peek'


def test_universal_focus_tail_and_block_sensitive():
    assert detect_focus_request('看看尾巴尖')['focus_target'] == 'tail'
    blocked = detect_focus_request('看看内裤')
    assert blocked['focus_target'] == 'blocked_sensitive'
    assert blocked['secondary_generation_allowed'] is False


def test_safe_redirect_chest():
    res = detect_focus_request('看看胸口')
    assert res['focus_target'] == 'upper_body_outfit_detail'
    assert res['secondary_generation_allowed'] is True


def test_outfit_switch_uses_runtime_state_not_static_config():
    outfit = choose_outfit(text='下次穿月羽云裳给你看', mood='playful', semantic_scene='play_scene')
    assert outfit['outfit_id'] == 'moonfeather_robe'
    assert outfit['persist_result']['status'] == 'ok'


def test_prepare_generation_context_focus_before_dedupe():
    pred = _prediction()
    ctx = prepare_generation_context(pred, text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看尾巴尖')
    assert pred['focus_target'] == 'tail'
    assert pred['outfit_id'] == 'moonfeather_robe'
    assert ctx['stage_hints']


def test_bridge_plans_secondary_only_on_focus():
    pred = _prediction()
    res = generate_from_prediction(pred, text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看尾巴尖', dry_run=True)
    assert res['status'] == 'dry_run_ready'
    assert res['focus_target'] == 'tail'
    assert res['secondary_generation_planned'] is True
    assert res['max_images_this_turn'] == 2


def test_no_focus_only_one_image_planned():
    pred = _prediction()
    res = generate_from_prediction(pred, text='（躲在屏幕后面偷笑）', user_message='偷偷看看你', dry_run=True)
    assert res['status'] == 'dry_run_ready'
    assert res['secondary_generation_planned'] is False
    assert res['max_images_this_turn'] == 1


def test_dedupe_key_differs_by_focus():
    a = {'mood': 'shy', 'semantic_scene': 'bashful_scene', 'focus_target': 'tail', 'outfit_id': 'moonfeather_robe'}
    b = {'mood': 'shy', 'semantic_scene': 'bashful_scene', 'focus_target': 'ears', 'outfit_id': 'moonfeather_robe'}
    assert make_dedupe_key('给你看一下', a, 'one') != make_dedupe_key('给你看一下', b, 'two')
