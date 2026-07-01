#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    import sys as _sys
    _sys.path.insert(0, str(ROOT))

    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request, build_focus_enhanced_prompt
    from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction, prepare_generation_context
    from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit
    from memory_context.persona_runtime.persona_visual_scene_defaults import get_scene_default_image

    # =====================
    # 1. Clear runtime state & test 看看腿
    # =====================
    runtime_state = ROOT / '.persona_visual/runtime_wardrobe_state.json'
    if runtime_state.exists():
        json.dump({}, runtime_state.open('w'))

    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['脸红'],
    }
    result = generate_from_prediction(dict(pred), text='', user_message='看看腿', dry_run=True)
    outfit = result.get('outfit', {})

    report = {
        'status': 'ok' if result.get('status') == 'dry_run_ready' else 'fail',
        'version': 'V111_48_FOCUS_DRIVEN_WARDROBE',
        'focus_target': result.get('focus_target'),
        'outfit_id': outfit.get('outfit_id'),
        'outfit_choice_source': outfit.get('choice_source'),
        'reference_priority_source': result.get('reference_priority_source'),
        'reference_image': result.get('reference_image'),
        'generated_image_target_count': result.get('generated_image_target_count'),
        'focus_generation_model': result.get('focus_generation_model'),
        'focus_prompt_enhanced': result.get('focus_prompt_enhanced'),
        'focus_prompt_style': result.get('focus_prompt_style'),
        'focus_generation_planned': result.get('focus_generation_planned'),
    }

    out = ROOT / 'reports/V111_48_FOCUS_DRIVEN_WARDROBE_AUDIT.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Assertions
    assert report['status'] == 'ok', f"Expected ok, got {report['status']}"
    assert report['focus_target'] == 'legs', f"Expected legs, got {report['focus_target']}"
    assert outfit.get('outfit_id') in ('moonfeather_robe', 'stardust_dream', 'galaxy_gown'), \
        f"Expected focus outfit, got {outfit.get('outfit_id')}"
    assert outfit.get('choice_source') == 'focus_recommend', \
        f"Expected focus_recommend, got {outfit.get('choice_source')}"
    assert report['reference_priority_source'] == 'outfit_image', \
        f"Expected outfit_image, got {report['reference_priority_source']}"
    assert report['generated_image_target_count'] == 1, \
        f"Expected 1, got {report['generated_image_target_count']}"
    assert report['focus_generation_model'] == 'seedream5.0_image_to_image', \
        f"Got {report['focus_generation_model']}"
    assert report['focus_prompt_enhanced'] is True, "Expected prompt enhanced"
    assert report['focus_prompt_style'] == 'scene_enhanced', \
        f"Got {report['focus_prompt_style']}"

    print("\n✅ V111.48 Audit all assertions passed!")
    print(f"   Focus target: {report['focus_target']}")
    print(f"   Outfit ID: {report['outfit_id']}")
    print(f"   Outfit choice source: {report['outfit_choice_source']}")
    print(f"   Reference priority source: {report['reference_priority_source']}")
    print(f"   Generated image target count: {report['generated_image_target_count']}")
    print(f"   Focus generation model: {report['focus_generation_model']}")


if __name__ == '__main__':
    main()
