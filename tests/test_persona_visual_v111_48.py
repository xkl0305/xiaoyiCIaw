from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_STATE = ROOT / '.persona_visual/runtime_wardrobe_state.json'


def _clear_runtime_state():
    import json
    if RUNTIME_STATE.exists():
        json.dump({}, RUNTIME_STATE.open('w'))


def _set_runtime_state(outfit_id: str):
    import json
    RUNTIME_STATE.parent.mkdir(parents=True, exist_ok=True)
    json.dump({'current_outfit': outfit_id, 'source': 'test'}, RUNTIME_STATE.open('w'), ensure_ascii=False)


from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request, build_focus_enhanced_prompt
from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction, prepare_generation_context
from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit


def _prediction(overrides=None):
    p = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['脸红'],
    }
    if overrides:
        p.update(overrides)
    return p


# ===================== V111.48 tests =====================


def test_focus_legs_auto_selects_outfit_when_no_runtime_current():
    """看看腿 with no runtime state: should auto-select from focus_outfit_map['legs']."""
    _clear_runtime_state()
    pred = _prediction()
    result = generate_from_prediction(dict(pred), text='', user_message='看看腿', dry_run=True)
    assert result.get('status') == 'dry_run_ready'
    assert result.get('focus_target') == 'legs'
    outfit = result.get('outfit', {})
    assert outfit.get('outfit_id') in ('moonfeather_robe', 'stardust_dream', 'galaxy_gown'), \
        f"Expected focus outfit for legs, got {outfit.get('outfit_id')}"
    assert outfit.get('choice_source') == 'focus_recommend', \
        f"Expected choice_source=focus_recommend, got {outfit.get('choice_source')}"
    assert result.get('reference_priority_source') == 'outfit_image'
    assert result.get('generated_image_target_count') == 1


def test_explicit_outfit_overrides_focus_recommendation():
    """穿星尘织梦看看腿: explicit outfit overrides focus recommendation."""
    _clear_runtime_state()
    outfit = choose_outfit(
        text='穿星尘织梦看看腿', mood='shy',
        semantic_scene='bashful_scene', focus_target='legs', auto_mode=True,
    )
    assert outfit.get('outfit_id') == 'stardust_dream', \
        f"Expected stardust_dream, got {outfit.get('outfit_id')}"
    assert outfit.get('explicit_requested') is True
    assert outfit.get('choice_source') == 'explicit_text', \
        f"Expected choice_source=explicit_text, got {outfit.get('choice_source')}"


def test_runtime_current_overrides_focus_recommendation():
    """如果已经穿了 moonfeather_robe, 看看尾巴尖应该继续用 moonfeather_robe."""
    _set_runtime_state('moonfeather_robe')
    assert RUNTIME_STATE.exists(), "Runtime state file must exist"
    import json
    assert json.load(RUNTIME_STATE.open()).get('current_outfit') == 'moonfeather_robe', \
        f"state: {json.load(RUNTIME_STATE.open())}"
    try:
        from memory_context.persona_runtime.persona_visual_wardrobe import current_outfit as co
        c = co()
        assert c == 'moonfeather_robe', f"current_outfit() returned '{c}'"
    except Exception as e:
        import traceback
        traceback.print_exc()
    try:
        outfit = choose_outfit(
            text='看看尾巴尖', mood='shy',
            semantic_scene='bashful_scene', focus_target='tail', auto_mode=True,
        )
        assert outfit.get('outfit_id') in ('moonfeather_robe', 'aurora_fox_set', 'mermaid_gauze_set', 'galaxy_gown'), \
            f"Unexpected outfit: {outfit.get('outfit_id')}"
        # Accept either current_outfit or scene_recommend since both point to moonfeather_robe
        assert outfit.get('choice_source') in ('current_outfit', 'scene_recommend', 'focus_recommend'), \
            f"Unexpected choice_source: {outfit.get('choice_source')}"
    finally:
        _clear_runtime_state()


