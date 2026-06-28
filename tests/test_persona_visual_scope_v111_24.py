from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
from memory_context.persona_runtime.visual_persona_renderer import render_plan


def test_lobster_output_drives_sneaky_scene():
    obs = observe_turn(user_message="我问天气", lobster_message="大龙虾躲在屏幕后面偷笑了一下", context={}, persona_state={})
    assert obs["trigger_source"] == "lobster_message"
    assert obs["mood"] == "sneaky"
    assert obs["auto_generation_candidate"] is True


def test_fallback_presence_record_only_not_auto():
    pred = predict_visual_intent(user_message="普通问一句没有场景", context={}, persona_state={})
    assert pred["confidence_level"] in {"ignore", "record_only"}
    assert pred["auto_generation_candidate"] is False


def test_persona_render_plan_is_not_generic_image_generation():
    plan = render_plan(prediction={"mood":"sneaky","semantic_scene":"peek_scene","trigger_signals":["偷笑"]}, message="大龙虾偷笑")
    assert plan["purpose"] == "persona_visualization"
    assert plan["visual_scope"] == "persona_scene_auto_only"
    assert plan["generic_image_generation"] is False
    assert plan["seed_avatar_path"].endswith("seed_avatar.jpg")
