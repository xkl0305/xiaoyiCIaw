from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn


def test_sneaky_peek_assistant_output_hits_mid_low():
    obs = observe_turn(user_message='随便聊聊', assistant_message='我正躲在屏幕后面偷笑，偷偷看看你。', context={}, persona_state={})
    pred = obs['prediction']
    assert pred['mood'] == 'sneaky'
    assert pred['semantic_scene'] == 'peek_scene'
    assert pred['auto_generation_candidate'] is True
    assert pred['confidence'] >= 0.5


def test_record_only_vs_auto_threshold_aligned():
    pred = predict_visual_intent('我在，日常在线待命。', context={}, persona_state={})
    assert pred['should_suggest_visual'] is True
    assert pred['auto_generation_candidate'] in {True, False}
    if pred['confidence'] < 0.5:
        assert pred['auto_generation_candidate'] is False


def test_release_plus_pass_promotes_success_or_victory():
    pred = predict_visual_intent('搞定了，全部通过验收，全绿，发布成功。', context={}, persona_state={})
    assert pred['mood'] in {'victorious', 'success_moment'}
    assert pred['auto_generation_candidate'] is True