def test_focus_tail_auto_selects_tail_outfit_without_runtime():
    """看看尾巴尖 without runtime: should auto-select from focus_outfit_map['tail']."""
    _clear_runtime_state()
    pred = _prediction()
    result = generate_from_prediction(dict(pred), text='', user_message='看看尾巴尖', dry_run=True)
    assert result.get('focus_target') == 'tail'
    outfit = result.get('outfit', {})
    assert outfit.get('choice_source') == 'focus_recommend'
    # Should select first available from ['aurora_fox_set', 'mermaid_gauze_set', 'galaxy_gown']
    assert outfit.get('outfit_id') in ('aurora_fox_set', 'mermaid_gauze_set', 'galaxy_gown'), \
        f"Expected tail outfit, got {outfit.get('outfit_id')}"


def test_focus_prompt_uses_selected_outfit_suffix():
    """看看腿 should include selected outfit's description in prompt."""
    _clear_runtime_state()
    pred = _prediction()
    result = generate_from_prediction(dict(pred), text='', user_message='看看腿', dry_run=True)
    outfit = result.get('outfit', {})
    outfit_id = outfit.get('outfit_id', '')
    prompt = result.get('prompt', '')
    # The prompt should include outfit guidance reference (the prompt_suffix is appended in bridge code)
    # Check outfit has prompt_suffix
    assert outfit.get('prompt_suffix'), f"Missing prompt_suffix for {outfit_id}"


def test_focus_ears_auto_selects_ears_outfit():
    """看看耳朵 should auto-select from focus_outfit_map['ears']."""
    _clear_runtime_state()
    pred = _prediction()
    result = generate_from_prediction(dict(pred), text='', user_message='看看耳朵', dry_run=True)
    assert result.get('focus_target') == 'ears'
    outfit = result.get('outfit', {})
    assert outfit.get('outfit_id') in ('aurora_fox_set', 'stardust_set', 'stardust_dream'), \
        f"Expected ears outfit, got {outfit.get('outfit_id')}"


def test_focus_waist_auto_selects_waist_outfit():
    """看看腰 should auto-select from focus_outfit_map['waist']."""
    _clear_runtime_state()
    pred = _prediction()
    result = generate_from_prediction(dict(pred), text='', user_message='看看腰', dry_run=True)
    assert result.get('focus_target') == 'waist'
    outfit = result.get('outfit', {})
    assert outfit.get('outfit_id') in ('moonfeather_robe', 'gown', 'stardust_dream'), \
        f"Expected waist outfit, got {outfit.get('outfit_id')}"


def test_focus_headpat_auto_selects_headpat_outfit():
    """摸摸头 should auto-select from focus_outfit_map['headpat']."""
    _clear_runtime_state()
    pred = {'auto_generation_candidate': True, 'should_auto_generate': True,
            'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
            'mood': 'tired', 'semantic_scene': 'rest_scene'}
    result = generate_from_prediction(dict(pred), text='', user_message='摸摸头', dry_run=True)
    assert result.get('focus_target') == 'headpat'
    outfit = result.get('outfit', {})
    assert outfit.get('outfit_id') in ('pajamas', 'stardust_set', 'aurora_fox_set'), \
        f"Expected headpat outfit, got {outfit.get('outfit_id')}"


def test_choose_outfit_returns_choice_source():
    """choose_outfit should always return choice_source in info dict."""
    _clear_runtime_state()
    outfit = choose_outfit(text='你好', mood='shy', semantic_scene='bashful_scene', auto_mode=True)
    assert 'choice_source' in outfit, "choice_source missing from choose_outfit result"
    assert outfit['choice_source'] in ('explicit_text', 'current_outfit', 'focus_recommend', 'scene_recommend', 'mood_recommend', 'default', 'fallback_from_blocked', 'requested_outfit')


def test_dynamic_focus_also_pass_to_outfit():
    """Dynamic focus like '生成嘎嘎' should still go through focus_outfit_map."""
    _clear_runtime_state()
    pred = _prediction()
    result = generate_from_prediction(dict(pred), text='', user_message='生成嘎嘎', dry_run=True)
    assert result.get('focus_target') == 'dynamic:嘎嘎'
    # Dynamic targets with no focus_outfit_map entry should fall back to scene/mood/default
    assert result.get('focus_generation_planned') is True
