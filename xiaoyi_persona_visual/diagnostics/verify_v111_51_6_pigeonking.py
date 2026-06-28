from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import (
        build_persona_prompt_safe,
        FIXED_IDENTITY_BLOCK,
        DEFAULT_APPEARANCE_BLOCK,
        OLD_IDENTITY_PHRASE,
    )
    from memory_context.persona_runtime.providers.seedream_provider import generate_image

    failures = []
    samples = {}

    for name, kwargs in {
        'appearance_dynamic': dict(base_prompt='看看你的样子', scene_type='display_appearance_scene', outfit_id='moonfeather_robe', outfit_suffix='月羽云裳'),
        'legs_dynamic': dict(base_prompt='看看腿', scene_type='', focus_target='legs', outfit_id='moonfeather_robe', outfit_suffix='月羽云裳'),
        'head_touch_dynamic': dict(base_prompt='摸摸头', scene_type='head_touch_scene', focus_target='head', outfit_id='stardust_dream', outfit_suffix='星尘织梦'),
        'default_appearance': dict(base_prompt='默认展示', scene_type='display_appearance_scene', outfit_id='', outfit_suffix=''),
    }.items():
        prompt, neg, meta = build_persona_prompt_safe(**kwargs)
        samples[name] = {
            'prompt_preview': prompt[:320],
            'fixed_identity_block_present': FIXED_IDENTITY_BLOCK in prompt,
            'bikini_in_fixed_identity_block': DEFAULT_APPEARANCE_BLOCK in FIXED_IDENTITY_BLOCK,
            'default_appearance_block_used': meta.get('default_appearance_block_used'),
            'dynamic_outfit_used': meta.get('dynamic_outfit_used'),
            'dynamic_block_effective_chinese_length': meta.get('dynamic_block_effective_chinese_length'),
            'old_identity_phrase_present': OLD_IDENTITY_PHRASE in prompt,
            'persona_subject': meta.get('persona_subject'),
        }
        if not prompt.startswith(FIXED_IDENTITY_BLOCK):
            failures.append(f'{name}:fixed_identity_not_at_front')
        if DEFAULT_APPEARANCE_BLOCK in FIXED_IDENTITY_BLOCK:
            failures.append('bikini_still_in_fixed_identity')
        if OLD_IDENTITY_PHRASE in prompt:
            failures.append(f'{name}:old_identity_phrase_present')
        if int(meta.get('dynamic_block_effective_chinese_length') or 0) < 100:
            failures.append(f'{name}:dynamic_block_too_short')
    if samples['appearance_dynamic']['default_appearance_block_used']:
        failures.append('dynamic_outfit_wrongly_uses_default_appearance')
    if not samples['default_appearance']['default_appearance_block_used']:
        failures.append('default_appearance_not_used_when_no_outfit')

    manual = generate_image(prompt='摸摸头，鸽子王', input_image='assets/persona/seed_avatar.jpg')
    manual_ok = manual.get('status') == 'blocked' and manual.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline'
    if not manual_ok:
        failures.append('manual_provider_persona_request_not_blocked')

    normal = generate_image(prompt='生成一张山水图')
    normal_ok = normal.get('status') != 'blocked'
    if not normal_ok:
        failures.append('ordinary_provider_request_blocked')

    result = {
        'status': 'passed' if not failures else 'failed',
        'failures': failures,
        'samples': samples,
        'manual_provider_persona_block': {
            'ok': manual_ok,
            'status': manual.get('status'),
            'blocked_reason': manual.get('blocked_reason'),
        },
        'ordinary_provider_direct': {
            'ok': normal_ok,
            'status': normal.get('status'),
            'reason': normal.get('reason'),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
