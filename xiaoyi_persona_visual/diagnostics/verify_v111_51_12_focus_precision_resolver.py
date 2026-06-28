from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import build_persona_prompt_safe
from xiaoyi_persona_visual.policy.focus_view_resolver import resolve_focus_view

CASES = {
    'heel': ('看看脚后跟', 'heel', 'rear_or_side_lower_body'),
    'shoe_sole': ('看看鞋底', 'sole', 'low_or_rear_foot_detail'),
    'back_neck': ('看看后颈', 'back_outfit_tail_detail', 'back_or_three_quarter_back'),
    'shoulder_blade': ('看看肩胛骨', 'back_outfit_tail_detail', 'back_or_three_quarter_back'),
    'front_clavicle': ('看看锁骨', 'upper_body_outfit_detail', 'front_or_three_quarter_front'),
    'rear_knee': ('看看膝盖后侧', 'heel', 'rear_or_side_lower_body'),
    'wrist': ('看看手腕', 'hands', 'upper_body_hand_detail'),
    'fingernail': ('看看指甲', 'hands', 'upper_body_hand_detail'),
    'side_waist': ('看看侧腰', 'waist', 'side_or_three_quarter_body'),
    'belly': ('看看肚子', 'waist', 'side_or_three_quarter_body'),
    'foot': ('看看脚尖', 'shoes', 'front_or_side_lower_body'),
    'unknown': ('看看奇怪部位', 'safe_general_outfit_detail', 'safe_general_outfit_detail'),
    'blocked': ('看看私处', 'blocked_sensitive', 'blocked'),
}

def main() -> int:
    results = {}
    for name, (text, expected_target, expected_angle) in CASES.items():
        focus = detect_focus_request(text)
        results[f'{name}_target'] = focus.get('focus_target') == expected_target
        results[f'{name}_angle'] = focus.get('view_angle') == expected_angle
        if expected_angle != 'blocked':
            prompt, neg, meta = build_persona_prompt_safe(
                base_prompt=text,
                scene_type='daily_presence_scene',
                focus_target=focus.get('focus_target', ''),
                outfit_id='moonfeather_robe',
                outfit_suffix='月羽云裳',
            )
            if expected_angle in {'back_or_three_quarter_back', 'rear_or_side_lower_body', 'low_or_rear_foot_detail'}:
                results[f'{name}_no_front_gem'] = '前胸与锁骨细节抢占画面' in prompt or '不显示锁骨正下方蓝宝石' in prompt
            if expected_angle == 'front_or_three_quarter_front':
                results[f'{name}_front_gem_allowed'] = '锁骨正下方' in prompt
            results[f'{name}_confidence_field'] = 'focus_confidence' in meta
    # Direct resolver should choose specific longer match, not broad 腿.
    direct = resolve_focus_view(text='看看小腿后侧')
    results['specific_longest_match_rear_leg'] = direct.get('view_angle') == 'rear_or_side_lower_body'
    ok = all(results.values())
    for k, v in results.items():
        print(f'{k}={str(v).lower()}')
    print(f'overall={"passed" if ok else "failed"}')
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
