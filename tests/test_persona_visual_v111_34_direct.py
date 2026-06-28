from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
def test_direct_mood_triggers():
    for text in ["开心", "生气", "委屈难过", "紧张", "惊讶", "尴尬"]:
        assert predict_visual_intent(text)["auto_generation_candidate"] is True
def test_assistant_output_priority():
    r = observe_turn(user_message="普通输入", reply_text="我正躲在屏幕后面偷笑，偷偷看看你。")
    assert r["trigger_source"] == "reply_text"
    assert r["prediction"]["mood"] == "sneaky"
def test_wardrobe_trigger():
    r = predict_visual_intent("打开衣柜换睡衣")
    assert r["auto_generation_candidate"] is True
