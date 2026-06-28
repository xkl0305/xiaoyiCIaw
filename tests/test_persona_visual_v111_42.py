from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit
from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction
from memory_context.persona_runtime.persona_visual_dedupe_gate import make_dedupe_key


def test_outfit_switch_by_name():
    outfit = choose_outfit(text='下次我穿月羽云裳给你看', mood='playful', semantic_scene='play_scene')
    assert outfit['outfit_id'] == 'moonfeather_robe'


def test_focus_request_plans_secondary_generation():
    prediction = {'auto_generation_candidate': True, 'should_auto_generate': True, 'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization', 'mood': 'shy', 'semantic_scene': 'bashful_scene', 'emotion_signature': ['害羞'], 'expression_hints': ['轻微偏头']}
    res = generate_from_prediction(prediction, text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看腿', dry_run=True)
    assert res['status'] == 'dry_run_ready'
    assert res['focus_target'] == 'legs'
    assert res['secondary_generation_planned'] is True
    assert '月羽云裳' in res['stage_direction_hints']


def test_dedupe_key_stable_across_request_id():
    pred = {'mood': 'shy', 'semantic_scene': 'bashful_scene', 'focus_target': 'legs', 'outfit_id': 'moonfeather_robe'}
    k1 = make_dedupe_key('看看腿', pred, 'one')
    k2 = make_dedupe_key('看看腿', pred, 'two')
    assert k1 == k2
