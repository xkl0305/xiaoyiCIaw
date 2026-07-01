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
    # 1. Focus request: 看看腿 with 月羽云裳
    # =====================
    focus = detect_focus_request('看看腿')
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞', '配合'], 'expression_hints': ['轻微偏头', '脸红'],
    }
    prepared = prepare_generation_context(pred, text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看腿')
    result = generate_from_prediction(dict(pred), text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看腿', dry_run=True)

    # =====================
    # 2. Verify scene default image exists
    # =====================
    scene_img = get_scene_default_image('bashful_scene', '看看腿')

    # =====================
    # 3. Build enhanced prompt
    # =====================
    outfit = choose_outfit(text='看看腿 月羽云裳', mood='shy', semantic_scene='bashful_scene', auto_mode=True)
    enhanced = build_focus_enhanced_prompt(
        focus_target='legs', focus_label='腿',
        mood='shy', semantic_scene='bashful_scene',
        outfit='moonfeather_robe',
        outfit_prompt_suffix=outfit.get('prompt_suffix', ''),
        stage_hints='月羽云裳的薄纱裙摆随风飘了一下',
        emotion_signature=['害羞', '配合'],
        expression_hints=['脸红', '偏头'],
    )

    focus_preview = enhanced.get('focus_prompt_preview', '')
    focus_enhanced = enhanced.get('enhanced_focus_prompt', '')

    report = {
        'status': 'ok',
        'version': 'V111_47_FOCUS_REFERENCE_PRIORITY_ENHANCED_PROMPT',
        'focus_target': result.get('focus_target'),
        'reference_priority_source': result.get('reference_priority_source'),
        'scene_direct_send_planned': result.get('scene_direct_send_planned'),
        'focus_generation_model': result.get('focus_generation_model'),
        'generated_image_target_count': result.get('generated_image_target_count'),
        'max_images_this_turn': result.get('max_images_this_turn'),
        'focus_prompt_enhanced': result.get('focus_prompt_enhanced'),
        'focus_prompt_style': result.get('focus_prompt_style'),
        'focus_prompt_preview': focus_preview[:300] if focus_preview else '',
        'scene_default_status': scene_img.get('status'),
        'scene_default_file': scene_img.get('file_path'),
        'reference_policy': result.get('reference_policy'),
        'reference_priority': result.get('reference_priority'),
    }

    out = ROOT / 'reports/V111_47_FOCUS_REFERENCE_PRIORITY_ENHANCED_PROMPT_AUDIT.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Assertions
    assert report['focus_target'] == 'legs', f"Expected legs, got {report['focus_target']}"
    assert report['reference_priority_source'] == 'outfit_image', f"Expected outfit_image, got {report['reference_priority_source']}"
    assert report['scene_direct_send_planned'] is True, "Expected scene_direct_send_planned=True"
    assert report['focus_generation_model'] == 'seedream5.0_image_to_image', f"Got {report['focus_generation_model']}"
    assert report['generated_image_target_count'] == 1, f"Expected 1, got {report['generated_image_target_count']}"
    assert report['max_images_this_turn'] == 2, f"Expected 2, got {report['max_images_this_turn']}"
    assert report['focus_prompt_enhanced'] is True, "Expected prompt enhanced"
    assert report['focus_prompt_style'] == 'scene_enhanced', f"Got {report['focus_prompt_style']}"
    assert report['scene_default_status'] == 'default_scene_available_manual_only', f"Got {report['scene_default_status']}"
    assert focus_preview, "Expected non-empty focus prompt preview"
    assert report['reference_policy'] == 'priority_context_reference', f"Got {report['reference_policy']}"

    print("\n✅ All audit assertions passed!")
    print(f"   Focus target: {report['focus_target']}")
    print(f"   Reference priority source: {report['reference_priority_source']}")
    print(f"   Scene direct send planned: {report['scene_direct_send_planned']}")
    print(f"   Focus generation model: {report['focus_generation_model']}")
    print(f"   Generated image target count: {report['generated_image_target_count']}")
    print(f"   Max images this turn: {report['max_images_this_turn']}")
    print(f"   Focus prompt enhanced: {report['focus_prompt_enhanced']}")
    print(f"   Focus prompt style: {report['focus_prompt_style']}")
    print(f"   Scene default status: {report['scene_default_status']}")


if __name__ == '__main__':
    main()
