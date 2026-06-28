from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import (
    FIXED_IDENTITY_BLOCK,
    build_persona_prompt_safe,
)


def main() -> int:
    checks = {}

    back_prompt, back_neg, back_meta = build_persona_prompt_safe(
        base_prompt='看看屁股',
        focus_target='back_outfit_tail_detail',
        outfit_id='moonfeather_robe',
        outfit_suffix='月羽云裳',
    )
    front_prompt, front_neg, front_meta = build_persona_prompt_safe(
        base_prompt='看看你的样子',
        scene_type='display_appearance_scene',
        focus_target='',
        outfit_id='moonfeather_robe',
        outfit_suffix='月羽云裳',
    )
    default_prompt, default_neg, default_meta = build_persona_prompt_safe(
        base_prompt='展示一下',
        scene_type='display_appearance_scene',
        focus_target='',
        outfit_id='',
        outfit_suffix='',
    )

    checks['fixed_identity_has_no_fox_girl_phrase'] = '九尾狐少女' not in FIXED_IDENTITY_BLOCK
    checks['fixed_identity_has_no_clavicle_gem'] = '锁骨下嵌蓝宝石' not in FIXED_IDENTITY_BLOCK
    checks['fixed_identity_has_human_head_no_animal_ears'] = '正常人类头型' in FIXED_IDENTITY_BLOCK and '不出现狐狸耳朵' in FIXED_IDENTITY_BLOCK

    checks['back_uses_back_view_exclusion_block'] = '当前为背面或侧背面视角' in back_prompt and '不添加任何背部宝石' in back_prompt
    checks['back_does_not_inject_front_detail_block'] = '前视角可见细节' not in back_prompt
    checks['back_has_no_clavicle_gem_phrase'] = '锁骨下嵌蓝宝石' not in back_prompt
    checks['back_has_no_face_clear_phrase'] = '面部清晰' not in back_prompt
    checks['back_has_no_duplicate_phrase'] = back_meta.get('prompt_has_duplicate_phrase') is False
    checks['back_blocks_back_gem_in_negative'] = any(x in back_neg for x in ['gem on back', 'back jewel', 'back gemstone', 'misplaced clavicle gem'])
    checks['back_blocks_fox_ears_in_negative'] = all(x in back_neg for x in ['fox ears', 'animal ears', 'kemonomimi'])
    checks['back_effective_chinese_len_ge_100'] = int(back_meta.get('prompt_effective_chinese_length') or 0) >= 100

    checks['front_uses_front_view_detail_block'] = '前视角可见细节' in front_prompt
    checks['front_clavicle_gem_allowed'] = '锁骨下嵌蓝宝石' in front_prompt
    checks['front_no_fox_girl_in_fixed_block'] = '九尾狐少女' not in front_prompt
    checks['front_blocks_fox_ears_in_negative'] = all(x in front_neg for x in ['fox ears', 'animal ears', 'kemonomimi'])
    checks['front_effective_chinese_len_ge_100'] = int(front_meta.get('prompt_effective_chinese_length') or 0) >= 100

    checks['default_appearance_still_uses_bikini_only_without_dynamic_outfit'] = '默认外观块启用：身着银亮色比基尼' in default_prompt
    checks['dynamic_outfit_suppresses_default_bikini'] = '默认外观块启用：身着银亮色比基尼' not in front_prompt
    checks['old_identity_phrase_absent'] = '参考图角色身份锁定，保持同一张脸和同一人物气质' not in back_prompt and '参考图角色身份锁定，保持同一张脸和同一人物气质' not in front_prompt

    ok = all(checks.values())
    print(json.dumps({
        'version': 'V111.51.9',
        'overall': 'passed' if ok else 'failed',
        'all_checks_passed': ok,
        'checks': checks,
        'back_meta': back_meta,
        'front_meta': front_meta,
        'back_prompt_preview': back_prompt[:420],
        'front_prompt_preview': front_prompt[:420],
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
