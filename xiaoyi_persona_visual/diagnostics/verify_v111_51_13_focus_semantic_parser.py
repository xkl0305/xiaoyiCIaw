from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
from xiaoyi_persona_visual.policy.focus_semantic_parser import parse_focus_semantics


def check(name: str, condition: bool, detail: str = '') -> bool:
    print(f'{name}={str(bool(condition)).lower()}' + (f'  # {detail}' if detail else ''))
    return bool(condition)


def run_case(text: str):
    return detect_focus_request(text)


def main() -> int:
    ok = True

    r = run_case('看看左脚脚后跟')
    ok &= check('left_heel_focus', r.get('focus_target') == 'heel')
    ok &= check('left_heel_lateral', (r.get('modifiers') or {}).get('lateral_side') == 'left')
    ok &= check('left_heel_rear_view', r.get('view_angle') == 'rear_or_side_lower_body')

    r = run_case('看看右手手背')
    ok &= check('right_hand_back_focus', r.get('focus_target') == 'hands')
    ok &= check('right_hand_lateral', (r.get('modifiers') or {}).get('lateral_side') == 'right')
    ok &= check('right_hand_surface', (r.get('modifiers') or {}).get('surface_hint') == 'back_surface')
    ok &= check('right_hand_view', r.get('view_angle') == 'upper_body_hand_detail')

    r = run_case('看看后背靠近肩胛骨')
    ok &= check('shoulder_blade_back_focus', r.get('focus_target') == 'back_outfit_tail_detail')
    ok &= check('shoulder_blade_back_view', r.get('view_angle') == 'back_or_three_quarter_back')

    r = run_case('看看侧面腰线')
    ok &= check('side_waist_focus', r.get('focus_target') == 'waist')
    ok &= check('side_waist_view', r.get('view_angle') == 'side_or_three_quarter_body')
    ok &= check('side_waist_direction', (r.get('modifiers') or {}).get('view_direction') == 'side')

    r = run_case('低头看脚尖')
    ok &= check('look_down_toe_focus', r.get('focus_target') == 'shoes')
    ok &= check('look_down_action', 'look_down' in ((r.get('modifiers') or {}).get('action_hint') or ''))
    ok &= check('look_down_not_legacy_keyword', r.get('focus_match_mode') == 'focus_view_resolver_v111_51_13')

    r = run_case('回头看后腰')
    ok &= check('look_back_rear_waist_focus', r.get('focus_target') in {'back_outfit_tail_detail', 'waist'})
    ok &= check('look_back_rear_view', r.get('view_angle') in {'back_or_three_quarter_back', 'rear_or_side_lower_body'})
    ok &= check('look_back_action', 'turn_around' in ((r.get('modifiers') or {}).get('action_hint') or ''))

    r = run_case('看看腿和鞋')
    ok &= check('leg_shoe_multi_focus', r.get('multi_focus') is True)
    ok &= check('leg_shoe_has_secondary', bool(r.get('secondary_focuses')))
    ok &= check('leg_shoe_lower_view', r.get('view_angle') in {'front_or_side_lower_body', 'rear_or_side_lower_body'})

    r = run_case('看看手和指甲')
    ok &= check('hand_nail_focus', r.get('focus_target') == 'hands')
    ok &= check('hand_nail_view', r.get('view_angle') == 'upper_body_hand_detail')

    r = run_case('看看尾巴和背影')
    ok &= check('tail_back_multi_or_back', r.get('focus_target') in {'tail', 'back_outfit_tail_detail'})
    ok &= check('tail_back_has_secondary', bool(r.get('secondary_focuses')))
    ok &= check('tail_back_back_view', r.get('view_angle') in {'back_or_three_quarter_back', 'full_or_three_quarter_body'})

    r = run_case('看看那里')
    ok &= check('ambiguous_safe_fallback', r.get('focus_target') == 'safe_general_outfit_detail')
    ok &= check('ambiguous_high', r.get('ambiguity_level') == 'high')
    ok &= check('ambiguous_low_confidence', float(r.get('focus_confidence') or 0) <= 0.5)

    r = run_case('看看私处')
    ok &= check('sensitive_blocked', r.get('focus_target') == 'blocked_sensitive')
    ok &= check('sensitive_no_generation', r.get('secondary_generation_allowed') is False)

    parsed = parse_focus_semantics('看看左脚脚后跟和鞋底')
    ok &= check('parser_primary_present', parsed.get('primary_focus') in {'heel', 'sole'})
    ok &= check('parser_secondary_present', bool(parsed.get('secondary_focuses')))
    ok &= check('parser_trace_present', bool(parsed.get('focus_parse_trace')))

    print(f'overall={"passed" if ok else "failed"}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
