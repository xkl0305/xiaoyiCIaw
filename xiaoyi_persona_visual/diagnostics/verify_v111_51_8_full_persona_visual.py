from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import (
    build_persona_prompt_safe,
    FIXED_IDENTITY_BLOCK,
    DEFAULT_APPEARANCE_BLOCK,
    OLD_IDENTITY_PHRASE,
)


def _ok(name: str, value: bool, results: dict) -> None:
    results[name] = bool(value)
    print(f'{name}={str(bool(value)).lower()}')


def _load_post_reply():
    path = ROOT / '.openclaw' / 'hooks' / 'post_reply.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('post_reply_runtime_verify', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _find(obj, key):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                out.append(v)
            out.extend(_find(v, key))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_find(item, key))
    return out


def main() -> int:
    results = {}

    back_prompt, back_neg, back_meta = build_persona_prompt_safe(
        base_prompt='看看屁股',
        focus_target='back_outfit_tail_detail',
        outfit_id='moonfeather_robe',
        outfit_suffix='月羽云裳',
    )
    display_prompt, display_neg, display_meta = build_persona_prompt_safe(
        base_prompt='看看你的样子',
        scene_type='display_appearance_scene',
        focus_target='',
        outfit_id='moonfeather_robe',
        outfit_suffix='月羽云裳',
    )
    default_prompt, default_neg, default_meta = build_persona_prompt_safe(
        base_prompt='默认展示',
        scene_type='display_appearance_scene',
        focus_target='',
        outfit_id='',
        outfit_suffix='',
    )

    _ok('subject_is_pigeonking', back_meta.get('persona_subject') == '鸽子王', results)
    _ok('fixed_identity_has_no_fox_ears', '不要狐狸耳朵' in FIXED_IDENTITY_BLOCK, results)
    _ok('fixed_identity_no_bikini', DEFAULT_APPEARANCE_BLOCK not in FIXED_IDENTITY_BLOCK, results)
    _ok('old_identity_phrase_removed', OLD_IDENTITY_PHRASE not in back_prompt + display_prompt + default_prompt, results)
    _ok('back_focus_has_back_view', '采用背面或侧背面构图' in back_prompt, results)
    _ok('back_focus_no_face_clear', '面部清晰' not in back_prompt, results)
    _ok('back_focus_no_front_expression_template', '表情保持自然和轻微配合感' not in back_prompt, results)
    _ok('back_focus_prompt_len_ge_100', int(back_meta.get('prompt_effective_chinese_length', 0)) >= 100, results)
    _ok('dynamic_outfit_blocks_default_bikini', '默认外观块启用：身着银亮色比基尼' not in display_prompt, results)
    _ok('default_appearance_uses_bikini_without_dynamic_outfit', '默认外观块启用：身着银亮色比基尼' in default_prompt, results)
    _ok('display_scene_prompt_len_ge_100', int(display_meta.get('prompt_effective_chinese_length', 0)) >= 100, results)
    _ok('negative_guard_has_fox_ears', 'fox ears' in (back_neg or ''), results)
    _ok('negative_guard_no_bikini_conflict', 'bikini' not in (back_neg or '').lower(), results)

    # Provider-level bypass guard: persona visual naked provider call must block.
    try:
        from memory_context.persona_runtime.providers.seedream_provider import generate_image
        blocked = generate_image(prompt='摸摸头，鸽子王', input_image='assets/persona/seed_avatar.jpg', max_images=1)
        _ok('manual_provider_persona_visual_blocked', blocked.get('status') == 'blocked' and blocked.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline', results)
    except Exception as exc:
        print(f'manual_provider_persona_visual_blocked=error:{type(exc).__name__}:{exc}')
        results['manual_provider_persona_visual_blocked'] = False

    # Normal post_reply dry run should expose main-pipeline signals when available.
    try:
        mod = _load_post_reply()
        if mod and hasattr(mod, 'run'):
            res = mod.run(user_message='看看腿', assistant_message='看看腿', reply_text='看看腿', dry_run=True, request_id='verify_v111_51_8_legs')
            txt = json.dumps(res, ensure_ascii=False)
            _ok('post_reply_uses_prompt_builder', 'persona_image_prompt_builder' in txt, results)
            _ok('post_reply_has_persona_controller_signal', ('PersonaVisualController' in txt) or ('persona_visual_controller_used' in txt), results)
            _ok('post_reply_legs_focus_present', 'legs' in txt, results)
        else:
            print('post_reply_uses_prompt_builder=skipped_no_post_reply')
            print('post_reply_has_persona_controller_signal=skipped_no_post_reply')
            print('post_reply_legs_focus_present=skipped_no_post_reply')
    except Exception as exc:
        print(f'post_reply_checks=error:{type(exc).__name__}:{exc}')
        results['post_reply_uses_prompt_builder'] = False
        results['post_reply_has_persona_controller_signal'] = False
        results['post_reply_legs_focus_present'] = False

    ok = all(results.values())
    print(f'overall={"passed" if ok else "failed"}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
